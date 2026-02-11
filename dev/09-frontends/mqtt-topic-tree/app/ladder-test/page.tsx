'use client';

import { useState, useEffect } from 'react';
import {
  generateRandomMachine,
  generateLadderLogic,
  loadLadderProgram,
  startLadderSimulator,
  stopLadderSimulator,
} from '@/lib/machines-api';
import type {
  GeneratedMachineResponse,
  GenerateLadderResponse,
} from '@/types/machines';

export default function LadderTestPage() {
  const [machine, setMachine] = useState<GeneratedMachineResponse | null>(null);
  const [ladderResponse, setLadderResponse] = useState<GenerateLadderResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'idle' | 'generating-machine' | 'generating-ladder' | 'loading' | 'ready'>('idle');
  const [simulatorRunning, setSimulatorRunning] = useState(false);
  const [iframeKey, setIframeKey] = useState(0);
  const [iframeHeight, setIframeHeight] = useState(600);

  // Listen for iframe resize messages
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'resize-iframe' && event.data?.height) {
        setIframeHeight(event.data.height);
      }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const handleGenerateMachine = async () => {
    setLoading(true);
    setError(null);
    setStep('generating-machine');
    setMachine(null);
    setLadderResponse(null);

    try {
      const result = await generateRandomMachine();
      setMachine(result);
      setStep('idle');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate machine');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateLadder = async () => {
    if (!machine) return;

    setLoading(true);
    setError(null);
    setStep('generating-ladder');

    try {
      const result = await generateLadderLogic(
        machine.machine_type,
        machine.fields,
        machine.description
      );
      setLadderResponse(result);

      // Auto-load and start the simulator
      setStep('loading');
      await loadLadderProgram(result.ladder_program.rungs);
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1); // Force iframe refresh
      setStep('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate ladder logic');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadAndStart = async () => {
    if (!ladderResponse) return;

    setLoading(true);
    setError(null);
    setStep('loading');

    try {
      // Load the ladder program
      await loadLadderProgram(ladderResponse.ladder_program.rungs);

      // Start the simulator
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1); // Force iframe refresh
      setStep('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load/start ladder');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      await stopLadderSimulator();
      setSimulatorRunning(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulator');
    }
  };

  const handleFullGeneration = async () => {
    setLoading(true);
    setError(null);
    setMachine(null);
    setLadderResponse(null);

    try {
      // Step 1: Generate machine
      setStep('generating-machine');
      const machineResult = await generateRandomMachine();
      setMachine(machineResult);

      // Step 2: Generate ladder logic
      setStep('generating-ladder');
      const ladderResult = await generateLadderLogic(
        machineResult.machine_type,
        machineResult.fields,
        machineResult.description
      );
      setLadderResponse(ladderResult);

      // Step 3: Load and start
      setStep('loading');
      await loadLadderProgram(ladderResult.ladder_program.rungs);
      await startLadderSimulator();
      setSimulatorRunning(true);
      setIframeKey(prev => prev + 1); // Force iframe refresh
      setStep('ready');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed during generation');
      setStep('idle');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 px-4 py-6">
      <div className="w-full max-w-none">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Ladder Logic Generator Test</h1>
          <p className="text-gray-400">
            Generate a random machine and create ladder logic based on its fields
          </p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/20 border border-red-500 rounded-lg">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Controls */}
        <div className="mb-8 bg-gray-900 rounded-lg border border-gray-800 p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Controls</h2>
          <div className="flex flex-wrap gap-4">
            <button
              onClick={handleFullGeneration}
              disabled={loading}
              className="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
            >
              {loading ? `${step === 'generating-machine' ? 'Generating Machine...' : step === 'generating-ladder' ? 'Generating Ladder...' : step === 'loading' ? 'Loading Simulator...' : 'Processing...'}` : 'Generate All & Start'}
            </button>

            <div className="border-l border-gray-700 mx-2" />

            <button
              onClick={handleGenerateMachine}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg text-sm transition-colors"
            >
              1. Generate Machine
            </button>

            <button
              onClick={handleGenerateLadder}
              disabled={loading || !machine}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg text-sm transition-colors"
            >
              2. Generate Ladder
            </button>

            <button
              onClick={handleLoadAndStart}
              disabled={loading || !ladderResponse}
              className="px-4 py-2 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded-lg text-sm transition-colors"
            >
              3. Load & Start
            </button>

            {simulatorRunning && (
              <button
                onClick={handleStop}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm transition-colors"
              >
                Stop Simulator
              </button>
            )}
          </div>

          {/* Progress Indicator */}
          {loading && (
            <div className="mt-4 flex items-center gap-3">
              <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-500" />
              <span className="text-gray-400 text-sm">
                {step === 'generating-machine' && 'Generating random machine with LLM...'}
                {step === 'generating-ladder' && 'Generating ladder logic with LLM...'}
                {step === 'loading' && 'Loading ladder program and starting simulator...'}
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Left Column - Machine Info */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Generated Machine</h2>
            {machine ? (
              <div className="space-y-4">
                <div>
                  <span className="text-gray-400 text-sm">Type:</span>
                  <p className="text-white font-medium">{machine.machine_type}</p>
                </div>
                <div>
                  <span className="text-gray-400 text-sm">Name:</span>
                  <p className="text-white font-medium">{machine.suggested_name}</p>
                </div>
                {machine.description && (
                  <div>
                    <span className="text-gray-400 text-sm">Description:</span>
                    <p className="text-gray-300 text-sm">{machine.description}</p>
                  </div>
                )}
                <div>
                  <span className="text-gray-400 text-sm">Fields ({machine.fields.length}):</span>
                  <div className="mt-2 space-y-1">
                    {machine.fields.map((field, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-sm">
                        <span className="font-mono text-blue-400">{field.name}</span>
                        <span className="text-gray-500">({field.type})</span>
                        {field.min_value !== undefined && field.max_value !== undefined && (
                          <span className="text-gray-600">[{field.min_value} - {field.max_value}]</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">No machine generated yet</p>
            )}
          </div>

          {/* Right Column - Ladder Logic Info */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-6">
            <h2 className="text-xl font-semibold text-white mb-4">Generated Ladder Logic</h2>
            {ladderResponse ? (
              <div className="space-y-4">
                {/* I/O Mapping */}
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <span className="text-green-400 text-sm font-medium">Inputs</span>
                    <div className="mt-1 space-y-1">
                      {ladderResponse.io_mapping.inputs.map((input, idx) => (
                        <div key={idx} className="text-xs font-mono text-gray-300">{input}</div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-red-400 text-sm font-medium">Outputs</span>
                    <div className="mt-1 space-y-1">
                      {ladderResponse.io_mapping.outputs.map((output, idx) => (
                        <div key={idx} className="text-xs font-mono text-gray-300">{output}</div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-yellow-400 text-sm font-medium">Internal</span>
                    <div className="mt-1 space-y-1">
                      {ladderResponse.io_mapping.internal.length > 0 ? (
                        ladderResponse.io_mapping.internal.map((bit, idx) => (
                          <div key={idx} className="text-xs font-mono text-gray-300">{bit}</div>
                        ))
                      ) : (
                        <div className="text-xs text-gray-500">None</div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Rationale */}
                {ladderResponse.rationale && (
                  <div>
                    <span className="text-gray-400 text-sm">Rationale:</span>
                    <p className="text-gray-300 text-sm mt-1">{ladderResponse.rationale}</p>
                  </div>
                )}

                {/* Rungs */}
                <div>
                  <span className="text-gray-400 text-sm">Rungs ({ladderResponse.ladder_program.rungs.length}):</span>
                  <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
                    {ladderResponse.ladder_program.rungs.map((rung, idx) => (
                      <div key={idx} className="p-3 bg-gray-800 rounded text-sm">
                        <div className="text-gray-300 font-medium mb-1">
                          {idx + 1}. {rung.description}
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {rung.elements.map((elem, elemIdx) => (
                            <span
                              key={elemIdx}
                              className={`px-2 py-1 rounded text-xs font-mono ${
                                elem.type === 'contact' ? 'bg-green-900/50 text-green-300' :
                                elem.type === 'inverted_contact' ? 'bg-yellow-900/50 text-yellow-300' :
                                elem.type === 'output' ? 'bg-red-900/50 text-red-300' :
                                elem.type === 'set_coil' ? 'bg-purple-900/50 text-purple-300' :
                                elem.type === 'reset_coil' ? 'bg-orange-900/50 text-orange-300' :
                                'bg-gray-700 text-gray-300'
                              }`}
                            >
                              {elem.type === 'contact' ? '[ ]' :
                               elem.type === 'inverted_contact' ? '[/]' :
                               elem.type === 'output' ? '( )' :
                               elem.type === 'set_coil' ? '(S)' :
                               elem.type === 'reset_coil' ? '(R)' :
                               elem.type} {elem.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-gray-500">No ladder logic generated yet</p>
            )}
          </div>
        </div>

        {/* Full Width - Live Simulator */}
        <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden mb-8">
          <div className="p-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">Live Ladder Simulator</h2>
            {simulatorRunning && (
              <span className="px-3 py-1 bg-green-900/50 text-green-400 rounded-full text-sm">
                Running
              </span>
            )}
          </div>
          <div className="relative" style={{ height: `${iframeHeight}px` }}>
            <iframe
              key={iframeKey}
              src="/api/plcopen/simulate/ladder/render/simple"
              className="w-full h-full border-0"
              title="Ladder Logic Simulator"
            />
          </div>
        </div>

        {/* JSON Debug Panel */}
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Debug: Raw JSON</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Machine Response</h3>
              <pre className="p-4 bg-gray-950 rounded text-xs text-gray-300 overflow-auto max-h-64">
                {machine ? JSON.stringify(machine, null, 2) : 'null'}
              </pre>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-400 mb-2">Ladder Response</h3>
              <pre className="p-4 bg-gray-950 rounded text-xs text-gray-300 overflow-auto max-h-64">
                {ladderResponse ? JSON.stringify(ladderResponse, null, 2) : 'null'}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
