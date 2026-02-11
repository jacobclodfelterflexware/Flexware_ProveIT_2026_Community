'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import DynamicChart from './DynamicChart';
import TopicBrowserSidebar, { type ChartHistoryItem } from './TopicBrowserSidebar';
import ChartSuggestions from './ChartSuggestions';
import {
  generateChart,
  listSkills,
  type ChartGenerateResponse,
  type SkillInfo,
  type RAGContext,
} from '@/lib/chart-engine-api';

export default function ChartPage() {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentChart, setCurrentChart] = useState<ChartGenerateResponse | null>(null);
  const [history, setHistory] = useState<ChartHistoryItem[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load skills on mount
  useEffect(() => {
    listSkills()
      .then(setSkills)
      .catch((err) => console.error('Failed to load skills:', err));
  }, []);

  // Handle form submission
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await generateChart({
        query: query.trim(),
        preferences: {
          time_window: '1h',
          max_series: 10,
        },
      });

      setCurrentChart(response);
      setHistory((prev) => [
        {
          id: response.chart_id,
          query: query.trim(),
          response,
          timestamp: new Date(),
        },
        ...prev.slice(0, 9), // Keep last 10
      ]);
      setQuery('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate chart');
    } finally {
      setIsLoading(false);
    }
  }, [query, isLoading]);

  // Load chart from history
  const loadFromHistory = useCallback((item: ChartHistoryItem) => {
    setCurrentChart(item.response);
    setError(null);
  }, []);

  // Handle topic selection from browser — fills query input
  const handleTopicSelect = useCallback((queryText: string, _topicPath: string) => {
    setQuery(queryText);
    inputRef.current?.focus();
  }, []);

  // Handle suggestion selection — fills query and auto-submits
  const handleSuggestionSelect = useCallback(async (queryText: string) => {
    if (isLoading) return;
    setQuery(queryText);
    setIsLoading(true);
    setError(null);
    try {
      const response = await generateChart({
        query: queryText.trim(),
        preferences: { time_window: '1h', max_series: 10 },
      });
      setCurrentChart(response);
      setHistory((prev) => [
        { id: response.chart_id, query: queryText.trim(), response, timestamp: new Date() },
        ...prev.slice(0, 9),
      ]);
      setQuery('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate chart');
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  return (
    <div className="h-screen flex flex-col bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white">Chart Generator</h1>
            <p className="text-sm text-gray-400 mt-1">
              Describe the chart you want in natural language
            </p>
          </div>
        </div>

        {/* Query input */}
        <form onSubmit={handleSubmit} className="mt-4">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Show temperature trends for all machines in Line 3"
              className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Generating...
                </span>
              ) : (
                'Generate Chart'
              )}
            </button>
          </div>
        </form>

        {/* Error display */}
        {error && (
          <div className="mt-3 px-4 py-3 bg-red-900/50 border border-red-700 rounded-lg text-red-200 text-sm">
            {error}
          </div>
        )}
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Topic Browser Sidebar */}
        <TopicBrowserSidebar
          history={history}
          currentChartId={currentChart?.chart_id ?? null}
          skills={skills}
          onLoadHistory={loadFromHistory}
          onSelectTopic={handleTopicSelect}
          onSelectSuggestion={handleSuggestionSelect}
        />

        {/* Chart canvas */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {currentChart ? (
            <div className="flex-1 p-6 flex flex-col">
              {/* Chart info bar */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-sm px-3 py-1 bg-blue-900/50 text-blue-300 rounded-full">
                    {currentChart.skill_used}
                  </span>
                </div>
                <div className="text-sm text-gray-400">
                  Chart ID: {currentChart.chart_id.slice(0, 8)}...
                </div>
              </div>

              {/* Reasoning */}
              {currentChart.reasoning && (
                <div className="mb-4 px-4 py-3 bg-gray-800 rounded-lg border border-gray-700">
                  <p className="text-sm text-gray-300">
                    <span className="text-gray-500">AI: </span>
                    {currentChart.reasoning}
                  </p>
                </div>
              )}

              {/* Selected Data Info Panel */}
              {currentChart.parameters_used && (
                <div className="mb-4 px-4 py-3 bg-gray-800/50 rounded-lg border border-gray-700">
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                    <div>
                      <span className="text-gray-500">Topics: </span>
                      <span className="text-cyan-400 font-mono text-xs">
                        {currentChart.parameters_used.topics?.join(', ') ||
                         currentChart.parameters_used.topic ||
                         'None'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Fields: </span>
                      <span className="text-green-400 font-mono text-xs">
                        {currentChart.parameters_used.fields?.join(', ') ||
                         currentChart.parameters_used.field ||
                         'value'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Window: </span>
                      <span className="text-yellow-400">
                        {currentChart.parameters_used.window || '1h'}
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-500">Records: </span>
                      <span className={currentChart.initial_data?.records > 0 ? 'text-green-400' : 'text-red-400'}>
                        {currentChart.initial_data?.records ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Chart */}
              <div className="flex-1 bg-gray-800 rounded-lg p-4 border border-gray-700 relative">
                {/* No Data Warning Overlay */}
                {currentChart.initial_data?.records === 0 && (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 rounded-lg z-10">
                    <div className="text-center p-6">
                      <svg className="w-12 h-12 mx-auto mb-3 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                      </svg>
                      <p className="text-yellow-400 text-lg mb-2">No data found</p>
                      <p className="text-gray-500 text-sm max-w-sm">
                        No messages found for topic &quot;{currentChart.parameters_used?.topics?.[0] || currentChart.parameters_used?.topic || 'unknown'}&quot;
                        {' '}in the last {currentChart.parameters_used?.window || '1h'}
                      </p>
                    </div>
                  </div>
                )}
                <DynamicChart
                  chartId={currentChart.chart_id}
                  config={currentChart.chart_config}
                  streamUrl={currentChart.stream_url}
                  onError={(err) => setError(err)}
                />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center max-w-lg">
                <svg
                  className="w-16 h-16 mx-auto mb-4 text-gray-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <h2 className="text-xl font-medium text-gray-400 mb-2">
                  No chart yet
                </h2>
                <p className="text-sm text-gray-500 mb-6">
                  Type a query above, browse topics in the sidebar, or try a suggestion:
                </p>

                {/* Quick-start suggestions */}
                <div className="text-left">
                  <ChartSuggestions
                    skills={skills}
                    onSelectSuggestion={handleSuggestionSelect}
                  />
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
