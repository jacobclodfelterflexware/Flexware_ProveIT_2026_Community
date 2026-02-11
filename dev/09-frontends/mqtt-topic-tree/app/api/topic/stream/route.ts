// GET /api/topic/stream?topic=<topic_path>&aggregate=true|false
// SSE endpoint that streams payload updates for a specific topic from Neo4j
// When aggregate=true, streams merged data from all child topics

import { NextRequest } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

const POLL_INTERVAL_MS = 2000; // Poll every 2 seconds
const HEARTBEAT_INTERVAL_MS = 30000; // Send heartbeat every 30 seconds to prevent idle timeout

// Query for single topic (Pattern A)
const LATEST_MESSAGE_QUERY = `
MATCH (t:Topic {path: $topicPath})-[:HAS_MESSAGE]->(m:Message)
WITH m
ORDER BY m.timestamp DESC
LIMIT 1
RETURN m.rawPayload AS payload, m.numericValue AS numericValue, m.timestamp AS timestamp
`;

// Query for aggregating child topics (Pattern B)
const AGGREGATED_MESSAGE_QUERY = `
MATCH (t:Topic)
WHERE t.path STARTS WITH $pathPrefix
WITH t
MATCH (t)-[:HAS_MESSAGE]->(m:Message)
WITH t.path AS childPath, m
ORDER BY m.timestamp DESC
WITH childPath, collect(m)[0] AS latestMsg
RETURN childPath, latestMsg.rawPayload AS payload, latestMsg.numericValue AS numericValue, latestMsg.timestamp AS timestamp
ORDER BY childPath
`;

const excludedFields = ['timestamp', 'time', 'ts', 'created_at', 'updated_at'];

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('topic');
  const aggregate = searchParams.get('aggregate') === 'true';

  if (!topicPath) {
    return new Response(JSON.stringify({ error: 'Missing topic parameter' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const encoder = new TextEncoder();
  let isClosed = false;
  let lastTimestamp: string | null = null;
  // For aggregation, track timestamps per child topic
  const childTimestamps = new Map<string, string>();

  let heartbeatInterval: ReturnType<typeof setInterval> | null = null;

  const stream = new ReadableStream({
    async start(controller) {
      const sendEvent = (data: object) => {
        if (isClosed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch (err) {
          console.error('[Topic Stream] Failed to send event:', err);
        }
      };

      // Start heartbeat to keep connection alive and prevent infrastructure timeouts
      heartbeatInterval = setInterval(() => {
        if (!isClosed) {
          sendEvent({ type: 'heartbeat', timestamp: Date.now() });
        }
      }, HEARTBEAT_INTERVAL_MS);

      const pollForUpdates = async () => {
        if (isClosed) return;

        const session = getSession();
        try {
          if (aggregate) {
            // Aggregation mode: poll all child topics
            const result = await session.run(AGGREGATED_MESSAGE_QUERY, { pathPrefix: topicPath + '/' });

            if (result.records.length > 0) {
              let hasUpdates = false;
              const mergedPayload: Record<string, unknown> = {};
              const numericFields: string[] = [];
              let latestTimestamp = '';

              for (const record of result.records) {
                const childPath = record.get('childPath') as string;
                const payloadStr = record.get('payload') as string;
                const numericValue = record.get('numericValue');
                const timestamp = record.get('timestamp') as string;

                // Check if this child has a new message
                if (childTimestamps.get(childPath) !== timestamp) {
                  childTimestamps.set(childPath, timestamp);
                  hasUpdates = true;
                }

                // Track latest timestamp
                if (!latestTimestamp || timestamp > latestTimestamp) {
                  latestTimestamp = timestamp;
                }

                // Extract child topic name (last segment)
                const childName = childPath.split('/').pop() || childPath;

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

                // Merge with prefixed keys
                for (const [key, value] of Object.entries(payload)) {
                  const prefixedKey = `${childName}.${key}`;
                  mergedPayload[prefixedKey] = value;

                  if (typeof value === 'number' && !excludedFields.includes(key.toLowerCase())) {
                    numericFields.push(prefixedKey);
                  }
                }
              }

              // Send event if any child has updates
              if (hasUpdates) {
                sendEvent({
                  topic: topicPath,
                  payload: mergedPayload,
                  timestamp: latestTimestamp,
                  numericFields,
                  isAggregated: true,
                });
              }
            }
          } else {
            // Single topic mode
            const result = await session.run(LATEST_MESSAGE_QUERY, { topicPath });

            if (result.records.length > 0) {
              const record = result.records[0];
              const payloadStr = record.get('payload') as string;
              const numericValue = record.get('numericValue');
              const timestamp = record.get('timestamp') as string;

              // Only send if timestamp changed (new message)
              if (timestamp !== lastTimestamp) {
                lastTimestamp = timestamp;

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

                sendEvent({
                  topic: topicPath,
                  payload,
                  timestamp,
                  isAggregated: false,
                });
              }
            }
          }
        } catch (err) {
          console.error('[Topic Stream] Poll error:', err);
        } finally {
          await session.close();
        }

        // Schedule next poll
        if (!isClosed) {
          setTimeout(pollForUpdates, POLL_INTERVAL_MS);
        }
      };

      // Send initial connection event
      sendEvent({ type: 'connected', topic: topicPath, aggregate });

      // Start polling
      pollForUpdates();
    },

    cancel() {
      isClosed = true;
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}

export const dynamic = 'force-dynamic';
