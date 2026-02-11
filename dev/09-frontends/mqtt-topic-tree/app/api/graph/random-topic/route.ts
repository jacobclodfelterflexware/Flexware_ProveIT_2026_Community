// GET /api/graph/random-topic
// Returns a random topic that has message payloads for similarity search
import { NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

const RANDOM_TOPIC_QUERY = `
MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
WHERE m.rawPayload IS NOT NULL AND m.rawPayload <> ''
WITH t, m
ORDER BY rand()
LIMIT 1
RETURN t.path as topic_path,
       m.rawPayload as payload,
       m.timestamp as timestamp
`;

export async function GET() {
  const session = getSession();

  try {
    const result = await session.run(RANDOM_TOPIC_QUERY);

    if (result.records.length === 0) {
      return NextResponse.json(
        { error: 'No topics with payloads found' },
        { status: 404 }
      );
    }

    const record = result.records[0];
    const topicPath = record.get('topic_path') as string;
    const payload = record.get('payload') as string;
    const timestamp = record.get('timestamp');

    return NextResponse.json({
      topic_path: topicPath,
      payload: payload,
      timestamp: timestamp ? timestamp.toString() : null,
    });
  } catch (error) {
    console.error('[Random Topic API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch random topic', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
