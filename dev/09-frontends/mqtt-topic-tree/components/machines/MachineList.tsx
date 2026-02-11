'use client';

import { useEffect, useState, useCallback } from 'react';
import type { MachineDefinition } from '@/types/machines';
import { listMachines } from '@/lib/machines-api';
import MachineCard from './MachineCard';

interface MachineListProps {
  refreshTrigger?: number;
}

export default function MachineList({ refreshTrigger }: MachineListProps) {
  const [machines, setMachines] = useState<MachineDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');

  const fetchMachines = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const status = filter === 'all' ? undefined : filter;
      const response = await listMachines(status);
      setMachines(response.machines);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load machines');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchMachines();
  }, [fetchMachines, refreshTrigger]);

  // Auto-refresh for running machines
  useEffect(() => {
    const hasRunning = machines.some(m => m.status === 'running');
    if (!hasRunning) return;

    const interval = setInterval(fetchMachines, 10000);
    return () => clearInterval(interval);
  }, [machines, fetchMachines]);

  return (
    <div>
      {/* Filter */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-2">
          {['all', 'draft', 'running'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                filter === f
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <button
          onClick={fetchMachines}
          disabled={loading}
          className="px-3 py-1 text-sm bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded p-4 mb-4">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* Machine Grid */}
      {loading && machines.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          Loading machines...
        </div>
      ) : machines.length === 0 ? (
        <div className="text-center text-gray-400 py-12">
          <p className="mb-2">No machines found</p>
          <p className="text-sm">Create a new machine to get started</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {machines.map((machine) => (
            <MachineCard
              key={machine.id}
              machine={machine}
              onStartStop={fetchMachines}
              onDelete={fetchMachines}
            />
          ))}
        </div>
      )}
    </div>
  );
}
