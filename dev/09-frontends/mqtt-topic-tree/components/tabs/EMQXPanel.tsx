'use client';

import { useState } from 'react';

export default function EMQXPanel() {
  const [isLoading, setIsLoading] = useState(true);
  const [selectedBroker, setSelectedBroker] = useState<'uncurated' | 'curated'>('uncurated');

  // Use environment variable or fallback to default
  const emqxUrl = selectedBroker === 'curated'
    ? (process.env.NEXT_PUBLIC_EMQX_CURATED_URL || 'http://YOUR_HOSTNAME:31084')
    : (process.env.NEXT_PUBLIC_EMQX_DASHBOARD_URL || 'http://YOUR_HOSTNAME:31083');

  return (
    <div className="h-full flex flex-col">
      {/* Header Bar */}
      <div className="bg-gray-800 rounded-t-lg border border-gray-700 px-4 py-2 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-gray-300 text-sm font-medium">EMQX Dashboard</span>
          </div>
          <select
            value={selectedBroker}
            onChange={(e) => {
              setSelectedBroker(e.target.value as 'uncurated' | 'curated');
              setIsLoading(true);
            }}
            className="bg-gray-700 border border-gray-600 text-gray-300 rounded px-2 py-1 text-xs"
          >
            <option value="uncurated">Uncurated Broker</option>
            <option value="curated">Curated Broker</option>
          </select>
        </div>
        <div className="flex items-center gap-4">
          <a
            href={emqxUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-sm transition-colors"
          >
            <span>Open in new tab</span>
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </div>

      {/* Iframe Container - fills remaining space */}
      <div className="flex-1 bg-gray-900 rounded-b-lg border-x border-b border-gray-700 relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900 z-10">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
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
