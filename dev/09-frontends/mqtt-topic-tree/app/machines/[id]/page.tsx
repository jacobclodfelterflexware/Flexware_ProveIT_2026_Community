'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { QRCodeSVG } from 'qrcode.react';
import type { MachineDefinition } from '@/types/machines';
import { getMachine, getMachineByCreator, getMachineStatus, startMachine, stopMachine } from '@/lib/machines-api';
import MachinePayloadChart from '@/components/machines/MachinePayloadChart';
import MLInsightsSection from '@/components/machines/MLInsightsSection';
import MachineChatbot from '@/components/machines/MachineChatbot';
import SparkMESSection from '@/components/machines/SparkMESSection';
import SMProfileSection from '@/components/machines/SMProfileSection';
import LadderLogicSidebar from '@/components/machines/LadderLogicSidebar';

// Dynamic import for GraphVisualization to avoid SSR/WebGL issues
const GraphVisualization = dynamic(
  () => import('@/components/machines/GraphVisualization'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-400 text-sm">Loading 3D renderer...</p>
        </div>
      </div>
    )
  }
);

const statusColors = {
  draft: 'bg-yellow-500',
  running: 'bg-green-500',
};

const statusLabels = {
  draft: 'Draft',
  running: 'Running',
};

// UUID v4 pattern
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function MachineDetailPage() {
  const params = useParams();
  const router = useRouter();
  const rawId = params.id as string;

  // Determine if this is kiosk mode (name-based) or normal mode (UUID-based)
  const isKiosk = !UUID_REGEX.test(rawId);
  const creatorName = isKiosk ? decodeURIComponent(rawId) : null;

  const [machine, setMachine] = useState<MachineDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [pageUrl, setPageUrl] = useState('');

  // Graph visibility toggle (defaults to shown)
  const [graphExpanded, setGraphExpanded] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('machine-graph-expanded');
      return stored !== null ? stored === 'true' : true;
    }
    return true;
  });

  // Defer graph rendering until the browser is idle (after page loads)
  const [graphReady, setGraphReady] = useState(false);
  useEffect(() => {
    const cb = () => setGraphReady(true);
    if (typeof window.requestIdleCallback === 'function') {
      const id = window.requestIdleCallback(cb, { timeout: 2000 });
      return () => window.cancelIdleCallback(id);
    }
    const timer = setTimeout(cb, 500);
    return () => clearTimeout(timer);
  }, []);

  // Dynamic similarity search state
  const [similarTopics, setSimilarTopics] = useState<Array<{
    topic_path: string;
    similarity: number;
    field_names: string[];
    historical_payloads: Array<{ payload: Record<string, unknown>; timestamp?: string }>;
  }> | null>(null);
  const [loadingSimilarity, setLoadingSimilarity] = useState(false);
  const [messagesPublished, setMessagesPublished] = useState(0);

  // Capture page URL for QR code (client-side only)
  useEffect(() => {
    setPageUrl(window.location.href);
  }, []);

  const fetchMachine = useCallback(async () => {
    try {
      let data: MachineDefinition;
      if (isKiosk && creatorName) {
        data = await getMachineByCreator(creatorName);
      } else {
        data = await getMachine(rawId);
      }
      setMachine(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load machine');
    } finally {
      setLoading(false);
    }
  }, [rawId, isKiosk, creatorName]);

  useEffect(() => {
    fetchMachine();
  }, [fetchMachine]);

  // Auto-refresh when machine is running
  useEffect(() => {
    if (machine?.status !== 'running' || !machine?.id) {
      setMessagesPublished(0);
      return;
    }

    const machineId = machine.id;
    const fetchStatus = async () => {
      try {
        const status = await getMachineStatus(machineId);
        setMessagesPublished(status.messages_published);
      } catch (err) {
        console.error('Failed to fetch machine status:', err);
      }
    };

    fetchStatus(); // Initial fetch
    const interval = setInterval(() => {
      fetchMachine();
      fetchStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [machine?.status, machine?.id, fetchMachine]);

  // Fetch similar topics on-the-fly using machine_type or name
  useEffect(() => {
    if (!machine) return;

    const query = machine.machine_type || machine.name;
    if (!query) return;

    const timeoutId = setTimeout(() => {
      const fetchSimilarTopics = async () => {
        setLoadingSimilarity(true);
        try {
          const response = await fetch(
            `/api/graph/similar-search?q=${encodeURIComponent(query)}&k=20`
          );
          if (response.ok) {
            const data = await response.json();
            setSimilarTopics(data.results || []);
          } else {
            console.error('Failed to fetch similar topics:', response.statusText);
            setSimilarTopics([]);
          }
        } catch (err) {
          console.error('Failed to fetch similar topics:', err);
          setSimilarTopics([]);
        } finally {
          setLoadingSimilarity(false);
        }
      };

      fetchSimilarTopics();
    }, 100);

    return () => clearTimeout(timeoutId);
  }, [machine?.machine_type, machine?.name]);

  const handleStartStop = async () => {
    if (!machine?.id) return;
    setActionLoading(true);

    try {
      if (machine.status === 'running') {
        await stopMachine(machine.id);
      } else {
        await startMachine(machine.id);
      }
      await fetchMachine();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Operation failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className={`min-h-screen bg-gray-900 flex items-center justify-center ${isKiosk ? 'fixed inset-0 z-50' : ''}`}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading machine...</p>
        </div>
      </div>
    );
  }

  if (error || !machine) {
    return (
      <div className={`min-h-screen bg-gray-900 flex items-center justify-center ${isKiosk ? 'fixed inset-0 z-50' : ''}`}>
        <div className="text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-lg text-gray-300 mb-2">{error || 'Machine not found'}</p>
          {!isKiosk && (
            <Link
              href="/machines"
              className="text-blue-400 hover:text-blue-300 underline"
            >
              Back to Machines
            </Link>
          )}
        </div>
      </div>
    );
  }

  const topicCount = machine.topics?.length || (machine.topic_path ? 1 : 0);
  const fieldCount = machine.topics?.reduce((sum, t) => sum + (t.fields?.length || 0), 0) || machine.fields?.length || 0;
  const suggestedTopic = machine.topics?.[0]?.topic_path || machine.topic_path;
  const showCreatedBy = machine.created_by && machine.created_by !== 'system';

  // Shared content sections (used in both normal and kiosk mode)
  const renderInfoCards = () => (
    <div className="mb-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Topics</div>
        <div className="text-2xl font-semibold text-gray-100">{topicCount}</div>
      </div>
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Fields</div>
        <div className="text-2xl font-semibold text-gray-100">{fieldCount}</div>
      </div>
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Similar Topics</div>
        <div className="text-2xl font-semibold text-gray-100">
          {loadingSimilarity ? '...' : (similarTopics?.length || 0)}
        </div>
      </div>
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Messages</div>
        <div className="text-2xl font-semibold text-gray-100">
          {machine.status === 'running' ? messagesPublished.toLocaleString() : '—'}
        </div>
      </div>
    </div>
  );

  const handleToggleGraph = () => {
    const next = !graphExpanded;
    setGraphExpanded(next);
    try { localStorage.setItem('machine-graph-expanded', String(next)); } catch {}
  };

  const renderGraphAndChart = () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Knowledge Graph */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            Knowledge Graph Context
          </h2>
          <div className="flex items-center gap-2">
            {loadingSimilarity ? (
              <span className="text-xs text-cyan-400 flex items-center gap-1.5">
                <div className="animate-spin rounded-full h-3 w-3 border-t border-b border-cyan-400"></div>
                Searching...
              </span>
            ) : similarTopics && similarTopics.length > 0 ? (
              <span className="text-xs text-gray-500">
                {similarTopics.length} similar topics found
              </span>
            ) : null}
            {similarTopics && similarTopics.length > 0 && (
              <button
                onClick={handleToggleGraph}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-200 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
                title={graphExpanded ? 'Hide 3D graph (saves CPU)' : 'Show 3D graph'}
              >
                <svg className={`w-3.5 h-3.5 transition-transform ${graphExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
                {graphExpanded ? 'Hide' : 'Show'}
              </button>
            )}
          </div>
        </div>
        <div className={graphExpanded ? 'h-[500px] p-4' : ''}>
          {loadingSimilarity ? (
            <div className="h-[500px] p-4 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-cyan-500 mx-auto mb-4"></div>
                <p className="text-lg font-medium text-gray-300">Searching for similar topics...</p>
                <p className="text-sm mt-1 text-gray-500">
                  Finding related topics in the knowledge graph
                </p>
              </div>
            </div>
          ) : similarTopics && similarTopics.length > 0 ? (
            graphExpanded ? (
              graphReady ? (
                <GraphVisualization
                  similarResults={similarTopics}
                  suggestedTopic={suggestedTopic}
                  enableAutoRotate={true}
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-500">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mx-auto mb-3"></div>
                    <p className="text-sm text-gray-400">Preparing 3D graph...</p>
                  </div>
                </div>
              )
            ) : (
              <div className="px-4 py-6 flex items-center justify-center">
                <button
                  onClick={handleToggleGraph}
                  className="flex items-center gap-3 text-gray-400 hover:text-gray-200 transition-colors group"
                >
                  <svg className="w-10 h-10 text-gray-600 group-hover:text-cyan-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
                  </svg>
                  <div className="text-left">
                    <p className="text-sm font-medium group-hover:text-gray-100">Click to show 3D knowledge graph</p>
                    <p className="text-xs text-gray-500">{similarTopics.length} similar topics &middot; Hidden to save CPU</p>
                  </div>
                </button>
              </div>
            )
          ) : (
            <div className="h-[500px] p-4 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <p className="text-lg font-medium text-gray-400">No similar topics found</p>
                <p className="text-sm mt-1 text-gray-500">
                  No matching topics were found in the knowledge graph
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Realtime Chart */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            Live Telemetry
          </h2>
          {machine.status === 'running' && (
            <span className="flex items-center gap-1.5 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              Streaming
            </span>
          )}
        </div>
        <div className="h-[500px] p-4">
          <MachinePayloadChart machine={machine} />
        </div>
      </div>
    </div>
  );

  const renderExtraSections = () => (
    <>
      {/* ML Insights Section */}
      <MLInsightsSection machine={machine} />

      {/* SparkMES Configuration Section */}
      {machine.sparkmes_enabled && machine.sparkmes && (
        <SparkMESSection
          sparkmes={machine.sparkmes}
          machineId={machine.id}
          isRunning={machine.status === 'running'}
        />
      )}

      {/* CESMII SM Profile Section */}
      {machine.smprofile && (
        <SMProfileSection smprofile={machine.smprofile} />
      )}

      {/* Similar Topics List */}
      {similarTopics && similarTopics.length > 0 && (
        <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700">
            <h2 className="text-lg font-semibold text-gray-100">Similar Topics</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              Topics in the knowledge graph related to {machine.machine_type || machine.name}
            </p>
          </div>
          <div className="p-4">
            <div className="space-y-2">
              {similarTopics.map((topic, index) => (
                <div
                  key={topic.topic_path}
                  className="flex items-center justify-between bg-gray-900 rounded-lg border border-gray-700 px-4 py-3"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-lg font-semibold text-gray-500">#{index + 1}</span>
                    <div>
                      <p className="text-gray-200 font-mono text-sm">{topic.topic_path}</p>
                      {topic.field_names && topic.field_names.length > 0 && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          Fields: {topic.field_names.slice(0, 5).join(', ')}
                          {topic.field_names.length > 5 && ` +${topic.field_names.length - 5} more`}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-cyan-400">
                      {(topic.similarity * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-gray-500">similarity</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );

  // ==================== KIOSK MODE ====================
  if (isKiosk) {
    return (
      <div className="fixed inset-0 z-50 bg-gray-950 overflow-y-auto">
        {/* Kiosk Header */}
        <header className="bg-gray-900 border-b border-gray-800 shadow-lg">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                {/* Machine image thumbnail */}
                {machine.image_base64 && (
                  <div className="w-14 h-14 rounded-lg overflow-hidden border border-gray-700">
                    <img
                      src={`data:image/png;base64,${machine.image_base64}`}
                      alt={machine.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}

                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-gray-100">{machine.name}</h1>
                    <div className="flex items-center gap-1.5 bg-gray-800 px-2 py-1 rounded-full">
                      <span className={`w-2 h-2 rounded-full ${statusColors[machine.status]}`} />
                      <span className="text-xs text-gray-200">{statusLabels[machine.status]}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {machine.machine_type && (
                      <span className="text-sm text-gray-400">{machine.machine_type}</span>
                    )}
                    {showCreatedBy && (
                      <span className="inline-flex items-center gap-1.5 text-sm bg-purple-900/40 text-purple-300 px-2.5 py-0.5 rounded-full border border-purple-700/50">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                        </svg>
                        Created by {machine.created_by}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* QR Code + Actions */}
              <div className="flex items-center gap-4">
                <button
                  onClick={handleStartStop}
                  disabled={actionLoading}
                  className={`px-4 py-2 text-white font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 ${
                    machine.status === 'running'
                      ? 'bg-orange-600 hover:bg-orange-700'
                      : 'bg-green-600 hover:bg-green-700'
                  }`}
                >
                  {actionLoading ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                  ) : machine.status === 'running' ? (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                      </svg>
                      Stop
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      Start
                    </>
                  )}
                </button>

                {/* QR Code */}
                {pageUrl && (
                  <div className="bg-white p-2 rounded-lg" title="Scan to open this page">
                    <QRCodeSVG value={pageUrl} size={64} />
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Kiosk Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {renderInfoCards()}
          {renderGraphAndChart()}
          {renderExtraSections()}
        </main>

        {/* Sidebars */}
        <LadderLogicSidebar machine={machine} />
        <MachineChatbot machine={machine} />
      </div>
    );
  }

  // ==================== NORMAL MODE ====================
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/machines"
                className="text-gray-400 hover:text-gray-200 flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                Machines
              </Link>

              {/* Machine image thumbnail */}
              {machine.image_base64 && (
                <div className="w-12 h-12 rounded-lg overflow-hidden border border-gray-700">
                  <img
                    src={`data:image/png;base64,${machine.image_base64}`}
                    alt={machine.name}
                    className="w-full h-full object-cover"
                  />
                </div>
              )}

              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-gray-100">{machine.name}</h1>
                  <div className="flex items-center gap-1.5 bg-gray-900/80 px-2 py-1 rounded-full">
                    <span className={`w-2 h-2 rounded-full ${statusColors[machine.status]}`} />
                    <span className="text-xs text-gray-200">{statusLabels[machine.status]}</span>
                  </div>
                  {showCreatedBy && (
                    <span className="inline-flex items-center gap-1.5 text-xs bg-purple-900/40 text-purple-300 px-2.5 py-0.5 rounded-full border border-purple-700/50">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Created by {machine.created_by}
                    </span>
                  )}
                </div>
                {machine.machine_type && (
                  <p className="text-sm text-gray-400 mt-1">{machine.machine_type}</p>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleStartStop}
                disabled={actionLoading}
                className={`px-4 py-2 text-white font-medium rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 ${
                  machine.status === 'running'
                    ? 'bg-orange-600 hover:bg-orange-700'
                    : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                {actionLoading ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                ) : machine.status === 'running' ? (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                    </svg>
                    Stop
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Start
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {renderInfoCards()}
        {renderGraphAndChart()}
        {renderExtraSections()}
      </main>

      {/* Docked PLC Sidebar (left) */}
      <LadderLogicSidebar machine={machine} />

      {/* Docked Chat Sidebar (right) */}
      <MachineChatbot machine={machine} />
    </div>
  );
}
