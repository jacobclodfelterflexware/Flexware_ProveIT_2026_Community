/**
 * Types for Machine Chat functionality
 */

import type { MachineDefinition, SimilarResult } from './machines';

/**
 * A single chat message in the conversation
 */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

/**
 * A historical MQTT message from Neo4j
 */
export interface HistoricalMessage {
  topic: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

/**
 * Graph relationships for a topic
 */
export interface GraphRelationships {
  parent_topics: string[];
  child_topics: string[];
}

/**
 * Historical context fetched for a machine
 */
export interface HistoricalContext {
  recent_messages: HistoricalMessage[];
  graph_relationships: GraphRelationships;
}

/**
 * RAG context from similarity search
 */
export interface RAGContext {
  query: string;
  similar_topics: SimilarResult[];
}

/**
 * Time series prediction data
 */
export interface PredictionContext {
  field: string;
  topic: string;
  horizon: string;
  predictions: Array<{
    date: string;
    value: number;
    lower: number;
    upper: number;
  }>;
  metrics: {
    rmse?: number;
    mae?: number;
    mape?: number;
  };
  dataPointsUsed: number;
}

/**
 * Regression feature info
 */
export interface RegressionFeature {
  topic: string;
  field: string;
  coefficient: number;
  pValue?: number;
  importance?: number;
}

/**
 * Regression analysis data
 */
export interface RegressionContext {
  targetField: string;
  targetTopic: string;
  features: RegressionFeature[];
  intercept: number;
  rSquared: number;
  correlationMatrix: Record<string, Record<string, number>>;
  dataPointsUsed: number;
}

/**
 * ML Insights context for chat
 */
export interface MLContext {
  prediction?: PredictionContext;
  regression?: RegressionContext;
}

/**
 * Machine context sent to the chat API
 */
export interface MachineContext {
  id?: string;
  name: string;
  machine_type?: string;
  description?: string;
  status: string;
  publish_interval_ms: number;
  topic_path?: string;
  topics?: Array<{
    topic_path: string;
    fields: Array<{
      name: string;
      type: string;
      min_value?: number;
      max_value?: number;
      description?: string;
    }>;
  }>;
  fields?: Array<{
    name: string;
    type: string;
    min_value?: number;
    max_value?: number;
    description?: string;
  }>;
  similarity_results?: SimilarResult[];
}

/**
 * Request body for the chat API
 */
export interface ChatRequest {
  machine_context: MachineContext;
  historical_context?: HistoricalContext;
  rag_context?: RAGContext;
  ml_context?: MLContext;
  conversation_history: ChatMessage[];
  user_message: string;
  stream?: boolean;
}

/**
 * Response from non-streaming chat API
 */
export interface ChatResponse {
  content: string;
  role: 'assistant';
}

/**
 * SSE event data from streaming chat
 */
export interface ChatStreamEvent {
  content?: string;
  done?: boolean;
  error?: string;
}

/**
 * Props for the MachineChatbot component
 */
export interface MachineChatbotProps {
  machine: MachineDefinition;
}

/**
 * State for managing chat in the UI
 */
export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  isRagLoading: boolean;
  error: string | null;
  historicalContext: HistoricalContext | null;
  mlContext: MLContext | null;
  contextLoading: boolean;
}
