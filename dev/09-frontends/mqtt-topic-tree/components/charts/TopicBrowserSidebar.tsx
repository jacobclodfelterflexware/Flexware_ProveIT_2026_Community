'use client';

import { useState } from 'react';
import ChartTopicBrowser from './ChartTopicBrowser';
import ChartSuggestions from './ChartSuggestions';
import type { ChartGenerateResponse, SkillInfo } from '@/lib/chart-engine-api';

interface ChartHistoryItem {
  id: string;
  query: string;
  response: ChartGenerateResponse;
  timestamp: Date;
}

interface TopicBrowserSidebarProps {
  history: ChartHistoryItem[];
  currentChartId: string | null;
  skills: SkillInfo[];
  onLoadHistory: (item: ChartHistoryItem) => void;
  onSelectTopic: (query: string, topicPath: string) => void;
  onSelectSuggestion: (query: string) => void;
}

type TabId = 'history' | 'browse' | 'suggestions';

export type { ChartHistoryItem };

export default function TopicBrowserSidebar({
  history,
  currentChartId,
  skills,
  onLoadHistory,
  onSelectTopic,
  onSelectSuggestion,
}: TopicBrowserSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabId>(
    history.length > 0 ? 'history' : 'suggestions'
  );

  const tabs: { id: TabId; label: string }[] = [
    { id: 'history', label: 'History' },
    { id: 'browse', label: 'Browse' },
    { id: 'suggestions', label: 'Suggest' },
  ];

  return (
    <aside className="w-72 bg-gray-800 border-r border-gray-700 flex flex-col">
      {/* Tab bar */}
      <div className="flex border-b border-gray-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-2 py-2.5 text-xs font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-white border-b-2 border-blue-500 bg-gray-700/30'
                : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/20'
            }`}
          >
            {tab.label}
            {tab.id === 'history' && history.length > 0 && (
              <span className="ml-1 text-gray-500">({history.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {/* History tab */}
        {activeTab === 'history' && (
          <div className="p-2">
            {history.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">
                No charts generated yet
              </p>
            ) : (
              <div className="space-y-2">
                {history.map((item) => (
                  <button
                    key={item.id}
                    onClick={() => onLoadHistory(item)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      currentChartId === item.id
                        ? 'bg-blue-900/50 border border-blue-700'
                        : 'bg-gray-700/50 hover:bg-gray-700 border border-transparent'
                    }`}
                  >
                    <p className="text-sm text-gray-200 truncate">{item.query}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 bg-gray-600 rounded text-gray-300">
                        {item.response.skill_used}
                      </span>
                      <span className="text-xs text-gray-500">
                        {item.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Browse tab */}
        {activeTab === 'browse' && (
          <ChartTopicBrowser onSelectTopic={onSelectTopic} />
        )}

        {/* Suggestions tab */}
        {activeTab === 'suggestions' && (
          <ChartSuggestions
            skills={skills}
            onSelectSuggestion={onSelectSuggestion}
          />
        )}
      </div>
    </aside>
  );
}
