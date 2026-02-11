'use client';

import { useMemo } from 'react';
import type { ViewTransform } from '@/app/api/view-transform/route';
import TopicTelemetryChart from '@/components/analyzer/TopicTelemetryChart';
import TopicSimilarityPanel from '@/components/analyzer/TopicSimilarityPanel';
import TopicPredictionPanel from '@/components/analyzer/TopicPredictionPanel';
import TopicRegressionPanel from '@/components/analyzer/TopicRegressionPanel';

interface TransformedMachineViewProps {
  transform: ViewTransform;
  topicPath: string;
  isAggregated?: boolean;
  childTopics?: string[];
  onStreamingChange?: (streaming: boolean) => void;
  messageCount?: number;
}

export default function TransformedMachineView({
  transform,
  topicPath,
  isAggregated = false,
  childTopics,
  onStreamingChange,
  messageCount,
}: TransformedMachineViewProps) {
  const schema = transform.schema;

  // Get numeric field names from the transform schema
  // Use SOURCE field names (what's actually in the payload), not target/display names
  // For single topics, the field names are direct (e.g., "value")
  // For aggregated topics, they're prefixed (e.g., "availability.value")
  const numericFields = useMemo(() => {
    // Extract source field names from fieldMappings for numeric types
    const sourceFields = schema.fieldMappings
      .filter(fm => fm.type === 'number' || fm.type === 'integer')
      .map(fm => fm.source);

    // Fall back to schema.numericFields if no mappings found
    return sourceFields.length > 0 ? sourceFields : (schema.numericFields || []);
  }, [schema.fieldMappings, schema.numericFields]);

  return (
    <div className="space-y-6">
      {/* Machine Info Header */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-100">{topicPath}</h2>
            {schema.description && (
              <p className="text-sm text-gray-400 mt-1">{schema.description}</p>
            )}
          </div>
          <div className="flex items-center gap-4">
            {schema.machineType && (
              <span className="text-xs text-gray-500 bg-gray-700 px-2 py-1 rounded">
                {schema.machineType}
              </span>
            )}
            <span className="text-xs text-green-400 bg-green-900/30 px-2 py-1 rounded flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
              Transform Active
            </span>
          </div>
        </div>

        {/* Field Mappings Preview */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-2">
          <div className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-500">Total Messages</div>
            <div className="text-lg font-semibold text-gray-100">
              {messageCount?.toLocaleString() ?? '-'}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-500">Fields</div>
            <div className="text-lg font-semibold text-gray-100">
              {schema.fieldMappings.length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-500">Numeric</div>
            <div className="text-lg font-semibold text-gray-100">
              {schema.numericFields.length}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-500">Primary Metric</div>
            <div className="text-lg font-semibold text-blue-400 truncate">
              {schema.primaryMetric || '-'}
            </div>
          </div>
          <div className="bg-gray-700/50 rounded p-2">
            <div className="text-xs text-gray-500">Data Mode</div>
            <div className={`text-lg font-semibold ${isAggregated ? 'text-amber-400' : 'text-green-400'}`}>
              {isAggregated ? 'Aggregated' : 'Direct'}
            </div>
          </div>
        </div>
      </div>

      {/* Two-column layout for Similarity (left) and Chart (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Similarity Graph - Left */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700">
            <h3 className="text-lg font-semibold text-gray-100">Topic Similarity</h3>
          </div>
          <div className="h-[400px] p-4">
            <TopicSimilarityPanel topicPath={topicPath} />
          </div>
        </div>

        {/* Realtime Chart - Right */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-700">
            <h3 className="text-lg font-semibold text-gray-100">Live Telemetry</h3>
          </div>
          <div className="h-[400px] p-4">
            <TopicTelemetryChart
              topicPath={topicPath}
              numericFields={numericFields}
              isAggregated={isAggregated}
              onStreamingChange={onStreamingChange}
            />
          </div>
        </div>
      </div>

      {/* Time Series Prediction - Full width row */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <TopicPredictionPanel
          topicPath={topicPath}
          numericFields={numericFields}
        />
      </div>

      {/* Multilinear Regression - Full width row */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <TopicRegressionPanel
          topicPath={topicPath}
          numericFields={numericFields}
        />
      </div>

      {/* Transform Details (collapsible) */}
      <details className="bg-gray-800 rounded-lg border border-gray-700">
        <summary className="px-4 py-3 cursor-pointer hover:bg-gray-750 text-gray-300">
          View Transform Schema (Debug)
        </summary>
        <div className="px-4 py-3 border-t border-gray-700">
          <pre className="text-xs text-gray-400 overflow-auto max-h-64">
            {JSON.stringify(schema, null, 2)}
          </pre>
        </div>
      </details>
    </div>
  );
}
