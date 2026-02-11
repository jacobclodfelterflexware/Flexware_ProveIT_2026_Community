'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage, RAGContext } from '@/types/chat';
import type { GraphSummary } from '@/types/knowledge-base';
import type { ProveITGPTChat } from '@/types/proveitgpt-chat';
import { searchSimilarTopics } from '@/lib/chat-api';
import { fetchGraphSummary, streamKBChat, buildKBChatRequest } from '@/lib/knowledge-base-api';
import {
  fetchChatList,
  createChat,
  fetchChat,
  deleteChat,
  addMessage,
  updateMessage,
  deriveChatTitle,
} from '@/lib/proveitgpt-chat-api';
import ChatMessageComponent from '@/components/machines/chat/ChatMessage';
import RAGSourcesIndicator from '@/components/machines/chat/RAGSourcesIndicator';
import ChatHistorySidebar from '@/components/proveitgpt/ChatHistorySidebar';

const SUGGESTED_PROMPTS = [
  {
    title: 'Explore topics',
    prompt: 'What MQTT topics exist in the knowledge graph? Give me an overview of the topic hierarchy.',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    title: 'Find patterns',
    prompt: 'What data patterns and sensor types are most common across the system?',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
      </svg>
    ),
  },
  {
    title: 'Search by topic',
    prompt: 'Show me topics related to temperature monitoring and their recent data.',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    title: 'Schema mappings',
    prompt: 'What schema mappings have been created? Show me the relationship between raw and curated topics.',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
      </svg>
    ),
  },
];

