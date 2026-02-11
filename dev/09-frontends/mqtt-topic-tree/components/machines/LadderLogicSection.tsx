'use client';

import { useState, useEffect, useCallback } from 'react';
import type { MachineDefinition, LadderLogicData } from '@/types/machines';
import {
  getLadderLogic,
  loadLadderProgram,
  startLadderSimulator,
  stopLadderSimulator,
} from '@/lib/machines-api';

interface LadderLogicSectionProps {
  machine: MachineDefinition;
}

export default function LadderLogicSection({ machine }: LadderLogicSectionProps) {
  const [ladderData, setLadderData] = useState<LadderLogicData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [simulatorRunning, setSimulatorRunning] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);
  const [expanded, setExpanded] = useState(false);

  // Load ladder logic and start simulator
  const loadAndStartLadder = useCallback(async () => {
    if (!machine.id) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch ladder logic from Neo4j
      const data = await getLadderLogic(machine.id);

      if (!data) {
        setLoading(false);
        return; // No ladder logic stored for this machine
      }

      setLadderData(data);

      // Load the ladder program into PLCOpen
      await loadLadderProgram(data.rungs);

      // Start the simulator
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1); // Force iframe refresh

    } catch (err) {
      console.error('Failed to load/start ladder:', err);
      setError(err instanceof Error ? err.message : 'Failed to load ladder logic');
    } finally {
      setLoading(false);
    }
  }, [machine.id]);

  // Stop simulator on unmount
  useEffect(() => {
    return () => {
      if (simulatorRunning) {
        stopLadderSimulator().catch(console.error);
      }
    };
  }, [simulatorRunning]);

  // Load ladder when component mounts or machine changes
  useEffect(() => {
    loadAndStartLadder();
  }, [loadAndStartLadder]);

  const handleStop = async () => {
    try {
      await stopLadderSimulator();
      setSimulatorRunning(false);
    } catch (err) {
      console.error('Failed to stop simulator:', err);
    }
  };

  const handleRestart = async () => {
    if (!ladderData) return;

    try {
      await loadLadderProgram(ladderData.rungs);
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1);
    } catch (err) {
      console.error('Failed to restart simulator:', err);
    }
  };

  // Don't render if no ladder logic is available
  if (!loading && !ladderData) {
    return null;
  }

  return (
    <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-gray-400 hover:text-gray-200"
          >
            <svg
              className={`w-5 h-5 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
          <h2 className="text-lg font-semibold text-gray-100">Ladder Logic Visualization</h2>
          {simulatorRunning && (
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Running
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {simulatorRunning ? (
            <button
              onClick={handleStop}
              className="px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white text-sm rounded transition-colors"
            >
              Stop
            </button>
          ) : ladderData && (
            <button
              onClick={handleRestart}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-sm rounded transition-colors"
            >
              Start
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {expanded && (
        <div className="p-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500 mx-auto mb-3" />
                <p className="text-gray-400">Loading ladder logic...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-900/20 border border-red-600/50 rounded-lg">
              <p className="text-red-400">{error}</p>
              <button
                onClick={loadAndStartLadder}
                className="mt-2 text-sm text-red-300 underline hover:text-red-200"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && ladderData && (
            <div className="space-y-4">
              {/* I/O Summary */}
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-gray-900 rounded p-3 border border-gray-700">
                  <span className="text-xs text-gray-500 uppercase">Rungs</span>
                  <p className="text-xl font-semibold text-gray-100">{ladderData.rungs.length}</p>
                </div>
                <div className="bg-gray-900 rounded p-3 border border-gray-700">
                  <span className="text-xs text-green-400 uppercase">Inputs</span>
                  <p className="text-xl font-semibold text-gray-100">
                    {ladderData.io_mapping.inputs.length}
                  </p>
                </div>
                <div className="bg-gray-900 rounded p-3 border border-gray-700">
                  <span className="text-xs text-red-400 uppercase">Outputs</span>
                  <p className="text-xl font-semibold text-gray-100">
                    {ladderData.io_mapping.outputs.length}
                  </p>
                </div>
                <div className="bg-gray-900 rounded p-3 border border-gray-700">
                  <span className="text-xs text-yellow-400 uppercase">Internal</span>
                  <p className="text-xl font-semibold text-gray-100">
                    {ladderData.io_mapping.internal.length}
                  </p>
                </div>
              </div>

              {/* Rationale */}
              {ladderData.rationale && (
                <div className="p-3 bg-gray-900 rounded border border-gray-700">
                  <span className="text-xs text-gray-500 uppercase">Design Rationale</span>
                  <p className="text-sm text-gray-300 mt-1">{ladderData.rationale}</p>
                </div>
              )}

              {/* Live Simulator View */}
              <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                <div className="px-3 py-2 border-b border-gray-700 flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-300">Live Simulation</span>
                  {ladderData.created_at && (
                    <span className="text-xs text-gray-500">
                      Generated: {new Date(ladderData.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className="relative" style={{ height: '500px' }}>
                  {simulatorRunning ? (
                    <iframe
                      key={iframeKey}
                      src="/api/plcopen/simulate/ladder/render/simple"
                      className="w-full h-full border-0"
                      title="Ladder Logic Simulator"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-gray-950">
                      <div className="text-center">
                        <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <p className="text-gray-400">Simulator stopped</p>
                        <button
                          onClick={handleRestart}
                          className="mt-3 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition-colors"
                        >
                          Start Simulation
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Collapsed summary */}
      {!expanded && ladderData && (
        <div className="px-4 py-2 text-sm text-gray-400">
          {ladderData.rungs.length} rungs | {ladderData.io_mapping.inputs.length} inputs | {ladderData.io_mapping.outputs.length} outputs
          {simulatorRunning && ' | Click to view live simulation'}
        </div>
      )}
    </div>
  );
}
