'use client';

import { useEffect, useState, useCallback } from 'react';
import type { SelectedTopicInfo } from './TopicAnalyzerPage';

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;       // Direct messages on this topic
  totalMessageCount?: number;  // Sum of self + all descendant messages
  hasNumericData?: boolean;    // Whether this topic has numeric fields (eligible for ML)
  hasMLReadyDescendant?: boolean; // True if any child/grandchild is ML-ready
}

interface TopicSelectorProps {
  onSelect: (topic: SelectedTopicInfo) => void;
  selectedTopic?: string;
}

export default function TopicSelector({ onSelect, selectedTopic }: TopicSelectorProps) {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [loadingPayload, setLoadingPayload] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Fetch topic tree
  useEffect(() => {
    async function fetchTree() {
      try {
        const response = await fetch('/api/graph/tree');
        if (!response.ok) throw new Error('Failed to fetch topic tree');
        const data = await response.json();
        setTree(data.tree);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load topics');
      } finally {
        setLoading(false);
      }
    }

    fetchTree();
  }, []);

  // Toggle node expansion
  const toggleExpand = useCallback((path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Handle topic selection - only ML-ready topics (20+ messages with numeric data) are selectable
  const handleSelect = useCallback(async (node: TreeNode) => {
    const hasChildren = node.children.length > 0;
    const hasNumericData = node.hasNumericData ?? false;
    const directMsgCount = node.messageCount ?? 0;
    const MIN_MESSAGES_FOR_ML = 20;
    const isMLReady = node.isLeaf && hasNumericData && directMsgCount >= MIN_MESSAGES_FOR_ML;

    // Non-leaf nodes: toggle expand/collapse only
    if (hasChildren) {
      setExpandedPaths(prev => {
        const next = new Set(prev);
        if (next.has(node.fullPath)) {
          next.delete(node.fullPath);
        } else {
          next.add(node.fullPath);
        }
        return next;
      });
      return;
    }

    // Leaf nodes not ML-ready: not selectable
    if (!isMLReady) {
      return;
    }

    // Leaf node with numeric data: fetch payload and select
    setLoadingPayload(node.fullPath);

    try {
      const url = `/api/topic/payload?path=${encodeURIComponent(node.fullPath)}`;

      const response = await fetch(url);
      if (!response.ok) {
        throw new Error('Failed to fetch topic payload');
      }

      const data = await response.json();

      onSelect({
        topicPath: node.fullPath,
        payload: data.payload,
        numericFields: data.numericFields,
        timestamp: data.timestamp,
        isAggregated: data.isAggregated,
        childTopics: data.childTopics,
        messageCount: data.messageCount,
      });

      // Collapse the selector after selection
      setIsCollapsed(true);
    } catch (err) {
      console.error('Failed to fetch payload:', err);
    } finally {
      setLoadingPayload(null);
    }
  }, [onSelect]);

  // Render a tree node
  const renderNode = (node: TreeNode, depth: number = 0): React.ReactNode => {
    const isExpanded = expandedPaths.has(node.fullPath);
    const hasChildren = node.children.length > 0;
    const isSelected = selectedTopic === node.fullPath;
    const isLoading = loadingPayload === node.fullPath;

    // Data availability
    const directMsgCount = node.messageCount ?? 0;
    const hasNumericData = node.hasNumericData ?? false;

    // ML eligibility requires: leaf + numeric data + minimum 20 messages for time series
    const MIN_MESSAGES_FOR_ML = 20;
    const isAnalyzable = node.isLeaf && hasNumericData;
    const isMLReady = isAnalyzable && directMsgCount >= MIN_MESSAGES_FOR_ML;

    // Determine indicator color and tooltip based on ML eligibility
    const getDataIndicator = () => {
      if (hasChildren) {
        // Folder - show green if it contains ML-ready descendants
        if (node.hasMLReadyDescendant) {
          return { color: 'bg-green-500', tooltip: 'Contains ML-ready topics - expand to find them' };
        }
        return { color: 'bg-gray-500', tooltip: 'Folder - no ML-ready topics inside' };
      } else if (isMLReady) {
        // Leaf with enough data for ML - clickable
        return { color: 'bg-green-500', tooltip: `${directMsgCount} messages - Click to analyze with ML` };
      } else if (isAnalyzable) {
        // Leaf with numeric data but not enough for ML - NOT clickable here
        return { color: 'bg-gray-500', tooltip: `${directMsgCount} messages - Need ${MIN_MESSAGES_FOR_ML}+ for ML (use Telemetry Viewer)` };
      } else if (directMsgCount > 0) {
        // Leaf with messages but no numeric data
        return { color: 'bg-amber-500', tooltip: `${directMsgCount} messages (no numeric data)` };
      } else {
        // Leaf with no messages
        return { color: 'bg-gray-600', tooltip: 'No data' };
      }
    };
    const indicator = getDataIndicator();

    // Only clickable if ML-ready (20+ messages with numeric data)
    const isClickable = hasChildren || isMLReady;

    return (
      <div key={node.fullPath}>
        <div
          className={`flex items-center gap-2 py-1.5 px-2 rounded transition-colors ${
            isSelected
              ? 'bg-blue-900/50 border border-blue-700'
              : hasChildren
                ? 'hover:bg-gray-800 cursor-pointer'
                : isMLReady
                  ? 'hover:bg-gray-800 cursor-pointer'
                  : 'opacity-40 cursor-not-allowed'
          } ${isLoading ? 'opacity-60' : ''}`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => handleSelect(node)}
          title={indicator.tooltip}
        >
          {/* Expand/collapse button */}
          {hasChildren ? (
            <button
              onClick={(e) => toggleExpand(node.fullPath, e)}
              className="w-4 h-4 flex items-center justify-center text-gray-500 hover:text-gray-300"
            >
              <svg
                className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          ) : (
            <span className="w-4" />
          )}

          {/* ML eligibility indicator dot */}
          <span
            className={`w-2 h-2 rounded-full flex-shrink-0 ${indicator.color}`}
            title={indicator.tooltip}
          />

          {/* Icon */}
          {node.isLeaf ? (
            <svg className={`w-4 h-4 flex-shrink-0 ${isMLReady ? 'text-green-400' : 'text-gray-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-yellow-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          )}

          {/* Name */}
          <span className={`text-sm truncate ${
            isSelected
              ? 'text-blue-300 font-medium'
              : isMLReady
                ? 'text-gray-300'
                : hasChildren
                  ? 'text-gray-400'
                  : 'text-gray-500'
          }`}>
            {node.name}
          </span>

          {/* Status badge */}
          {!isLoading && (
            hasChildren ? (
              // Folder badge - show if has ML-ready descendants
              node.hasMLReadyDescendant ? (
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-green-400 bg-green-900/30">
                  Has ML
                </span>
              ) : null
            ) : (
              // Leaf badge - only show ML Ready for clickable topics
              isMLReady ? (
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-green-400 bg-green-900/30">
                  ML Ready
                </span>
              ) : isAnalyzable ? (
                // Not enough for ML - show count but indicate it needs more
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-gray-500 bg-gray-800">
                  {directMsgCount}/{MIN_MESSAGES_FOR_ML}
                </span>
              ) : directMsgCount > 0 ? (
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-amber-400 bg-amber-900/30">
                  No numeric
                </span>
              ) : null
            )
          )}

          {/* Loading indicator */}
          {isLoading && (
            <div className="ml-auto animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500"></div>
          )}
        </div>

        {/* Children */}
        {isExpanded && hasChildren && (
          <div>
            {node.children.map(child => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-500"></div>
          <span className="text-gray-400">Loading topic tree...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center gap-3 text-red-400">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div
        className="px-4 py-3 border-b border-gray-700 flex items-center justify-between cursor-pointer hover:bg-gray-750"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="flex items-center gap-3">
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          <h2 className="text-sm font-semibold text-gray-100">
            Select Topic (ML Ready Only)
          </h2>
          {selectedTopic && (
            <span className="text-xs text-blue-400 font-mono bg-blue-900/30 px-2 py-0.5 rounded">
              {selectedTopic.split('/').pop()}
            </span>
          )}
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isCollapsed ? '' : 'rotate-180'}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Tree */}
      {!isCollapsed && (
        <div className="p-2 max-h-80 overflow-y-auto">
          {tree.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <p className="text-sm">No topics found</p>
              <p className="text-xs mt-1">Topics will appear as messages are ingested</p>
            </div>
          ) : (
            tree.map(node => renderNode(node))
          )}
        </div>
      )}
    </div>
  );
}
