import { getSession } from '@/lib/neo4j-client';

/**
 * GET /api/topics/list
 * Returns a list of all topic paths for autocomplete suggestions
 */
export async function GET() {
  const session = getSession();

  try {
    const result = await session.run(`
      MATCH (t:Topic)
      RETURN t.path as path
      ORDER BY t.path
    `);

    const topics = result.records.map((record) => record.get('path') as string);

    return Response.json({ topics });
  } catch (error) {
    console.error('[Topics List] Error:', error);
    return Response.json({ error: 'Failed to fetch topics' }, { status: 500 });
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
