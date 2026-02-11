// GET /api/graph/siblings?path=<topic_path>
// Returns all sibling topics (topics with the same parent)
// Used for cross-topic regression to find closely related topics

import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

// Query to find siblings - topics that share the same parent
const SIBLINGS_QUERY = `
MATCH (t:Topic {path: $topicPath})
MATCH (t)-[:CHILD_OF]->(parent:Topic)
MATCH (sibling:Topic)-[:CHILD_OF]->(parent)
WHERE sibling.path <> $topicPath
RETURN sibling.path AS path, parent.path AS parentPath
ORDER BY sibling.path
`;

// Fallback: if topic doesn't have CHILD_OF relationship, use path parsing
const SIBLINGS_BY_PATH_QUERY = `
MATCH (t:Topic)
WHERE t.path STARTS WITH $parentPrefix
  AND t.path <> $topicPath
  AND NOT t.path CONTAINS '/' + $parentPrefix
  AND size(split(t.path, '/')) = $depth
RETURN t.path AS path
ORDER BY t.path
LIMIT 20
`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const topicPath = searchParams.get('path');

  if (!topicPath) {
    return NextResponse.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  console.log('[Siblings API] Finding siblings for:', topicPath);

  const session = getSession();

  try {
    // First try using CHILD_OF relationships
    const result = await session.run(SIBLINGS_QUERY, { topicPath });

    if (result.records.length > 0) {
      const siblings = result.records.map(record => ({
        path: record.get('path') as string,
        parentPath: record.get('parentPath') as string,
      }));

      console.log('[Siblings API] Found', siblings.length, 'siblings via CHILD_OF');

      return NextResponse.json({
        topicPath,
        siblings,
        count: siblings.length,
        method: 'child_of_relationship',
      });
    }

    // Fallback: parse path to find parent and query by path prefix
    const pathParts = topicPath.split('/');
    if (pathParts.length > 1) {
      const parentPrefix = pathParts.slice(0, -1).join('/') + '/';
      const depth = pathParts.length;

      console.log('[Siblings API] No CHILD_OF found, trying path-based search with prefix:', parentPrefix);

      const pathResult = await session.run(SIBLINGS_BY_PATH_QUERY, {
        parentPrefix,
        topicPath,
        depth,
      });

      const siblings = pathResult.records.map(record => ({
        path: record.get('path') as string,
        parentPath: pathParts.slice(0, -1).join('/'),
      }));

      console.log('[Siblings API] Found', siblings.length, 'siblings via path prefix');

      return NextResponse.json({
        topicPath,
        siblings,
        count: siblings.length,
        method: 'path_prefix',
      });
    }

    // No siblings found
    return NextResponse.json({
      topicPath,
      siblings: [],
      count: 0,
      method: 'none',
    });
  } catch (error) {
    console.error('[Siblings API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch siblings', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
