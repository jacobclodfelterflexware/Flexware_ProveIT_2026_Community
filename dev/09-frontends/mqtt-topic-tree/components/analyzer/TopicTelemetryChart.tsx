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

// Register Chart.js components
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

interface TopicTelemetryChartProps {
  topicPath: string;
  numericFields: string[];
  onStreamingChange?: (streaming: boolean) => void;
  isAggregated?: boolean;
}

interface StreamEvent {
  topic: string;
  payload: Record<string, number>;
  timestamp: string;
  type?: string;
}

interface TimeSeriesPoint {
  label: string;
  values: Record<string, number>;
}

const MAX_DATA_POINTS = 30;

const CHART_COLORS = [
  { border: 'rgb(59, 130, 246)', background: 'rgba(59, 130, 246, 0.1)' },   // blue
  { border: 'rgb(16, 185, 129)', background: 'rgba(16, 185, 129, 0.1)' },   // green
  { border: 'rgb(245, 158, 11)', background: 'rgba(245, 158, 11, 0.1)' },   // amber
  { border: 'rgb(239, 68, 68)', background: 'rgba(239, 68, 68, 0.1)' },     // red
  { border: 'rgb(139, 92, 246)', background: 'rgba(139, 92, 246, 0.1)' },   // purple
  { border: 'rgb(236, 72, 153)', background: 'rgba(236, 72, 153, 0.1)' },   // pink
  { border: 'rgb(6, 182, 212)', background: 'rgba(6, 182, 212, 0.1)' },     // cyan
  { border: 'rgb(251, 191, 36)', background: 'rgba(251, 191, 36, 0.1)' },   // yellow
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

export default function TopicTelemetryChart({
  topicPath,
  numericFields,
  onStreamingChange,
  isAggregated = false,
}: TopicTelemetryChartProps) {
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesPoint[]>([]);
  const [currentPayload, setCurrentPayload] = useState<Record<string, number> | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Initialize selected field
  useEffect(() => {
    if (numericFields.length > 0 && !selectedField) {
      setSelectedField(numericFields[0]);
    } else if (numericFields.length > 0 && selectedField && !numericFields.includes(selectedField)) {
      setSelectedField(numericFields[0]);
    }
  }, [numericFields, selectedField]);

  // Connect to SSE stream
  useEffect(() => {
    if (!topicPath) {
      setConnectionStatus('disconnected');
      return;
    }

    // Reset data on topic change
    setTimeSeriesData([]);
    setCurrentPayload(null);
    setMessageCount(0);
    setConnectionStatus('connecting');
    onStreamingChange?.(false);

    // Add aggregate parameter if this is an aggregated topic
    const streamUrl = `/api/topic/stream?topic=${encodeURIComponent(topicPath)}${isAggregated ? '&aggregate=true' : ''}`;
    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnectionStatus('connected');
      onStreamingChange?.(true);
    };

    eventSource.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);

        // Skip connection and heartbeat events
        if (data.type === 'connected' || data.type === 'heartbeat') return;

        // Extract numeric values from payload
        const numericValues: Record<string, number> = {};
        for (const [key, value] of Object.entries(data.payload)) {
          if (typeof value === 'number') {
            numericValues[key] = value;
          }
        }

        setCurrentPayload(numericValues);
        setMessageCount(prev => prev + 1);

        const now = new Date();
        const timeLabel = now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });

        setTimeSeriesData(prev => {
          const newPoint: TimeSeriesPoint = {
            label: timeLabel,
            values: numericValues,
          };
          const updated = [...prev, newPoint];
          return updated.slice(-MAX_DATA_POINTS);
        });

        setLastUpdate(timeLabel);
      } catch (err) {
        console.error('Failed to parse stream event:', err);
      }
    };

    eventSource.onerror = () => {
      // Don't close the connection - EventSource will auto-reconnect
      // Just temporarily show connecting status while it reconnects
      setConnectionStatus('connecting');
    };

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
      onStreamingChange?.(false);
    };
  }, [topicPath, onStreamingChange]);

  // Build chart data
  const chartData = useMemo(() => {
    if (!selectedField) {
      return { labels: [], datasets: [] };
    }

    const fieldIndex = numericFields.indexOf(selectedField);
    const color = CHART_COLORS[Math.max(0, fieldIndex) % CHART_COLORS.length];

    const labels = timeSeriesData.map(point => point.label);
    const data = timeSeriesData.map(point => point.values[selectedField] ?? null);

    return {
      labels,
      datasets: [{
        label: selectedField,
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
      }],
    };
  }, [timeSeriesData, selectedField, numericFields]);

  // Compute adaptive precision from the data range for the selected field
  const displayPrecision = useMemo(() => {
    if (!selectedField || timeSeriesData.length < 2) return 2;
    const values = timeSeriesData
      .map(p => p.values[selectedField])
      .filter((v): v is number => v !== null && v !== undefined);
    return getAdaptivePrecision(values);
  }, [timeSeriesData, selectedField]);

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

  const statusConfig = {
    connecting: { color: 'bg-yellow-500', text: 'Connecting...' },
    connected: { color: 'bg-green-500', text: 'Live' },
    disconnected: { color: 'bg-gray-500', text: 'Disconnected' },
    error: { color: 'bg-red-500', text: 'Error' },
  };

  if (numericFields.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <p className="text-lg font-medium text-gray-400">No numeric fields</p>
          <p className="text-sm mt-1 text-gray-500">This topic has no numeric fields to chart</p>
        </div>
      </div>
    );
  }

  const currentValue = selectedField && currentPayload ? currentPayload[selectedField] : null;
  const fieldIndex = selectedField ? numericFields.indexOf(selectedField) : 0;
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
          <span>Messages: {messageCount}</span>
        </div>
      </div>

      {/* Field selector */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-gray-400 mb-1.5">
          Select Field
        </label>
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-2 max-h-20 overflow-y-auto">
          <div className="flex flex-wrap gap-1">
            {numericFields.map((field, idx) => {
              const isSelected = selectedField === field;
              const color = CHART_COLORS[idx % CHART_COLORS.length];
              return (
                <button
                  key={field}
                  onClick={() => setSelectedField(field)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    isSelected
                      ? 'text-white'
                      : 'text-gray-400 bg-gray-800 hover:bg-gray-700'
                  }`}
                  style={isSelected ? { backgroundColor: color.border } : undefined}
                >
                  {field}
                </button>
              );
            })}
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
        ) : (
          <Line data={chartData} options={chartOptions} />
        )}
      </div>

      {/* Current value display */}
      {selectedField && (
        <div className="mt-3">
          <div
            className="bg-gray-900 rounded-lg px-4 py-3 border-l-4"
            style={{ borderLeftColor: selectedColor.border }}
          >
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-gray-300">{selectedField}</div>
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
