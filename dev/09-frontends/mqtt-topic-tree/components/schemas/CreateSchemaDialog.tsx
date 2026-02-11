'use client';

import { useState } from 'react';
import { ExpectedSchema, FieldType, createEmptySchema, addFieldToSchema } from '@/types/conformance';
import { createProposal } from '@/lib/conformance-api';

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

const FIELD_TYPES: FieldType[] = ['string', 'number', 'integer', 'boolean', 'array', 'object', 'null'];

export default function CreateSchemaDialog({ onClose, onCreated }: Props) {
  const [name, setName] = useState('');
  const [folder, setFolder] = useState('default');
  const [description, setDescription] = useState('');
  const [additionalProperties, setAdditionalProperties] = useState(false);
  const [fields, setFields] = useState<Array<{ name: string; type: FieldType; required: boolean }>>([]);
  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldType, setNewFieldType] = useState<FieldType>('string');
  const [newFieldRequired, setNewFieldRequired] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addField = () => {
    if (!newFieldName.trim()) return;
    if (fields.some(f => f.name === newFieldName.trim())) {
      setError('Field name already exists');
      return;
    }

    setFields([...fields, {
      name: newFieldName.trim(),
      type: newFieldType,
      required: newFieldRequired
    }]);
    setNewFieldName('');
    setNewFieldType('string');
    setNewFieldRequired(true);
    setError(null);
  };

  const removeField = (index: number) => {
    setFields(fields.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    // Build schema
    let schema = createEmptySchema();
    schema.additionalProperties = additionalProperties;
    for (const field of fields) {
      schema = addFieldToSchema(schema, field.name, field.type, field.required);
    }

    setSaving(true);
    setError(null);

    try {
      const result = await createProposal({
        name: name.trim(),
        folder: folder.trim() || 'default',
        description: description.trim() || undefined,
        expectedSchema: schema
      });

      if ('success' in result && result.success) {
        onCreated();
      } else {
        setError('error' in result ? result.error : 'Failed to create schema');
      }
    } catch (err) {
      setError('Failed to create schema');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-gray-700">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-100">Create Schema Proposal</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., TemperatureSensor"
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">Folder</label>
              <input
                type="text"
                value={folder}
                onChange={(e) => setFolder(e.target.value)}
                placeholder="e.g., manufacturing/sensors"
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description of this schema..."
              rows={2}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>

          {/* Strict mode toggle */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="additionalProperties"
              checked={additionalProperties}
              onChange={(e) => setAdditionalProperties(e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            <label htmlFor="additionalProperties" className="text-sm text-gray-300">
              Allow additional properties (non-strict mode)
            </label>
          </div>

          {/* Fields */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Expected Fields</label>

            {/* Existing fields */}
            {fields.length > 0 && (
              <div className="space-y-2 mb-4">
                {fields.map((field, index) => (
                  <div key={index} className="flex items-center gap-2 bg-gray-900 rounded-lg p-2">
                    <span className={`font-mono text-sm ${field.required ? 'text-red-400' : 'text-gray-300'}`}>
                      {field.name}
                    </span>
                    <span className="text-gray-600">:</span>
                    <span className="text-blue-400 text-sm">{field.type}</span>
                    {field.required && <span className="text-red-400 text-xs">*required</span>}
                    <button
                      onClick={() => removeField(index)}
                      className="ml-auto text-gray-500 hover:text-red-400"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Add new field */}
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <input
                  type="text"
                  value={newFieldName}
                  onChange={(e) => setNewFieldName(e.target.value)}
                  placeholder="Field name"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                  onKeyDown={(e) => e.key === 'Enter' && addField()}
                />
              </div>
              <div className="w-28">
                <select
                  value={newFieldType}
                  onChange={(e) => setNewFieldType(e.target.value as FieldType)}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                >
                  {FIELD_TYPES.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-1 text-sm text-gray-400">
                <input
                  type="checkbox"
                  checked={newFieldRequired}
                  onChange={(e) => setNewFieldRequired(e.target.checked)}
                  className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded"
                />
                Req
              </label>
              <button
                onClick={addField}
                className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                Add
              </button>
            </div>
          </div>

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
            onClick={handleSave}
            disabled={saving || !name.trim()}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Creating...' : 'Create Schema'}
          </button>
        </div>
      </div>
    </div>
  );
}
