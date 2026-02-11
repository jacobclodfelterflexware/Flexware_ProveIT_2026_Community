'use client';

import { useState } from 'react';
import { SchemaProposal, countSchemaFields } from '@/types/conformance';
import { deleteProposal } from '@/lib/conformance-api';
import BindTopicDialog from './BindTopicDialog';

interface Props {
  proposal: SchemaProposal;
  onRefresh: () => void;
}

export default function SchemaProposalCard({ proposal, onRefresh }: Props) {
  const [showSchema, setShowSchema] = useState(false);
  const [showBindDialog, setShowBindDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const { total: fieldCount, required: requiredCount } = countSchemaFields(proposal.expectedSchema);

  const handleDelete = async () => {
    if (!confirm(`Delete schema "${proposal.name}"? This will also remove all topic bindings.`)) {
      return;
    }

    setDeleting(true);
    try {
      const result = await deleteProposal(proposal.id);
      if ('success' in result && result.success) {
        onRefresh();
      } else {
        alert('error' in result ? result.error : 'Failed to delete');
      }
    } catch (err) {
      alert('Failed to delete schema');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-100 truncate" title={proposal.name}>
            {proposal.name}
          </h3>
          <p className="text-xs text-gray-500 truncate" title={proposal.folder}>
            {proposal.folder}
          </p>
        </div>
        <span className="text-xs text-gray-500 ml-2 flex-shrink-0">v{proposal.version}</span>
      </div>

      {/* Description */}
      {proposal.description && (
        <p className="text-sm text-gray-400 mb-3 line-clamp-2">{proposal.description}</p>
      )}

      {/* Stats */}
      <div className="flex gap-4 text-xs text-gray-500 mb-3">
        <span>{fieldCount} field{fieldCount !== 1 ? 's' : ''}</span>
        <span>{requiredCount} required</span>
        <span>
          {proposal.expectedSchema.additionalProperties ? 'Flexible' : 'Strict'}
        </span>
      </div>

      {/* Schema details (collapsible) */}
      {showSchema && (
        <div className="bg-gray-900 rounded p-3 mb-3 text-sm">
          <h4 className="text-xs text-gray-400 mb-2 uppercase tracking-wide">Expected Fields</h4>
          {Object.keys(proposal.expectedSchema.properties).length === 0 ? (
            <p className="text-gray-500 italic">No fields defined</p>
          ) : (
            <div className="space-y-1 font-mono text-xs">
              {Object.entries(proposal.expectedSchema.properties).map(([key, field]) => (
                <div key={key} className="flex items-center">
                  <span className={field.required ? 'text-red-400' : 'text-gray-300'}>
                    {key}
                  </span>
                  <span className="text-gray-600 mx-1">:</span>
                  <span className="text-blue-400">{field.type}</span>
                  {field.required && (
                    <span className="text-red-400 text-xs ml-1">*</span>
                  )}
                </div>
              ))}
            </div>
          )}
          {!proposal.expectedSchema.additionalProperties && (
            <p className="text-xs text-yellow-500 mt-2">
              No additional fields allowed
            </p>
          )}
        </div>
      )}

      {/* Bound topics count */}
      {proposal.boundTopics && proposal.boundTopics.length > 0 && (
        <p className="text-xs text-purple-400 mb-3">
          Bound to {proposal.boundTopics.length} topic{proposal.boundTopics.length !== 1 ? 's' : ''}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setShowSchema(!showSchema)}
          className="px-3 py-1.5 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600 transition-colors"
        >
          {showSchema ? 'Hide' : 'Show'} Schema
        </button>
        <button
          onClick={() => setShowBindDialog(true)}
          className="px-3 py-1.5 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
        >
          Bind to Topic
        </button>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="px-3 py-1.5 text-xs bg-red-900/50 text-red-400 rounded hover:bg-red-900 transition-colors disabled:opacity-50"
        >
          {deleting ? 'Deleting...' : 'Delete'}
        </button>
      </div>

      {/* Bind Dialog */}
      {showBindDialog && (
        <BindTopicDialog
          proposal={proposal}
          onClose={() => setShowBindDialog(false)}
          onBound={() => {
            setShowBindDialog(false);
            onRefresh();
          }}
        />
      )}
    </div>
  );
}
