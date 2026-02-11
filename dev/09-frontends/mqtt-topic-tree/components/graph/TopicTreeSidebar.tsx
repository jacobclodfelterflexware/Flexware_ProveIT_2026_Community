'use client';

import { useEffect, useState, useCallback } from 'react';

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;
  totalMessageCount?: number;
  hasNumericData?: boolean;
  hasMLReadyDescendant?: boolean;
  hasVariance?: boolean | null; // true=varying, false=static, null=indeterminate
}

interface TopicTreeSidebarProps {
  selectedPath: string | null;
  onSelectTopic: (path: string, isLeaf: boolean) => void;
}

interface TreeNodeProps {
  node: TreeNode;
  level: number;
  selectedPath: string | null;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string, isLeaf: boolean) => void;
}

function TreeNodeComponent({ node, level, selectedPath, expandedPaths, onToggle, onSelect }: TreeNodeProps) {
  const isExpanded = expandedPaths.has(node.fullPath);
  const isSelected = selectedPath === node.fullPath;
  const hasChildren = node.children.length > 0;

  const handleClick = () => {
    onSelect(node.fullPath, node.isLeaf);
    if (hasChildren) {
      onToggle(node.fullPath);
    }
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

        {/* Variance indicator for leaf nodes */}
        {node.isLeaf && node.hasVariance === true && (
          <span
            className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse flex-shrink-0 mr-1"
            title="Active variance detected"
          />
        )}
        {node.isLeaf && node.hasVariance === false && (
          <span
            className="w-1.5 h-1.5 rounded-full bg-amber-600 flex-shrink-0 mr-1"
            title="Static value (no variance)"
          />
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

export default function TopicTreeSidebar({ selectedPath, onSelectTopic }: TopicTreeSidebarProps) {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [totalTopics, setTotalTopics] = useState(0);

  // Fetch tree data (no broker filter - client IDs are root segments)
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

        // Auto-expand first level (client IDs)
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

  // Toggle expand/collapse
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

  // Handle selection
  const handleSelect = useCallback((path: string, isLeaf: boolean) => {
    onSelectTopic(path, isLeaf);
  }, [onSelectTopic]);

  return (
    <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">Topic Tree</h3>
          <span className="text-xs text-gray-500">{totalTopics} topics</span>
        </div>
      </div>

      {/* Tree content */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading && (
          <div className="flex items-center justify-center py-8">
            <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <span className="ml-2 text-sm text-gray-400">Loading...</span>
          </div>
        )}

        {error && (
          <div className="px-3 py-4 text-center">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}

        {!loading && !error && tree.length === 0 && (
          <div className="px-3 py-4 text-center text-gray-500 text-sm">
            No topics found
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

      {/* Footer with instructions */}
      <div className="p-2 border-t border-gray-700 flex-shrink-0">
        <div className="text-xs text-gray-500 text-center space-y-0.5">
          <div>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-1 align-middle" />
            <span className="align-middle">varying</span>
            <span className="mx-1.5">&middot;</span>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-600 mr-1 align-middle" />
            <span className="align-middle">static</span>
          </div>
          <div>Click folder for children, leaf for messages</div>
        </div>
      </div>
    </div>
  );
}
