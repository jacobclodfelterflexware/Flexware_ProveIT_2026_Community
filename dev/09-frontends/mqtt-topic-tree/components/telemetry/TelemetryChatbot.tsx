'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ViewTransform } from '@/app/api/view-transform/route';
import type { ChatMessage, HistoricalContext, RAGContext, MLContext, MachineContext } from '@/types/chat';
import {
  searchSimilarTopics,
  streamChatMessage,
} from '@/lib/chat-api';
import ChatMessageComponent from '../machines/chat/ChatMessage';
import ChatInput from '../machines/chat/ChatInput';
import RAGSourcesIndicator from '../machines/chat/RAGSourcesIndicator';

interface TelemetryChatbotProps {
  topicPath: string;
  transform: ViewTransform;
  numericFields: string[];
  messageCount?: number;
}

const STORAGE_KEY_PREFIX = 'telemetry-chat-history-';
const SIDEBAR_OPEN_KEY = 'telemetry-chat-sidebar-open';

/**
 * Fetch historical messages for a topic from the knowledge graph
 */
async function fetchTopicContext(topicPath: string): Promise<HistoricalContext> {
  console.log('[TelemetryChatbot] Fetching context for topic:', topicPath);
  console.log('[TelemetryChatbot] Encoded path:', encodeURIComponent(topicPath));

  const response = await fetch(
    `/api/topic/messages?path=${encodeURIComponent(topicPath)}&limit=50`
  );

  if (!response.ok) {
    console.error('[TelemetryChatbot] API error:', response.status, response.statusText);
    throw new Error('Failed to fetch topic context');
  }

  const data = await response.json();
  console.log('[TelemetryChatbot] Received data:', {
    messagesCount: data.messages?.length || 0,
    parentTopics: data.parent_topics?.length || 0,
    childTopics: data.child_topics?.length || 0,
  });

  // Transform the response into HistoricalContext format
  return {
    recent_messages: (data.messages || []).map((msg: { topic: string; payload: Record<string, unknown>; timestamp: string }) => ({
      topic: msg.topic || topicPath,
      payload: msg.payload,
      timestamp: msg.timestamp,
    })),
    graph_relationships: {
      parent_topics: data.parent_topics || [],
      child_topics: data.child_topics || [],
    },
  };
}

/**
 * Build topic context from ViewTransform schema
 */
function buildTopicContext(
  topicPath: string,
  transform: ViewTransform,
  numericFields: string[],
  messageCount?: number
): MachineContext {
  const schema = transform.schema;

  return {
    name: topicPath.split('/').pop() || topicPath,
    machine_type: schema.machineType || 'telemetry',
    description: schema.description || `Telemetry data from topic: ${topicPath}`,
    status: 'active',
    publish_interval_ms: 0,
    topic_path: topicPath,
    topics: [{
      topic_path: topicPath,
      fields: schema.fieldMappings.map(fm => ({
        name: fm.source,
        type: fm.type,
        description: fm.target !== fm.source ? `Mapped to: ${fm.target}` : undefined,
      })),
    }],
    fields: schema.fieldMappings.map(fm => ({
      name: fm.source,
      type: fm.type,
      description: fm.target !== fm.source ? `Mapped to: ${fm.target}` : undefined,
    })),
  };
}

/**
 * Build a chat request with topic context
 */
function buildTopicChatRequest(
  topicPath: string,
  transform: ViewTransform,
  numericFields: string[],
  messageCount: number | undefined,
  historicalContext: HistoricalContext | null,
  ragContext: RAGContext | null,
  mlContext: MLContext | null,
  conversationHistory: ChatMessage[],
  userMessage: string,
  stream: boolean = true
) {
  return {
    machine_context: buildTopicContext(topicPath, transform, numericFields, messageCount),
    historical_context: historicalContext || undefined,
    rag_context: ragContext || undefined,
    ml_context: mlContext || undefined,
    conversation_history: conversationHistory,
    user_message: userMessage,
    stream,
  };
}

/**
 * Docked sidebar chat interface for telemetry page
 */
