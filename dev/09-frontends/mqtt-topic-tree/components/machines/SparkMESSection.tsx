'use client';

import { useState, useEffect, useRef } from 'react';
import type { SparkMESStructure, SparkMESTag } from '@/types/machines';

interface SparkMESSectionProps {
  sparkmes: SparkMESStructure;
  machineId?: string;
  isRunning?: boolean;
}

// Format value for display
function formatValue(value: unknown): string {
  if (value === undefined || value === null) {
    return '—';
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'string') {
    return value === '' ? '""' : `"${value}"`;
  }
  return String(value);
}

// Get value color class based on type
function getValueColor(value: unknown): string {
  if (value === undefined || value === null) {
    return 'text-gray-500';
  }
  if (typeof value === 'boolean') {
    return value ? 'text-green-400' : 'text-red-400';
  }
  if (typeof value === 'number') {
    return 'text-blue-400';
  }
  return 'text-amber-400';
}

// Recursive tag node component
function TagNode({ tag, depth = 0 }: { tag: SparkMESTag; depth?: number }) {
  const [expanded, setExpanded] = useState(true);
  const isFolder = tag.tagType === 'Folder' && tag.tags && tag.tags.length > 0;
  const indent = depth * 20;

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1 hover:bg-gray-700/30 rounded px-2 -mx-2"
        style={{ paddingLeft: `${indent + 8}px` }}
      >
        {isFolder ? (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-400 hover:text-gray-200 focus:outline-none"
          >
            <svg
              className={`w-4 h-4 transition-transform ${expanded ? 'rotate-90' : ''}`}
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

        {/* Icon */}
        {isFolder ? (
          <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
            />
          </svg>
        ) : (
          <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
            />
          </svg>
        )}

        {/* Name */}
        <span className="text-gray-200 font-mono text-sm">{tag.name}</span>

        {/* Value (for AtomicTag) */}
        {!isFolder && tag.value !== undefined && (
          <>
            <span className="text-gray-500">:</span>
            <span className={`font-mono text-sm ${getValueColor(tag.value)}`}>
              {formatValue(tag.value)}
            </span>
          </>
        )}

        {/* Tag type badge */}
        <span className="text-xs text-gray-500 ml-auto">
          {tag.tagType}
        </span>
      </div>

      {/* Children */}
      {isFolder && expanded && tag.tags && (
        <div>
          {tag.tags.map((childTag, index) => (
            <TagNode key={`${childTag.name}-${index}`} tag={childTag} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SparkMESSection({ sparkmes, machineId, isRunning }: SparkMESSectionProps) {
  const [liveSparkmes, setLiveSparkmes] = useState<SparkMESStructure | null>(null);
  const [expanded, setExpanded] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Subscribe to live stream when machine is running
  useEffect(() => {
    if (!isRunning || !machineId) {
      setLiveSparkmes(null);
      return;
    }

    const eventSource = new EventSource(`/api/machines-proxy/${machineId}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'sparkmes' && data.payload) {
          setLiveSparkmes(data.payload);
        }
      } catch (e) {
        console.error('Failed to parse SparkMES stream data:', e);
      }
    };

    eventSource.onerror = () => {
      // Stream ended or errored, will reconnect automatically
      setLiveSparkmes(null);
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [machineId, isRunning]);

  // Use live data if available, otherwise fall back to template
  const displaySparkmes = liveSparkmes || sparkmes;
  const parameters = Object.entries(displaySparkmes.parameters || {});

  return (
    <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="text-left">
            <h2 className="text-lg font-semibold text-gray-100">SparkMES Configuration</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              {displaySparkmes.name} <span className="text-gray-600">•</span> {displaySparkmes.typeId}
            </p>
          </div>
        </div>
        {isRunning && liveSparkmes && (
          <span className="flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            Live
          </span>
        )}
      </button>

      {/* Collapsible Content */}
      {expanded && (
        <div className="p-4 border-t border-gray-700">
          {/* Parameters Table */}
          {parameters.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-300 mb-2">Parameters</h3>
              <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Name
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Type
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {parameters.map(([name, param]) => (
                      <tr key={name}>
                        <td className="px-4 py-2 font-mono text-gray-200">{name}</td>
                        <td className="px-4 py-2 text-gray-400">{param.dataType}</td>
                        <td className={`px-4 py-2 font-mono ${getValueColor(param.value)}`}>
                          {formatValue(param.value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tags Tree */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">Tags</h3>
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-3">
              {displaySparkmes.tags && displaySparkmes.tags.length > 0 ? (
                <div className="space-y-0.5">
                  {displaySparkmes.tags.map((tag, index) => (
                    <TagNode key={`${tag.name}-${index}`} tag={tag} />
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm">No tags defined</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
