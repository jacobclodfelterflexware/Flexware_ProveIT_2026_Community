import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';
import { randomUUID } from 'crypto';

/**
 * GET /api/proveitgpt-chats
 * List all chats ordered by updatedAt DESC
 */
export async function GET() {
  const session = getSession();

  try {
    const result = await session.run(`
      MATCH (c:ProveITGPTChat)
      OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:ProveITGPTMessage)
      WITH c, count(m) AS messageCount
      RETURN c {
        .id, .title,
        createdAt: toString(c.createdAt),
        updatedAt: toString(c.updatedAt)
      } AS chat, messageCount
      ORDER BY c.updatedAt DESC
    `);

    const chats = result.records.map(record => ({
      ...record.get('chat'),
      messageCount: record.get('messageCount').toNumber(),
    }));

    return NextResponse.json({ chats, total: chats.length });
  } catch (error) {
    console.error('[ProveITGPT Chats] Error listing chats:', error);
    return NextResponse.json(
      { error: 'Failed to list chats' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * POST /api/proveitgpt-chats
 * Create a new chat
 */
export async function POST(request: NextRequest) {
  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { title } = body;
  if (!title) {
    return NextResponse.json({ error: 'title is required' }, { status: 400 });
  }

  const id = randomUUID();
  const now = new Date().toISOString();
  const session = getSession();

  try {
    await session.run(
      `CREATE (c:ProveITGPTChat {
        id: $id,
        title: $title,
        createdAt: datetime($now),
        updatedAt: datetime($now)
      })
      RETURN c.id AS id`,
      { id, title, now }
    );

    return NextResponse.json({ success: true, id });
  } catch (error) {
    console.error('[ProveITGPT Chats] Error creating chat:', error);
    return NextResponse.json(
      { error: 'Failed to create chat' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
