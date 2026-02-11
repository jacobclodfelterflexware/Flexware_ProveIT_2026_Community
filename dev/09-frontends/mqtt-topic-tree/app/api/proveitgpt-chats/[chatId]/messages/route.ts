import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';
import { randomUUID } from 'crypto';

interface RouteParams {
  params: Promise<{ chatId: string }>;
}

/**
 * POST /api/proveitgpt-chats/[chatId]/messages
 * Add a message to a chat
 */
export async function POST(
  request: NextRequest,
  { params }: RouteParams
) {
  const { chatId } = await params;

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { role, content, timestamp } = body;
  if (!role || content === undefined || !timestamp) {
    return NextResponse.json(
      { error: 'role, content, and timestamp are required' },
      { status: 400 }
    );
  }

  const msgId = randomUUID();
  const session = getSession();

  try {
    const result = await session.run(
      `MATCH (c:ProveITGPTChat {id: $chatId})
      OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(existing:ProveITGPTMessage)
      WITH c, count(existing) AS currentCount
      CREATE (m:ProveITGPTMessage {
        id: $msgId,
        role: $role,
        content: $content,
        timestamp: datetime($timestamp),
        orderIndex: currentCount
      })
      CREATE (c)-[:HAS_MESSAGE]->(m)
      SET c.updatedAt = datetime($timestamp)
      RETURN m.id AS id, m.orderIndex AS orderIndex`,
      { chatId, msgId, role, content, timestamp }
    );

    const record = result.records[0];
    if (!record) {
      return NextResponse.json({ error: 'Chat not found' }, { status: 404 });
    }

    return NextResponse.json({
      success: true,
      messageId: record.get('id'),
      orderIndex: record.get('orderIndex').toNumber(),
    });
  } catch (error) {
    console.error('[ProveITGPT Messages] Error adding message:', error);
    return NextResponse.json(
      { error: 'Failed to add message' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

/**
 * PATCH /api/proveitgpt-chats/[chatId]/messages
 * Update a message's content (used after streaming completes)
 */
export async function PATCH(
  request: NextRequest,
  { params }: RouteParams
) {
  const { chatId } = await params;

  let body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { messageId, content } = body;
  if (!messageId || content === undefined) {
    return NextResponse.json(
      { error: 'messageId and content are required' },
      { status: 400 }
    );
  }

  const session = getSession();

  try {
    const result = await session.run(
      `MATCH (c:ProveITGPTChat {id: $chatId})-[:HAS_MESSAGE]->(m:ProveITGPTMessage {id: $messageId})
      SET m.content = $content
      RETURN m.id AS id`,
      { chatId, messageId, content }
    );

    const record = result.records[0];
    if (!record) {
      return NextResponse.json({ error: 'Message not found' }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('[ProveITGPT Messages] Error updating message:', error);
    return NextResponse.json(
      { error: 'Failed to update message' },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
