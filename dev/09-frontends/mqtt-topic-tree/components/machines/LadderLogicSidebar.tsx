'use client';

import { useState, useEffect, useCallback } from 'react';
import type { MachineDefinition, LadderLogicData } from '@/types/machines';
import {
  getLadderLogic,
  loadLadderProgram,
  startLadderSimulator,
  stopLadderSimulator,
  setLadderIOValues,
  generateLadderLogic,
  saveLadderLogic,
} from '@/lib/machines-api';
import type { FieldDefinition } from '@/types/machines';

interface LadderLogicSidebarProps {
  machine: MachineDefinition;
}

const SIDEBAR_OPEN_KEY = 'ladder-logic-sidebar-open';

/**
 * Docked left sidebar for ladder logic visualization
 */
export default function LadderLogicSidebar({ machine }: LadderLogicSidebarProps) {
  const [ladderData, setLadderData] = useState<LadderLogicData | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasAttemptedLoad, setHasAttemptedLoad] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulatorRunning, setSimulatorRunning] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  // Load sidebar state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(SIDEBAR_OPEN_KEY);
      if (stored === 'true') {
        setIsOpen(true);
      }
    } catch (e) {
      // Ignore localStorage errors
    }
  }, []);

  // Save sidebar state to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_OPEN_KEY, String(isOpen));
    } catch (e) {
      // Ignore localStorage errors
    }
  }, [isOpen]);

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

  // Load ladder when sidebar opens (lazy load)
  useEffect(() => {
    if (isOpen && !hasAttemptedLoad) {
      setHasAttemptedLoad(true);
      loadAndStartLadder();
    }
  }, [isOpen, hasAttemptedLoad, loadAndStartLadder]);

  // Subscribe to machine telemetry stream and inject real values into PLCOpen
  useEffect(() => {
    if (!machine.id || !simulatorRunning || !isOpen) return;

    // Use the backend machine stream (same reliable source as the telemetry chart)
    const url = `/api/machines-proxy/${machine.id}/stream`;
    console.log('[Ladder Stream] Connecting to:', url);
    const eventSource = new EventSource(url);

    eventSource.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        // Only process telemetry events (skip sparkmes, stopped, etc.)
        if (data.type !== 'telemetry') return;

        // Extract the topic name (last segment of topic path)
        const topicName = data.topic?.split('/').pop();
        if (!topicName) return;

        // Get the value from payload - handle different formats
        let value: number | boolean | undefined;
        const payload = data.payload;

        if (payload?.value !== undefined) {
          value = payload.value;
        } else if (payload?.state !== undefined) {
          value = payload.state;
        } else if (typeof payload === 'object') {
          for (const v of Object.values(payload)) {
            if (typeof v === 'number' || typeof v === 'boolean') {
              value = v as number | boolean;
              break;
            }
          }
        }

        if (value !== undefined) {
          try {
            await setLadderIOValues({ [topicName]: value });
          } catch (ioErr) {
            console.error(`[Ladder Stream] Failed to inject ${topicName}:`, ioErr);
          }
        }
      } catch {
        // Ignore parsing errors for non-data messages
      }
    };

    eventSource.onerror = () => {
      // EventSource will auto-reconnect, no action needed
    };

    return () => {
      eventSource.close();
    };
  }, [machine.id, simulatorRunning, isOpen]);

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

  // Regenerate ladder logic using LLM with updated prompts
  const handleRegenerate = async () => {
    if (!machine.id || !machine.machine_type) return;

    setRegenerating(true);
    setError(null);

    try {
      // Stop simulator if running
      if (simulatorRunning) {
        await stopLadderSimulator();
        setSimulatorRunning(false);
      }

      // Collect fields for ladder generation
      let allFields: FieldDefinition[] = [];
      if (machine.topics && machine.topics.length > 0) {
        // Multi-topic: extract field names from topic paths (last segment)
        // Each topic represents one machine field (e.g., "hvac-01/inlet_temperature" → "inlet_temperature")
        for (const topic of machine.topics) {
          const topicName = topic.topic_path.split('/').pop() || topic.topic_path;
          // Find the "value" field to get its type, or default to number
          const valueField = topic.fields.find(f => f.name === 'value');
          const stateField = topic.fields.find(f => f.name === 'state');

          allFields.push({
            name: topicName,
            type: stateField ? 'boolean' : (valueField?.type || 'number'),
            min_value: valueField?.min_value,
            max_value: valueField?.max_value,
          });
        }
      } else if (machine.fields && machine.fields.length > 0) {
        allFields = machine.fields;
      }

      if (allFields.length === 0) {
        throw new Error('No fields found for ladder generation');
      }

      console.log('[Ladder] Regenerating with fields:', allFields.map(f => f.name));

      // Generate new ladder logic using updated prompts
      const response = await generateLadderLogic(
        machine.machine_type,
        allFields,
        machine.description
      );

      // Save to Neo4j
      await saveLadderLogic(machine.id, {
        rungs: response.ladder_program.rungs,
        io_mapping: response.io_mapping,
        rationale: response.rationale,
      });

      // Update local state
      const newLadderData: LadderLogicData = {
        rungs: response.ladder_program.rungs,
        io_mapping: response.io_mapping,
        rationale: response.rationale,
        created_at: new Date().toISOString(),
      };
      setLadderData(newLadderData);

      // Load and start the new ladder
      await loadLadderProgram(newLadderData.rungs);
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1);

    } catch (err) {
      console.error('Failed to regenerate ladder:', err);
      setError(err instanceof Error ? err.message : 'Failed to regenerate ladder logic');
    } finally {
      setRegenerating(false);
    }
  };

  // Check if this machine has ladder logic (we'll show button regardless but indicate if available)
  const hasLadder = ladderData !== null;

  return (
    <>
      {/* Fixed sidebar container - LEFT side */}
      <div
        className={`fixed top-0 left-0 h-full z-50 flex transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-[50vw]'
        }`}
      >
        {/* Sidebar panel */}
        <div className="w-[50vw] h-full bg-gray-800 border-r border-gray-700 flex flex-col shadow-2xl">
          {/* Header */}
          <div className="flex-shrink-0 px-4 py-3 border-b border-gray-700 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-100">Ladder Logic Simulator</h3>
                <p className="text-xs text-gray-500">
                  {loading ? 'Loading...' :
                   error ? 'Error loading' :
                   !hasLadder ? 'No ladder logic' :
                   simulatorRunning ? 'Running' : 'Stopped'}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {simulatorRunning && (
                <span className="flex items-center gap-1.5 text-xs text-green-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                  Live
                </span>
              )}
              {/* Regenerate button - always show if machine has type */}
              {machine.machine_type && (
                <button
                  onClick={handleRegenerate}
                  disabled={regenerating || loading}
                  className="px-2 py-1 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:opacity-50 text-white text-xs rounded transition-colors flex items-center gap-1"
                  title="Regenerate ladder logic using updated AI prompts"
                >
                  {regenerating ? (
                    <>
                      <div className="w-3 h-3 border-t-2 border-white rounded-full animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Regenerate
                    </>
                  )}
                </button>
              )}
              {hasLadder && (
                <>
                  {simulatorRunning ? (
                    <button
                      onClick={handleStop}
                      className="px-2 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs rounded transition-colors"
                    >
                      Stop
                    </button>
                  ) : (
                    <button
                      onClick={handleRestart}
                      className="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded transition-colors"
                    >
                      Start
                    </button>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Main content area */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {(loading || regenerating) && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500 mx-auto mb-3" />
                  <p className="text-gray-400">
                    {regenerating ? 'Generating new ladder logic...' : 'Loading ladder logic...'}
                  </p>
                  {regenerating && (
                    <p className="text-xs text-gray-500 mt-2">This may take 10-30 seconds</p>
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="flex-1 flex items-center justify-center p-4">
                <div className="text-center">
                  <div className="p-4 bg-red-900/20 border border-red-600/50 rounded-lg">
                    <p className="text-red-400">{error}</p>
                    <button
                      onClick={loadAndStartLadder}
                      className="mt-2 text-sm text-red-300 underline hover:text-red-200"
                    >
                      Try again
                    </button>
                  </div>
                </div>
              </div>
            )}

            {!loading && !error && !hasLadder && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center px-8">
                  <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                  </svg>
                  <p className="text-lg font-medium text-gray-400">No Ladder Logic</p>
                  <p className="text-sm mt-2 text-gray-500">
                    This machine does not have ladder logic configured.
                    Generate ladder logic when creating a new machine.
                  </p>
                </div>
              </div>
            )}

            {!loading && !error && hasLadder && (
              <>
                {/* I/O Summary - compact */}
                <div className="flex-shrink-0 p-3 border-b border-gray-700">
                  <div className="grid grid-cols-4 gap-2">
                    <div className="bg-gray-900 rounded p-2 border border-gray-700">
                      <span className="text-xs text-gray-500">Rungs</span>
                      <p className="text-lg font-semibold text-gray-100">{ladderData.rungs.length}</p>
                    </div>
                    <div className="bg-gray-900 rounded p-2 border border-gray-700">
                      <span className="text-xs text-green-400">Inputs</span>
                      <p className="text-lg font-semibold text-gray-100">
                        {ladderData.io_mapping.inputs.length}
                      </p>
                    </div>
                    <div className="bg-gray-900 rounded p-2 border border-gray-700">
                      <span className="text-xs text-red-400">Outputs</span>
                      <p className="text-lg font-semibold text-gray-100">
                        {ladderData.io_mapping.outputs.length}
                      </p>
                    </div>
                    <div className="bg-gray-900 rounded p-2 border border-gray-700">
                      <span className="text-xs text-yellow-400">Internal</span>
                      <p className="text-lg font-semibold text-gray-100">
                        {ladderData.io_mapping.internal.length}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Rationale - collapsible */}
                {ladderData.rationale && (
                  <div className="flex-shrink-0 px-3 py-2 border-b border-gray-700 bg-gray-900/50">
                    <p className="text-xs text-gray-400 line-clamp-2" title={ladderData.rationale}>
                      {ladderData.rationale}
                    </p>
                  </div>
                )}

                {/* Live Simulator View */}
                <div className="flex-1 relative">
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

                {/* Generated timestamp */}
                {ladderData.created_at && (
                  <div className="flex-shrink-0 px-3 py-2 border-t border-gray-700 text-xs text-gray-500 text-center">
                    Generated: {new Date(ladderData.created_at).toLocaleDateString()}
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Toggle button - on the right edge of sidebar */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex-shrink-0 w-12 bg-gray-800 border-r border-y border-gray-700 rounded-r-lg flex flex-col items-center justify-center gap-2 hover:bg-gray-750 transition-colors group"
          title={isOpen ? 'Close PLC panel' : 'Open PLC panel'}
        >
          {/* Arrow icon - points left when closed, right when open */}
          <svg
            className={`w-5 h-5 text-gray-400 group-hover:text-gray-200 transition-transform duration-300 ${
              isOpen ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>

          {/* PLC icon */}
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
            </svg>
          </div>

          {/* Indicator when running */}
          {simulatorRunning && !isOpen && (
            <span className="absolute top-4 left-2 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          )}
        </button>
      </div>
    </>
  );
}
