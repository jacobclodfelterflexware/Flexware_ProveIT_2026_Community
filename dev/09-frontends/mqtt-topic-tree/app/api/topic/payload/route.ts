// GET /api/topic/payload?path=<topic_path>&aggregate=true|false
// Returns the latest payload for a specific topic from Neo4j
// When aggregate=true, fetches data from all child topics and merges them

import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

// Query for single topic (Pattern A - leaf message) - includes message count
const PAYLOAD_QUERY = `
MATCH (t:Topic {path: $topicPath})-[:HAS_MESSAGE]->(m:Message)
WITH m
ORDER BY m.timestamp DESC
WITH collect(m) AS allMessages
WITH allMessages[0] AS latestMsg, size(allMessages) AS messageCount
RETURN latestMsg.rawPayload AS payload, latestMsg.numericValue AS numericValue, latestMsg.timestamp AS timestamp, messageCount
`;

// Query for aggregating child topics (Pattern B - parent with children) - includes message counts
const AGGREGATED_QUERY = `
MATCH (t:Topic)
WHERE t.path STARTS WITH $pathPrefix
WITH t
MATCH (t)-[:HAS_MESSAGE]->(m:Message)
WITH t.path AS childPath, m
ORDER BY m.timestamp DESC
WITH childPath, collect(m) AS allMessages
WITH childPath, allMessages[0] AS latestMsg, size(allMessages) AS messageCount
RETURN childPath, latestMsg.rawPayload AS payload, latestMsg.numericValue AS numericValue, latestMsg.timestamp AS timestamp, messageCount
ORDER BY childPath
`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('path');
  const aggregate = searchParams.get('aggregate') === 'true';

  if (!topicPath) {
    return NextResponse.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  const session = getSession();
  const excludedFields = ['timestamp', 'time', 'ts', 'created_at', 'updated_at'];

  try {
    if (aggregate) {
      // Aggregation mode: fetch latest message from each child topic
      const result = await session.run(AGGREGATED_QUERY, { pathPrefix: topicPath + '/' });

      if (result.records.length === 0) {
        return NextResponse.json(
          { error: 'No messages found in child topics' },
          { status: 404 }
        );
      }

      const mergedPayload: Record<string, unknown> = {};
      const numericFields: string[] = [];
      const childTopics: string[] = [];
      let latestTimestamp = '';
      let totalMessageCount = 0;

      for (const record of result.records) {
        const childPath = record.get('childPath') as string;
        const payloadStr = record.get('payload') as string;
        const numericValue = record.get('numericValue');
        const timestamp = record.get('timestamp') as string;
        const messageCount = (record.get('messageCount') as { toNumber?: () => number })?.toNumber?.() ||
                            Number(record.get('messageCount')) || 0;

        totalMessageCount += messageCount;

        // Track latest timestamp
        if (!latestTimestamp || timestamp > latestTimestamp) {
          latestTimestamp = timestamp;
        }

        // Extract child topic name (last segment of path)
        const childName = childPath.split('/').pop() || childPath;
        childTopics.push(childPath);

        // Parse payload - try JSON first, fall back to simple value
        let payload: Record<string, unknown> = {};
        if (payloadStr) {
          try {
            const parsed = JSON.parse(payloadStr);
            if (typeof parsed === 'object' && parsed !== null) {
              payload = parsed;
            } else {
              // Simple value - use numericValue if available, otherwise rawPayload
              payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : parsed };
            }
          } catch {
            // Not JSON - use numericValue if available, otherwise raw string
            payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : payloadStr };
          }
        }

        // Merge with prefixed keys
        for (const [key, value] of Object.entries(payload || {})) {
          const prefixedKey = `${childName}.${key}`;
          mergedPayload[prefixedKey] = value;

          if (typeof value === 'number' && !excludedFields.includes(key.toLowerCase())) {
            numericFields.push(prefixedKey);
          }
        }
      }

      return NextResponse.json({
        topicPath,
        payload: mergedPayload,
        timestamp: latestTimestamp,
        numericFields,
        isAggregated: true,
        childTopics,
        messageCount: totalMessageCount,
      });
    } else {
      // Single topic mode
      const result = await session.run(PAYLOAD_QUERY, { topicPath });

      if (result.records.length === 0) {
        return NextResponse.json(
          { error: 'No messages found for this topic' },
          { status: 404 }
        );
      }

      const record = result.records[0];
      const payloadStr = record.get('payload') as string;
      const numericValue = record.get('numericValue');
      const timestamp = record.get('timestamp') as string;
      const messageCount = (record.get('messageCount') as { toNumber?: () => number })?.toNumber?.() ||
                          Number(record.get('messageCount')) || 0;

      // Parse payload - try JSON first, fall back to simple value
      let payload: Record<string, unknown> = {};
      if (payloadStr) {
        try {
          const parsed = JSON.parse(payloadStr);
          if (typeof parsed === 'object' && parsed !== null) {
            payload = parsed;
          } else {
            // Simple value - use numericValue if available, otherwise rawPayload
            payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : parsed };
          }
        } catch {
          // Not JSON - use numericValue if available, otherwise raw string
          payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : payloadStr };
        }
      }

      // Detect numeric fields
      const numericFields: string[] = [];

      for (const [key, value] of Object.entries(payload || {})) {
        if (typeof value === 'number' && !excludedFields.includes(key.toLowerCase())) {
          numericFields.push(key);
        }
      }

      return NextResponse.json({
        topicPath,
        payload,
        timestamp,
        numericFields,
        isAggregated: false,
        messageCount,
      });
    }
  } catch (error) {
    console.error('[Topic Payload API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch topic payload', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
