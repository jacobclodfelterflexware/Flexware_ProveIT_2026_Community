'use client';

import { useState } from 'react';

export default function EMQXCompactPanel() {
  const [isLoading, setIsLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);
  const [selectedBroker, setSelectedBroker] = useState<'uncurated' | 'curated'>('uncurated');

  // Use environment variable or fallback to default
  const emqxUrl = selectedBroker === 'curated'
    ? (process.env.NEXT_PUBLIC_EMQX_CURATED_URL || 'http://YOUR_HOSTNAME:31084')
    : (process.env.NEXT_PUBLIC_EMQX_DASHBOARD_URL || 'http://YOUR_HOSTNAME:31083');

  if (!isExpanded) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 mb-6">
        <button
          onClick={() => setIsExpanded(true)}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/50 transition-colors rounded-lg"
        >
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-green-500"></div>
            <span className="text-gray-300 font-medium">EMQX Broker Dashboard</span>
          </div>
          <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 mb-6 overflow-hidden shadow-xl">
      {/* Header */}
      <div className="bg-gray-900 px-4 py-2 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-gray-300 text-sm font-medium">EMQX Broker Dashboard</span>
          <select
            value={selectedBroker}
            onChange={(e) => {
              setSelectedBroker(e.target.value as 'uncurated' | 'curated');
              setIsLoading(true);
            }}
            className="bg-gray-700 border border-gray-600 text-gray-300 rounded px-2 py-0.5 text-xs"
          >
            <option value="uncurated">Uncurated</option>
            <option value="curated">Curated</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <a
            href={emqxUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs transition-colors"
          >
            <span>Open full</span>
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          <button
            onClick={() => setIsExpanded(false)}
            className="text-gray-400 hover:text-gray-200 transition-colors"
            title="Collapse"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Iframe */}
      <div className="relative" style={{ height: '400px' }}>
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
            <div className="flex flex-col items-center gap-3">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
              <span className="text-gray-400 text-sm">Loading EMQX Dashboard...</span>
            </div>
          </div>
        )}
        <iframe
          src={emqxUrl}
          className="w-full h-full border-0"
          title="EMQX Dashboard"
          onLoad={() => setIsLoading(false)}
          allow="fullscreen"
        />
      </div>
    </div>
  );
}
