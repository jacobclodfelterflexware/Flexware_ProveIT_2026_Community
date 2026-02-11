/**
 * API client for ProveITGPT knowledge base chat
 */

import type { GraphSummary, KBChatRequest, ChatStreamEvent, ChatMessage } from '@/types/knowledge-base';

const KB_CHAT_PROXY = '/api/knowledge-chat';
const GRAPH_SUMMARY_URL = '/api/graph/summary';

/**
 * Fetch high-level graph summary stats from Neo4j
 */
export async function fetchGraphSummary(): Promise<GraphSummary> {
  const response = await fetch(GRAPH_SUMMARY_URL);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || 'Failed to fetch graph summary');
  }

  return response.json();
}

/**
 * Stream a knowledge base chat response via SSE
 */
export async function* streamKBChat(
  request: KBChatRequest
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(KB_CHAT_PROXY, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to send chat message');
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event: ChatStreamEvent = JSON.parse(data);
            if (event.error) {
              throw new Error(event.error);
            }
            if (event.content) {
              yield event.content;
            }
            if (event.done) {
              return;
            }
          } catch (e) {
            if (data.trim() && !data.includes('[DONE]')) {
              console.warn('Failed to parse SSE event:', data);
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Build a knowledge base chat request
 */
export function buildKBChatRequest(
  graphSummary: GraphSummary | null,
  ragContext: { query: string; similar_topics: Array<{ topic_path: string; similarity: number; field_names: string[]; historical_payloads: Array<{ payload: Record<string, unknown>; timestamp?: string }> }> } | null,
  conversationHistory: ChatMessage[],
  userMessage: string,
): KBChatRequest {
  return {
    graph_summary: graphSummary,
    rag_context: ragContext || undefined,
    conversation_history: conversationHistory,
    user_message: userMessage,
    stream: true,
  };
}
