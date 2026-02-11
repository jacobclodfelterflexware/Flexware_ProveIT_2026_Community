'use client';

import { useEffect, useState } from 'react';
import TopicNode from './TopicNode';
import JsonTreeViewer from './JsonTreeViewer';
import GraphVisualizer from './graph/GraphVisualizer';
import TabNavigation, { TabId } from './tabs/TabNavigation';
import EMQXPanel from './tabs/EMQXPanel';
import EMQXCompactPanel from './tabs/EMQXCompactPanel';
import KnowledgeGraphPanel from './tabs/KnowledgeGraphPanel';
import DashboardGraphVisualization from './dashboard/DashboardGraphVisualization';
import SuggestSchemaDialog from './schemas/SuggestSchemaDialog';
import { SerializableTopicNode } from '@/lib/topic-tree-builder';

interface DashboardState {
  tree: SerializableTopicNode | null;
  stats: {
    totalTopics: number;
    totalMessages: number;
    lastUpdate: number;
  };
  connected: boolean;
}

export default function Dashboard() {
  const [state, setState] = useState<DashboardState>({
    tree: null,
    stats: {
      totalTopics: 0,
      totalMessages: 0,
      lastUpdate: Date.now(),
    },
    connected: false,
  });

  const [selectedTopic, setSelectedTopic] = useState<SerializableTopicNode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('topics');
  const [showSuggestDialog, setShowSuggestDialog] = useState(false);
  const [selectedBroker, setSelectedBroker] = useState<'uncurated' | 'curated'>('uncurated');
  const [fetchedPayload, setFetchedPayload] = useState<{
    payload: Record<string, unknown> | null;
    timestamp: string | null;
    loading: boolean;
    error: string | null;
  }>({ payload: null, timestamp: null, loading: false, error: null });

  useEffect(() => {
    // Only connect to SSE when on topics tab
    if (activeTab !== 'topics') return;

    let eventSource: EventSource | null = null;

    const connectToSSE = () => {
      try {
        // Pass broker parameter to filter by broker
        eventSource = new EventSource(`/api/mqtt?broker=${selectedBroker}`);

        eventSource.onopen = () => {
          console.log('[SSE] Connected to MQTT stream');
          setError(null);
        };

        eventSource.addEventListener('tree', (event) => {
          try {
            const data = JSON.parse(event.data);
            setState((prev) => ({
              ...prev,
              tree: data.tree,
              stats: data.stats,
              connected: true,
            }));
          } catch (err) {
            console.error('[SSE] Error parsing tree data:', err);
          }
        });

        eventSource.addEventListener('connection', (event) => {
          try {
            const data = JSON.parse(event.data);
            setState((prev) => ({
              ...prev,
              connected: data.connected,
            }));
          } catch (err) {
            console.error('[SSE] Error parsing connection data:', err);
          }
        });

        eventSource.onerror = (err) => {
          console.error('[SSE] Connection error:', err);
          setError('Connection to MQTT broker lost. Attempting to reconnect...');
          eventSource?.close();

          // Attempt to reconnect after 5 seconds
          setTimeout(() => {
            connectToSSE();
          }, 5000);
        };
      } catch (err) {
        console.error('[SSE] Failed to establish connection:', err);
        setError('Failed to connect to MQTT broker');
      }
    };

    connectToSSE();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [activeTab, selectedBroker]);

  // Fetch payload when topic is selected
  useEffect(() => {
    if (!selectedTopic?.isLeaf) {
      setFetchedPayload({ payload: null, timestamp: null, loading: false, error: null });
      return;
    }

    const fetchPayload = async () => {
      setFetchedPayload(prev => ({ ...prev, loading: true, error: null }));
      try {
        const res = await fetch(`/api/topic/payload?path=${encodeURIComponent(selectedTopic.fullPath)}`);
        if (!res.ok) {
          const data = await res.json();
          throw new Error(data.error || 'Failed to fetch payload');
        }
        const data = await res.json();
        setFetchedPayload({
          payload: data.payload,
          timestamp: data.timestamp,
          loading: false,
          error: null,
        });
      } catch (err) {
        setFetchedPayload({
          payload: null,
          timestamp: null,
          loading: false,
          error: (err as Error).message,
        });
      }
    };

    fetchPayload();
  }, [selectedTopic]);

  const formatTime = (timestamp: number): string => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <div className={`bg-gray-900 ${activeTab === 'emqx' ? 'h-screen flex flex-col overflow-hidden' : 'min-h-screen'}`}>
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            {/* Title */}
            <div>
              <h1 className="text-2xl font-bold text-gray-100">MQTT Topic Explorer</h1>
              <p className="text-sm text-gray-400 mt-1">Real-time MQTT topic tree visualization</p>
            </div>

            {/* Navigation and Status */}
            <div className="flex items-center gap-4">
              <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />

              <div className="flex items-center gap-2 pl-4 border-l border-gray-600">
                <div
                  className={`w-2.5 h-2.5 rounded-full ${
                    state.connected ? 'bg-green-500' : 'bg-red-500'
                  }`}
                ></div>
                <span className="text-sm text-gray-300">
                  {state.connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Tab Content */}
      {activeTab === 'topics' && (
        <>
          {/* Error Banner */}
          {error && (
            <div className="bg-red-900/20 border-l-4 border-red-500 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg
                    className="h-5 w-5 text-red-400"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-red-300">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Stats Bar with Broker Selector */}
          <div className="bg-gray-800 border-b border-gray-700">
            <div className="px-4 sm:px-6 lg:px-8 py-3">
              <div className="flex items-center justify-between">
                <div className="flex space-x-8 text-sm">
                  <div>
                    <span className="text-gray-400">Topics:</span>
                    <span className="ml-2 font-semibold text-gray-100">
                      {state.stats.totalTopics}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Messages:</span>
                    <span className="ml-2 font-semibold text-gray-100">
                      {state.stats.totalMessages}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Last Update:</span>
                    <span className="ml-2 font-semibold text-gray-100">
                      {formatTime(state.stats.lastUpdate)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Data Source:</span>
                  <select
                    value={selectedBroker}
                    onChange={(e) => setSelectedBroker(e.target.value as 'uncurated' | 'curated')}
                    className="bg-gray-700 border border-gray-600 text-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="uncurated">Uncurated Broker (1883)</option>
                    <option value="curated">Curated Broker (1884)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="px-4 sm:px-6 lg:px-8 py-6">
            {/* EMQX Dashboard at top */}
            <EMQXCompactPanel />

            {/* Row 1: Topic Tree (left) + Knowledge Graph (right) */}
            <div
              className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6"
              style={{ height: '600px' }}
            >
              {/* Topic Tree Panel - Left */}
              <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 flex flex-col h-full relative z-10 overflow-hidden min-h-0">
                <div className="border-b border-gray-700 px-6 py-4 flex-shrink-0">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-gray-100">Topic Tree</h2>
                    <div className="flex items-center gap-4 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-green-500"></span>
                        Conformant
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                        Non-conformant
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-yellow-500"></span>
                        Mixed
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 rounded-full bg-gray-500"></span>
                        Unbound
                      </span>
                    </div>
                  </div>
                </div>
                <div className="overflow-auto flex-1">
                  {state.tree && state.tree.children.length > 0 ? (
                    state.tree.children.map((child) => (
                      <TopicNode
                        key={child.fullPath}
                        node={child}
                        level={0}
                        onSelectTopic={setSelectedTopic}
                        selectedTopic={selectedTopic?.fullPath}
                      />
                    ))
                  ) : (
                    <div className="p-6 text-center text-gray-400">
                      {state.connected
                        ? 'Waiting for MQTT messages...'
                        : 'Connecting to MQTT broker...'}
                    </div>
                  )}
                </div>
              </div>

              {/* Knowledge Graph - Right */}
              <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden h-full relative z-10 min-h-0">
                <DashboardGraphVisualization className="w-full h-full" />
              </div>
            </div>

            {/* Row 2: Topic Details - full width */}
            <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 relative z-20">
              <div className="border-b border-gray-700 px-6 py-4">
                <h2 className="text-lg font-semibold text-gray-100">Topic Details</h2>
              </div>
              <div className="p-6">
                {selectedTopic ? (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Column 1: Basic Info */}
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">
                          Topic Path
                        </label>
                        <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 font-mono text-sm text-gray-100 break-all">
                          {selectedTopic.fullPath}
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-1">
                          Message Count
                        </label>
                        <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
                          {selectedTopic.messageCount}
                        </div>
                      </div>

                      {(fetchedPayload.timestamp || selectedTopic.lastMessage) && (
                        <div>
                          <label className="block text-sm font-medium text-gray-300 mb-1">
                            Last Message Time
                          </label>
                          <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100">
                            {new Date(Number(fetchedPayload.timestamp) || selectedTopic.lastMessage!.timestamp).toLocaleString()}
                          </div>
                        </div>
                      )}

                      {/* Schema Actions */}
                      {selectedTopic.isLeaf && (
                        <div className="pt-4 border-t border-gray-700">
                          <button
                            onClick={() => setShowSuggestDialog(true)}
                            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                          >
                            Suggest Schema
                          </button>
                          {selectedTopic.boundProposalName && (
                            <span className="ml-3 text-sm text-gray-400">
                              Bound to: <span className="text-purple-400">{selectedTopic.boundProposalName}</span>
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Column 2: Payload */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Payload
                      </label>
                      <div className="bg-black border border-gray-700 text-green-400 rounded p-4 overflow-auto font-mono text-sm" style={{ maxHeight: '300px', minHeight: '200px' }}>
                        {fetchedPayload.loading ? (
                          <div className="text-gray-400">Loading payload...</div>
                        ) : fetchedPayload.error ? (
                          <div className="text-red-400">{fetchedPayload.error}</div>
                        ) : fetchedPayload.payload ? (
                          <JsonTreeViewer data={fetchedPayload.payload} />
                        ) : (
                          <div className="text-gray-500">No payload available</div>
                        )}
                      </div>
                    </div>

                    {/* Column 3: Knowledge Graph Context */}
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Knowledge Graph Context
                      </label>
                      <GraphVisualizer
                        topicPath={selectedTopic.fullPath}
                      />
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-gray-400 py-12">
                    Select a topic to view details
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'emqx' && (
        <div className="flex-1 min-h-0">
          <EMQXPanel />
        </div>
      )}

      {activeTab === 'graph' && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <KnowledgeGraphPanel />
        </div>
      )}

      {/* Suggest Schema Dialog */}
      {showSuggestDialog && selectedTopic && (
        <SuggestSchemaDialog
          topicPath={selectedTopic.fullPath}
          payload={selectedTopic.lastMessage?.payload}
          onClose={() => setShowSuggestDialog(false)}
          onCreated={() => {
            setShowSuggestDialog(false);
            // Optionally refresh data here
          }}
        />
      )}
    </div>
  );
}
