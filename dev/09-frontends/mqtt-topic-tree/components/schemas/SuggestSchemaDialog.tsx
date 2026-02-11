'use client';

import { useState, useEffect } from 'react';
import { createProposal, createBinding } from '@/lib/conformance-api';
import { FieldType, ExpectedSchema, FieldSchema } from '@/types/conformance';

interface SimilarMessage {
  topicPath: string;
  payload: string;
  similarity: number;
  boundProposalId: string | null;
  boundProposalName: string | null;
}

interface SuggestedField {
  name: string;
  type: string;
  required: boolean;
  source: 'similar' | 'payload' | 'removed';
}

interface SuggestionResponse {
  similarMessages: SimilarMessage[];
  suggestedSchema: {
    fields: SuggestedField[];
    basedOn: 'similar_schema' | 'payload_analysis' | 'no_data';
    similarSchemaId?: string;
    similarSchemaName?: string;
    confidence: 'high' | 'medium' | 'low';
    similarity: number;
  };
  payloadFields: Array<{ name: string; type: string; value: unknown }>;
}

interface Props {
  topicPath: string;
  payload?: string;
  onClose: () => void;
  onCreated: () => void;
}

const CONFIDENCE_COLORS = {
  high: 'bg-green-600 text-white',
  medium: 'bg-yellow-600 text-white',
  low: 'bg-red-600 text-white',
};

const SOURCE_COLORS = {
  similar: 'text-green-400',
  payload: 'text-blue-400',
  removed: 'text-red-400 line-through',
};

