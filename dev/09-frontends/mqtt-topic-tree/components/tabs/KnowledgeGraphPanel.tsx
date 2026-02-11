'use client';

import { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import TopicTreeSidebar from '../graph/TopicTreeSidebar';
import GraphLegend from '../graph/GraphLegend';
import NodeDetailPanel from '../graph/NodeDetailPanel';
import type { GraphData, NvlNode } from '@/types/graph';
import type { Node, HitTargets } from '@neo4j-nvl/base';

// Dynamically import NVL to avoid SSR issues
const InteractiveNvlWrapper = dynamic(
  () => import('@neo4j-nvl/react').then((mod) => mod.InteractiveNvlWrapper),
  { ssr: false }
);

export default function KnowledgeGraphPanel() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<NvlNode | null>(null);
  const [viewMode, setViewMode] = useState<'children' | 'messages' | null>(null);

  // Execute query for topic selection
  const executeTopicQuery = useCallback(async (path: string, isLeaf: boolean) => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedPath(path);
    setViewMode(isLeaf ? 'messages' : 'children');

    try {
      let query: string;

      if (isLeaf) {
        // Fetch the topic and its messages (no broker filter - client IDs are root segments)
        query = `
          MATCH (t:Topic {path: $path})
          OPTIONAL MATCH (t)-[r:HAS_MESSAGE]->(m:Message)
          WITH t, r, m
          ORDER BY m.timestamp DESC
          RETURN t, r, m
          LIMIT 50
        `;
      } else {
        // Fetch direct children using Topic nodes and CHILD_OF relationships
        query = `
          MATCH (parent:Topic {path: $path})<-[r:CHILD_OF]-(child:Topic)
          WITH DISTINCT parent, child, r
          RETURN parent, r, child
          ORDER BY child.path
        `;
      }

      const response = await fetch('/api/graph/explore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          params: { path },
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to execute query');
      }

      const data = await response.json();
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setGraphData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle topic selection from sidebar
  const handleSelectTopic = useCallback((path: string, isLeaf: boolean) => {
    executeTopicQuery(path, isLeaf);
  }, [executeTopicQuery]);

  // Handle node click in graph
  const handleNodeClick = useCallback((node: Node, _hitTargets: HitTargets, _event: MouseEvent) => {
    setSelectedNode(node as NvlNode);
  }, []);

  // Close node detail panel
  const handleCloseDetail = useCallback(() => {
    setSelectedNode(null);
  }, []);

  // Load initial view - show all root-level TopicSegments (client IDs)
  useEffect(() => {
    async function loadInitialView() {
      setLoading(true);
      try {
        const response = await fetch('/api/graph/explore', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: `
              MATCH (s:Topic)
              WHERE NOT (s)-[:CHILD_OF]->()
              RETURN s
              LIMIT 50
            `,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          setGraphData(data);
          setViewMode('children');
        }
      } catch (err) {
        console.error('Failed to load initial view:', err);
      } finally {
        setLoading(false);
      }
    }

    loadInitialView();
  }, []);

  return (
    <div className="h-[calc(100vh-180px)] flex flex-col">
      {/* Header Bar */}
      <div className="bg-gray-800 rounded-t-xl border border-gray-700 px-4 py-3 flex items-center gap-4">
        {/* Current path display */}
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          <span className="text-sm text-gray-300 font-mono">
            {selectedPath || 'Select a topic from the tree'}
          </span>
        </div>

        {/* View mode indicator */}
        {viewMode && (
          <span className={`text-xs px-2 py-1 rounded ${
            viewMode === 'messages'
              ? 'bg-amber-600/20 text-amber-400'
              : 'bg-blue-600/20 text-blue-400'
          }`}>
            {viewMode === 'messages' ? 'Messages' : 'Topics'}
          </span>
        )}

        <div className="flex-1"></div>

        {/* Stats */}
        {graphData && (
          <div className="flex items-center gap-4 text-sm text-gray-400">
            <div className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728m-9.9-2.829a5 5 0 010-7.07m7.072 0a5 5 0 010 7.07M13 12a1 1 0 11-2 0 1 1 0 012 0z" />
              </svg>
              <span>{graphData.nodes.length} nodes</span>
            </div>
            <div className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
              <span>{graphData.relationships.length} relationships</span>
            </div>
          </div>
        )}

      </div>

      {/* Main content with sidebar */}
      <div className="flex-1 flex rounded-b-xl border-x border-b border-gray-700 overflow-hidden">
        {/* Topic Tree Sidebar */}
        <TopicTreeSidebar
          selectedPath={selectedPath}
          onSelectTopic={handleSelectTopic}
        />

        {/* Graph Canvas */}
        <div className="flex-1 bg-gray-900 overflow-hidden relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10">
              <div className="flex flex-col items-center gap-4">
                <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="text-gray-400">Querying Neo4j...</span>
              </div>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center max-w-md p-6">
                <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-red-900/50 flex items-center justify-center">
                  <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="text-red-400 font-medium mb-2">Query Error</div>
                <div className="text-gray-400 text-sm">{error}</div>
              </div>
            </div>
          )}

          {!loading && !error && (!graphData || graphData.nodes.length === 0) && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center p-6">
                <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-gray-800 flex items-center justify-center">
                  <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 16l2.879-2.879m0 0a3 3 0 104.243-4.242 3 3 0 00-4.243 4.242zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="text-gray-400 font-medium mb-1">
                  {selectedPath ? 'No data found' : 'Select a topic'}
                </div>
                <div className="text-gray-500 text-sm">
                  {selectedPath
                    ? 'This topic has no children or messages'
                    : 'Click on a topic in the tree to visualize it'
                  }
                </div>
              </div>
            </div>
          )}

          {!loading && !error && graphData && graphData.nodes.length > 0 && (
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
          )}

          <GraphLegend />

          {selectedNode && (
            <NodeDetailPanel node={selectedNode} onClose={handleCloseDetail} />
          )}
        </div>
      </div>

      {/* Footer with info */}
      <div className="mt-3 px-4 py-2 bg-gray-800/50 rounded-lg border border-gray-700">
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <svg className="w-4 h-4 text-blue-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Click folders to see children topics, click leaf topics to see messages. Click graph nodes to view details.</span>
        </div>
      </div>
    </div>
  );
}
