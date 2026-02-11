'use client';

import type { MachineDefinition } from '@/types/machines';
import PredictionPanel from './PredictionPanel';
import RegressionPanel from './RegressionPanel';

interface MLInsightsSectionProps {
  machine: MachineDefinition;
}

export default function MLInsightsSection({ machine }: MLInsightsSectionProps) {
  // Only show ML insights for machines with an ID (saved machines)
  if (!machine.id) {
    return null;
  }

  return (
    <div className="mt-6">
      {/* Section Header */}
      <div className="flex items-center gap-3 mb-4">
        <svg className="w-6 h-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
        <h2 className="text-xl font-semibold text-gray-100">ML Insights</h2>
        <span className="px-2 py-0.5 text-xs bg-purple-900/50 text-purple-300 rounded-full">
          AutoGluon
        </span>
      </div>

      {/* Prediction Panel - Full width on its own row */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden h-[450px] mb-6">
        <PredictionPanel machine={machine} />
      </div>

      {/* Regression Panel - Full width below, auto-expands with content */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden min-h-[450px]">
        <RegressionPanel key={machine.id} machine={machine} />
      </div>

      {/* Info note */}
      <div className="mt-4 flex items-start gap-2 text-xs text-gray-500">
        <svg className="w-4 h-4 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p>
          Predictions are generated using AutoGluon time series models trained on daily aggregated historical data.
          Models are automatically updated daily at 02:00 UTC. Use the refresh button for on-demand updates.
        </p>
      </div>
    </div>
  );
}
