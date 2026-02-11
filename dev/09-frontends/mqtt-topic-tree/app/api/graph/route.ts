// GET /api/graph?topic=<path>
// Returns graph data for Neo4j visualization
// Client IDs are now the root level of the topic hierarchy (no broker filter needed)
import { NextRequest, NextResponse } from 'next/server';
import neo4j from 'neo4j-driver';
import { getSession } from '@/lib/neo4j-client';
import { transformToNvlFormat } from '@/lib/graph-transformer';
import type { GraphApiResponse } from '@/types/graph';

// Cypher query to fetch topic with full context (unified Topic model)
const GRAPH_QUERY = `
MATCH (topic:Topic {path: $topicPath})

// Get recent messages (limit 5)
OPTIONAL MATCH (topic)-[has_msg:HAS_MESSAGE]->(msg:Message)
WITH topic, has_msg, msg
ORDER BY msg.timestamp DESC
WITH topic, collect({
  id: elementId(msg),
  rawPayload: msg.rawPayload,
  payloadText: msg.payloadText,
  timestamp: toString(msg.timestamp),
  relId: elementId(has_msg)
})[0..$messageLimit] AS messages

// Get parent Topics via CHILD_OF chain (all ancestors up to root)
OPTIONAL MATCH (topic)-[:CHILD_OF*1..]->(ancestor:Topic)
WITH topic, messages, collect(DISTINCT {
  id: elementId(ancestor),
  name: ancestor.name,
  fullPath: ancestor.path
}) AS parents

// Return structured data
RETURN {
  topic: {
    id: elementId(topic),
    path: topic.path
  },
  messages: [m IN messages WHERE m.id IS NOT NULL],
  parents: parents
} AS graphData
`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('topic');

  if (!topicPath) {
    return NextResponse.json(
      { error: 'topic parameter is required' },
      { status: 400 }
    );
  }

  const session = getSession();

  try {
    // Execute main graph query (no broker filter)
    const result = await session.run(GRAPH_QUERY, {
      topicPath,
      messageLimit: neo4j.int(5),
    });

    if (result.records.length === 0) {
      return NextResponse.json(
        { error: 'Topic not found in graph database' },
        { status: 404 }
      );
    }

    const graphData = result.records[0].get('graphData') as GraphApiResponse;

    // Only show literal relationships (messages, parent hierarchy) - no vector similarity
    const fullResponse: GraphApiResponse = {
      ...graphData,
      routings: [], // No schema mappings yet
      similarTopics: [], // Disabled - only show literal graph relationships
    };

    // Transform to NVL format
    const nvlData = transformToNvlFormat(fullResponse);

    return NextResponse.json(nvlData);
  } catch (error) {
    console.error('[Graph API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch graph data', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
