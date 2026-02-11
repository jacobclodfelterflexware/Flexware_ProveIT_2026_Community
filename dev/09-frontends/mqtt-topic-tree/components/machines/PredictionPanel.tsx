'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
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
import {
  getPredictableFields,
  getPrediction,
  type PredictionResponse,
  type FieldsByTopic,
} from '@/lib/ml-api';

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

interface PredictionPanelProps {
  machine: MachineDefinition;
}

export default function PredictionPanel({ machine }: PredictionPanelProps) {
  const [fieldsByTopic, setFieldsByTopic] = useState<FieldsByTopic | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch available fields
  useEffect(() => {
    if (!machine.id) return;

    async function loadFields() {
      try {
        const fields = await getPredictableFields(machine.id!);
        setFieldsByTopic(fields);

        // Auto-select first topic and field
        const topics = Object.keys(fields.fieldsByTopic);
        if (topics.length > 0) {
          setSelectedTopic(topics[0]);
          const topicFields = fields.fieldsByTopic[topics[0]];
          if (topicFields.length > 0) {
            setSelectedField(topicFields[0]);
          }
        }
      } catch (err) {
        console.error('Failed to load predictable fields:', err);
      }
    }

    loadFields();
  }, [machine.id]);

  // Fetch cached prediction
  const fetchPrediction = useCallback(async () => {
    if (!machine.id || !selectedTopic || !selectedField) return;

    setLoading(true);
    setError(null);

    try {
      const result = await getPrediction(machine.id, selectedField, selectedTopic, 'day');
      setPrediction(result);
    } catch (err: any) {
      // 404 means prediction not yet trained — not an error
      if (err?.message?.includes('404') || err?.status === 404) {
        setPrediction(null);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load prediction');
      }
    } finally {
      setLoading(false);
    }
  }, [machine.id, selectedTopic, selectedField]);

  // Fetch prediction when selection changes
  useEffect(() => {
    fetchPrediction();
  }, [fetchPrediction]);

  // Handle topic change
  const handleTopicChange = (topic: string) => {
    setSelectedTopic(topic);
    const fields = fieldsByTopic?.fieldsByTopic[topic] || [];
    if (fields.length > 0 && !fields.includes(selectedField || '')) {
      setSelectedField(fields[0]);
    }
  };

  // Get available topics and fields
  const topics = useMemo(() => {
    return Object.keys(fieldsByTopic?.fieldsByTopic || {});
  }, [fieldsByTopic]);

  const fields = useMemo(() => {
    if (!selectedTopic || !fieldsByTopic) return [];
    return fieldsByTopic.fieldsByTopic[selectedTopic] || [];
  }, [selectedTopic, fieldsByTopic]);

  // Format label - always show time since we use 1-minute intervals
  const formatLabel = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  };

  // Build chart data
  const chartData = useMemo(() => {
    if (!prediction) return { labels: [], datasets: [] };

    const historicalLabels = prediction.historical.map(p => formatLabel(p.date));
    const predictionLabels = prediction.predictions.map(p => formatLabel(p.date));
    const allLabels = [...historicalLabels, ...predictionLabels];

    const historicalValues = prediction.historical.map(p => p.value);
    const predictionValues = prediction.predictions.map(p => p.value);
    const lowerBound = prediction.predictions.map(p => p.lower);
    const upperBound = prediction.predictions.map(p => p.upper);

    return {
      labels: allLabels,
      datasets: [
        {
          label: 'Historical',
          data: [...historicalValues, ...Array(predictionLabels.length).fill(null)],
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          pointRadius: 2,
        },
        {
          label: 'Prediction',
          data: [...Array(historicalLabels.length).fill(null), ...predictionValues],
          borderColor: 'rgb(16, 185, 129)',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          borderWidth: 2,
          borderDash: [5, 5],
          fill: false,
          tension: 0.3,
          pointRadius: 3,
        },
        {
          label: 'Upper Bound',
          data: [...Array(historicalLabels.length).fill(null), ...upperBound],
          borderColor: 'rgba(16, 185, 129, 0.3)',
          backgroundColor: 'transparent',
          borderWidth: 1,
          borderDash: [2, 2],
          fill: false,
          pointRadius: 0,
        },
        {
          label: 'Lower Bound',
          data: [...Array(historicalLabels.length).fill(null), ...lowerBound],
          borderColor: 'rgba(16, 185, 129, 0.3)',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          borderWidth: 1,
          borderDash: [2, 2],
          fill: '-1',
          pointRadius: 0,
        },
      ],
    };
  }, [prediction]);

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          color: '#9ca3af',
          font: { size: 11 },
          filter: (item: any) => !item.text.includes('Bound'),
        },
      },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleColor: '#f3f4f6',
        bodyColor: '#d1d5db',
        borderColor: '#374151',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        ticks: {
          color: '#6b7280',
          font: { size: 10 },
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 10,
        },
        grid: { color: 'rgba(75, 85, 99, 0.2)' },
      },
      y: {
        ticks: {
          color: '#6b7280',
          font: { size: 10 },
        },
        grid: { color: 'rgba(75, 85, 99, 0.2)' },
      },
    },
  }), []);

  // Short topic name helper
  const getTopicShortName = (topic: string) => topic.split('/').pop() || topic;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100">
          Time Series Prediction
        </h3>
      </div>

      {/* Controls */}
      <div className="p-4 border-b border-gray-700">
        <div className="grid grid-cols-2 gap-3">
          {/* Topic Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Topic</label>
            <select
              value={selectedTopic || ''}
              onChange={(e) => handleTopicChange(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {topics.map((topic) => (
                <option key={topic} value={topic}>
                  {getTopicShortName(topic)}
                </option>
              ))}
            </select>
          </div>

          {/* Field Selector */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Field</label>
            <select
              value={selectedField || ''}
              onChange={(e) => setSelectedField(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {fields.map((field) => (
                <option key={field} value={field}>
                  {field}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Chart Area */}
      <div className="flex-1 p-4 min-h-0">
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-3"></div>
              <p className="text-sm text-gray-500">Loading prediction...</p>
            </div>
          </div>
        ) : prediction && prediction.predictions.length > 0 ? (
          <Line data={chartData} options={chartOptions} />
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-700 flex items-center justify-center">
                <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-sm">Predictions will appear automatically once enough data has been collected</p>
            </div>
          </div>
        )}
      </div>

      {/* Metrics Footer */}
      {prediction && prediction.metrics && (
        <div className="px-4 py-3 border-t border-gray-700 bg-gray-900/50">
          <div className="flex items-center justify-between text-xs">
            <div className="flex gap-4">
              {prediction.metrics.mape != null && (
                <span className="text-gray-400">
                  MAPE: <span className="text-gray-200">{prediction.metrics.mape.toFixed(2)}%</span>
                </span>
              )}
              {prediction.metrics.rmse != null && (
                <span className="text-gray-400">
                  RMSE: <span className="text-gray-200">{prediction.metrics.rmse.toFixed(2)}</span>
                </span>
              )}
              <span className="text-gray-400">
                Data points: <span className="text-gray-200">{prediction.dataPointsUsed}</span>
              </span>
            </div>
            {prediction.trainedAt && (
              <span className="text-gray-500">
                Updated: {new Date(prediction.trainedAt).toLocaleDateString()}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
