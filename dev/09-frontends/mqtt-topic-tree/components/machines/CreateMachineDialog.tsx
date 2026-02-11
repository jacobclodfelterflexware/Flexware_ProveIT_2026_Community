'use client';

import { useState, useEffect } from 'react';
import type { GeneratedMachineResponse, FieldDefinition, ContextTopic } from '@/types/machines';
import { generateRandomMachine, generatePromptedMachine, generateMachineImage } from '@/lib/machines-api';

interface CreateMachineDialogProps {
  onClose: () => void;
  onMachineGenerated: (machine: GeneratedMachineResponse, name: string, imageBase64?: string, autoPilot?: boolean, connectMode?: boolean) => void;
}

type Mode = 'select' | 'random' | 'prompted' | 'autopilot' | 'connect';

export default function CreateMachineDialog({
  onClose,
  onMachineGenerated,
}: CreateMachineDialogProps) {
  const [mode, setMode] = useState<Mode>('select');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generatedMachine, setGeneratedMachine] = useState<GeneratedMachineResponse | null>(null);
  const [machineName, setMachineName] = useState('');
  const [machineImage, setMachineImage] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [isAutoPilot, setIsAutoPilot] = useState(false);
  const [autoPilotCountdown, setAutoPilotCountdown] = useState(20);
  const [showContextTopics, setShowContextTopics] = useState(false);
  const [connectCountdown, setConnectCountdown] = useState(20);
  const [connectPhase, setConnectPhase] = useState<'waiting' | 'generating' | null>(null);
  const [isConnectMode, setIsConnectMode] = useState(false);

  // Auto-pilot countdown and auto-proceed
  useEffect(() => {
    if (!isAutoPilot || !generatedMachine || imageLoading) return;

    const timer = setInterval(() => {
      setAutoPilotCountdown(prev => {
        if (prev <= 1) {
          // Auto-proceed to next step
          if (machineName.trim()) {
            onMachineGenerated(generatedMachine, machineName.trim(), machineImage || undefined, true, isConnectMode);
          }
          return 20;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isAutoPilot, generatedMachine, imageLoading, machineName, machineImage, onMachineGenerated]);

  // Connect Machine: 20-second connection countdown
  useEffect(() => {
    if (connectPhase !== 'waiting') return;

    const timer = setInterval(() => {
      setConnectCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          setConnectPhase('generating');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [connectPhase]);

  // Connect Machine: Start generation when connection phase completes
  useEffect(() => {
    if (connectPhase !== 'generating') return;

    const generateMachine = async () => {
      setLoading(true);

      console.log('[CreateMachine] Connect mode: Starting machine generation after connection...');
      const startTime = performance.now();

      try {
        const machine = await generateRandomMachine();
        const elapsed = (performance.now() - startTime).toFixed(0);
        console.log(`[CreateMachine] Connect mode: Machine generated in ${elapsed}ms:`, {
          machine_type: machine.machine_type,
          suggested_name: machine.suggested_name,
          field_count: machine.fields?.length,
        });
        setGeneratedMachine(machine);
        setMachineName(machine.suggested_name);
        setIsAutoPilot(true);
        setAutoPilotCountdown(10);
      } catch (err) {
        const elapsed = (performance.now() - startTime).toFixed(0);
        console.error(`[CreateMachine] Connect mode: Generation failed after ${elapsed}ms:`, err);
        setError(err instanceof Error ? err.message : 'Failed to generate machine');
        setConnectPhase(null);
        setMode('select');
      } finally {
        setLoading(false);
      }
    };

    generateMachine();
  }, [connectPhase]);

  // Generate image when machine is generated
  useEffect(() => {
    if (generatedMachine && !machineImage && !imageLoading) {
      generateImage(generatedMachine);
    }
  }, [generatedMachine]);

  const generateImage = async (machine: GeneratedMachineResponse) => {
    setImageLoading(true);
    setImageError(null);

    try {
      const response = await generateMachineImage({
        machine_type: machine.machine_type,
        description: machine.description,
        fields: machine.fields.map(f => ({ name: f.name, type: f.type })),
      });
      setMachineImage(response.image_base64);
    } catch (err) {
      console.error('Image generation failed:', err);
      setImageError('Image generation unavailable');
    } finally {
      setImageLoading(false);
    }
  };

  const handleGenerateRandom = async () => {
    setLoading(true);
    setError(null);

    try {
      const machine = await generateRandomMachine();
      setGeneratedMachine(machine);
      setMachineName(machine.suggested_name);
      setMode('random');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate machine');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoPilot = async () => {
    setLoading(true);
    setError(null);
    setIsAutoPilot(true);
    setMode('autopilot');

    console.log('[CreateMachine] Starting auto-pilot machine generation...');
    const startTime = performance.now();

    try {
      const machine = await generateRandomMachine();
      const elapsed = (performance.now() - startTime).toFixed(0);
      console.log(`[CreateMachine] Machine generated in ${elapsed}ms:`, {
        machine_type: machine.machine_type,
        suggested_name: machine.suggested_name,
        field_count: machine.fields?.length,
      });
      setGeneratedMachine(machine);
      setMachineName(machine.suggested_name);
      setAutoPilotCountdown(20);
    } catch (err) {
      const elapsed = (performance.now() - startTime).toFixed(0);
      console.error(`[CreateMachine] Machine generation failed after ${elapsed}ms:`, err);
      setError(err instanceof Error ? err.message : 'Failed to generate machine');
      setIsAutoPilot(false);
      setMode('select');
    } finally {
      setLoading(false);
    }
  };

  const handleConnectMachine = () => {
    setMode('connect');
    setConnectPhase('waiting');
    setConnectCountdown(10);
    setIsConnectMode(true);
    setError(null);
  };

  const handleGenerateFromPrompt = async () => {
    if (!prompt.trim()) {
      setError('Please enter a description');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const machine = await generatePromptedMachine({ prompt });
      setGeneratedMachine(machine);
      setMachineName(machine.suggested_name);
      setIsAutoPilot(true);
      setAutoPilotCountdown(20);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate machine');
    } finally {
      setLoading(false);
    }
  };

  const handleProceed = () => {
    if (generatedMachine && machineName.trim()) {
      onMachineGenerated(generatedMachine, machineName.trim(), machineImage || undefined);
    }
  };

  const handleReset = () => {
    setGeneratedMachine(null);
    setMachineImage(null);
    setImageError(null);
    setMode('select');
  };

  const renderFieldType = (type: string) => {
    const colors: Record<string, string> = {
      number: 'text-blue-400',
      integer: 'text-cyan-400',
      boolean: 'text-yellow-400',
      string: 'text-green-400',
    };
    return <span className={colors[type] || 'text-gray-400'}>{type}</span>;
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-100">
            {mode === 'select'
              ? 'Create New Machine'
              : mode === 'connect' && !generatedMachine
              ? 'Connect Machine'
              : generatedMachine
              ? 'Review Generated Machine'
              : 'Generate Machine'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 140px)' }}>
          {error && (
            <div className="bg-red-900/20 border border-red-500 rounded p-3 mb-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Mode Selection */}
          {mode === 'select' && !generatedMachine && (
            <div className="space-y-4">
              <p className="text-gray-300 mb-6">
                Choose how you want to create your simulated machine:
              </p>

              <button
                onClick={handleGenerateRandom}
                disabled={loading}
                className="w-full p-4 bg-gray-700 hover:bg-gray-600 rounded-lg border border-gray-600 text-left transition-colors disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-100">Human in the Loop</h3>
                    <p className="text-sm text-gray-400">
                      Let AI generate a random industrial machine with realistic fields
                    </p>
                  </div>
                </div>
              </button>

              <button
                onClick={() => setMode('prompted')}
                disabled={loading}
                className="w-full p-4 bg-gray-700 hover:bg-gray-600 rounded-lg border border-gray-600 text-left transition-colors disabled:opacity-50"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-100">Custom Machine</h3>
                    <p className="text-sm text-gray-400">
                      Tell AI what kind of machine you want to simulate
                    </p>
                  </div>
                </div>
              </button>

              <button
                onClick={handleAutoPilot}
                disabled={loading}
                className="w-full p-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 rounded-lg border border-purple-500 text-left transition-all disabled:opacity-50 shadow-lg shadow-purple-900/30"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-white">Auto-Pilot Mode</h3>
                    <p className="text-sm text-purple-100">
                      AI creates and configures everything automatically
                    </p>
                  </div>
                </div>
              </button>

              <button
                onClick={handleConnectMachine}
                disabled={loading}
                className="w-full p-4 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 rounded-lg border border-emerald-500 text-left transition-all disabled:opacity-50 shadow-lg shadow-emerald-900/30"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
                    <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-white">Connect Machine</h3>
                    <p className="text-sm text-emerald-100">
                      Connect a real PLC and auto-configure from live data
                    </p>
                  </div>
                </div>
              </button>

              {loading && (
                <div className="text-center text-gray-400 py-4">
                  Generating machine...
                </div>
              )}
            </div>
          )}

          {/* Auto-pilot Loading */}
          {mode === 'autopilot' && loading && !generatedMachine && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500 mx-auto mb-4"></div>
              <p className="text-purple-300 font-medium">Starting Auto-Pilot...</p>
              <p className="text-gray-400 text-sm mt-2">AI is generating your machine</p>
            </div>
          )}

          {/* Connect Machine: Connection Phase */}
          {mode === 'connect' && connectPhase === 'waiting' && (
            <div className="text-center py-16">
              {/* Animated connection icon */}
              <div className="relative mx-auto mb-8 w-24 h-24">
                <div className="absolute inset-0 rounded-full border-2 border-emerald-500/30 animate-ping" style={{ animationDuration: '2s' }} />
                <div className="absolute inset-2 rounded-full border-2 border-emerald-400/40 animate-ping" style={{ animationDuration: '1.5s', animationDelay: '0.3s' }} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-16 h-16 bg-gradient-to-br from-emerald-600 to-cyan-600 rounded-full flex items-center justify-center shadow-lg shadow-emerald-500/30">
                    <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101M10.172 13.828a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                </div>
              </div>

              <h3 className="text-emerald-300 text-xl font-semibold mb-2">Connect Your Machine</h3>
              <p className="text-gray-400 text-sm mb-6">Waiting for PLC connection on the network...</p>

              {/* Countdown ring */}
              <div className="relative mx-auto w-16 h-16 mb-4">
                <svg className="w-16 h-16 transform -rotate-90" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="28" fill="none" stroke="#374151" strokeWidth="3" />
                  <circle
                    cx="32" cy="32" r="28" fill="none"
                    stroke="url(#connectGradient)"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 28}`}
                    strokeDashoffset={`${2 * Math.PI * 28 * (1 - connectCountdown / 10)}`}
                    style={{ transition: 'stroke-dashoffset 1s linear' }}
                  />
                  <defs>
                    <linearGradient id="connectGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#059669" />
                      <stop offset="100%" stopColor="#0891b2" />
                    </linearGradient>
                  </defs>
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-emerald-400 text-lg font-mono font-bold">{connectCountdown}</span>
                </div>
              </div>

              <p className="text-gray-500 text-xs">Scanning for devices...</p>

              <button
                onClick={() => {
                  setConnectPhase(null);
                  setMode('select');
                }}
                className="mt-6 px-4 py-2 text-gray-400 hover:text-gray-200 text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Connect Machine: Generating Phase (Loading PLC Data) */}
          {mode === 'connect' && connectPhase === 'generating' && !generatedMachine && (
            <div className="text-center py-16">
              <div className="relative mx-auto mb-8 w-20 h-20">
                <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-emerald-500 border-r-cyan-500 animate-spin" style={{ animationDuration: '1.5s' }} />
                <div className="absolute inset-2 flex items-center justify-center">
                  <div className="w-14 h-14 bg-gray-800 rounded-full flex items-center justify-center border border-emerald-600/50">
                    <svg className="w-7 h-7 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-center gap-2 mb-2">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <h3 className="text-emerald-300 text-xl font-semibold">Connected</h3>
              </div>
              <p className="text-cyan-300 font-medium mb-1">Loading PLC Data...</p>
              <p className="text-gray-400 text-sm">Reading tag configuration and I/O points</p>
            </div>
          )}

          {/* Prompted Mode */}
          {mode === 'prompted' && !generatedMachine && (
            <div className="space-y-4">
              <button
                onClick={() => setMode('select')}
                className="text-sm text-gray-400 hover:text-gray-200 flex items-center gap-1"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Back
              </button>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Describe the machine you want to simulate
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g., A CNC milling machine that monitors spindle speed, temperature, and part count..."
                  className="w-full h-32 bg-gray-900 border border-gray-600 rounded-lg px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
                />
              </div>

              <button
                onClick={handleGenerateFromPrompt}
                disabled={loading || !prompt.trim()}
                className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? 'Generating...' : 'Generate Machine'}
              </button>
            </div>
          )}

          {/* Generated Machine Preview */}
          {generatedMachine && (
            <div className="space-y-4">
              {/* Auto-Pilot Indicator */}
              {isAutoPilot && (
                <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 border border-purple-500 rounded-lg p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                    <span className="text-purple-300 font-medium">AUTO-PILOT ACTIVE</span>
                    <span className="text-purple-400">
                      {imageLoading ? 'Generating image...' : `Continuing in ${autoPilotCountdown}s...`}
                    </span>
                  </div>
                  <button
                    onClick={() => setIsAutoPilot(false)}
                    className="px-3 py-1 bg-purple-700 hover:bg-purple-600 text-white rounded text-sm transition-colors"
                  >
                    Take Control
                  </button>
                </div>
              )}

              {!isAutoPilot && (
                <button
                  onClick={handleReset}
                  className="text-sm text-gray-400 hover:text-gray-200 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  Generate Another
                </button>
              )}

              {/* Machine Image */}
              <div className="relative rounded-lg overflow-hidden bg-gray-900 border border-gray-700">
                {imageLoading ? (
                  <div className="h-64 flex items-center justify-center">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-purple-500 mx-auto mb-3"></div>
                      <p className="text-gray-400 text-sm">Generating machine visualization...</p>
                    </div>
                  </div>
                ) : machineImage ? (
                  <img
                    src={`data:image/png;base64,${machineImage}`}
                    alt={generatedMachine.machine_type}
                    className="w-full h-64 object-cover"
                  />
                ) : imageError ? (
                  <div className="h-64 flex items-center justify-center bg-gray-800">
                    <div className="text-center text-gray-500">
                      <svg className="w-12 h-12 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-sm">{imageError}</p>
                      <button
                        onClick={() => generateImage(generatedMachine)}
                        className="mt-2 text-purple-400 hover:text-purple-300 text-sm"
                      >
                        Retry
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Machine Name Input */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Machine Name
                </label>
                <input
                  type="text"
                  value={machineName}
                  onChange={(e) => setMachineName(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-600 rounded px-4 py-2 text-gray-100 focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Machine Type & Description */}
              <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm text-gray-400">Type:</span>
                  <span className="text-gray-100">{generatedMachine.machine_type}</span>
                </div>
                {generatedMachine.description && (
                  <p className="text-sm text-gray-400">{generatedMachine.description}</p>
                )}
              </div>

              {/* Fields */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Fields ({generatedMachine.fields.length})
                </label>
                <div className="bg-gray-900 border border-gray-700 rounded overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-800/50">
                        <th className="px-4 py-2 text-left text-gray-400 font-medium">Name</th>
                        <th className="px-4 py-2 text-left text-gray-400 font-medium">Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {generatedMachine.fields.map((field, idx) => (
                        <tr key={idx}>
                          <td className="px-4 py-2 text-gray-100 font-mono">{field.name}</td>
                          <td className="px-4 py-2">{renderFieldType(field.type)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Context Topics (collapsible) */}
              {generatedMachine.context_topics && generatedMachine.context_topics.length > 0 && (
                <div className="border border-gray-700 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setShowContextTopics(!showContextTopics)}
                    className="w-full px-4 py-3 bg-gray-800/50 flex items-center justify-between hover:bg-gray-800 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                      <span className="text-sm font-medium text-gray-300">
                        Context Topics ({generatedMachine.context_topics.length} samples from knowledge graph)
                      </span>
                    </div>
                    <svg
                      className={`w-5 h-5 text-gray-400 transition-transform ${showContextTopics ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {showContextTopics && (
                    <div className="bg-gray-900 divide-y divide-gray-800 max-h-64 overflow-y-auto">
                      {generatedMachine.context_topics.map((topic, idx) => (
                        <div key={idx} className="px-4 py-3">
                          <div className="flex items-start gap-2">
                            <span className="text-purple-400 font-mono text-xs mt-0.5">{idx + 1}.</span>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-gray-100 font-mono truncate" title={topic.topic_path}>
                                {topic.topic_path}
                              </p>
                              <p className="text-xs text-gray-500 mt-1">
                                Fields: {topic.field_names.join(', ')}
                              </p>
                              <p className="text-xs text-gray-600 mt-1 font-mono truncate" title={topic.payload_preview}>
                                {topic.payload_preview}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {generatedMachine && (
          <div className="border-t border-gray-700 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleProceed}
              disabled={!machineName.trim()}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50"
            >
              Continue to Connect
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
