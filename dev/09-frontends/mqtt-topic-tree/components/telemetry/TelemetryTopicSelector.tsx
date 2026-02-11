'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import type { SelectedTopicInfo } from './TelemetryPage';

interface DataTypes {
  numeric: boolean;
  string: boolean;
  boolean: boolean;
  object: boolean;
  array: boolean;
}

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;
  totalMessageCount?: number;
  hasNumericData?: boolean;
  hasMLReadyDescendant?: boolean;
  hasVariance?: boolean | null;  // true=varying, false=static, null=indeterminate
  dataTypes?: DataTypes;
}

interface TelemetryTopicSelectorProps {
  onSelect: (topic: SelectedTopicInfo) => void;
  selectedTopic?: string;
}

export default function TelemetryTopicSelector({ onSelect, selectedTopic }: TelemetryTopicSelectorProps) {
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

  // Check if any descendant has numeric data
  const hasNumericDescendant = useCallback((node: TreeNode): boolean => {
    if (node.hasNumericData) return true;
    return node.children.some(child => hasNumericDescendant(child));
  }, []);

  // Extract suggested topics: ML-ready with variance (changing numeric values)
  const suggestedTopics = useMemo(() => {
    const MIN_MESSAGES_FOR_ML = 20;
    const candidates: TreeNode[] = [];

    function collectInteresting(node: TreeNode) {
      // Check if this node qualifies:
      // - Is a leaf node
      // - Has numeric data
      // - Has variance (values are actually changing, not static)
      // - Has 20+ messages (ML-ready)
      if (
        node.isLeaf &&
        node.hasNumericData &&
        node.hasVariance === true &&  // Must be confirmed varying (not false/null)
        node.messageCount &&
        node.messageCount >= MIN_MESSAGES_FOR_ML
      ) {
        candidates.push(node);
      }

      // Recurse into children
      node.children?.forEach(collectInteresting);
    }

    tree.forEach(collectInteresting);

    // Sort by message count (most data first)
    return candidates
      .sort((a, b) => (b.messageCount || 0) - (a.messageCount || 0))
      .slice(0, 10);  // Show top 10
  }, [tree]);

  // Handle topic selection - any topic with numeric data is selectable
  const handleSelect = useCallback(async (node: TreeNode) => {
    const hasChildren = node.children.length > 0;
    const hasNumericData = node.hasNumericData ?? false;

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

    // Leaf nodes without numeric data: not selectable
    if (!hasNumericData) {
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

    // ML eligibility: 20+ messages with numeric data
    const MIN_MESSAGES_FOR_ML = 20;
    const isMLReady = node.isLeaf && hasNumericData && directMsgCount >= MIN_MESSAGES_FOR_ML;

    // Get data indicators: Cyan = ML Ready, Green = Explorable, Blue = Has Data
    const getDataTypeIndicators = () => {
      const indicators: { color: string; label: string }[] = [];

      if (hasChildren) {
        // Folder - show if it contains explorable (numeric) data
        const hasNumericChild = hasNumericDescendant(node);
        if (hasNumericChild) {
          indicators.push({ color: 'bg-green-500', label: 'Contains explorable data' });
        }
        // Folders always have data if they exist in the tree
        indicators.push({ color: 'bg-blue-500', label: 'Has data' });
      } else {
        // Leaf node
        if (isMLReady) {
          indicators.push({ color: 'bg-cyan-500', label: 'ML Ready (20+ messages)' });
        }
        if (hasNumericData) {
          indicators.push({ color: 'bg-green-500', label: 'Explorable' });
        }
        if (directMsgCount > 0) {
          indicators.push({ color: 'bg-blue-500', label: 'Has data' });
        }
      }

      if (indicators.length === 0) {
        indicators.push({ color: 'bg-gray-600', label: 'No data' });
      }

      return indicators;
    };
    const indicators = getDataTypeIndicators();

    // Clickable if it has numeric data
    const isClickable = hasChildren || hasNumericData;

    return (
      <div key={node.fullPath}>
        <div
          className={`flex items-center gap-2 py-1.5 px-2 rounded transition-colors ${
            isSelected
              ? 'bg-purple-900/50 border border-purple-700'
              : hasChildren
                ? 'hover:bg-gray-800 cursor-pointer'
                : hasNumericData
                  ? 'hover:bg-gray-800 cursor-pointer'
                  : 'opacity-40 cursor-not-allowed'
          } ${isLoading ? 'opacity-60' : ''}`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => handleSelect(node)}
          title={indicators.map(i => i.label).join(', ')}
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

          {/* Data type indicator dots */}
          <div className="flex gap-0.5 flex-shrink-0" title={indicators.map(i => i.label).join(', ')}>
            {indicators.map((ind, idx) => (
              <span
                key={idx}
                className={`w-2 h-2 rounded-full ${ind.color}`}
                title={ind.label}
              />
            ))}
          </div>

          {/* Icon */}
          {node.isLeaf ? (
            <svg className={`w-4 h-4 flex-shrink-0 ${hasNumericData ? 'text-purple-400' : 'text-gray-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
              ? 'text-purple-300 font-medium'
              : hasNumericData
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
              // Folder badge - show if has numeric descendants
              hasNumericDescendant(node) ? (
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-purple-400 bg-purple-900/30">
                  Has Data
                </span>
              ) : null
            ) : (
              // Leaf badge - show message count and ML status
              hasNumericData ? (
                <div className="ml-auto flex items-center gap-1">
                  <span className="text-xs px-1.5 py-0.5 rounded text-green-400 bg-green-900/30">
                    {directMsgCount} msgs
                  </span>
                  {isMLReady && (
                    <span className="text-xs px-1.5 py-0.5 rounded text-cyan-400 bg-cyan-900/30">
                      ML Ready
                    </span>
                  )}
                </div>
              ) : directMsgCount > 0 ? (
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded text-amber-400 bg-amber-900/30">
                  {directMsgCount} msgs
                </span>
              ) : null
            )
          )}

          {/* Loading indicator */}
          {isLoading && (
            <div className="ml-auto animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-purple-500"></div>
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
          <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-purple-500"></div>
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
            Select Topic (All Numeric)
          </h2>
          {selectedTopic && (
            <span className="text-xs text-purple-400 font-mono bg-purple-900/30 px-2 py-0.5 rounded">
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

      {/* Suggested Topics + Legend + Tree */}
      {!isCollapsed && (
        <>
          {/* Suggested Topics Section */}
          {suggestedTopics.length > 0 && (
            <div className="px-3 py-3 border-b border-gray-700 bg-gradient-to-r from-yellow-900/20 to-transparent">
              <h4 className="text-sm font-medium text-gray-200 mb-2 flex items-center gap-2">
                <span className="text-yellow-400">★</span>
                Suggested Topics
                <span className="text-xs text-gray-500 font-normal">
                  (ML-ready with changing values)
                </span>
              </h4>
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {suggestedTopics.map(topic => (
                  <button
                    key={topic.fullPath}
                    onClick={() => handleSelect(topic)}
                    disabled={loadingPayload === topic.fullPath}
                    className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                      selectedTopic === topic.fullPath
                        ? 'bg-purple-900/50 border border-purple-700'
                        : 'bg-gray-700/50 hover:bg-gray-700'
                    } ${loadingPayload === topic.fullPath ? 'opacity-60' : ''}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-gray-200 truncate font-medium">{topic.name}</span>
                      <div className="flex items-center gap-2 text-xs flex-shrink-0">
                        <span className="text-green-400">{topic.messageCount} msgs</span>
                        <span className="text-cyan-400 bg-cyan-900/30 px-1.5 py-0.5 rounded">ML Ready</span>
                      </div>
                    </div>
                    <div className="text-xs text-gray-500 truncate mt-0.5">
                      {topic.fullPath}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Legend */}
          <div className="px-3 py-2 border-b border-gray-700 flex items-center gap-4 text-xs text-gray-400">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-500" />
              <span>ML Ready</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <span>Numeric</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <span>Has Data</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-gray-600" />
              <span>Empty</span>
            </div>
          </div>
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
        </>
      )}
    </div>
  );
}
