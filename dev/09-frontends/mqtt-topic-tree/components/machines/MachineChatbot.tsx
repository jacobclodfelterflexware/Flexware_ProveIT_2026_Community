'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { MachineDefinition } from '@/types/machines';
import type { ChatMessage, HistoricalContext, RAGContext, MLContext } from '@/types/chat';
import { getPrediction, getRegression } from '@/lib/ml-api';
import type { PredictionResponse, RegressionResponse } from '@/lib/ml-api';
import {
  fetchMachineContext,
  searchSimilarTopics,
  streamChatMessage,
  buildChatRequest,
} from '@/lib/chat-api';
import ChatMessageComponent from './chat/ChatMessage';
import ChatInput from './chat/ChatInput';
import RAGSourcesIndicator from './chat/RAGSourcesIndicator';

interface MachineChatbotProps {
  machine: MachineDefinition;
}

const STORAGE_KEY_PREFIX = 'machine-chat-history-';
const SIDEBAR_OPEN_KEY = 'machine-chat-sidebar-open';

/**
 * Docked sidebar chat interface for machine detail page
 */
export default function MachineChatbot({ machine }: MachineChatbotProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historicalContext, setHistoricalContext] = useState<HistoricalContext | null>(null);
  const [mlContext, setMlContext] = useState<MLContext | null>(null);
  const [contextLoading, setContextLoading] = useState(true);
  const [isOpen, setIsOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const storageKey = `${STORAGE_KEY_PREFIX}${machine.id}`;

  // Get topic paths from machine
  const topicPaths = machine.topics?.map(t => t.topic_path) ||
    (machine.topic_path ? [machine.topic_path] : []);

  // Load sidebar state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_OPEN_KEY);
      if (stored === 'true') {
        setIsOpen(true);
      }
    } catch (e) {
      // Ignore localStorage errors
    }
  }, []);

  // Save sidebar state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(isOpen));
    } catch (e) {
      // Ignore localStorage errors
    }
  }, [isOpen]);

  // Load conversation history from sessionStorage
  useEffect(() => {
    if (machine.id) {
      try {
        const stored = sessionStorage.getItem(storageKey);
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            setMessages(parsed);
          }
        }
      } catch (e) {
        console.error('Failed to load chat history:', e);
      }
    }
  }, [machine.id, storageKey]);

  // Save conversation history to sessionStorage
  useEffect(() => {
    if (machine.id && messages.length > 0) {
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(messages));
      } catch (e) {
        console.error('Failed to save chat history:', e);
      }
    }
  }, [messages, machine.id, storageKey]);

  // Get first numeric field for ML analysis
  const getFirstNumericField = () => {
    const fields = machine.topics?.[0]?.fields || machine.fields || [];
    const numericField = fields.find(f =>
      f.type === 'number' || f.type === 'integer'
    );
    const topic = machine.topics?.[0]?.topic_path || machine.topic_path;
    return numericField && topic ? { field: numericField.name, topic } : null;
  };

  // Fetch historical context and ML data on mount
  useEffect(() => {
    async function loadContext() {
      if (!machine.id || topicPaths.length === 0) {
        setContextLoading(false);
        return;
      }

      try {
        // Fetch historical context
        const context = await fetchMachineContext(machine.id, topicPaths);
        setHistoricalContext(context);

        // Fetch ML data if we have a numeric field
        const numericField = getFirstNumericField();
        if (numericField && machine.id) {
          const mlData: MLContext = {};

          // Fetch prediction data (silently fail if unavailable)
          try {
            const prediction: PredictionResponse = await getPrediction(
              machine.id,
              numericField.field,
              numericField.topic,
              'week',
              false
            );
            mlData.prediction = {
              field: prediction.field,
              topic: prediction.topic,
              horizon: prediction.horizon,
              predictions: prediction.predictions,
              metrics: prediction.metrics,
              dataPointsUsed: prediction.dataPointsUsed,
            };
          } catch (e) {
            console.log('Prediction data not available for chat context');
          }

          // Fetch regression data (silently fail if unavailable)
          try {
            const regression: RegressionResponse = await getRegression(
              machine.id,
              numericField.field,
              numericField.topic,
              true,
              undefined,
              false
            );
            mlData.regression = {
              targetField: regression.targetField,
              targetTopic: regression.targetTopic,
              features: regression.features.map(f => ({
                topic: f.topic,
                field: f.field,
                coefficient: f.coefficient,
                pValue: f.pValue,
                importance: f.importance,
              })),
              intercept: regression.intercept,
              rSquared: regression.rSquared,
              correlationMatrix: regression.correlationMatrix,
              dataPointsUsed: regression.dataPointsUsed,
            };
          } catch (e) {
            console.log('Regression data not available for chat context');
          }

          // Only set ML context if we have at least one piece of data
          if (mlData.prediction || mlData.regression) {
            setMlContext(mlData);
          }
        }
      } catch (e) {
        console.error('Failed to load machine context:', e);
      } finally {
        setContextLoading(false);
      }
    }

    loadContext();
  }, [machine.id, topicPaths.join(',')]);

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

    setIsRagLoading(true);
    let ragContext: RAGContext | null = null;

    try {
      const ragResults = await searchSimilarTopics(userMessage, 20);
      ragContext = {
        query: userMessage,
        similar_topics: ragResults.results,
      };
    } catch (e) {
      console.error('RAG search failed:', e);
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
      const request = buildChatRequest(
        machine,
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
  }, [machine, historicalContext, mlContext, messages, isLoading]);

  const handleClear = useCallback(() => {
    setMessages([]);
    if (machine.id) {
      sessionStorage.removeItem(storageKey);
    }
    setError(null);
  }, [machine.id, storageKey]);

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

          {/* Chat icon */}
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>

          {/* Unread indicator when closed and has messages */}
          {!isOpen && messages.length > 0 && (
            <span className="absolute top-4 right-2 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
          )}
        </button>

        {/* Chat panel */}
        <div className="w-[50vw] h-full bg-gray-800 border-l border-gray-700 flex flex-col shadow-2xl">
          {/* Header */}
          <div className="flex-shrink-0 px-4 py-3 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-100">Machine Assistant</h3>
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
                       : 'Ask questions about this machine';
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
                <p className="text-xs mt-1 text-center px-4">Ask a question about {machine.name}</p>
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
                  ? 'Loading machine context...'
                  : 'Ask a question...'
              }
            />
          </div>
        </div>
      </div>
    </>
  );
}
