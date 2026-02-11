'use client';

import { useEffect, useState, useCallback } from 'react';

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;
}

interface TopicTreeBrowserProps {
  onSelect: (topicPath: string) => void;
  onClose: () => void;
}

interface TreeNodeProps {
  node: TreeNode;
  level: number;
  selectedPath: string | null;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}

function TreeNodeComponent({ node, level, selectedPath, expandedPaths, onToggle, onSelect }: TreeNodeProps) {
  const isExpanded = expandedPaths.has(node.fullPath);
  const isSelected = selectedPath === node.fullPath;
  const hasChildren = node.children.length > 0;

  const handleClick = () => {
    if (hasChildren) {
      onToggle(node.fullPath);
    }
    // Always allow selection (both folders and leaves can be topics)
    onSelect(node.fullPath);
  };

  return (
    <div>
      <div
        className={`
          flex items-center py-1.5 px-2 cursor-pointer transition-colors
          hover:bg-gray-700/50
          ${isSelected ? 'bg-blue-600/30 border-l-2 border-blue-500' : 'border-l-2 border-transparent'}
        `}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={handleClick}
      >
        {/* Expand/collapse icon */}
        {hasChildren ? (
          <svg
            className={`w-3 h-3 mr-1.5 text-gray-500 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        ) : (
          <span className="w-3 mr-1.5 flex-shrink-0"></span>
        )}

        {/* Folder/document icon */}
        {node.isLeaf ? (
          <svg
            className="w-4 h-4 mr-2 text-blue-400 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
        ) : (
          <svg
            className={`w-4 h-4 mr-2 flex-shrink-0 ${isExpanded ? 'text-yellow-500' : 'text-yellow-600'}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d={isExpanded
                ? "M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z"
                : "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              }
            />
          </svg>
        )}

        {/* Node name */}
        <span className={`text-sm truncate ${isSelected ? 'text-white font-medium' : 'text-gray-300'}`}>
          {node.name}
        </span>

        {/* Message count badge */}
        {node.isLeaf && node.messageCount !== undefined && node.messageCount > 0 && (
          <span className="ml-auto text-xs text-gray-500 flex-shrink-0 pl-2">
            {node.messageCount}
          </span>
        )}

        {/* Children count for folders */}
        {!node.isLeaf && node.children.length > 0 && (
          <span className="ml-auto text-xs text-gray-600 flex-shrink-0 pl-2">
            {node.children.length}
          </span>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeNodeComponent
              key={child.fullPath}
              node={child}
              level={level + 1}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TopicTreeBrowser({ onSelect, onClose }: TopicTreeBrowserProps) {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [totalTopics, setTotalTopics] = useState(0);

  // Fetch tree data
  useEffect(() => {
    async function fetchTree() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch('/api/graph/tree');
        if (!response.ok) {
          throw new Error('Failed to fetch topic tree');
        }

        const data = await response.json();
        setTree(data.tree);
        setTotalTopics(data.totalTopics);

        // Auto-expand first level
        const firstLevelPaths = new Set<string>();
        data.tree.forEach((node: TreeNode) => {
          firstLevelPaths.add(node.fullPath);
        });
        setExpandedPaths(firstLevelPaths);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    fetchTree();
  }, []);

  const handleToggle = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSelect = useCallback((path: string) => {
    setSelectedPath(path);
  }, []);

  const handleConfirm = () => {
    if (selectedPath) {
      onSelect(selectedPath);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-[60]">
      <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="border-b border-gray-700 px-4 py-3 flex items-center justify-between flex-shrink-0">
          <div>
            <h3 className="text-lg font-medium text-gray-100">Browse Topic Tree</h3>
            <p className="text-sm text-gray-400">{totalTopics} topics available</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tree content */}
        <div className="flex-1 overflow-y-auto py-2">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="ml-3 text-gray-400">Loading topic tree...</span>
            </div>
          )}

          {error && (
            <div className="px-4 py-8 text-center">
              <div className="text-red-400">{error}</div>
            </div>
          )}

          {!loading && !error && tree.length === 0 && (
            <div className="px-4 py-8 text-center text-gray-500">
              No topics found in the uncurated broker
            </div>
          )}

          {!loading && !error && tree.map((node) => (
            <TreeNodeComponent
              key={node.fullPath}
              node={node}
              level={0}
              selectedPath={selectedPath}
              expandedPaths={expandedPaths}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
          ))}
        </div>

        {/* Selected topic display */}
        {selectedPath && (
          <div className="border-t border-gray-700 px-4 py-2 bg-gray-900/50 flex-shrink-0">
            <span className="text-sm text-gray-400">Selected: </span>
            <span className="text-sm font-mono text-gray-100">{selectedPath}</span>
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-gray-700 px-4 py-3 flex justify-end gap-3 flex-shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={!selectedPath}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Select Topic
          </button>
        </div>
      </div>
    </div>
  );
}
