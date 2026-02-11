'use client';

import { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import GraphLegend from './GraphLegend';
import NodeDetailPanel from './NodeDetailPanel';
import type { GraphData, NvlNode } from '@/types/graph';
import type { Node, HitTargets } from '@neo4j-nvl/base';

// Dynamically import NVL to avoid SSR issues
const InteractiveNvlWrapper = dynamic(
  () => import('@neo4j-nvl/react').then((mod) => mod.InteractiveNvlWrapper),
  { ssr: false }
);

interface GraphVisualizerProps {
  topicPath: string;
}

export default function GraphVisualizer({ topicPath }: GraphVisualizerProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<NvlNode | null>(null);

  // Fetch graph data when topic changes (no broker filter - client IDs are root segments)
  useEffect(() => {
    if (!topicPath) return;

    const fetchGraphData = async () => {
      setLoading(true);
      setError(null);
      setSelectedNode(null);

      try {
        const response = await fetch(
          `/api/graph?topic=${encodeURIComponent(topicPath)}`
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to fetch graph data');
        }

        const data = await response.json();
        setGraphData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();
  }, [topicPath]);

  // Handle node click - signature from NVL: (node: Node, hitTargets: HitTargets, event: MouseEvent) => void
  const handleNodeClick = useCallback((node: Node, _hitTargets: HitTargets, _event: MouseEvent) => {
    setSelectedNode(node as NvlNode);
  }, []);

  // Close node detail panel
  const handleCloseDetail = useCallback(() => {
    setSelectedNode(null);
  }, []);

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-900 rounded border border-gray-700">
        <div className="flex items-center space-x-2 text-gray-400">
          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
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
          <span>Loading graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-900 rounded border border-gray-700">
        <div className="text-center">
          <div className="text-red-400 mb-2">{error}</div>
          <div className="text-gray-500 text-sm">
            Topic may not exist in the graph database yet
          </div>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center bg-gray-900 rounded border border-gray-700">
        <div className="text-gray-400 text-center">
          <div className="mb-2">No graph data available</div>
          <div className="text-sm text-gray-500">
            This topic hasn&apos;t been ingested to Neo4j yet
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        className="h-80 bg-gray-900 rounded border border-gray-700 overflow-hidden"
        style={{ minHeight: '320px' }}
      >
        <InteractiveNvlWrapper
          nodes={graphData.nodes}
          rels={graphData.relationships}
          nvlOptions={{
            initialZoom: 1.0,
            layout: 'forceDirected',
            relationshipThreshold: 0.55,
          }}
          mouseEventCallbacks={{
            onNodeClick: handleNodeClick,
            onZoom: true,
            onPan: true,
            onDrag: true,
          }}
        />
      </div>

      <GraphLegend />

      {selectedNode && (
        <NodeDetailPanel node={selectedNode} onClose={handleCloseDetail} />
      )}
    </div>
  );
}
