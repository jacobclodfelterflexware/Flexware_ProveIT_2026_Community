'use client';

import type { NvlNode } from '@/types/graph';
import { NODE_COLORS } from '@/lib/graph-transformer';

interface NodeDetailPanelProps {
  node: NvlNode;
  onClose: () => void;
}

export default function NodeDetailPanel({ node, onClose }: NodeDetailPanelProps) {
  // Determine node type label and color
  const getNodeTypeInfo = () => {
    switch (node.nodeType) {
      case 'topic':
        return {
          label: node.broker === 'curated' ? 'Curated Topic' : 'Uncurated Topic',
          color: node.broker === 'curated' ? NODE_COLORS.topic_curated : NODE_COLORS.topic_uncurated,
        };
      case 'curated_topic':
        return { label: 'Curated Topic', color: NODE_COLORS.topic_curated };
      case 'message':
        return { label: 'Message', color: NODE_COLORS.message };
      case 'similar_topic':
        return { label: 'Similar Topic', color: NODE_COLORS.similar };
      case 'schemaMapping':
        return { label: 'Schema Mapping', color: NODE_COLORS.schemaMapping };
      default:
        return { label: 'Node', color: '#6b7280' };
    }
  };

  const typeInfo = getNodeTypeInfo();

  return (
    <div className="absolute top-2 left-2 bg-gray-800 rounded-lg shadow-xl border border-gray-700 p-4 max-w-sm z-10">
      {/* Header with close button */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: typeInfo.color }}
          />
          <span className="text-sm font-medium text-gray-300">{typeInfo.label}</span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-200 transition-colors"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Node caption */}
      <div className="mb-3">
        <div className="text-lg font-semibold text-gray-100">{node.caption}</div>
      </div>

      {/* Node-specific details */}
      <div className="space-y-2 text-sm">
        {/* Topic path */}
        {node.path && (
          <div>
            <span className="text-gray-400">Path: </span>
            <span className="text-gray-200 font-mono text-xs break-all">{node.path}</span>
          </div>
        )}

        {/* Broker */}
        {node.broker && (
          <div>
            <span className="text-gray-400">Broker: </span>
            <span className={`font-medium ${node.broker === 'curated' ? 'text-green-400' : 'text-blue-400'}`}>
              {node.broker}
            </span>
          </div>
        )}

        {/* Client ID */}
        {node.clientId && (
          <div>
            <span className="text-gray-400">Client ID: </span>
            <span className="text-gray-200">{node.clientId}</span>
          </div>
        )}

        {/* Message timestamp */}
        {node.timestamp && (
          <div>
            <span className="text-gray-400">Timestamp: </span>
            <span className="text-gray-200">{new Date(node.timestamp).toLocaleString()}</span>
          </div>
        )}

        {/* Message payload preview */}
        {node.rawPayload && (
          <div>
            <span className="text-gray-400">Payload: </span>
            <pre className="mt-1 p-2 bg-gray-900 rounded text-xs text-green-400 overflow-auto max-h-32">
              {(() => {
                try {
                  return JSON.stringify(JSON.parse(node.rawPayload), null, 2);
                } catch {
                  return node.rawPayload;
                }
              })()}
            </pre>
          </div>
        )}

        {/* Similarity score */}
        {node.similarityScore !== undefined && (
          <div>
            <span className="text-gray-400">Similarity: </span>
            <span className="text-pink-400 font-medium">
              {Math.round(node.similarityScore * 100)}%
            </span>
          </div>
        )}

        {/* Schema mapping status */}
        {node.mappingStatus && (
          <div>
            <span className="text-gray-400">Mapping Status: </span>
            <span className={`font-medium ${
              node.mappingStatus === 'approved' ? 'text-green-400' :
              node.mappingStatus === 'rejected' ? 'text-red-400' :
              'text-yellow-400'
            }`}>
              {node.mappingStatus}
            </span>
          </div>
        )}

        {/* Confidence */}
        {node.confidence !== undefined && (
          <div>
            <span className="text-gray-400">Confidence: </span>
            <span className="text-purple-400 font-medium">
              {Math.round(node.confidence * 100)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
