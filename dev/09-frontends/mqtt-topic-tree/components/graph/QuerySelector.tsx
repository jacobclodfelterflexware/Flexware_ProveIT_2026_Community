'use client';

import { useState, useRef, useEffect } from 'react';

export interface PresetQuery {
  id: string;
  label: string;
  description: string;
  cypher: string;
}

export const PRESET_QUERIES: PresetQuery[] = [
  {
    id: 'all-topics',
    label: 'All Topics',
    description: 'Show all topic nodes',
    cypher: `MATCH (t:Topic {broker: $broker}) RETURN t LIMIT 200`,
  },
  {
    id: 'topics-with-messages',
    label: 'Topics with Messages',
    description: 'Topics and their recent messages',
    cypher: `
      MATCH (t:Topic {broker: $broker})-[r:HAS_MESSAGE]->(m:Message)
      WITH t, r, m ORDER BY m.timestamp DESC
      WITH t, collect({rel: r, msg: m})[0..3] as messages
      UNWIND messages as msg
      RETURN t, msg.rel, msg.msg
      LIMIT 500
    `,
  },
  {
    id: 'schema-mappings',
    label: 'Schema Mappings',
    description: 'Topics with their curated mappings',
    cypher: `
      MATCH (u:Topic {broker: "uncurated"})-[r:ROUTES_TO]->(c:Topic {broker: "curated"})
      RETURN u, r, c LIMIT 200
    `,
  },
  {
    id: 'machine-telemetry',
    label: 'Machine Telemetry',
    description: 'All topics related to machine data',
    cypher: `
      MATCH (t:Topic {broker: $broker})
      WHERE t.path CONTAINS 'telemetry' OR t.path CONTAINS 'state'
      OPTIONAL MATCH (t)-[r:HAS_MESSAGE]->(m:Message)
      WITH t, r, m ORDER BY m.timestamp DESC
      WITH t, collect({rel: r, msg: m})[0] as lastMsg
      RETURN t, lastMsg.rel, lastMsg.msg LIMIT 100
    `,
  },
  {
    id: 'recent-messages',
    label: 'Recent Messages',
    description: 'Most recent messages across all topics',
    cypher: `
      MATCH (t:Topic {broker: $broker})-[r:HAS_MESSAGE]->(m:Message)
      WITH t, r, m ORDER BY m.timestamp DESC LIMIT 50
      RETURN t, r, m
    `,
  },
  {
    id: 'high-traffic-topics',
    label: 'High Traffic Topics',
    description: 'Topics with most messages',
    cypher: `
      MATCH (t:Topic {broker: $broker})-[r:HAS_MESSAGE]->(m:Message)
      WITH t, count(m) as msgCount, collect({rel: r, msg: m})[0..3] as messages
      WHERE msgCount > 5
      ORDER BY msgCount DESC
      LIMIT 30
      UNWIND messages as msg
      RETURN t, msg.rel, msg.msg
    `,
  },
];

interface QuerySelectorProps {
  selectedQuery: PresetQuery | null;
  onSelect: (query: PresetQuery) => void;
  disabled?: boolean;
}

export default function QuerySelector({
  selectedQuery,
  onSelect,
  disabled = false,
}: QuerySelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={`
          flex items-center justify-between gap-2
          px-4 py-2 min-w-[200px]
          bg-gray-700 hover:bg-gray-600
          border border-gray-600 rounded-lg
          text-sm text-gray-200
          transition-colors
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        `}
      >
        <span>{selectedQuery?.label || 'Select a query...'}</span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="max-h-80 overflow-y-auto">
            {PRESET_QUERIES.map((query) => (
              <button
                key={query.id}
                onClick={() => {
                  onSelect(query);
                  setIsOpen(false);
                }}
                className={`
                  w-full px-4 py-3 text-left
                  hover:bg-gray-700 transition-colors
                  border-b border-gray-700 last:border-b-0
                  ${selectedQuery?.id === query.id ? 'bg-gray-700' : ''}
                `}
              >
                <div className="font-medium text-gray-200">{query.label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{query.description}</div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
