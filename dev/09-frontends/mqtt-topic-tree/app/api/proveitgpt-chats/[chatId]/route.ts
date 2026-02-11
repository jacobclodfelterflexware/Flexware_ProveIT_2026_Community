import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

interface RouteParams {
  params: Promise<{ chatId: string }>;
}

/**
 * GET /api/proveitgpt-chats/[chatId]
 * Load a chat with all its messages
 */
export async function GET(
  request: NextRequest,
  { params }: RouteParams
) {
  const { chatId } = await params;
  const session = getSession();

  try {
    const result = await session.run(
      `MATCH (c:ProveITGPTChat {id: $chatId})
      OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:ProveITGPTMessage)
      WITH c, m ORDER BY m.orderIndex ASC
      WITH c, collect(m {
        .id, .role, .content,
        timestamp: toString(m.timestamp)
      }) AS messages
      RETURN c {
        .id, .title,
        createdAt: toString(c.createdAt),
        updatedAt: toString(c.updatedAt)
      } AS chat, messages, size(messages) AS messageCount`,
      { chatId }
    );

    const record = result.records[0];
    if (!record) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }

    const chat = record.get('chat');
    const messages = record.get('messages').filter((m: Record<string, unknown>) => m.id !== null);

    return NextResponse.json({
      chat: {
        ...chat,
        messageCount: record.get('messageCount').toNumber(),
      },
      messages,
    });
  } catch (error) {
    console.error('[ProveITGPT Chats] Error fetching chat:', error);
    return NextResponse.json(
      { error: 'Failed to fetch chat' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * DELETE /api/proveitgpt-chats/[chatId]
 * Delete a chat and all its messages
 */
export async function DELETE(
  request: NextRequest,
  { params }: RouteParams
) {
  const { chatId } = await params;
  const session = getSession();

  try {
    const result = await session.run(
      `MATCH (c:ProveITGPTChat {id: $chatId})
      OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:ProveITGPTMessage)
      WITH c, collect(m) AS msgs, c.id AS deletedId
      FOREACH (m IN msgs | DETACH DELETE m)
      DETACH DELETE c
      RETURN deletedId`,
      { chatId }
    );

    const record = result.records[0];
    if (!record) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('[ProveITGPT Chats] Error deleting chat:', error);
    return NextResponse.json(
      { error: 'Failed to delete chat' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
