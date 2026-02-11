// GET /api/graph/machine-context
// Fetches historical messages and graph relationships for a machine's topics
import { NextRequest, NextResponse } from 'next/server';
import neo4j from 'neo4j-driver';
import { getSession } from '@/lib/neo4j-client';

// Cypher query to fetch recent messages for topics
const MESSAGES_QUERY = `
UNWIND $topicPaths AS topicPath
MATCH (t:Topic {path: topicPath})-[:HAS_MESSAGE]->(m:Message)
WHERE m.rawPayload IS NOT NULL
WITH t, m
ORDER BY m.timestamp DESC
LIMIT $limit
RETURN t.path AS topic, m.rawPayload AS payload, toString(m.timestamp) AS timestamp
`;

// Cypher query to fetch parent/child relationships for the primary topic
const RELATIONSHIPS_QUERY = `
MATCH (t:Topic {path: $primaryTopic})
OPTIONAL MATCH (t)-[:CHILD_OF]->(parent:Topic)
OPTIONAL MATCH (child:Topic)-[:CHILD_OF]->(t)
RETURN
  collect(DISTINCT parent.path) AS parents,
  collect(DISTINCT child.path) AS children
`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const machineId = searchParams.get('machineId');
  const topicPaths = searchParams.getAll('topics');

  if (!machineId) {
    return NextResponse.json(
      { error: 'machineId parameter is required' },
      { status: 400 }
    );
  }

  if (topicPaths.length === 0) {
    // Return empty context if no topics
    return NextResponse.json({
      recent_messages: [],
      graph_relationships: {
        parent_topics: [],
        child_topics: [],
      },
    });
  }

  const session = getSession();

  try {
    // Fetch recent messages for all topics
    const messagesResult = await session.run(MESSAGES_QUERY, {
      topicPaths,
      limit: neo4j.int(50),
    });

    const recentMessages = messagesResult.records.map(record => {
      let payload = record.get('payload');

      // Parse JSON payload if it's a string
      if (typeof payload === 'string') {
        try {
          payload = JSON.parse(payload);
        } catch {
          // Keep as string if parse fails
        }
      }

      return {
        topic: record.get('topic'),
        payload,
        timestamp: record.get('timestamp'),
      };
    });

    // Fetch relationships for the primary topic (first one)
    const primaryTopic = topicPaths[0];
    const relResult = await session.run(RELATIONSHIPS_QUERY, {
      primaryTopic,
    });

    let parentTopics: string[] = [];
    let childTopics: string[] = [];

    if (relResult.records.length > 0) {
      const record = relResult.records[0];
      parentTopics = (record.get('parents') || []).filter((p: string | null) => p !== null);
      childTopics = (record.get('children') || []).filter((c: string | null) => c !== null);
    }

    return NextResponse.json({
      recent_messages: recentMessages,
      graph_relationships: {
        parent_topics: parentTopics,
        child_topics: childTopics,
      },
    });
  } catch (error) {
    console.error('[Machine Context API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch machine context', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
