import type {
  ChatListResponse,
  ChatDetailResponse,
  AddMessageRequest,
} from '@/types/proveitgpt-chat';

const BASE = '/api/proveitgpt-chats';

/** Fetch all chats, most recent first */
export async function fetchChatList(): Promise<ChatListResponse> {
  const res = await fetch(BASE);
  if (!res.ok) throw new Error('Failed to fetch chats');
  return res.json();
}

/** Create a new chat */
export async function createChat(title: string): Promise<{ id: string }> {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create chat');
  return res.json();
}

/** Load a chat with all messages */
export async function fetchChat(chatId: string): Promise<ChatDetailResponse> {
  const res = await fetch(`${BASE}/${chatId}`);
  if (!res.ok) throw new Error('Failed to fetch chat');
  return res.json();
}

/** Delete a chat */
export async function deleteChat(chatId: string): Promise<void> {
  const res = await fetch(`${BASE}/${chatId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete chat');
}

/** Add a message to a chat */
export async function addMessage(
  chatId: string,
  message: AddMessageRequest
): Promise<{ messageId: string; orderIndex: number }> {
  const res = await fetch(`${BASE}/${chatId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(message),
  });
  if (!res.ok) throw new Error('Failed to add message');
  return res.json();
}

/** Update an existing message's content (after streaming completes) */
export async function updateMessage(
  chatId: string,
  messageId: string,
  content: string
): Promise<void> {
  const res = await fetch(`${BASE}/${chatId}/messages`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messageId, content }),
  });
  if (!res.ok) throw new Error('Failed to update message');
}

/** Derive a chat title from the first user message */
export function deriveChatTitle(firstMessage: string): string {
  const cleaned = firstMessage.replace(/\n/g, ' ').trim();
  return cleaned.length > 50 ? cleaned.substring(0, 47) + '...' : cleaned;
}
