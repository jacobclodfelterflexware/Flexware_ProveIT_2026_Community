'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import type { SimilarResult } from '@/types/machines';

// Dynamic import of GraphVisualization to avoid SSR issues
const GraphVisualization = dynamic(
  () => import('../machines/GraphVisualization'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-400 text-sm">Loading 3D visualization...</p>
        </div>
      </div>
    ),
  }
);

const CYCLE_INTERVAL_MS = 15000; // 15 seconds

interface DashboardGraphVisualizationProps {
  className?: string;
}

export default function DashboardGraphVisualization({ className }: DashboardGraphVisualizationProps) {
  const [currentTopic, setCurrentTopic] = useState<{ path: string; payload: string } | null>(null);
  const [similarResults, setSimilarResults] = useState<SimilarResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [cycleCount, setCycleCount] = useState(0);
  const [countdown, setCountdown] = useState(CYCLE_INTERVAL_MS / 1000);
  const [error, setError] = useState<string | null>(null);

  // Countdown timer effect
  useEffect(() => {
    const countdownInterval = setInterval(() => {
      setCountdown((prev) => (prev <= 1 ? CYCLE_INTERVAL_MS / 1000 : prev - 1));
    }, 1000);

    return () => clearInterval(countdownInterval);
  }, []);

  // Reset countdown when cycle completes
  useEffect(() => {
    setCountdown(CYCLE_INTERVAL_MS / 1000);
  }, [cycleCount]);

  // Main cycle logic
  const runCycle = useCallback(async () => {
    setIsSearching(true);
    setError(null);

    try {
      // Step 1: Get random topic with payload
      const topicRes = await fetch('/api/graph/random-topic');
      if (!topicRes.ok) {
        const errorData = await topicRes.json();
        throw new Error(errorData.error || 'Failed to get random topic');
      }
      const topic = await topicRes.json();

      setCurrentTopic({ path: topic.topic_path, payload: topic.payload });

      // Step 2: Perform similarity search using the payload
      const searchRes = await fetch(
        `/api/graph/similar-search?q=${encodeURIComponent(topic.payload)}&k=10`
      );
      if (!searchRes.ok) {
        const errorData = await searchRes.json();
        throw new Error(errorData.error || 'Similarity search failed');
      }
      const searchData = await searchRes.json();

      setSimilarResults(searchData.results || []);
      setCycleCount((prev) => prev + 1);
    } catch (err) {
      console.error('[DashboardGraph] Cycle error:', err);
      setError((err as Error).message);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Main cycle effect
  useEffect(() => {
    let isMounted = true;

    const runIfMounted = async () => {
      if (isMounted) {
        await runCycle();
      }
    };

    // Run immediately
    runIfMounted();

    // Then run every 15 seconds
    const interval = setInterval(() => {
      if (isMounted) {
        runIfMounted();
      }
    }, CYCLE_INTERVAL_MS);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [runCycle]);

  return (
    <div className={`relative overflow-hidden ${className || ''}`}>
      {/* Status overlay - top right */}
      <div className="absolute top-4 right-4 z-20 bg-gray-900/95 backdrop-blur-sm px-4 py-3 rounded-lg border border-gray-700 shadow-xl">
        <div className="flex items-center gap-4">
          {/* Cycle info */}
          <div className="text-sm">
            <span className="text-gray-400">Cycle</span>
            <span className="ml-2 font-mono text-white">#{cycleCount}</span>
          </div>

          {/* Divider */}
          <div className="w-px h-6 bg-gray-700"></div>

          {/* Countdown */}
          <div className="text-sm">
            <span className="text-gray-400">Next in</span>
            <span className="ml-2 font-mono text-cyan-400">{countdown}s</span>
          </div>

          {/* Search status indicator */}
          {isSearching && (
            <>
              <div className="w-px h-6 bg-gray-700"></div>
              <div className="flex items-center gap-2 text-blue-400">
                <div className="animate-spin rounded-full h-3 w-3 border-t-2 border-b-2 border-blue-400"></div>
                <span className="text-sm">Searching</span>
              </div>
            </>
          )}
        </div>

        {/* Current topic */}
        {currentTopic && (
          <div className="mt-2 pt-2 border-t border-gray-700">
            <div className="text-xs text-gray-500 mb-1">Current Topic</div>
            <div className="text-sm text-cyan-300 font-mono truncate max-w-md" title={currentTopic.path}>
              {currentTopic.path}
            </div>
          </div>
        )}
      </div>

      {/* Error overlay */}
      {error && (
        <div className="absolute top-4 left-4 z-20 bg-red-900/90 backdrop-blur-sm px-4 py-2 rounded-lg border border-red-700">
          <div className="text-sm text-red-200">{error}</div>
        </div>
      )}

      {/* Title overlay - top left */}
      <div className="absolute top-4 left-4 z-20 bg-gray-900/95 backdrop-blur-sm px-4 py-2 rounded-lg border border-gray-700">
        <h3 className="text-lg font-semibold text-white">Knowledge Graph Similarity Explorer</h3>
        <p className="text-xs text-gray-400 mt-1">
          Visualizing semantic relationships across MQTT topics
        </p>
      </div>

      {/* Graph visualization */}
      <GraphVisualization
        similarResults={similarResults}
        suggestedTopic={currentTopic?.path}
        isSearching={isSearching}
        enableAutoRotate={true}
      />
    </div>
  );
}