export default function SuggestSchemaDialog({ topicPath, payload, onClose, onCreated }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<SuggestionResponse | null>(null);

  // Editable schema name
  const [schemaName, setSchemaName] = useState('');
  const [folder, setFolder] = useState('default');

  // Fields that will be included in the schema (excluding 'removed' ones)
  const [selectedFields, setSelectedFields] = useState<SuggestedField[]>([]);

  const [saving, setSaving] = useState(false);
  const [bindAfterCreate, setBindAfterCreate] = useState(true);

  useEffect(() => {
    const fetchSuggestion = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch('/api/schemas/suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topicPath, payload }),
        });

        if (!response.ok) {
          throw new Error('Failed to get suggestion');
        }

        const data: SuggestionResponse = await response.json();
        setSuggestion(data);

        // Initialize selected fields (exclude 'removed' by default)
        setSelectedFields(data.suggestedSchema.fields.filter(f => f.source !== 'removed'));

        // Generate a default schema name from the topic path
        const segments = topicPath.split('/');
        const lastSegment = segments[segments.length - 1] || 'Schema';
        setSchemaName(lastSegment.charAt(0).toUpperCase() + lastSegment.slice(1));

        // Use topic path as folder hint
        if (segments.length > 2) {
          setFolder(segments.slice(0, -1).join('/'));
        }
      } catch (err) {
        setError('Failed to analyze topic');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchSuggestion();
  }, [topicPath, payload]);

  const toggleField = (fieldName: string) => {
    const field = suggestion?.suggestedSchema.fields.find(f => f.name === fieldName);
    if (!field) return;

    const isSelected = selectedFields.some(f => f.name === fieldName);
    if (isSelected) {
      setSelectedFields(selectedFields.filter(f => f.name !== fieldName));
    } else {
      setSelectedFields([...selectedFields, field]);
    }
  };

  const handleCreate = async () => {
    if (!schemaName.trim()) {
      setError('Schema name is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      // Build the expected schema
      const properties: Record<string, FieldSchema> = {};
      for (const field of selectedFields) {
        properties[field.name] = {
          type: field.type as FieldType,
          required: field.required,
        };
      }

      const expectedSchema: ExpectedSchema = {
        type: 'object',
        properties,
        additionalProperties: false,
      };

      // Create the proposal
      const result = await createProposal({
        name: schemaName.trim(),
        folder: folder.trim() || 'default',
        expectedSchema,
      });

      if (!('success' in result) || !result.success) {
        setError('error' in result ? result.error : 'Failed to create schema');
        return;
      }

      // Optionally bind to the topic
      if (bindAfterCreate && result.id) {
        const bindResult = await createBinding({
          topicPath,
          proposalId: result.id,
        });

        if (!('success' in bindResult) || !bindResult.success) {
          // Schema created but binding failed - warn but don't fail
          console.warn('Schema created but binding failed:', bindResult);
        }
      }

      onCreated();
    } catch (err) {
      setError('Failed to create schema');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-gray-700">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-100">Suggest Schema</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="text-center py-12 text-gray-400">
              <svg className="animate-spin h-8 w-8 mx-auto mb-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Analyzing topic...
            </div>
          ) : error && !suggestion ? (
            <div className="text-center py-12 text-red-400">{error}</div>
          ) : suggestion ? (
            <>
              {/* Topic Info */}
              <div className="bg-gray-900 rounded-lg p-4">
                <p className="text-sm text-gray-400">Topic Path</p>
                <p className="font-mono text-gray-200 text-sm break-all">{topicPath}</p>
              </div>

              {/* Similar Messages */}
              {suggestion.similarMessages.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-300 mb-2">
                    Similar Messages ({suggestion.similarMessages.length} found)
                  </h3>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {suggestion.similarMessages.slice(0, 5).map((msg, idx) => (
                      <div key={idx} className="bg-gray-900 rounded p-3 text-sm">
                        <div className="flex justify-between items-start mb-1">
                          <span className="font-mono text-gray-300 text-xs truncate flex-1">
                            {msg.topicPath}
                          </span>
                          <span className="text-blue-400 text-xs ml-2">
                            {Math.round(msg.similarity * 100)}%
                          </span>
                        </div>
                        {msg.boundProposalName && (
                          <span className="text-xs text-purple-400">
                            Schema: {msg.boundProposalName}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Suggested Schema */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-gray-300">Suggested Schema</h3>
                  <span className={`px-2 py-0.5 rounded text-xs ${CONFIDENCE_COLORS[suggestion.suggestedSchema.confidence]}`}>
                    {suggestion.suggestedSchema.confidence.charAt(0).toUpperCase() + suggestion.suggestedSchema.confidence.slice(1)} Confidence
                  </span>
                </div>

                {suggestion.suggestedSchema.basedOn === 'similar_schema' && (
                  <p className="text-xs text-gray-500 mb-3">
                    Based on schema "{suggestion.suggestedSchema.similarSchemaName}" ({Math.round(suggestion.suggestedSchema.similarity * 100)}% similar)
                  </p>
                )}

                {suggestion.suggestedSchema.basedOn === 'payload_analysis' && (
                  <p className="text-xs text-yellow-500 mb-3">
                    No similar schema found. Inferred from payload structure.
                  </p>
                )}

                {/* Schema Name & Folder */}
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Schema Name *</label>
                    <input
                      type="text"
                      value={schemaName}
                      onChange={(e) => setSchemaName(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Folder</label>
                    <input
                      type="text"
                      value={folder}
                      onChange={(e) => setFolder(e.target.value)}
                      className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                {/* Fields */}
                <div className="bg-gray-900 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-2">
                    Fields (click to toggle inclusion)
                  </p>
                  {suggestion.suggestedSchema.fields.length === 0 ? (
                    <p className="text-gray-500 italic text-sm">No fields detected</p>
                  ) : (
                    <div className="space-y-1">
                      {suggestion.suggestedSchema.fields.map((field) => {
                        const isSelected = selectedFields.some(f => f.name === field.name);
                        return (
                          <div
                            key={field.name}
                            onClick={() => toggleField(field.name)}
                            className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
                              isSelected ? 'bg-gray-800' : 'bg-gray-900 opacity-50'
                            } hover:bg-gray-700`}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                            />
                            <span className={`font-mono text-sm ${SOURCE_COLORS[field.source]}`}>
                              {field.name}
                            </span>
                            <span className="text-gray-600">:</span>
                            <span className="text-blue-400 text-sm">{field.type}</span>
                            {field.required && (
                              <span className="text-red-400 text-xs">*required</span>
                            )}
                            {field.source === 'removed' && (
                              <span className="text-xs text-red-400 ml-auto">(not in similar schema)</span>
                            )}
                            {field.source === 'similar' && (
                              <span className="text-xs text-green-400 ml-auto">(from similar)</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Payload Preview */}
                {suggestion.payloadFields.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs text-gray-400 mb-2">Current Payload Fields</p>
                    <div className="bg-gray-900 rounded p-3 font-mono text-xs text-gray-400">
                      {suggestion.payloadFields.map((f, idx) => (
                        <div key={idx}>
                          <span className="text-gray-300">{f.name}</span>
                          <span className="text-gray-600">: </span>
                          <span className="text-green-400">{JSON.stringify(f.value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Bind option */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="bindAfterCreate"
                  checked={bindAfterCreate}
                  onChange={(e) => setBindAfterCreate(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                />
                <label htmlFor="bindAfterCreate" className="text-sm text-gray-300">
                  Bind this schema to <span className="font-mono text-purple-400">{topicPath}</span> after creation
                </label>
              </div>

              {/* Error */}
              {error && (
                <div className="text-sm text-red-400 bg-red-900/30 border border-red-700 px-4 py-2 rounded">
                  {error}
                </div>
              )}
            </>
          ) : null}
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
            onClick={handleCreate}
            disabled={saving || loading || !suggestion || selectedFields.length === 0}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Creating...' : 'Create Schema'}
          </button>
        </div>
      </div>
    </div>
  );
}
