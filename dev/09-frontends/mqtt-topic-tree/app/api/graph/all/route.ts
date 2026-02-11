// GET /api/graph/all
// Returns all topic nodes and their parent relationships for 3D visualization
// Only returns topic hierarchy (not messages)
import { NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

// Cypher query to fetch ALL topics with parent relationships (no limit)
// This ensures similarity search results always match nodes in the graph
const ALL_TOPICS_QUERY = `
MATCH (t:Topic)
OPTIONAL MATCH (t)-[:CHILD_OF]->(parent:Topic)
WITH t, parent
ORDER BY t.path
RETURN t.path as id,
       t.name as name,
       size(split(t.path, '/')) as depth,
       parent.path as parent
`;

interface GraphNode {
  id: string;
  name: string;
  depth: number;
}

interface GraphLink {
  source: string;
  target: string;
}

export async function GET() {
  const session = getSession();

  try {
    const result = await session.run(ALL_TOPICS_QUERY);

    const nodes: GraphNode[] = [];
    const links: GraphLink[] = [];
    const seenIds = new Set<string>();

    for (const record of result.records) {
      const id = record.get('id') as string;
      const name = record.get('name') as string;
      const depth = record.get('depth');
      const parent = record.get('parent') as string | null;

      // Add node if not seen
      if (id && !seenIds.has(id)) {
        nodes.push({
          id,
          name: name || id.split('/').pop() || id,
          depth: typeof depth === 'object' && depth !== null ? depth.toNumber() : (depth || 1),
        });
        seenIds.add(id);
      }

      // Add link to parent
      if (parent) {
        links.push({
          source: id,
          target: parent,
        });
      }
    }

    return NextResponse.json({
      nodes,
      links,
      count: nodes.length,
    });
  } catch (error) {
    console.error('[Graph All API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch graph data', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