export default function TelemetryChatbot({
  topicPath,
  transform,
  numericFields,
  messageCount,
}: TelemetryChatbotProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historicalContext, setHistoricalContext] = useState<HistoricalContext | null>(null);
  const [mlContext, setMlContext] = useState<MLContext | null>(null);
  const [contextLoading, setContextLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Create a storage key based on the topic path (sanitized)
  const sanitizedPath = topicPath.replace(/[^a-zA-Z0-9]/g, '-');
  const storageKey = `${STORAGE_KEY_PREFIX}${sanitizedPath}`;

  // Load sidebar state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_OPEN_KEY);
      if (stored === 'true') {
        setIsOpen(true);
      }
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  // Save sidebar state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(isOpen));
    } catch {
      // Ignore localStorage errors
    }
  }, [isOpen]);

  // Clear chat history on page load (don't restore from sessionStorage)
  // This ensures fresh chat experience on each page refresh
  useEffect(() => {
    if (topicPath) {
      // Clear any stored history for this topic on mount
      try {
        sessionStorage.removeItem(storageKey);
      } catch {
        // Ignore storage errors
      }
    }
  }, [topicPath, storageKey]);

  // Save conversation history to sessionStorage
  useEffect(() => {
    if (topicPath && messages.length > 0) {
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(messages));
      } catch {
        console.error('Failed to save chat history');
      }
    }
  }, [messages, topicPath, storageKey]);

  // Fetch context on mount and when topic changes
  useEffect(() => {
    async function loadContext() {
      if (!topicPath) {
        console.log('[TelemetryChatbot] No topic path, skipping context load');
        setContextLoading(false);
        return;
      }

      console.log('[TelemetryChatbot] Loading context for topic:', topicPath);

      try {
        // Fetch historical context for the topic
        const context = await fetchTopicContext(topicPath);
        console.log('[TelemetryChatbot] Context loaded successfully:', {
          messages: context.recent_messages?.length || 0,
          parentTopics: context.graph_relationships?.parent_topics?.length || 0,
          childTopics: context.graph_relationships?.child_topics?.length || 0,
        });
        setHistoricalContext(context);

        // Note: ML context (predictions/regressions) is not preloaded here
        // because the ML panels are already visible on the telemetry page.
        // The chatbot can reference the topic's data and schema instead.
      } catch (e) {
        console.error('[TelemetryChatbot] Failed to load topic context:', e);
      } finally {
        setContextLoading(false);
      }
    }

    // Reset context when topic changes
    console.log('[TelemetryChatbot] Topic changed to:', topicPath);
    setHistoricalContext(null);
    setMlContext(null);
    setContextLoading(true);
    loadContext();
  }, [topicPath]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle sending a message
  const handleSend = useCallback(async (userMessage: string) => {
    if (!userMessage.trim() || isLoading) return;

    const userChatMessage: ChatMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userChatMessage]);
    setError(null);

    // Perform RAG search
    setIsRagLoading(true);
    let ragContext: RAGContext | null = null;

    try {
      const ragResults = await searchSimilarTopics(userMessage, 20);
      ragContext = {
        query: userMessage,
        similar_topics: ragResults.results,
      };
    } catch {
      console.error('RAG search failed');
    } finally {
      setIsRagLoading(false);
    }

    setIsLoading(true);

    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    try {
      const request = buildTopicChatRequest(
        topicPath,
        transform,
        numericFields,
        messageCount,
        historicalContext,
        ragContext,
        mlContext,
        messages,
        userMessage,
        true
      );

      let fullContent = '';
      for await (const chunk of streamChatMessage(request)) {
        fullContent += chunk;
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...updated[updated.length - 1],
            content: fullContent,
          };
          return updated;
        });
      }
    } catch (e) {
      const errorMessage = e instanceof Error ? e.message : 'Failed to get response';
      setError(errorMessage);
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: `Error: ${errorMessage}`,
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  }, [topicPath, transform, numericFields, messageCount, historicalContext, mlContext, messages, isLoading]);

  const handleClear = useCallback(() => {
    setMessages([]);
    if (topicPath) {
      sessionStorage.removeItem(storageKey);
    }
    setError(null);
  }, [topicPath, storageKey]);

  // Get display name from topic path
  const displayName = topicPath.split('/').pop() || 'Topic';

  return (
    <>
      {/* Fixed sidebar container */}
      <div
        className={`fixed top-0 right-0 h-full z-50 flex transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-[50vw]'
        }`}
      >
        {/* Toggle button - always visible on the left edge */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex-shrink-0 w-12 bg-gray-800 border-l border-y border-gray-700 rounded-l-lg flex flex-col items-center justify-center gap-2 hover:bg-gray-750 transition-colors group"
          title={isOpen ? 'Close chat' : 'Open chat'}
        >
          {/* Arrow icon */}
          <svg
            className={`w-5 h-5 text-gray-400 group-hover:text-gray-200 transition-transform duration-300 ${
              isOpen ? '' : 'rotate-180'
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>

          {/* Chat icon with purple gradient for telemetry */}
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>

          {/* Unread indicator when closed and has messages */}
          {!isOpen && messages.length > 0 && (
            <span className="absolute top-4 right-2 w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
          )}
        </button>

        {/* Chat panel */}
        <div className="w-[50vw] h-full bg-gray-800 border-l border-gray-700 flex flex-col shadow-2xl">
          {/* Header */}
          <div className="flex-shrink-0 px-4 py-3 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-100">Telemetry Assistant</h3>
                <p className="text-xs text-gray-500">
                  {contextLoading ? 'Loading context...' :
                   (() => {
                     const parts: string[] = [];
                     if (historicalContext?.recent_messages?.length) {
                       parts.push(`${historicalContext.recent_messages.length} msgs`);
                     }
                     if (mlContext?.prediction) parts.push('prediction');
                     if (mlContext?.regression) parts.push('regression');
                     return parts.length > 0
                       ? `Context: ${parts.join(', ')}`
                       : `Ask questions about ${displayName}`;
                   })()}
                </p>
              </div>
            </div>

            {messages.length > 0 && (
              <button
                onClick={handleClear}
                className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
              >
                Clear
              </button>
            )}
          </div>

          {/* Messages area - grows to fill available space */}
          <div className="flex-1 overflow-y-auto p-4 space-y-1">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-500">
                <svg className="w-12 h-12 mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-sm font-medium">No messages yet</p>
                <p className="text-xs mt-1 text-center px-4">Ask a question about {displayName}</p>
                <div className="mt-4 space-y-2 w-full max-w-xs">
                  <p className="text-xs text-gray-600 text-center">Suggested questions:</p>
                  <button
                    onClick={() => handleSend('What does this topic measure?')}
                    className="w-full text-left text-xs px-3 py-2 bg-gray-700/50 rounded hover:bg-gray-700 transition-colors"
                  >
                    What does this topic measure?
                  </button>
                  <button
                    onClick={() => handleSend('What are the recent values and trends?')}
                    className="w-full text-left text-xs px-3 py-2 bg-gray-700/50 rounded hover:bg-gray-700 transition-colors"
                  >
                    What are the recent values and trends?
                  </button>
                  <button
                    onClick={() => handleSend('Are there any anomalies in the data?')}
                    className="w-full text-left text-xs px-3 py-2 bg-gray-700/50 rounded hover:bg-gray-700 transition-colors"
                  >
                    Are there any anomalies in the data?
                  </button>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <ChatMessageComponent
                    key={idx}
                    message={msg}
                    isStreaming={isLoading && idx === messages.length - 1 && msg.role === 'assistant'}
                  />
                ))}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Error display */}
          {error && (
            <div className="flex-shrink-0 mx-3 mb-2 px-3 py-2 bg-red-900/30 border border-red-800/50 rounded-lg">
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* RAG loading indicator */}
          <div className="flex-shrink-0">
            <RAGSourcesIndicator visible={isRagLoading} />
          </div>

          {/* Input area */}
          <div className="flex-shrink-0">
            <ChatInput
              onSend={handleSend}
              disabled={isLoading || isRagLoading || contextLoading}
              placeholder={
                contextLoading
                  ? 'Loading topic context...'
                  : `Ask about ${displayName}...`
              }
            />
          </div>
        </div>
      </div>
    </>
  );
}
