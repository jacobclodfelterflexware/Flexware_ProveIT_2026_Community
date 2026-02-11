'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import ChartRenderer from './ChartRenderer';
import type { ChartConfig, StreamMessage } from '@/lib/chart-engine-api';
import { subscribeToChart } from '@/lib/chart-engine-api';

interface DynamicChartProps {
  chartId: string;
  config: ChartConfig;
  streamUrl: string;
  onError?: (error: string) => void;
}

/**
 * DynamicChart component with real-time streaming updates
 */
export default function DynamicChart({
  chartId,
  config,
  streamUrl,
  onError,
}: DynamicChartProps) {
  const [chartConfig, setChartConfig] = useState<ChartConfig>(config);
  const [isStreaming, setIsStreaming] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Update config when prop changes
  useEffect(() => {
    setChartConfig(config);
  }, [config]);

  // Handle incoming stream messages
  const handleStreamMessage = useCallback((message: StreamMessage) => {
    if (message.type === 'data_point' && message.series && message.value !== undefined) {
      setChartConfig((prevConfig) => {
        // Deep clone to avoid mutation
        const newConfig = JSON.parse(JSON.stringify(prevConfig)) as ChartConfig;

        // Find the dataset for this series
        const datasets = newConfig.data.datasets || [];
        let dataset = datasets.find((d) => d.label === message.series);

        if (!dataset) {
          // Create new dataset if not found
          dataset = {
            label: message.series || 'Unknown',
            data: [],
            borderColor: `hsl(${datasets.length * 40}, 70%, 50%)`,
            backgroundColor: `hsla(${datasets.length * 40}, 70%, 50%, 0.1)`,
            fill: false,
            tension: 0.1,
          };
          datasets.push(dataset);
        }

        // Add new data point
        const dataArray = dataset.data as Array<{ x: string | number; y: number }>;
        dataArray.push({
          x: message.timestamp || new Date().toISOString(),
          y: message.value ?? 0,
        });

        // Keep only last 50 points
        if (dataArray.length > 50) {
          dataArray.shift();
        }

        newConfig.data.datasets = datasets;
        return newConfig;
      });

      setLastUpdate(new Date().toLocaleTimeString());
    } else if (message.type === 'connected') {
      setIsStreaming(true);
    } else if (message.type === 'error') {
      onError?.(message.error || 'Stream error');
    }
  }, [onError]);

  // Set up streaming
  useEffect(() => {
    if (!streamUrl) return;

    // Extract chart ID from stream URL
    const chartIdFromUrl = streamUrl.split('/').pop();
    if (!chartIdFromUrl) return;

    const eventSource = subscribeToChart(
      chartIdFromUrl,
      handleStreamMessage,
      () => {
        setIsStreaming(false);
        onError?.('Stream connection lost');
      }
    );

    eventSourceRef.current = eventSource;

    return () => {
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [streamUrl, handleStreamMessage, onError]);

  return (
    <div className="w-full h-full flex flex-col">
      {/* Stream status indicator */}
      {streamUrl && (
        <div className="flex items-center gap-2 mb-2 px-1">
          <span
            className={`w-2 h-2 rounded-full ${
              isStreaming ? 'bg-green-500 animate-pulse' : 'bg-gray-500'
            }`}
          />
          <span className="text-xs text-gray-400">
            {isStreaming ? 'Live' : 'Connecting...'}
          </span>
          {lastUpdate && (
            <span className="text-xs text-gray-500 ml-auto">
              Updated: {lastUpdate}
            </span>
          )}
        </div>
      )}

      {/* Chart */}
      <div className="flex-1 min-h-0">
        <ChartRenderer config={chartConfig} />
      </div>
    </div>
  );
}
