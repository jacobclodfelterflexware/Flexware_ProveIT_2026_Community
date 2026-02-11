/**
 * Types for ProveITGPT knowledge base chat
 */

import type { ChatMessage, RAGContext, ChatStreamEvent } from './chat';

/**
 * High-level graph summary stats
 */
export interface GraphSummary {
  topics: {
    total: number;
    byBroker: Record<string, number>;
  };
  messages: {
    total: number;
  };
  topSegments: string[];
}

/**
 * Request body for the knowledge base chat API
 */
export interface KBChatRequest {
  graph_summary?: GraphSummary | null;
  rag_context?: RAGContext;
  conversation_history: ChatMessage[];
  user_message: string;
  stream?: boolean;
}

// Re-export shared types for convenience
export type { ChatMessage, RAGContext, ChatStreamEvent };
