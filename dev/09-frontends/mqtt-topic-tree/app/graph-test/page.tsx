'use client';

import { useState, useEffect } from 'react';
import GraphVisualization from '@/components/machines/GraphVisualization';
import type { GraphMetrics } from '@/types/graph';

export default function GraphTestPage() {
  const [mounted, setMounted] = useState(false);
  const [manualControlsEnabled, setManualControlsEnabled] = useState(false);
  const [cameraPos, setCameraPos] = useState({ x: 0, y: 443, z: 1925 });
  const [targetPos, setTargetPos] = useState({ x: 0, y: 0, z: 0 });
  const [disableAutoRotate, setDisableAutoRotate] = useState(false);
  const [metrics, setMetrics] = useState<GraphMetrics | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Manual controls object - only passed to GraphVisualization if enabled
  const manualControls = manualControlsEnabled ? {
    camera: cameraPos,
    target: targetPos,
    disableAutoRotate
  } : undefined;

  // Hardcoded test data - simulating similar results
  // This mimics what would come from the similarity search
  const testSimilarResults = [
    {
      topic_path: 'machine/status',
      similarity: 0.95,
      field_names: ['state', 'timestamp'],
      historical_payloads: [{ payload: { state: 'running', timestamp: '2024-01-10T12:00:00Z' } }]
    },
    {
      topic_path: 'machine/temperature',
      similarity: 0.88,
      field_names: ['value', 'unit'],
      historical_payloads: [{ payload: { value: 72.5, unit: 'celsius' } }]
    },
    {
      topic_path: 'machine/pressure',
      similarity: 0.82,
      field_names: ['value', 'unit'],
      historical_payloads: [{ payload: { value: 101.3, unit: 'kpa' } }]
    },
    {
      topic_path: 'machine/speed',
      similarity: 0.75,
      field_names: ['rpm'],
      historical_payloads: [{ payload: { rpm: 1500 } }]
    },
    {
      topic_path: 'machine/vibration',
      similarity: 0.70,
      field_names: ['level', 'frequency'],
      historical_payloads: [{ payload: { level: 0.5, frequency: 60 } }]
    },
    {
      topic_path: 'factory/line1/status',
      similarity: 0.65,
      field_names: ['state'],
      historical_payloads: [{ payload: { state: 'active' } }]
    },
    {
      topic_path: 'factory/line1/temperature',
      similarity: 0.60,
      field_names: ['value'],
      historical_payloads: [{ payload: { value: 68.2 } }]
    },
    {
      topic_path: 'sensor/temp',
      similarity: 0.55,
      field_names: ['temperature'],
      historical_payloads: [{ payload: { temperature: 70.1 } }]
    },
  ];

  if (!mounted) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-4">Graph Centering Test Suite</h1>
          <div className="bg-gray-900 p-6 rounded-lg border border-gray-800">
            <h2 className="text-xl font-semibold text-white mb-4">Instructions</h2>
            <ol className="text-gray-300 space-y-2 list-decimal list-inside">
              <li>Open browser console (F12)</li>
              <li>Set test mode: <code className="bg-gray-800 px-2 py-1 rounded">localStorage.setItem('graphTestMode', '1')</code></li>
              <li>Hard refresh: <code className="bg-gray-800 px-2 py-1 rounded">Ctrl+Shift+R</code></li>
              <li>Take screenshot and copy console logs</li>
              <li>Repeat for modes 2-6</li>
            </ol>
            <div className="mt-4 p-4 bg-blue-900/20 border border-blue-700 rounded">
              <p className="text-blue-300 font-semibold">Current Test Mode:</p>
              <p className="text-blue-200 font-mono text-sm mt-1">
                Check console for: <span className="text-green-400">[Graph] ===== RUNNING TEST MODE X =====</span>
              </p>
            </div>
            <div className="mt-4 p-4 bg-purple-900/20 border border-purple-700 rounded">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={manualControlsEnabled}
                  onChange={(e) => setManualControlsEnabled(e.target.checked)}
                  className="w-5 h-5"
                />
                <span className="text-purple-300 font-semibold">
                  Enable Manual Controls (Override Test Modes)
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Manual Controls Panel */}
        {manualControlsEnabled && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-6 mb-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-white">Manual Controls</h2>
              <div className="flex gap-4">
                <button
                  onClick={() => {
                    setCameraPos({ x: 0, y: 443, z: 1925 });
                    setTargetPos({ x: 0, y: 0, z: 0 });
                  }}
                  className="px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-sm"
                >
                  Reset to Default
                </button>
                <button
                  onClick={() => {
                    const values = `Camera: {x: ${cameraPos.x}, y: ${cameraPos.y}, z: ${cameraPos.z}}\nTarget: {x: ${targetPos.x}, y: ${targetPos.y}, z: ${targetPos.z}}`;
                    navigator.clipboard.writeText(values);
                  }}
                  className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
                >
                  Copy Values
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Camera Controls */}
              <div className="bg-gray-800 p-4 rounded">
                <h3 className="font-semibold text-green-400 mb-4">Camera Position</h3>

                {/* Camera X */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">X: {cameraPos.x}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={cameraPos.x}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, x: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={cameraPos.x}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, x: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Camera Y */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">Y: {cameraPos.y}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={cameraPos.y}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, y: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={cameraPos.y}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, y: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Camera Z */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">Z: {cameraPos.z}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={cameraPos.z}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, z: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={cameraPos.z}
                      onChange={(e) => setCameraPos(prev => ({ ...prev, z: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Preset buttons */}
                <div className="flex gap-2 mt-4">
                  <button
                    onClick={() => setCameraPos({ x: 0, y: 0, z: 2500 })}
                    className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs"
                  >
                    Front View
                  </button>
                  <button
                    onClick={() => setCameraPos({ x: 0, y: 2500, z: 0 })}
                    className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs"
                  >
                    Top View
                  </button>
                  <button
                    onClick={() => setCameraPos({ x: 2500, y: 0, z: 0 })}
                    className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs"
                  >
                    Side View
                  </button>
                </div>
              </div>

              {/* Target Controls */}
              <div className="bg-gray-800 p-4 rounded">
                <h3 className="font-semibold text-blue-400 mb-4">Controls Target (Look At)</h3>

                {/* Target X */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">X: {targetPos.x}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={targetPos.x}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, x: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={targetPos.x}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, x: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Target Y */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">Y: {targetPos.y}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={targetPos.y}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, y: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={targetPos.y}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, y: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Target Z */}
                <div className="mb-4">
                  <label className="block text-gray-300 text-sm mb-2">Z: {targetPos.z}</label>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min="-5000"
                      max="5000"
                      value={targetPos.z}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, z: parseInt(e.target.value) }))}
                      className="flex-1"
                    />
                    <input
                      type="number"
                      value={targetPos.z}
                      onChange={(e) => setTargetPos(prev => ({ ...prev, z: parseInt(e.target.value) || 0 }))}
                      className="w-24 bg-gray-700 text-white px-2 py-1 rounded text-sm"
                    />
                  </div>
                </div>

                {/* Reset to origin button */}
                <button
                  onClick={() => setTargetPos({ x: 0, y: 0, z: 0 })}
                  className="w-full px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-xs mt-4"
                >
                  Reset to Origin (0, 0, 0)
                </button>
              </div>
            </div>

            {/* Auto-rotate toggle */}
            <div className="mt-4 flex items-center gap-3">
              <label className="text-gray-300 text-sm">Disable Auto-Rotate:</label>
              <input
                type="checkbox"
                checked={disableAutoRotate}
                onChange={(e) => setDisableAutoRotate(e.target.checked)}
                className="w-4 h-4"
              />
            </div>
          </div>
        )}

        {/* Metrics Display */}
        {manualControlsEnabled && metrics && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-6 mb-8">
            <h2 className="text-xl font-semibold text-white mb-4">Live Metrics</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Dimensions */}
              <div className="bg-gray-800 p-4 rounded">
                <h3 className="font-semibold text-purple-400 mb-3 text-sm">Dimensions</h3>
                <div className="space-y-2 text-xs font-mono text-gray-300">
                  <div>
                    <span className="text-gray-500">Window:</span>{' '}
                    {metrics.windowDimensions.width} × {metrics.windowDimensions.height}{' '}
                    <span className="text-gray-500">({metrics.windowDimensions.aspectRatio})</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Container:</span>{' '}
                    {metrics.containerDimensions.width} × {metrics.containerDimensions.height}{' '}
                    <span className="text-gray-500">({metrics.containerDimensions.aspectRatio})</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Canvas:</span>{' '}
                    {metrics.canvasDimensions.width} × {metrics.canvasDimensions.height}{' '}
                    <span className="text-gray-500">({metrics.canvasDimensions.aspectRatio})</span>
                  </div>
                  {metrics.sizeMismatch && (
                    <div className="mt-2 p-2 bg-yellow-900/30 border border-yellow-700 rounded">
                      <span className="text-yellow-400 font-semibold">⚠️ SIZE MISMATCH</span>
                      <div className="mt-1 text-yellow-300">
                        Offset: {metrics.sizeMismatch.horizontalOffset}px
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Camera & Target */}
              <div className="bg-gray-800 p-4 rounded">
                <h3 className="font-semibold text-green-400 mb-3 text-sm">Camera & Target</h3>
                <div className="space-y-2 text-xs font-mono text-gray-300">
                  <div>
                    <span className="text-gray-500">Camera:</span>{' '}
                    ({metrics.cameraPosition.x}, {metrics.cameraPosition.y}, {metrics.cameraPosition.z})
                  </div>
                  <div>
                    <span className="text-gray-500">Target:</span>{' '}
                    ({metrics.controlsTarget.x}, {metrics.controlsTarget.y}, {metrics.controlsTarget.z})
                  </div>
                  <div>
                    <span className="text-gray-500">Distance:</span> {metrics.distance}
                  </div>
                </div>
              </div>

              {/* Graph Info */}
              <div className="bg-gray-800 p-4 rounded">
                <h3 className="font-semibold text-blue-400 mb-3 text-sm">Graph Info</h3>
                <div className="space-y-2 text-xs font-mono text-gray-300">
                  <div>
                    <span className="text-gray-500">Center:</span>{' '}
                    ({metrics.graphCenter.x.toFixed(2)}, {metrics.graphCenter.y.toFixed(2)}, {metrics.graphCenter.z.toFixed(2)})
                  </div>
                  <div>
                    <span className="text-gray-500">Nodes:</span> {metrics.nodeCount}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden" style={{ height: '600px' }}>
          <GraphVisualization
            similarResults={testSimilarResults}
            suggestedTopic="machine/status"
            enableAutoRotate={true}
            isSearching={false}
            manualControls={manualControls}
            onMetricsUpdate={setMetrics}
          />
        </div>

        <div className="mt-8 bg-gray-900 p-6 rounded-lg border border-gray-800">
          <h2 className="text-xl font-semibold text-white mb-4">Test Configurations</h2>
          <div className="mb-4 p-4 bg-yellow-900/20 border border-yellow-700 rounded">
            <p className="text-yellow-300 font-semibold">Root Cause Identified:</p>
            <p className="text-yellow-200 text-sm mt-1">
              ForceGraph3D uses window dimensions for camera calculations, but renders in a smaller container.
              This causes the graph to appear off-center to the right.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-green-400 mb-2">Test 1: zoomToFit() 50px padding</h3>
              <p className="text-gray-300 text-sm">Baseline - uses library's zoomToFit with default padding</p>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-blue-400 mb-2">Test 2: zoomToFit() 200px padding</h3>
              <p className="text-gray-300 text-sm">Test if more padding helps centering</p>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-purple-400 mb-2">Test 3: Camera X=-800</h3>
              <p className="text-gray-300 text-sm">Move camera LEFT to compensate</p>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-yellow-400 mb-2">Test 4: Target X=-800</h3>
              <p className="text-gray-300 text-sm">Move what we look at LEFT</p>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-orange-400 mb-2">Test 5: Camera X=+800</h3>
              <p className="text-gray-300 text-sm">Move camera RIGHT (opposite test)</p>
            </div>
            <div className="bg-gray-800 p-4 rounded">
              <h3 className="font-bold text-red-400 mb-2">Test 6: Static (no rotation)</h3>
              <p className="text-gray-300 text-sm">No rotation - see actual position</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
