'use client';

import { useState } from 'react';
import { SerializableTopicNode } from '@/lib/topic-tree-builder';
import { ConformanceStatus } from '@/types/conformance';

interface TopicNodeProps {
  node: SerializableTopicNode;
  level: number;
  onSelectTopic?: (node: SerializableTopicNode) => void;
  selectedTopic?: string;
}

/**
 * Get CSS classes for conformance status indicator
 */
function getConformanceColor(status?: ConformanceStatus): string {
  switch (status) {
    case 'conformant':
      return 'bg-green-500';
    case 'non_conformant':
      return 'bg-red-500';
    case 'mixed':
      return 'bg-yellow-500';
    case 'no_binding':
    default:
      return 'bg-gray-500';
  }
}

/**
 * Get tooltip text for conformance status
 */
function getConformanceTooltip(node: SerializableTopicNode): string {
  const { conformanceStatus, conformantCount, nonConformantCount, unboundCount, boundProposalName } = node;

  if (conformanceStatus === 'no_binding') {
    return 'No schema bound';
  }

  const parts: string[] = [];
  if (boundProposalName) {
    parts.push(`Schema: ${boundProposalName}`);
  }
  if (conformantCount > 0) {
    parts.push(`${conformantCount} conformant`);
  }
  if (nonConformantCount > 0) {
    parts.push(`${nonConformantCount} non-conformant`);
  }
  if (unboundCount > 0) {
    parts.push(`${unboundCount} unbound`);
  }

  return parts.join(', ') || 'Unknown';
}

export default function TopicNode({ node, level, onSelectTopic, selectedTopic }: TopicNodeProps) {
  const [isExpanded, setIsExpanded] = useState(level === 0);

  const hasChildren = node.children.length > 0;
  const isSelected = selectedTopic === node.fullPath;

  const handleToggle = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  };

  const handleSelect = () => {
    if (node.isLeaf && onSelectTopic) {
      onSelectTopic(node);
    }
  };

  const indentStyle = {
    paddingLeft: `${level * 1.5}rem`,
  };

  const conformanceColor = getConformanceColor(node.conformanceStatus);
  const conformanceTooltip = getConformanceTooltip(node);

  return (
    <div className="topic-node">
      <div
        className={`flex items-center py-1.5 px-3 hover:bg-gray-700 cursor-pointer transition-colors ${
          isSelected ? 'bg-blue-900 hover:bg-blue-800' : ''
        }`}
        style={indentStyle}
        onClick={handleSelect}
      >
        {hasChildren && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleToggle();
            }}
            className="mr-2 text-gray-400 hover:text-gray-200 focus:outline-none"
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            <svg
              className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        )}
        {!hasChildren && <span className="mr-2 w-4"></span>}

        {/* Conformance status indicator */}
        <span
          className={`w-2 h-2 rounded-full mr-2 flex-shrink-0 ${conformanceColor}`}
          title={conformanceTooltip}
        />

        <div className="flex items-center flex-1 min-w-0">
          {node.isLeaf ? (
            <svg
              className="w-4 h-4 mr-2 text-blue-500 flex-shrink-0"
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
              className="w-4 h-4 mr-2 text-yellow-600 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
              />
            </svg>
          )}

          <span className="font-mono text-sm text-gray-100 truncate">{node.name}</span>

          {/* Show bound proposal name if leaf has a binding */}
          {node.isLeaf && node.boundProposalName && (
            <span className="ml-2 text-xs text-purple-400 truncate max-w-[120px]" title={node.boundProposalName}>
              [{node.boundProposalName}]
            </span>
          )}

          {node.messageCount > 0 && (
            <span className="ml-auto text-xs text-gray-400 flex-shrink-0 ml-2">
              ({node.messageCount})
            </span>
          )}
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TopicNode
              key={child.fullPath}
              node={child}
              level={level + 1}
              onSelectTopic={onSelectTopic}
              selectedTopic={selectedTopic}
            />
          ))}
        </div>
      )}
    </div>
  );
}
