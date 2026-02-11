// GET /api/topic/messages?path=<topic_path>&limit=50
// Returns historical messages for a topic from Neo4j for chat context

import { NextRequest, NextResponse } from 'next/server';
import neo4j from 'neo4j-driver';
import { getSession } from '@/lib/neo4j-client';

// Query for historical messages from a topic
const MESSAGES_QUERY = `
MATCH (t:Topic {path: $topicPath})-[:HAS_MESSAGE]->(m:Message)
WITH m
ORDER BY m.timestamp DESC
LIMIT $limit
RETURN m.rawPayload AS payload, m.numericValue AS numericValue, m.timestamp AS timestamp
`;

// Query for graph relationships (parent/child topics)
const RELATIONSHIPS_QUERY = `
MATCH (t:Topic {path: $topicPath})
OPTIONAL MATCH (t)-[:CHILD_OF]->(parent:Topic)
OPTIONAL MATCH (child:Topic)-[:CHILD_OF]->(t)
RETURN
  parent.path AS parent,
  collect(DISTINCT child.path) AS children
`;

interface MessageRecord {
  payload: string | null;
  numericValue: number | null;
  timestamp: string;
}

interface ParsedMessage {
  topic: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('path');
  const limit = parseInt(searchParams.get('limit') || '50', 10);

  console.log('[Topic Messages API] Request received for path:', topicPath);

  if (!topicPath) {
    console.log('[Topic Messages API] Missing path parameter');
    return NextResponse.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  const session = getSession();

  try {
    console.log('[Topic Messages API] Running Neo4j query for topic:', topicPath);

    // Run queries sequentially to avoid Neo4j session/transaction conflicts
    // (Promise.all on same session causes "open transaction" error)
    // Use neo4j.int() for limit - Neo4j requires actual integer types for LIMIT
    const messagesResult = await session.run(MESSAGES_QUERY, { topicPath, limit: neo4j.int(limit) });
    console.log('[Topic Messages API] Messages query returned', messagesResult.records.length, 'records');

    const relationshipsResult = await session.run(RELATIONSHIPS_QUERY, { topicPath });

    // Parse messages
    const messages: ParsedMessage[] = messagesResult.records.map(record => {
      const payloadStr = record.get('payload') as string | null;
      const numericValue = record.get('numericValue');
      const timestampRaw = record.get('timestamp');

      // Convert Neo4j DateTime object to ISO string
      // Neo4j returns DateTime as complex objects, not strings
      let timestamp: string;
      if (timestampRaw && typeof timestampRaw === 'object' && 'toStandardDate' in timestampRaw) {
        // Neo4j DateTime object - convert to JS Date then to ISO string
        timestamp = (timestampRaw as { toStandardDate: () => Date }).toStandardDate().toISOString();
      } else if (timestampRaw && typeof timestampRaw === 'object' && 'toString' in timestampRaw) {
        // Fallback for other Neo4j temporal types
        timestamp = timestampRaw.toString();
      } else {
        // Already a string or primitive
        timestamp = String(timestampRaw || new Date().toISOString());
      }

      // Parse payload - try JSON first, fall back to simple value
      let payload: Record<string, unknown> = {};
      if (payloadStr) {
        try {
          const parsed = JSON.parse(payloadStr);
          if (typeof parsed === 'object' && parsed !== null) {
            payload = parsed;
          } else {
            payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : parsed };
          }
        } catch {
          payload = { value: numericValue !== null && numericValue !== undefined ? numericValue : payloadStr };
        }
      }

      return {
        topic: topicPath,
        payload,
        timestamp,
      };
    });

    // Parse relationships
    const relRecord = relationshipsResult.records[0];
    const parent = relRecord?.get('parent') as string | null;
    const children = (relRecord?.get('children') as string[] | null) || [];

    return NextResponse.json({
      topicPath,
      messages,
      parent_topics: parent ? [parent] : [],
      child_topics: children.filter(Boolean),
      messageCount: messages.length,
    });
  } catch (error) {
    console.error('[Topic Messages API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch topic messages', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
