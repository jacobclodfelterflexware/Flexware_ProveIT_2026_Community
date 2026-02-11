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
import {
  type PredictionResponse,
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

interface TopicPredictionPanelProps {
  topicPath: string;
  numericFields: string[];
}

export default function TopicPredictionPanel({ topicPath, numericFields }: TopicPredictionPanelProps) {
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);

  // Auto-select first field
  useEffect(() => {
    if (numericFields.length > 0 && !selectedField) {
      setSelectedField(numericFields[0]);
    } else if (numericFields.length > 0 && selectedField && !numericFields.includes(selectedField)) {
      setSelectedField(numericFields[0]);
    }
  }, [numericFields, selectedField]);

  // Reset state when topic changes
  useEffect(() => {
    setPrediction(null);
  }, [topicPath]);

  // Format label for time display
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

  if (numericFields.length === 0) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-gray-700">
          <h3 className="text-lg font-semibold text-gray-100">Time Series Prediction</h3>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <p className="text-lg font-medium text-gray-400">No numeric fields</p>
            <p className="text-sm mt-1 text-gray-500">This topic has no numeric fields to predict</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100">
          Time Series Prediction
        </h3>
      </div>

      {/* Field selector */}
      <div className="p-4 border-b border-gray-700">
        <label className="block text-xs font-medium text-gray-400 mb-1">Select Field to Predict</label>
        <select
          value={selectedField || ''}
          onChange={(e) => {
            setSelectedField(e.target.value);
            setPrediction(null);
          }}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {numericFields.map((field) => (
            <option key={field} value={field}>
              {field}
            </option>
          ))}
        </select>
      </div>

      {/* Chart Area */}
      <div className="flex-1 p-4 min-h-0">
        {prediction && prediction.predictions.length > 0 ? (
          <Line data={chartData} options={chartOptions} />
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm">Topic predictions will appear automatically once enough data has been collected</p>
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
                Updated: {new Date(prediction.trainedAt).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
