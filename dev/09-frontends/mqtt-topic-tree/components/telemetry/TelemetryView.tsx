'use client';

import { useMemo } from 'react';
import type { ViewTransform } from '@/app/api/view-transform/route';
import TopicTelemetryChart from '@/components/analyzer/TopicTelemetryChart';
import TopicSimilarityPanel from '@/components/analyzer/TopicSimilarityPanel';
import TopicPredictionPanel from '@/components/analyzer/TopicPredictionPanel';
import TopicRegressionPanel from '@/components/analyzer/TopicRegressionPanel';
import TelemetryChatbot from './TelemetryChatbot';

interface TelemetryViewProps {
  transform: ViewTransform;
  topicPath: string;
  isAggregated?: boolean;
  childTopics?: string[];
  onStreamingChange?: (streaming: boolean) => void;
  messageCount?: number;
}

export default function TelemetryView({
  transform,
  topicPath,
  isAggregated = false,
  childTopics,
  onStreamingChange,
  messageCount,
}: TelemetryViewProps) {
  const schema = transform.schema;

  // Get numeric field names from the transform schema
  // Use SOURCE field names (what's actually in the payload), not target/display names
  const numericFields = useMemo(() => {
    const sourceFields = schema.fieldMappings
      .filter(fm => fm.type === 'number' || fm.type === 'integer')
      .map(fm => fm.source);

    return sourceFields.length > 0 ? sourceFields : (schema.numericFields || []);
  }, [schema.fieldMappings, schema.numericFields]);

  return (
    <>
    <div className="space-y-6">
      {/* Topic Info Header */}
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
            <span className="text-xs text-purple-400 bg-purple-900/30 px-2 py-1 rounded flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse"></span>
              Telemetry Active
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
            <div className="text-lg font-semibold text-purple-400 truncate">
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

      {/* ML Analysis Section */}
      {messageCount && messageCount >= 20 ? (
        <div className="space-y-6">
          {/* Time Series Prediction */}
          <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <TopicPredictionPanel
              topicPath={topicPath}
              numericFields={numericFields}
            />
          </div>

          {/* Multilinear Regression */}
          <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
            <TopicRegressionPanel
              topicPath={topicPath}
              numericFields={numericFields}
            />
          </div>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-gray-200">ML Analysis Not Available</h4>
              <p className="text-sm text-gray-400 mt-1">
                Time series prediction and multilinear regression require at least 20 messages.
                <span className="text-amber-400"> This topic has {messageCount ?? 0} messages.</span>
              </p>
            </div>
          </div>
        </div>
      )}

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

    {/* Chatbot Sidebar */}
    <TelemetryChatbot
      topicPath={topicPath}
      transform={transform}
      numericFields={numericFields}
      messageCount={messageCount}
    />
    </>
  );
}