export default function ProveITGPTPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [graphSummary, setGraphSummary] = useState<GraphSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [input, setInput] = useState('');

  // Chat persistence state
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [chatList, setChatList] = useState<ProveITGPTChat[]>([]);
  const [chatListLoading, setChatListLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load graph summary on mount
  useEffect(() => {
    async function loadSummary() {
      try {
        const summary = await fetchGraphSummary();
        setGraphSummary(summary);
      } catch (e) {
        console.error('Failed to load graph summary:', e);
      } finally {
        setSummaryLoading(false);
      }
    }
    loadSummary();
  }, []);

  // Load chat list on mount
  useEffect(() => {
    async function loadChats() {
      try {
        const result = await fetchChatList();
        setChatList(result.chats);
      } catch (e) {
        console.error('Failed to load chat list:', e);
      } finally {
        setChatListLoading(false);
      }
    }
    loadChats();
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const handleSend = useCallback(async (userMessage: string) => {
    if (!userMessage.trim() || isLoading) return;

    const timestamp = new Date().toISOString();
    const userChatMessage: ChatMessage = {
      role: 'user',
      content: userMessage,
      timestamp,
    };
    setMessages(prev => [...prev, userChatMessage]);
    setError(null);
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Create or reuse chat in Neo4j
    let chatId = activeChatId;
    if (!chatId) {
      try {
        const title = deriveChatTitle(userMessage);
        const result = await createChat(title);
        chatId = result.id;
        setActiveChatId(chatId);
        setChatList(prev => [{
          id: chatId!,
          title,
          createdAt: timestamp,
          updatedAt: timestamp,
          messageCount: 0,
        }, ...prev]);
      } catch (e) {
        console.error('Failed to create chat:', e);
      }
    }

    // Persist user message
    if (chatId) {
      addMessage(chatId, { role: 'user', content: userMessage, timestamp })
        .catch(e => console.error('Failed to persist user message:', e));
    }

    // Perform RAG similarity search
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

    const assistantTimestamp = new Date().toISOString();
    const assistantMessage: ChatMessage = {
      role: 'assistant',
      content: '',
      timestamp: assistantTimestamp,
    };
    setMessages(prev => [...prev, assistantMessage]);

    // Persist assistant placeholder and get its ID
    let assistantMsgId: string | null = null;
    if (chatId) {
      try {
        const result = await addMessage(chatId, { role: 'assistant', content: '', timestamp: assistantTimestamp });
        assistantMsgId = result.messageId;
      } catch (e) {
        console.error('Failed to persist assistant placeholder:', e);
      }
    }

    let fullContent = '';
    try {
      const request = buildKBChatRequest(
        graphSummary,
        ragContext,
        messages,
        userMessage,
      );

      for await (const chunk of streamKBChat(request)) {
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
      fullContent = `Error: ${errorMessage}`;
      setMessages(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...updated[updated.length - 1],
          content: fullContent,
        };
        return updated;
      });
    } finally {
      setIsLoading(false);

      // Persist final assistant content
      if (chatId && assistantMsgId && fullContent) {
        updateMessage(chatId, assistantMsgId, fullContent)
          .catch(e => console.error('Failed to update assistant message:', e));
      }

      // Move chat to top of list
      if (chatId) {
        setChatList(prev => {
          const idx = prev.findIndex(c => c.id === chatId);
          if (idx <= 0) return prev;
          const chat = { ...prev[idx], updatedAt: new Date().toISOString() };
          return [chat, ...prev.filter(c => c.id !== chatId)];
        });
      }
    }
  }, [graphSummary, messages, isLoading, activeChatId]);

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setActiveChatId(null);
    setError(null);
  }, []);

  const handleSelectChat = useCallback(async (chatId: string) => {
    if (chatId === activeChatId) return;
    try {
      const result = await fetchChat(chatId);
      setActiveChatId(chatId);
      setMessages(result.messages.map(m => ({
        role: m.role as 'user' | 'assistant' | 'system',
        content: m.content,
        timestamp: m.timestamp,
      })));
      setError(null);
    } catch (e) {
      console.error('Failed to load chat:', e);
      setError('Failed to load chat');
    }
  }, [activeChatId]);

  const handleDeleteChat = useCallback(async (chatId: string) => {
    try {
      await deleteChat(chatId);
      setChatList(prev => prev.filter(c => c.id !== chatId));
      if (chatId === activeChatId) {
        setMessages([]);
        setActiveChatId(null);
      }
    } catch (e) {
      console.error('Failed to delete chat:', e);
    }
  }, [activeChatId]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend(input);
      }
    },
    [handleSend, input]
  );

  const hasMessages = messages.length > 0;

  // Format summary stats for display
  const summaryText = graphSummary
    ? `Connected to ${graphSummary.topics.total.toLocaleString()} topics and ${graphSummary.messages.total.toLocaleString()} messages`
    : summaryLoading
    ? 'Connecting to knowledge graph...'
    : 'Knowledge graph available';

  return (
    <div className="h-screen bg-gray-900 flex flex-col">
      {/* Header bar — spans full width above sidebar + content */}
      <div className="flex-shrink-0 border-b border-gray-700/50 bg-gray-900/80 backdrop-blur-sm">
        <div className="px-4 py-2 flex items-center justify-center relative">
          {/* Sidebar toggle (mobile) — left-aligned */}
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden absolute left-4 flex items-center text-gray-400 hover:text-gray-200 p-1.5 rounded-lg hover:bg-gray-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>

          {/* Centered header content */}
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-gray-100">ProveITGPT</span>
            <span className="text-xs text-gray-500 hidden sm:inline">|</span>
            <span className="text-xs text-gray-500 hidden sm:inline">{summaryText}</span>
          </div>

          {/* New chat button — right-aligned */}
          {hasMessages && (
            <button
              onClick={handleNewChat}
              className="absolute right-4 flex items-center gap-1.5 text-xs text-emerald-400/70 hover:text-emerald-300 px-2.5 py-1.5 rounded-lg hover:bg-emerald-500/10 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              New chat
            </button>
          )}
        </div>
      </div>

      {/* Sidebar + Main content row — below header */}
      <div className="flex-1 flex min-h-0">
        {/* Chat History Sidebar */}
        <ChatHistorySidebar
          chats={chatList}
          activeChatId={activeChatId}
          onSelectChat={handleSelectChat}
          onNewChat={handleNewChat}
          onDeleteChat={handleDeleteChat}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        {/* Main content area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Main chat area */}
        <div className="flex-1 overflow-y-auto">
          {!hasMessages ? (
            /* Empty state — ChatGPT-style welcome */
            <div className="h-full flex flex-col items-center justify-center px-4 lg:-ml-64">
              <div className="max-w-2xl w-full text-center mb-8">
                {/* Logo */}
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-emerald-500/20">
                  <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
                  </svg>
                </div>

                <h1 className="text-3xl font-semibold text-gray-100 mb-2">ProveITGPT</h1>
                <p className="text-gray-400 text-base">
                  Ask anything about your IoT knowledge graph
                </p>

                {/* Graph stats */}
                {graphSummary && (
                  <p className="text-xs text-gray-600 mt-2">
                    {graphSummary.topics.total.toLocaleString()} topics &middot; {graphSummary.messages.total.toLocaleString()} messages &middot; {graphSummary.topSegments.length} top-level segments
                  </p>
                )}
              </div>

              {/* Suggested prompts — 2x2 grid */}
              <div className="grid grid-cols-2 gap-3 max-w-2xl w-full px-4">
                {SUGGESTED_PROMPTS.map((item) => (
                  <button
                    key={item.title}
                    onClick={() => handleSend(item.prompt)}
                    disabled={isLoading || summaryLoading}
                    className="text-left p-4 rounded-xl border border-gray-700/50 hover:border-gray-600 hover:bg-gray-800/50 transition-all group disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <div className="flex items-start gap-3">
                      <div className="text-gray-500 group-hover:text-gray-300 transition-colors mt-0.5">
                        {item.icon}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-200 group-hover:text-gray-100 transition-colors">
                          {item.title}
                        </p>
                        <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                          {item.prompt}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Message list */
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-1">
              {messages.map((msg, idx) => (
                <ChatMessageComponent
                  key={idx}
                  message={msg}
                  isStreaming={isLoading && idx === messages.length - 1 && msg.role === 'assistant'}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Error display */}
        {error && (
          <div className="max-w-3xl mx-auto w-full px-4 mb-2">
            <div className="px-4 py-2 bg-red-900/30 border border-red-800/50 rounded-xl">
              <p className="text-sm text-red-300">{error}</p>
            </div>
          </div>
        )}

        {/* RAG loading indicator */}
        <div className="max-w-3xl mx-auto w-full px-4">
          <RAGSourcesIndicator visible={isRagLoading} />
        </div>

        {/* Input area — fixed at bottom */}
        <div className="flex-shrink-0 pb-4 pt-2 bg-gradient-to-t from-gray-900 via-gray-900 to-transparent">
          <div className="max-w-3xl mx-auto px-4">
            <div className="relative flex items-end bg-gray-800 border border-gray-600 rounded-2xl shadow-lg focus-within:border-gray-500 focus-within:ring-1 focus-within:ring-gray-500 transition-all">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading || isRagLoading}
                placeholder="Message ProveITGPT..."
                rows={1}
                className="flex-1 resize-none px-4 py-3.5 bg-transparent text-gray-100 text-sm placeholder-gray-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-[200px]"
              />
              <button
                onClick={() => handleSend(input)}
                disabled={isLoading || isRagLoading || !input.trim()}
                className={`flex-shrink-0 m-1.5 p-2 rounded-xl transition-all ${
                  isLoading || isRagLoading || !input.trim()
                    ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                    : 'bg-white text-gray-900 hover:bg-gray-200'
                }`}
              >
                {isLoading ? (
                  <div className="w-5 h-5 border-2 border-gray-500 border-t-gray-300 rounded-full animate-spin" />
                ) : (
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18" />
                  </svg>
                )}
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">
              ProveITGPT uses Neo4j vector similarity search to find relevant data for each question.
            </p>
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
