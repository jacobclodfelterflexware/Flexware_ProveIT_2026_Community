/**
 * API client for Machine Chat functionality
 */

import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  HistoricalContext,
  MachineContext,
  RAGContext,
  MLContext,
  ChatMessage,
} from '@/types/chat';
import type { MachineDefinition, SimilarResult } from '@/types/machines';

// Base URL for chat proxy (via Next.js API route)
const CHAT_PROXY_BASE = '/api/chat-proxy';
const CONTEXT_BASE = '/api/graph/machine-context';
const SIMILAR_SEARCH_BASE = '/api/graph/similar-search';

/**
 * Fetch historical messages and graph relationships for a machine
 */
export async function fetchMachineContext(
  machineId: string,
  topicPaths: string[]
): Promise<HistoricalContext> {
  const params = new URLSearchParams();
  params.set('machineId', machineId);
  topicPaths.forEach(tp => params.append('topics', tp));

  const response = await fetch(`${CONTEXT_BASE}?${params.toString()}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || 'Failed to fetch machine context');
  }

  return response.json();
}

/**
 * Perform RAG similarity search on the knowledge graph
 */
export async function searchSimilarTopics(
  query: string,
  k: number = 20
): Promise<{ results: SimilarResult[]; query: string; count: number }> {
  const response = await fetch(
    `${SIMILAR_SEARCH_BASE}?q=${encodeURIComponent(query)}&k=${k}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || 'Failed to search similar topics');
  }

  return response.json();
}

/**
 * Convert MachineDefinition to MachineContext for the API
 */
export function machineToContext(machine: MachineDefinition): MachineContext {
  return {
    id: machine.id,
    name: machine.name,
    machine_type: machine.machine_type,
    description: machine.description,
    status: machine.status,
    publish_interval_ms: machine.publish_interval_ms,
    topic_path: machine.topic_path,
    topics: machine.topics?.map(t => ({
      topic_path: t.topic_path,
      fields: t.fields.map(f => ({
        name: f.name,
        type: f.type,
        min_value: f.min_value,
        max_value: f.max_value,
        description: f.description,
      })),
    })),
    fields: machine.fields?.map(f => ({
      name: f.name,
      type: f.type,
      min_value: f.min_value,
      max_value: f.max_value,
      description: f.description,
    })),
    similarity_results: machine.similarity_results,
  };
}

/**
 * Send a chat message and receive a non-streaming response
 */
export async function sendChatMessage(
  request: ChatRequest
): Promise<ChatResponse> {
  const response = await fetch(`${CHAT_PROXY_BASE}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: false }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to send chat message');
  }

  return response.json();
}

/**
 * Send a chat message and stream the response
 * Returns an async iterator that yields content chunks
 */
export async function* streamChatMessage(
  request: ChatRequest
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${CHAT_PROXY_BASE}`, {
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

      // Parse SSE events from buffer
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

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
            // Skip non-JSON lines
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
 * Build a complete chat request with all context
 */
export function buildChatRequest(
  machine: MachineDefinition,
  historicalContext: HistoricalContext | null,
  ragContext: RAGContext | null,
  mlContext: MLContext | null,
  conversationHistory: ChatMessage[],
  userMessage: string,
  stream: boolean = true
): ChatRequest {
  return {
    machine_context: machineToContext(machine),
    historical_context: historicalContext || undefined,
    rag_context: ragContext || undefined,
    ml_context: mlContext || undefined,
    conversation_history: conversationHistory,
    user_message: userMessage,
    stream,
  };
}
