'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { MachineDefinition, MachineStatus } from '@/types/machines';
import { startMachine, stopMachine, deleteMachine } from '@/lib/machines-api';

interface MachineCardProps {
  machine: MachineDefinition;
  onStartStop?: () => void;
  onDelete?: () => void;
}

const statusColors: Record<MachineStatus, string> = {
  draft: 'bg-yellow-500',
  running: 'bg-green-500',
};

const statusLabels: Record<MachineStatus, string> = {
  draft: 'Draft',
  running: 'Running',
};

export default function MachineCard({
  machine,
  onStartStop,
  onDelete,
}: MachineCardProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCardClick = (e: React.MouseEvent) => {
    // Prevent navigation when clicking on action buttons
    if ((e.target as HTMLElement).closest('button')) return;
    if (machine.id) {
      router.push(`/machines/${machine.id}`);
    }
  };

  const handleStartStop = async () => {
    if (!machine.id) return;
    setLoading(true);
    setError(null);

    try {
      if (machine.status === 'running') {
        await stopMachine(machine.id);
      } else {
        await startMachine(machine.id);
      }
      onStartStop?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!machine.id) return;
    if (!confirm(`Delete machine "${machine.name}"?`)) return;

    setLoading(true);
    setError(null);

    try {
      await deleteMachine(machine.id);
      onDelete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      onClick={handleCardClick}
      className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden hover:border-gray-600 hover:bg-gray-750 cursor-pointer transition-colors">
      {/* Machine Image */}
      {machine.image_base64 ? (
        <div className="relative h-40 bg-gray-900">
          <img
            src={`data:image/png;base64,${machine.image_base64}`}
            alt={machine.machine_type || machine.name}
            className="w-full h-full object-cover"
          />
          {/* Status Badge Overlay */}
          <div className="absolute top-2 right-2 flex items-center gap-1.5 bg-gray-900/80 px-2 py-1 rounded-full">
            <span className={`w-2 h-2 rounded-full ${statusColors[machine.status]}`} />
            <span className="text-xs text-gray-200">{statusLabels[machine.status]}</span>
          </div>
        </div>
      ) : (
        <div className="h-32 bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center">
          <svg className="w-12 h-12 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
          </svg>
        </div>
      )}

      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="text-lg font-semibold text-gray-100">{machine.name}</h3>
            {machine.machine_type && (
              <span className="text-sm text-gray-400">{machine.machine_type}</span>
            )}
            {machine.smprofile && (
              <span className="inline-flex items-center gap-1 text-xs text-teal-400 mt-0.5">
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                CESMII
              </span>
            )}
          </div>
          {!machine.image_base64 && (
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${statusColors[machine.status]}`} />
              <span className="text-sm text-gray-300">{statusLabels[machine.status]}</span>
            </div>
          )}
        </div>

        {/* Description */}
        {machine.description && (
          <p className="text-sm text-gray-400 mb-3 line-clamp-2">
            {machine.description}
          </p>
        )}

        {/* Topics */}
        <div className="mb-3">
          <span className="text-xs text-gray-500">
            {machine.topics && machine.topics.length > 0 ? `Topics (${machine.topics.length}):` : 'Topic:'}
          </span>
          {machine.topics && machine.topics.length > 0 ? (
            <div className="mt-1 space-y-1 max-h-24 overflow-y-auto">
              {machine.topics.map((topic, idx) => (
                <div key={idx} className="text-xs font-mono text-gray-300 truncate bg-gray-700/50 px-2 py-1 rounded">
                  {topic.topic_path.split('/').pop()}
                  <span className="text-gray-500 ml-1">({topic.fields?.length || 0} fields)</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm font-mono text-gray-300 truncate">
              {machine.topic_path || 'Not set'}
            </p>
          )}
        </div>

        {/* Fields summary */}
        <div className="flex gap-4 mb-3 text-sm">
          <div>
            <span className="text-gray-500">Fields:</span>
            <span className="ml-1 text-gray-300">
              {machine.topics && machine.topics.length > 0
                ? machine.topics.reduce((sum, t) => sum + (t.fields?.length || 0), 0)
                : machine.fields?.length || 0}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Interval:</span>
            <span className="ml-1 text-gray-300">
              {machine.publish_interval_ms}ms
            </span>
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-red-400 mb-3">{error}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2 mt-4 pt-3 border-t border-gray-700">
          <button
            onClick={handleStartStop}
            disabled={loading}
            className={`flex-1 px-3 py-1.5 text-white text-sm rounded transition-colors disabled:opacity-50 ${
              machine.status === 'running'
                ? 'bg-orange-600 hover:bg-orange-700'
                : 'bg-green-600 hover:bg-green-700'
            }`}
          >
            {loading ? '...' : machine.status === 'running' ? 'Stop' : 'Start'}
          </button>
          <button
            onClick={handleDelete}
            disabled={loading}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded transition-colors disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
