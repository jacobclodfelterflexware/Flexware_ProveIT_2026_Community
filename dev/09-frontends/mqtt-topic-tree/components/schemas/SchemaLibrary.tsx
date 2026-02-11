'use client';

import { useState, useEffect } from 'react';
import { SchemaProposal } from '@/types/conformance';
import { fetchProposals } from '@/lib/conformance-api';
import SchemaProposalCard from './SchemaProposalCard';
import CreateSchemaDialog from './CreateSchemaDialog';

export default function SchemaLibrary() {
  const [proposals, setProposals] = useState<SchemaProposal[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProposals = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchProposals({
        folder: selectedFolder || undefined,
        search: searchQuery || undefined,
      });
      setProposals(data.proposals);
      setFolders(data.folders || []);
    } catch (err) {
      setError('Failed to load schemas');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProposals();
  }, [selectedFolder, searchQuery]);

  return (
    <div className="flex h-full bg-gray-900">
      {/* Folder sidebar */}
      <div className="w-56 border-r border-gray-700 p-4 flex-shrink-0">
        <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wide">
          Folders
        </h3>
        <ul className="space-y-1">
          <li>
            <button
              onClick={() => setSelectedFolder(null)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                !selectedFolder
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              All Schemas
            </button>
          </li>
          {folders.map((folder) => (
            <li key={folder}>
              <button
                onClick={() => setSelectedFolder(folder)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
                  selectedFolder === folder
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800'
                }`}
                title={folder}
              >
                {folder}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-100">Schema Library</h1>
            <p className="text-sm text-gray-400 mt-1">
              {selectedFolder ? `Folder: ${selectedFolder}` : 'All schemas'}
              {' · '}
              {proposals.length} schema{proposals.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create Schema
          </button>
        </div>

        {/* Search */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search schemas by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Content */}
        {loading ? (
          <div className="text-center py-12 text-gray-400">
            <svg className="animate-spin h-8 w-8 mx-auto mb-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Loading schemas...
          </div>
        ) : error ? (
          <div className="text-center py-12 text-red-400">
            <p>{error}</p>
            <button
              onClick={loadProposals}
              className="mt-4 px-4 py-2 bg-gray-700 rounded-lg hover:bg-gray-600"
            >
              Retry
            </button>
          </div>
        ) : proposals.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-lg">No schemas found</p>
            <p className="text-sm mt-1">
              {searchQuery
                ? 'Try a different search term'
                : 'Create your first schema to get started'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {proposals.map((proposal) => (
              <SchemaProposalCard
                key={proposal.id}
                proposal={proposal}
                onRefresh={loadProposals}
              />
            ))}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {showCreateDialog && (
        <CreateSchemaDialog
          onClose={() => setShowCreateDialog(false)}
          onCreated={() => {
            setShowCreateDialog(false);
            loadProposals();
          }}
        />
      )}
    </div>
  );
}
