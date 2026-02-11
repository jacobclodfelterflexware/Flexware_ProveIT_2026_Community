'use client';

import { memo } from 'react';
import type { ChatMessage as ChatMessageType } from '@/types/chat';

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

/**
 * Individual chat message bubble component
 */
function ChatMessageComponent({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}
    >
      <div
        className={`max-w-[80%] px-4 py-2.5 rounded-lg ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-700 text-gray-100'
        }`}
      >
        {/* Role label for assistant */}
        {isAssistant && (
          <div className="text-xs text-gray-400 mb-1 font-medium">
            Assistant
          </div>
        )}

        {/* Message content with markdown-like styling */}
        <div className="text-sm whitespace-pre-wrap break-words prose prose-invert prose-sm max-w-none">
          {message.content}
          {isStreaming && isAssistant && (
            <span className="inline-block w-2 h-4 ml-0.5 bg-gray-400 animate-pulse" />
          )}
        </div>

        {/* Timestamp if available */}
        {message.timestamp && (
          <div className={`text-xs mt-1.5 ${isUser ? 'text-blue-200' : 'text-gray-500'}`}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(ChatMessageComponent);
