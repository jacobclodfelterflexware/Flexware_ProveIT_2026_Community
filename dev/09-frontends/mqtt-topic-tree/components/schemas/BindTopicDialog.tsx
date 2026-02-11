'use client';

import { useState, useEffect } from 'react';
import { SchemaProposal } from '@/types/conformance';
import { createBinding } from '@/lib/conformance-api';

interface Props {
  proposal: SchemaProposal;
  onClose: () => void;
  onBound: () => void;
}

export default function BindTopicDialog({ proposal, onClose, onBound }: Props) {
  const [topicPath, setTopicPath] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch topic suggestions from the SSE-cached topic tree
  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const response = await fetch('/api/topics/list');
        if (response.ok) {
          const data = await response.json();
          setSuggestions(data.topics || []);
        }
      } catch (err) {
        // Silently fail - suggestions are optional
        console.warn('Could not fetch topic suggestions');
      }
    };
    fetchTopics();
  }, []);

  const filteredSuggestions = suggestions.filter(
    (topic) => topic.toLowerCase().includes(topicPath.toLowerCase()) && topic !== topicPath
  ).slice(0, 10);

  const handleBind = async () => {
    if (!topicPath.trim()) {
      setError('Topic path is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const result = await createBinding({
        topicPath: topicPath.trim(),
        proposalId: proposal.id,
      });

      if ('success' in result && result.success) {
        onBound();
      } else {
        setError('error' in result ? result.error : 'Failed to create binding');
      }
    } catch (err) {
      setError('Failed to create binding');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-lg border border-gray-700">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-100">Bind Schema to Topic</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Schema info */}
          <div className="bg-gray-900 rounded-lg p-4">
            <p className="text-sm text-gray-400">Binding schema:</p>
            <p className="text-gray-100 font-medium">{proposal.name}</p>
            <p className="text-xs text-gray-500">{proposal.folder}</p>
          </div>

          {/* Topic path input */}
          <div className="relative">
            <label className="block text-sm font-medium text-gray-300 mb-1">
              Topic Path *
            </label>
            <input
              type="text"
              value={topicPath}
              onChange={(e) => {
                setTopicPath(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              placeholder="e.g., client-001/sensors/temperature"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />

            {/* Autocomplete dropdown */}
            {showSuggestions && filteredSuggestions.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-gray-900 border border-gray-700 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {filteredSuggestions.map((topic) => (
                  <button
                    key={topic}
                    onClick={() => {
                      setTopicPath(topic);
                      setShowSuggestions(false);
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 truncate"
                  >
                    {topic}
                  </button>
                ))}
              </div>
            )}
          </div>

          <p className="text-xs text-gray-500">
            Messages published to this exact topic path will be validated against the schema.
            One topic can only be bound to one schema at a time.
          </p>

          {/* Error */}
          {error && (
            <div className="text-sm text-red-400 bg-red-900/30 border border-red-700 px-4 py-2 rounded">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-700 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 text-gray-200 rounded-lg hover:bg-gray-600"
          >
            Cancel
          </button>
          <button
            onClick={handleBind}
            disabled={saving || !topicPath.trim()}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Binding...' : 'Bind Schema'}
          </button>
        </div>
      </div>
    </div>
  );
}
