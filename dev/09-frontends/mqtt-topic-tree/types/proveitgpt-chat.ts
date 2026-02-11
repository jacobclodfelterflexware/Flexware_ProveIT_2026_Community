/**
 * Types for ProveITGPT chat persistence in Neo4j
 */

/** A persisted ProveITGPT chat conversation */
export interface ProveITGPTChat {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

/** A persisted chat message within a ProveITGPTChat */
export interface ProveITGPTPersistedMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

/** Response for listing chats */
export interface ChatListResponse {
  chats: ProveITGPTChat[];
  total: number;
}

/** Response for loading a single chat with messages */
export interface ChatDetailResponse {
  chat: ProveITGPTChat;
  messages: ProveITGPTPersistedMessage[];
}

/** Request to add a message to a chat */
export interface AddMessageRequest {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}
