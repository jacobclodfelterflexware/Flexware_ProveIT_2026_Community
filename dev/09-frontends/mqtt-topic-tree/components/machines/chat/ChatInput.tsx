'use client';

import { useState, useCallback, KeyboardEvent, useRef, useEffect } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * Chat input component with send button
 */
export default function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Ask a question about this machine...',
}: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (trimmed && !disabled) {
      onSend(trimmed);
      setInput('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  }, [input, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Submit on Enter (without Shift)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div className="flex items-end gap-2 p-3 border-t border-gray-700 bg-gray-800/50">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        className={`
          flex-1 resize-none px-3 py-2
          bg-gray-900 border border-gray-600 rounded-lg
          text-gray-100 text-sm placeholder-gray-500
          focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500
          disabled:opacity-50 disabled:cursor-not-allowed
          transition-colors
        `}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !input.trim()}
        className={`
          px-4 py-2 rounded-lg font-medium text-sm
          transition-colors flex items-center gap-2
          ${
            disabled || !input.trim()
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }
        `}
      >
        {disabled ? (
          <>
            <div className="w-4 h-4 border-2 border-gray-500 border-t-white rounded-full animate-spin" />
            <span className="sr-only">Sending...</span>
          </>
        ) : (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
            <span className="hidden sm:inline">Send</span>
          </>
        )}
      </button>
    </div>
  );
}
