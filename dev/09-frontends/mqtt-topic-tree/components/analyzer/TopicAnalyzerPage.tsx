'use client';

import { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import TopicSelector from './TopicSelector';
import TransformedMachineView from './TransformedMachineView';
import type { ViewTransform, TopicStructure, GenerateTransformResponse } from '@/app/api/view-transform/route';

// Selected topic info passed from TopicSelector
export interface SelectedTopicInfo {
  topicPath: string;
  payload: Record<string, unknown>;
  numericFields: string[];
  timestamp?: string;
  isAggregated?: boolean;
  childTopics?: string[];
  messageCount?: number;
}

type TransformState =
  | { status: 'idle' }
  | { status: 'loading'; message: string }
  | { status: 'ready'; transform: ViewTransform; cached: boolean }
  | { status: 'error'; message: string };

export default function TopicAnalyzerPage() {
  const [selectedTopic, setSelectedTopic] = useState<SelectedTopicInfo | null>(null);
  const [transformState, setTransformState] = useState<TransformState>({ status: 'idle' });
  const [isStreaming, setIsStreaming] = useState(false);

  // Generate or fetch transform when topic is selected
  useEffect(() => {
    if (!selectedTopic) {
      setTransformState({ status: 'idle' });
      return;
    }

    const generateTransform = async () => {
      setTransformState({ status: 'loading', message: 'Checking for existing transform...' });

      try {
        // Build the topic structure for transform generation
        const topicStructure: TopicStructure = {
          topicPath: selectedTopic.topicPath,
          isAggregated: selectedTopic.isAggregated || false,
          payload: selectedTopic.payload,
          numericFields: selectedTopic.numericFields,
          childTopics: selectedTopic.childTopics,
        };

        // If aggregated, include child payloads
        if (selectedTopic.isAggregated && selectedTopic.childTopics) {
          const childPayloads: Record<string, Record<string, unknown>> = {};
          for (const childPath of selectedTopic.childTopics) {
            const childName = childPath.split('/').pop() || childPath;
            // Extract fields for this child from the merged payload
            const childPayload: Record<string, unknown> = {};
            for (const [key, value] of Object.entries(selectedTopic.payload)) {
              if (key.startsWith(`${childName}.`)) {
                const fieldName = key.slice(childName.length + 1);
                childPayload[fieldName] = value;
              }
            }
            if (Object.keys(childPayload).length > 0) {
              childPayloads[childPath] = childPayload;
            }
          }
          topicStructure.childPayloads = childPayloads;
        }

        setTransformState({ status: 'loading', message: 'Generating view transform with AI...' });

        const response = await fetch('/api/view-transform', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topicStructure }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.details || error.error || 'Failed to generate transform');
        }

        const result: GenerateTransformResponse = await response.json();
        setTransformState({
          status: 'ready',
          transform: result.transform,
          cached: result.cached,
        });
      } catch (error) {
        console.error('Transform generation failed:', error);
        setTransformState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Unknown error',
        });
      }
    };

    generateTransform();
  }, [selectedTopic]);

  const handleTopicSelect = useCallback((topic: SelectedTopicInfo) => {
    setSelectedTopic(topic);
  }, []);

  const handleStreamingChange = useCallback((streaming: boolean) => {
    setIsStreaming(streaming);
  }, []);

  const handleRegenerateTransform = useCallback(async () => {
    if (!selectedTopic) return;

    setTransformState({ status: 'loading', message: 'Regenerating transform with AI...' });

    try {
      const topicStructure: TopicStructure = {
        topicPath: selectedTopic.topicPath,
        isAggregated: selectedTopic.isAggregated || false,
        payload: selectedTopic.payload,
        numericFields: selectedTopic.numericFields,
        childTopics: selectedTopic.childTopics,
      };

      const response = await fetch('/api/view-transform?force=true', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topicStructure }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.details || error.error || 'Failed to regenerate transform');
      }

      const result: GenerateTransformResponse = await response.json();
      setTransformState({
        status: 'ready',
        transform: result.transform,
        cached: false,
      });
    } catch (error) {
      console.error('Transform regeneration failed:', error);
      setTransformState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }, [selectedTopic]);

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/"
                className="text-gray-400 hover:text-gray-200 flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Dashboard
              </Link>

              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-gray-100">Unified Data Layer</h1>
                  {transformState.status === 'ready' && (
                    <div className="flex items-center gap-1.5 bg-blue-900/50 px-2 py-1 rounded-full">
                      <svg className="w-3 h-3 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span className="text-xs text-blue-300">
                        {transformState.cached ? 'Cached Transform' : 'AI Transform'}
                      </span>
                    </div>
                  )}
                  {isStreaming && (
                    <div className="flex items-center gap-1.5 bg-green-900/50 px-2 py-1 rounded-full">
                      <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                      <span className="text-xs text-green-300">Live</span>
                    </div>
                  )}
                </div>
                {selectedTopic && (
                  <p className="text-sm text-gray-400 mt-1 font-mono">{selectedTopic.topicPath}</p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Telemetry link */}
              <Link
                href="/telemetry"
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 hover:text-gray-100 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Telemetry
              </Link>

              {/* Regenerate button */}
              {transformState.status === 'ready' && (
                <button
                  onClick={handleRegenerateTransform}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 hover:text-gray-100 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Regenerate
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Topic Selector */}
        <div className="mb-6">
          <TopicSelector onSelect={handleTopicSelect} selectedTopic={selectedTopic?.topicPath} />
        </div>

        {/* Content based on state */}
        {transformState.status === 'idle' && (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-xl font-semibold text-gray-300 mb-2">Select an ML-Ready Topic</h3>
            <p className="text-gray-500">
              Choose a topic with 20+ messages from the tree above for time series prediction and regression analysis.
            </p>
            <p className="text-gray-500 mt-2 text-sm">
              For topics with fewer messages, use the <Link href="/telemetry" className="text-purple-400 hover:text-purple-300">Telemetry Viewer</Link>.
            </p>
          </div>
        )}

        {transformState.status === 'loading' && (
          <div className="bg-gray-800 rounded-lg border border-gray-700 p-12 text-center">
            <div className="relative w-16 h-16 mx-auto mb-4">
              <div className="absolute inset-0 rounded-full border-4 border-gray-700"></div>
              <div className="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div>
              <svg className="absolute inset-3 w-10 h-10 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold text-gray-300 mb-2">Generating View Transform</h3>
            <p className="text-gray-500">{transformState.message}</p>
          </div>
        )}

        {transformState.status === 'error' && (
          <div className="bg-gray-800 rounded-lg border border-red-900 p-12 text-center">
            <svg className="w-16 h-16 mx-auto mb-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3 className="text-xl font-semibold text-red-400 mb-2">Transform Generation Failed</h3>
            <p className="text-gray-400 mb-4">{transformState.message}</p>
            <button
              onClick={() => selectedTopic && handleTopicSelect(selectedTopic)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
            >
              Try Again
            </button>
          </div>
        )}

        {transformState.status === 'ready' && selectedTopic && (
          <TransformedMachineView
            transform={transformState.transform}
            topicPath={selectedTopic.topicPath}
            isAggregated={selectedTopic.isAggregated}
            childTopics={selectedTopic.childTopics}
            onStreamingChange={handleStreamingChange}
            messageCount={selectedTopic.messageCount}
          />
        )}
      </main>
    </div>
  );
}
