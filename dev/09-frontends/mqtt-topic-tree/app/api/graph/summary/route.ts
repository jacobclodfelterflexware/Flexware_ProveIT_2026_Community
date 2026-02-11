// GET /api/graph/summary
// Returns high-level stats about the Neo4j knowledge graph
import { NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

export async function GET() {
  const session = getSession();

  try {
    // Get topic counts by broker
    const topicResult = await session.run(`
      MATCH (t:Topic)
      RETURN t.broker AS broker, count(t) AS count
    `);

    let totalTopics = 0;
    const byBroker: Record<string, number> = {};
    for (const record of topicResult.records) {
      const broker = record.get('broker') || 'unknown';
      const count = record.get('count').toNumber();
      byBroker[broker] = count;
      totalTopics += count;
    }

    // Get total message count
    const messageResult = await session.run(`
      MATCH (m:Message)
      RETURN count(m) AS messageCount
    `);

    const totalMessages = messageResult.records.length > 0
      ? messageResult.records[0].get('messageCount').toNumber()
      : 0;

    // Get top-level topic segments (depth 1)
    const segmentResult = await session.run(`
      MATCH (t:Topic)
      WHERE t.depth = 1
      RETURN DISTINCT t.name AS segment
      ORDER BY segment
      LIMIT 50
    `);

    const topSegments = segmentResult.records.map(r => r.get('segment') as string);

    return NextResponse.json({
      topics: {
        total: totalTopics,
        byBroker,
      },
      messages: {
        total: totalMessages,
      },
      topSegments,
    });
  } catch (error) {
    console.error('[Graph Summary API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch graph summary', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
