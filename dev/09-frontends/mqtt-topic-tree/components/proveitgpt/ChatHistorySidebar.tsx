'use client';

import { useState, useMemo } from 'react';
import { isToday, isYesterday, differenceInDays } from 'date-fns';
import type { ProveITGPTChat } from '@/types/proveitgpt-chat';

interface ChatHistorySidebarProps {
  chats: ProveITGPTChat[];
  activeChatId: string | null;
  onSelectChat: (chatId: string) => void;
  onNewChat: () => void;
  onDeleteChat: (chatId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

const DATE_GROUP_ORDER = ['Today', 'Yesterday', 'Previous 7 days', 'Older'];

function groupChatsByDate(chats: ProveITGPTChat[]): Record<string, ProveITGPTChat[]> {
  const groups: Record<string, ProveITGPTChat[]> = {};
  const now = new Date();

  for (const chat of chats) {
    const date = new Date(chat.updatedAt);
    let label: string;

    if (isToday(date)) label = 'Today';
    else if (isYesterday(date)) label = 'Yesterday';
    else if (differenceInDays(now, date) <= 7) label = 'Previous 7 days';
    else label = 'Older';

    if (!groups[label]) groups[label] = [];
    groups[label].push(chat);
  }

  return groups;
}

export default function ChatHistorySidebar({
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
  isOpen,
  onClose,
}: ChatHistorySidebarProps) {
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const grouped = useMemo(() => groupChatsByDate(chats), [chats]);

  const handleDelete = (chatId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmDeleteId === chatId) {
      onDeleteChat(chatId);
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(chatId);
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed lg:relative inset-y-0 left-0 z-40
          transform transition-transform duration-200 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0
          w-64 bg-[#161b22] border-r border-gray-700/50 flex flex-col h-full flex-shrink-0
        `}
      >
        {/* Chat list with New Chat button at top */}
        <div className="flex-1 overflow-y-auto px-2 pt-3 pb-2">
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="w-full flex items-center gap-2 px-2.5 py-2 mb-2 rounded-lg bg-gradient-to-r from-emerald-500/15 to-cyan-500/15 border border-emerald-500/25 hover:border-emerald-400/40 hover:from-emerald-500/25 hover:to-cyan-500/25 text-emerald-300 hover:text-emerald-200 transition-all text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
            New chat
          </button>
          {chats.length === 0 ? (
            <div className="text-center py-8">
              <svg className="w-5 h-5 text-gray-600 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              </svg>
              <p className="text-xs text-gray-500">No chat history yet</p>
            </div>
          ) : (
            DATE_GROUP_ORDER.map(groupLabel => {
              const groupChats = grouped[groupLabel];
              if (!groupChats || groupChats.length === 0) return null;

              return (
                <div key={groupLabel} className="mb-3">
                  <p className="text-[11px] font-medium text-gray-500/70 px-2 py-1.5 uppercase tracking-wider">
                    {groupLabel}
                  </p>
                  {groupChats.map(chat => (
                    <button
                      key={chat.id}
                      onClick={() => {
                        onSelectChat(chat.id);
                        onClose();
                      }}
                      className={`
                        w-full text-left px-2.5 py-2 rounded-lg text-sm transition-colors group relative
                        ${chat.id === activeChatId
                          ? 'bg-gray-800/60 text-gray-100'
                          : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
                        }
                      `}
                    >
                      <span className="block truncate pr-6">{chat.title}</span>

                      {/* Delete button */}
                      <span
                        onClick={(e) => handleDelete(chat.id, e)}
                        className={`
                          absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded
                          transition-opacity
                          ${confirmDeleteId === chat.id
                            ? 'opacity-100 text-red-400 hover:text-red-300'
                            : 'opacity-0 group-hover:opacity-100 text-gray-500 hover:text-gray-300'
                          }
                        `}
                        title={confirmDeleteId === chat.id ? 'Click again to confirm' : 'Delete chat'}
                      >
                        {confirmDeleteId === chat.id ? (
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        ) : (
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                          </svg>
                        )}
                      </span>
                    </button>
                  ))}
                </div>
              );
            })
          )}
        </div>
      </aside>
    </>
  );
}
