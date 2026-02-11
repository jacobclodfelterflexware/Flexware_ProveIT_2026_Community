'use client';

import { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import type { MachineDefinition } from '@/types/machines';

// Register Chart.js components for line chart
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface MachinePayloadChartProps {
  machine: MachineDefinition;
}

interface PayloadData {
  [fullKey: string]: number; // Using "topic:fieldName" as key
}

interface StreamEvent {
  topic: string;
  payload: Record<string, number>;
  timestamp: string;
  messages_published: number;
}

interface TimeSeriesPoint {
  label: string;
  values: PayloadData;
}

// Field with topic context for unique identification
interface TopicField {
  topic: string;
  fieldName: string;
  fullKey: string; // "topic:fieldName" for unique identification
}

// Rolling window of data points to display
const MAX_DATA_POINTS = 30;

// Fields to exclude from charting
const EXCLUDED_FIELDS = ['timestamp', 'time', 'ts', 'created_at', 'updated_at'];

const CHART_COLORS = [
  { border: 'rgb(59, 130, 246)', background: 'rgba(59, 130, 246, 0.1)' },   // blue
  { border: 'rgb(16, 185, 129)', background: 'rgba(16, 185, 129, 0.1)' },   // green
  { border: 'rgb(245, 158, 11)', background: 'rgba(245, 158, 11, 0.1)' },   // amber
  { border: 'rgb(239, 68, 68)', background: 'rgba(239, 68, 68, 0.1)' },     // red
  { border: 'rgb(139, 92, 246)', background: 'rgba(139, 92, 246, 0.1)' },   // purple
  { border: 'rgb(236, 72, 153)', background: 'rgba(236, 72, 153, 0.1)' },   // pink
  { border: 'rgb(6, 182, 212)', background: 'rgba(6, 182, 212, 0.1)' },     // cyan
  { border: 'rgb(251, 191, 36)', background: 'rgba(251, 191, 36, 0.1)' },   // yellow
  { border: 'rgb(34, 197, 94)', background: 'rgba(34, 197, 94, 0.1)' },     // emerald
  { border: 'rgb(168, 85, 247)', background: 'rgba(168, 85, 247, 0.1)' },   // violet
];

// Compute decimal places needed to show meaningful differences in data
function getAdaptivePrecision(values: number[]): number {
  if (values.length < 2) return 2;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min;
  if (range === 0) return 2;
  const digitsNeeded = Math.ceil(-Math.log10(range)) + 1;
  return Math.max(2, Math.min(10, digitsNeeded));
}

export default function MachinePayloadChart({ machine }: MachinePayloadChartProps) {
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesPoint[]>([]);
  const [currentPayload, setCurrentPayload] = useState<PayloadData | null>(null);
  const [messagesPublished, setMessagesPublished] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [selectedFieldName, setSelectedFieldName] = useState<string | null>(null);
  const [discoveredFields, setDiscoveredFields] = useState<TopicField[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Get all numeric fields from all topics, organized by topic (excluding timestamp-like fields)
  const topicFields = useMemo(() => {
    const allTopics = machine.topics?.length
      ? machine.topics
      : machine.topic_path && machine.fields
        ? [{ topic_path: machine.topic_path, fields: machine.fields }]
        : [];

    const fields: TopicField[] = [];
    allTopics.forEach(topic => {
      topic.fields?.forEach(field => {
        if (field.type === 'number' || field.type === 'integer') {
          // Exclude timestamp-like fields
          const fieldLower = field.name.toLowerCase();
          const isExcluded = EXCLUDED_FIELDS.some(excluded =>
            fieldLower === excluded || fieldLower.includes('timestamp')
          );
          if (!isExcluded) {
            const fullKey = `${topic.topic_path}:${field.name}`;
            fields.push({
              topic: topic.topic_path,
              fieldName: field.name,
              fullKey,
            });
          }
        }
      });
    });
    return fields;
  }, [machine]);

  // Use discovered fields as fallback when definition has no numeric fields
  const effectiveFields = useMemo(() => {
    return topicFields.length > 0 ? topicFields : discoveredFields;
  }, [topicFields, discoveredFields]);

  // Group fields by topic for display
  const fieldsByTopic = useMemo(() => {
    const grouped: Record<string, TopicField[]> = {};
    effectiveFields.forEach(field => {
      if (!grouped[field.topic]) {
        grouped[field.topic] = [];
      }
      grouped[field.topic].push(field);
    });
    return grouped;
  }, [effectiveFields]);

  // Get sorted topic list (only topics with numeric fields)
  const sortedTopics = useMemo(() => {
    return Object.keys(fieldsByTopic).sort();
  }, [fieldsByTopic]);

  // Get fields for selected topic
  const fieldsForSelectedTopic = useMemo(() => {
    if (!selectedTopic) return [];
    return fieldsByTopic[selectedTopic] || [];
  }, [fieldsByTopic, selectedTopic]);

  // Initialize selected topic and field when data changes
  useEffect(() => {
    if (sortedTopics.length > 0 && !selectedTopic) {
      setSelectedTopic(sortedTopics[0]);
    }
  }, [sortedTopics, selectedTopic]);

  useEffect(() => {
    if (fieldsForSelectedTopic.length > 0 && !selectedFieldName) {
      setSelectedFieldName(fieldsForSelectedTopic[0].fieldName);
    } else if (fieldsForSelectedTopic.length > 0) {
      // Check if current field exists in new topic, otherwise reset
      const fieldExists = fieldsForSelectedTopic.some(f => f.fieldName === selectedFieldName);
      if (!fieldExists) {
        setSelectedFieldName(fieldsForSelectedTopic[0].fieldName);
      }
    }
  }, [fieldsForSelectedTopic, selectedFieldName]);

  // Get full key for selected field
  const selectedFullKey = useMemo(() => {
    if (!selectedTopic || !selectedFieldName) return null;
    return `${selectedTopic}:${selectedFieldName}`;
  }, [selectedTopic, selectedFieldName]);

  // Handle topic change
  const handleTopicChange = useCallback((topic: string) => {
    setSelectedTopic(topic);
    // Reset field to first available in new topic
    const fields = fieldsByTopic[topic] || [];
    if (fields.length > 0) {
      setSelectedFieldName(fields[0].fieldName);
    }
  }, [fieldsByTopic]);

  // Subscribe to realtime payloads via SSE
  useEffect(() => {
    if (!machine.id || machine.status !== 'running') {
      setConnectionStatus('disconnected');
      return;
    }

    setConnectionStatus('connecting');
    // Clear previous data when starting fresh
    setTimeSeriesData([]);

    const eventSource = new EventSource(`/api/machines-proxy/${machine.id}/stream`);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnectionStatus('connected');
    };

    eventSource.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);

        // Build payload with topic-prefixed keys
        setCurrentPayload(prev => {
          const updated = { ...(prev || {}) };
          Object.entries(data.payload).forEach(([fieldName, value]) => {
            if (typeof value === 'number') {
              const fullKey = `${data.topic}:${fieldName}`;
              updated[fullKey] = value;
            }
          });
          return updated;
        });

        const now = new Date();
        const timeLabel = now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });

        // Build payload for time series with topic-prefixed keys
        setTimeSeriesData(prev => {
          const latestValues = { ...(prev[prev.length - 1]?.values || {}) };
          Object.entries(data.payload).forEach(([fieldName, value]) => {
            if (typeof value === 'number') {
              const fullKey = `${data.topic}:${fieldName}`;
              latestValues[fullKey] = value;
            }
          });

          const newPoint: TimeSeriesPoint = {
            label: timeLabel,
            values: latestValues,
          };
          const updated = [...prev, newPoint];
          // Keep only the last MAX_DATA_POINTS
          return updated.slice(-MAX_DATA_POINTS);
        });

        // Discover numeric fields from streaming data when definition has none
        if (topicFields.length === 0) {
          Object.entries(data.payload).forEach(([fieldName, value]) => {
            if (typeof value === 'number') {
              const fieldLower = fieldName.toLowerCase();
              const isExcluded = EXCLUDED_FIELDS.some(excluded =>
                fieldLower === excluded || fieldLower.includes('timestamp')
              );
              if (!isExcluded) {
                const fullKey = `${data.topic}:${fieldName}`;
                setDiscoveredFields(prev => {
                  if (prev.some(f => f.fullKey === fullKey)) return prev;
                  return [...prev, { topic: data.topic, fieldName, fullKey }];
                });
              }
            }
          });
        }

        setMessagesPublished(data.messages_published);
        setLastUpdate(timeLabel);
      } catch (err) {
        console.error('Failed to parse payload:', err);
      }
    };

    eventSource.onerror = () => {
      setConnectionStatus('error');
      eventSource.close();
    };

    eventSource.addEventListener('stopped', () => {
      setConnectionStatus('disconnected');
      eventSource.close();
    });

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [machine.id, machine.status]);

  // Build chart data from time series (only selected field)
  const chartData = useMemo(() => {
    if (!selectedFullKey) {
      return { labels: [], datasets: [] };
    }

    const fieldIndex = effectiveFields.findIndex(f => f.fullKey === selectedFullKey);
    const color = CHART_COLORS[Math.max(0, fieldIndex) % CHART_COLORS.length];

    const labels = timeSeriesData.map(point => point.label);
    const data = timeSeriesData.map(point => point.values[selectedFullKey] ?? null);

    const datasets = [{
      label: selectedFieldName || '',
      data,
      borderColor: color.border,
      backgroundColor: color.background,
      borderWidth: 2,
      fill: true,
      tension: 0.3,
      pointRadius: data.length > 100 ? 0 : 2,
      pointHoverRadius: 5,
      pointBackgroundColor: color.border,
      pointBorderColor: color.border,
    }];

    return { labels, datasets };
  }, [timeSeriesData, selectedFullKey, selectedFieldName, effectiveFields]);

  // Compute adaptive precision from the data range for the selected field
  const displayPrecision = useMemo(() => {
    if (!selectedFullKey || timeSeriesData.length < 2) return 2;
    const values = timeSeriesData
      .map(p => p.values[selectedFullKey])
      .filter((v): v is number => v !== null && v !== undefined);
    return getAdaptivePrecision(values);
  }, [timeSeriesData, selectedFullKey]);

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 200,
    },
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleColor: '#f3f4f6',
        bodyColor: '#d1d5db',
        borderColor: '#374151',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          label: function(context: any) {
            const value = context.parsed.y;
            if (typeof value === 'number') {
              return `${context.dataset.label}: ${value.toFixed(displayPrecision)}`;
            }
            return context.formattedValue;
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
        ticks: {
          color: '#6b7280',
          font: { size: 10 },
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 8,
        },
        grid: {
          color: 'rgba(75, 85, 99, 0.2)',
        },
      },
      y: {
        display: true,
        grace: '10%',
        ticks: {
          color: '#6b7280',
          font: { size: 10 },
          padding: 8,
          callback: function(tickValue: number | string) {
            if (typeof tickValue === 'number') {
              return tickValue.toFixed(displayPrecision);
            }
            return tickValue;
          },
        },
        grid: {
          color: 'rgba(75, 85, 99, 0.2)',
        },
      },
    },
  }), [displayPrecision]);

  // Status indicator
  const statusConfig = {
    connecting: { color: 'bg-yellow-500', text: 'Connecting...' },
    connected: { color: 'bg-green-500', text: 'Live' },
    disconnected: { color: 'bg-gray-500', text: 'Disconnected' },
    error: { color: 'bg-red-500', text: 'Error' },
  };

  // Get short topic name for display
  const getTopicShortName = (topic: string) => topic.split('/').pop() || topic;

  if (machine.status !== 'running') {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
          </svg>
          <p className="text-lg font-medium text-gray-400">Machine is not running</p>
          <p className="text-sm mt-1 text-gray-500">Start the machine to see live telemetry</p>
        </div>
      </div>
    );
  }

  if (effectiveFields.length === 0) {
    // If the machine is running, show a discovering state instead of giving up
    if (machine.status === 'running' && connectionStatus !== 'error') {
      return (
        <div className="h-full flex items-center justify-center text-gray-500">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-3"></div>
            <p className="text-sm text-gray-500">Discovering numeric fields from stream...</p>
          </div>
        </div>
      );
    }
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <p className="text-lg font-medium text-gray-400">No numeric fields</p>
          <p className="text-sm mt-1 text-gray-500">This machine has no numeric fields to chart</p>
        </div>
      </div>
    );
  }

  const currentValue = selectedFullKey && currentPayload ? currentPayload[selectedFullKey] : null;
  const fieldIndex = selectedFullKey ? effectiveFields.findIndex(f => f.fullKey === selectedFullKey) : 0;
  const selectedColor = CHART_COLORS[Math.max(0, fieldIndex) % CHART_COLORS.length];

  return (
    <div className="h-full flex flex-col">
      {/* Status bar */}
      <div className="flex items-center justify-between mb-3 px-1">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusConfig[connectionStatus].color} ${connectionStatus === 'connected' ? 'animate-pulse' : ''}`} />
          <span className="text-xs text-gray-400">{statusConfig[connectionStatus].text}</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          {lastUpdate && <span>Updated: {lastUpdate}</span>}
          <span>Messages: {messagesPublished}</span>
        </div>
      </div>

      {/* Selectors Row */}
      <div className="grid grid-cols-2 gap-3 mb-4 min-w-0">
        {/* Topic Dropdown */}
        <div className="min-w-0">
          <label className="block text-xs font-medium text-gray-400 mb-1.5">
            Select Topic
          </label>
          <select
            value={selectedTopic || ''}
            onChange={(e) => handleTopicChange(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer truncate"
          >
            {sortedTopics.map((topic) => (
              <option key={topic} value={topic}>
                {getTopicShortName(topic)}
              </option>
            ))}
          </select>
          {selectedTopic && (
            <div className="mt-1 text-xs text-gray-600 font-mono truncate" title={selectedTopic}>
              {selectedTopic}
            </div>
          )}
        </div>

        {/* Field Radio Buttons */}
        <div className="min-w-0">
          <label className="block text-xs font-medium text-gray-400 mb-1.5">
            Select Field
          </label>
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-2 max-h-20 overflow-y-auto">
            {fieldsForSelectedTopic.length === 0 ? (
              <div className="text-xs text-gray-500 py-1 px-1">No numeric fields</div>
            ) : (
              <div className="space-y-0.5">
                {fieldsForSelectedTopic.map((field) => {
                  const isSelected = selectedFieldName === field.fieldName;
                  const fIndex = topicFields.findIndex(f => f.fullKey === field.fullKey);
                  const color = CHART_COLORS[Math.max(0, fIndex) % CHART_COLORS.length];
                  return (
                    <label
                      key={field.fullKey}
                      className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-gray-700'
                          : 'hover:bg-gray-750'
                      }`}
                    >
                      <input
                        type="radio"
                        name="field-selector"
                        value={field.fieldName}
                        checked={isSelected}
                        onChange={() => setSelectedFieldName(field.fieldName)}
                        className="sr-only"
                      />
                      {/* Custom radio circle */}
                      <span
                        className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                          isSelected
                            ? 'border-blue-500'
                            : 'border-gray-500'
                        }`}
                      >
                        {isSelected && (
                          <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ backgroundColor: color.border }}
                          />
                        )}
                      </span>
                      {/* Field name */}
                      <span className={`text-sm truncate ${isSelected ? 'text-gray-200' : 'text-gray-400'}`}>
                        {field.fieldName}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 min-h-0">
        {timeSeriesData.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-3"></div>
              <p className="text-sm text-gray-500">Waiting for data...</p>
            </div>
          </div>
        ) : !selectedFullKey ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <p className="text-sm">Select a topic and field above to display</p>
            </div>
          </div>
        ) : (
          <Line data={chartData} options={chartOptions} />
        )}
      </div>

      {/* Current value display */}
      {selectedFieldName && (
        <div className="mt-3">
          <div
            className="bg-gray-900 rounded-lg px-4 py-3 border-l-4"
            style={{ borderLeftColor: selectedColor.border }}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-300">{selectedFieldName}</div>
                <div className="text-xs text-gray-500">
                  {selectedTopic ? getTopicShortName(selectedTopic) : ''}
                </div>
              </div>
              <div
                className="text-3xl font-mono font-semibold"
                style={{ color: selectedColor.border }}
              >
                {currentValue !== null && currentValue !== undefined
                  ? typeof currentValue === 'number'
                    ? currentValue.toFixed(displayPrecision)
                    : currentValue
                  : '-'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
