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
  hasVariance?: boolean | null;
}

interface ChartTopicBrowserProps {
  onSelectTopic: (query: string, topicPath: string) => void;
}

interface BrowserTreeNodeProps {
  node: TreeNode;
  level: number;
  expandedPaths: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (query: string, topicPath: string) => void;
}

function BrowserTreeNode({ node, level, expandedPaths, onToggle, onSelect }: BrowserTreeNodeProps) {
  const isExpanded = expandedPaths.has(node.fullPath);
  const hasChildren = node.children.length > 0;
  const lastSegment = node.name;

  const handleClick = () => {
    if (hasChildren) {
      onToggle(node.fullPath);
    }
    if (node.isLeaf && node.hasNumericData) {
      const query = `Show ${lastSegment} trends over the last hour for ${node.fullPath}`;
      onSelect(query, node.fullPath);
    } else if (!node.isLeaf && node.hasMLReadyDescendant) {
      const query = `Overview dashboard for ${node.fullPath}`;
      onSelect(query, node.fullPath);
    }
  };

  return (
    <div>
      <div
        className={`
          flex items-center py-1.5 px-2 cursor-pointer transition-colors
          hover:bg-gray-700/50
          ${node.isLeaf && node.hasNumericData ? 'hover:bg-blue-900/30' : ''}
        `}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={handleClick}
        title={node.isLeaf && node.hasNumericData
          ? `Click to chart: ${node.fullPath}`
          : node.hasMLReadyDescendant
            ? `Click for overview: ${node.fullPath}`
            : node.fullPath
        }
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
          <span className="w-3 mr-1.5 flex-shrink-0" />
        )}

        {/* Numeric data indicator */}
        {node.isLeaf && node.hasNumericData && (
          <span className="w-2 h-2 rounded-full bg-green-500 mr-2 flex-shrink-0" title="Has numeric data" />
        )}
        {node.isLeaf && !node.hasNumericData && (
          <span className="w-2 h-2 rounded-full bg-gray-600 mr-2 flex-shrink-0" title="No numeric data" />
        )}

        {/* Folder icon for non-leaf */}
        {!node.isLeaf && (
          <svg
            className={`w-4 h-4 mr-1.5 flex-shrink-0 ${node.hasMLReadyDescendant ? 'text-yellow-500' : 'text-gray-600'}`}
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
        <span className={`text-sm truncate ${
          node.isLeaf && node.hasNumericData
            ? 'text-gray-200'
            : node.hasMLReadyDescendant
              ? 'text-gray-300'
              : 'text-gray-500'
        }`}>
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
            <BrowserTreeNode
              key={child.fullPath}
              node={child}
              level={level + 1}
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

export default function ChartTopicBrowser({ onSelectTopic }: ChartTopicBrowserProps) {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [totalTopics, setTotalTopics] = useState(0);

  useEffect(() => {
    async function fetchTree() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch('/api/graph/tree');
        if (!response.ok) throw new Error('Failed to fetch topic tree');
        const data = await response.json();
        setTree(data.tree);
        setTotalTopics(data.totalTopics);

        // Auto-expand first level
        const firstLevel = new Set<string>();
        data.tree.forEach((node: TreeNode) => firstLevel.add(node.fullPath));
        setExpandedPaths(firstLevel);
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
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="ml-2 text-sm text-gray-400">Loading topics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-3 py-4 text-center text-sm text-red-400">{error}</div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-sm text-gray-500">No topics found</div>
    );
  }

  return (
    <div>
      <div className="px-3 py-2 text-xs text-gray-500 border-b border-gray-700/50">
        {totalTopics} topics &middot; <span className="text-green-500">&#9679;</span> = numeric data
      </div>
      <div className="py-1">
        {tree.map((node) => (
          <BrowserTreeNode
            key={node.fullPath}
            node={node}
            level={0}
            expandedPaths={expandedPaths}
            onToggle={handleToggle}
            onSelect={onSelectTopic}
          />
        ))}
      </div>
    </div>
  );
}
