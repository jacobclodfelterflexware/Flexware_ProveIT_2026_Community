'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import type { SimilarResult } from '@/types/machines';

// Dynamic import for GraphVisualization to avoid SSR/WebGL issues
const GraphVisualization = dynamic(
  () => import('@/components/machines/GraphVisualization'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-400 text-sm">Loading 3D renderer...</p>
        </div>
      </div>
    )
  }
);

interface TopicSimilarityPanelProps {
  topicPath: string;
}

export default function TopicSimilarityPanel({ topicPath }: TopicSimilarityPanelProps) {
  const [similarResults, setSimilarResults] = useState<SimilarResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSimilarity() {
      if (!topicPath) return;

      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `/api/graph/similar-search?q=${encodeURIComponent(topicPath)}&k=10`
        );

        if (!response.ok) {
          throw new Error('Failed to fetch similar topics');
        }

        const data = await response.json();

        // Filter out the selected topic from results
        const filteredResults = (data.results || []).filter(
          (r: SimilarResult) => r.topic_path !== topicPath
        );

        setSimilarResults(filteredResults);
      } catch (err) {
        console.error('Similarity search failed:', err);
        setError(err instanceof Error ? err.message : 'Failed to search');
      } finally {
        setLoading(false);
      }
    }

    fetchSimilarity();
  }, [topicPath]);

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-3"></div>
          <p className="text-sm text-gray-400">Searching for similar topics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-center text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-2 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (similarResults.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <div className="text-center text-gray-500">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <p className="text-lg font-medium text-gray-400">No similar topics found</p>
          <p className="text-sm mt-1 text-gray-500">
            Similar topics will appear as more messages are ingested
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full">
      <GraphVisualization
        similarResults={similarResults}
        suggestedTopic={topicPath}
        enableAutoRotate={true}
      />
    </div>
  );
}
