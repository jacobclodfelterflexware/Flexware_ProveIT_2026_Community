'use client';

import { useEffect, useState, useMemo, useCallback, useRef, memo } from 'react';
import {
  getCachedRegression,
  type RegressionResponse,
  type FeatureSelection,
  type FeatureInfo,
} from '@/lib/ml-api';

interface SimilarTopic {
  path: string;
  numericFields: string[];
  similarity?: number;
}
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

// Helper to get short topic name (last segment of path)
const getTopicShortName = (topicPath: string): string => {
  const segments = topicPath.split('/');
  return segments[segments.length - 1] || topicPath;
};

// Helper to get descriptive feature label combining topic and field
const getFeatureLabel = (feature: FeatureInfo): string => {
  const topicName = getTopicShortName(feature.topic);
  return `${topicName}.${feature.field}`;  // e.g., "Infeed.value"
};

interface TopicRegressionPanelProps {
  topicPath: string;
  numericFields: string[];
}

function TopicRegressionPanel({ topicPath, numericFields }: TopicRegressionPanelProps) {
  const [targetField, setTargetField] = useState<string | null>(null);
  const [regression, setRegression] = useState<RegressionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasAutoRun = useRef(false);

  // Cross-topic regression state
  const [similarTopics, setSimilarTopics] = useState<SimilarTopic[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const crossTopicMode = numericFields.length < 2;

  // Reset when topic changes
  useEffect(() => {
    setRegression(null);
    setError(null);
    hasAutoRun.current = false;
    setSimilarTopics([]);
    if (numericFields.length > 0) {
      setTargetField(numericFields[0]);
    }
  }, [topicPath, numericFields]);

  // Fetch similar topics when in cross-topic mode
  useEffect(() => {
    if (!crossTopicMode || !topicPath) return;

    async function fetchSimilarTopics() {
      setSimilarLoading(true);
      try {
        // Get similar topics via similarity search
        const res = await fetch(`/api/graph/similar-search?q=${encodeURIComponent(topicPath)}&k=15`);
        if (!res.ok) throw new Error('Failed to fetch similar topics');
        const data = await res.json();

        // Fetch payload for each to get numeric fields (stop after 5 with numeric data)
        const topicsWithFields: SimilarTopic[] = [];
        for (const result of data.results || []) {
          if (result.topic_path === topicPath) continue;
          if (topicsWithFields.length >= 5) break;

          try {
            const payloadRes = await fetch(`/api/topic/payload?path=${encodeURIComponent(result.topic_path)}`);
            if (payloadRes.ok) {
              const payloadData = await payloadRes.json();
              if (payloadData.numericFields?.length > 0) {
                topicsWithFields.push({
                  path: result.topic_path,
                  numericFields: payloadData.numericFields,
                  similarity: result.similarity,
                });
              }
            }
          } catch {
            // Skip topics that fail to fetch
          }
        }

        // Track paths we already have to avoid duplicates
        const existingPaths = new Set(topicsWithFields.map(t => t.path));

        // Step 1: Try TRUE siblings first (topics with exact same parent)
        // This is more reliable than hierarchical which returns cousins
        if (topicsWithFields.length < 5) {
          console.log('[Regression] Only found', topicsWithFields.length, 'similar topics, trying true siblings first...');

          const siblingsRes = await fetch(`/api/graph/siblings?path=${encodeURIComponent(topicPath)}`);
          if (siblingsRes.ok) {
            const siblingsData = await siblingsRes.json();
            console.log('[Regression] Siblings API found', siblingsData.count || 0, 'true siblings:',
              siblingsData.siblings?.map((s: { path: string }) => s.path.split('/').pop()).join(', '));

            for (const sibling of siblingsData.siblings || []) {
              if (existingPaths.has(sibling.path)) continue;
              if (topicsWithFields.length >= 8) break;

              try {
                const payloadRes = await fetch(`/api/topic/payload?path=${encodeURIComponent(sibling.path)}`);
                if (payloadRes.ok) {
                  const payloadData = await payloadRes.json();
                  console.log('[Regression] Sibling', sibling.path.split('/').pop(),
                    '- numericFields:', payloadData.numericFields?.length || 0,
                    payloadData.numericFields || []);
                  if (payloadData.numericFields?.length > 0) {
                    topicsWithFields.push({
                      path: sibling.path,
                      numericFields: payloadData.numericFields,
                      similarity: 0.95, // High similarity for true siblings
                    });
                    existingPaths.add(sibling.path);
                  }
                } else {
                  console.log('[Regression] Sibling', sibling.path.split('/').pop(), '- payload fetch failed:', payloadRes.status);
                }
              } catch (e) {
                console.log('[Regression] Sibling', sibling.path.split('/').pop(), '- error:', e);
              }
            }
            console.log('[Regression] After siblings:', topicsWithFields.length, 'total topics');
          }
        }

        // Step 2: If still not enough, try hierarchical API (cousins from different branches)
        if (topicsWithFields.length < 5) {
          console.log('[Regression] Still only', topicsWithFields.length, 'topics, trying hierarchical fallback...');

          const hierarchicalRes = await fetch(
            `/api/graph/hierarchical-topics?topic=${encodeURIComponent(topicPath)}&k=30`
          );

          if (hierarchicalRes.ok) {
            const hierarchicalData = await hierarchicalRes.json();
            console.log('[Regression] Hierarchical API returned', hierarchicalData.count || 0, 'related topics');

            let checked = 0;
            let noNumeric = 0;
            let failed = 0;

            for (const result of hierarchicalData.results || []) {
              const resultPath = result.topic || result.topicPath;
              if (!resultPath || resultPath === topicPath) continue;
              if (existingPaths.has(resultPath)) continue;
              if (topicsWithFields.length >= 8) break;

              checked++;
              try {
                const payloadRes = await fetch(`/api/topic/payload?path=${encodeURIComponent(resultPath)}`);
                if (payloadRes.ok) {
                  const payloadData = await payloadRes.json();
                  if (payloadData.numericFields?.length > 0) {
                    topicsWithFields.push({
                      path: resultPath,
                      numericFields: payloadData.numericFields,
                      similarity: result.similarity || result.score,
                    });
                    existingPaths.add(resultPath);
                  } else {
                    noNumeric++;
                  }
                } else {
                  failed++;
                }
              } catch {
                failed++;
              }
            }
            console.log('[Regression] Hierarchical: checked', checked, '| no numeric:', noNumeric, '| failed:', failed);
            console.log('[Regression] After hierarchical fallback:', topicsWithFields.length, 'total topics');
          }
        }

        setSimilarTopics(topicsWithFields);
      } catch (err) {
        console.error('Failed to fetch similar topics:', err);
        setSimilarTopics([]);
      } finally {
        setSimilarLoading(false);
      }
    }

    fetchSimilarTopics();
  }, [crossTopicMode, topicPath]);

  // Get feature fields (all numeric fields except target)
  const featureFields = useMemo(() => {
    if (!targetField) return [];
    return numericFields.filter(f => f !== targetField);
  }, [numericFields, targetField]);

  // Run regression analysis
  const handleAnalyze = useCallback(async () => {
    if (!topicPath || !targetField) return;

    // Check if we have enough features for regression
    if (crossTopicMode) {
      if (similarTopics.length === 0) return;
    } else {
      if (featureFields.length === 0) return;
    }

    setLoading(true);
    setError(null);

    try {
      let features: FeatureSelection[];

      if (crossTopicMode) {
        // Use first numeric field from each similar topic as features
        features = similarTopics.map(t => ({
          topic: t.path,
          field: t.numericFields[0],
        }));
      } else {
        // Normal mode: use other fields from same topic
        features = featureFields.map(field => ({
          topic: topicPath,
          field,
        }));
      }

      // Check for cached regression (trained automatically in background)
      const result = await getCachedRegression(
        '_topic_analyzer_',
        topicPath,
        targetField,
        features
      );
      setRegression(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Regression analysis failed');
      setRegression(null);
    } finally {
      setLoading(false);
    }
  }, [topicPath, targetField, featureFields, crossTopicMode, similarTopics]);

  // Auto-run when component mounts with valid fields
  useEffect(() => {
    if (hasAutoRun.current || loading || similarLoading || !targetField) return;

    // Check if we can run
    const canRun = crossTopicMode
      ? similarTopics.length > 0
      : featureFields.length > 0;

    if (canRun) {
      hasAutoRun.current = true;
      handleAnalyze();
    }
  }, [targetField, featureFields, loading, similarLoading, crossTopicMode, similarTopics, handleAnalyze]);

  // Format coefficient for display
  const formatCoefficient = (value: number) => {
    if (Math.abs(value) < 0.001) return value.toExponential(2);
    return value.toFixed(4);
  };

  // Prepare chart data
  const coefficientChartData = useMemo(() => {
    if (!regression) return { labels: [], datasets: [] };

    const sortedFeatures = [...regression.features].sort(
      (a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient)
    );

    return {
      labels: sortedFeatures.map(f => getFeatureLabel(f)),
      datasets: [{
        label: 'Coefficient',
        data: sortedFeatures.map(f => f.coefficient),
        backgroundColor: sortedFeatures.map(f =>
          f.coefficient >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)'
        ),
        borderColor: sortedFeatures.map(f =>
          f.coefficient >= 0 ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'
        ),
        borderWidth: 1,
        borderRadius: 4,
      }]
    };
  }, [regression]);

  const coefficientChartOptions = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleColor: '#f3f4f6',
        bodyColor: '#d1d5db',
        borderColor: '#374151',
        borderWidth: 1,
        padding: 12,
        callbacks: {
          label: (context: any) => {
            // Find feature by matching the full label (topic.field)
            const feature = regression?.features.find(f => getFeatureLabel(f) === context.label);
            const lines = [`Coefficient: ${context.raw.toFixed(4)}`];
            if (feature?.pValue !== undefined) {
              lines.push(`p-value: ${feature.pValue < 0.001 ? '<0.001' : feature.pValue.toFixed(4)}`);
            }
            return lines;
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(75, 85, 99, 0.3)' },
        ticks: { color: '#9ca3af' },
        title: { display: true, text: 'Coefficient Value', color: '#9ca3af' }
      },
      y: {
        grid: { display: false },
        ticks: { color: '#e5e7eb', font: { size: 12 } }
      }
    }
  };

  // R² gauge data
  const r2GaugeData = useMemo(() => {
    if (!regression) return { labels: [], datasets: [] };
    const r2Percentage = regression.rSquared * 100;
    return {
      labels: ['Explained', 'Unexplained'],
      datasets: [{
        data: [r2Percentage, 100 - r2Percentage],
        backgroundColor: [
          r2Percentage > 70 ? 'rgba(34, 197, 94, 0.8)' :
          r2Percentage > 40 ? 'rgba(234, 179, 8, 0.8)' : 'rgba(239, 68, 68, 0.8)',
          'rgba(55, 65, 81, 0.5)'
        ],
        borderWidth: 0,
        circumference: 180,
        rotation: 270,
      }]
    };
  }, [regression]);

  const r2GaugeOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '75%',
    plugins: {
      legend: { display: false },
      tooltip: { enabled: false }
    }
  };

  // Show loading state when fetching similar topics
  if (crossTopicMode && similarLoading) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-gray-700">
          <h3 className="text-lg font-semibold text-gray-100">Cross-Topic Regression</h3>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
            <p className="text-lg font-medium text-gray-400">Finding Similar Topics</p>
            <p className="text-sm mt-1 text-gray-500">
              Searching for related topics with numeric data...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Show message if cross-topic mode but no similar topics found
  if (crossTopicMode && similarTopics.length === 0 && !similarLoading) {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-gray-700">
          <h3 className="text-lg font-semibold text-gray-100">Cross-Topic Regression</h3>
        </div>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p className="text-lg font-medium text-gray-400">No Similar Topics Found</p>
            <p className="text-sm mt-1 text-gray-500">
              Could not find related topics with numeric data for regression
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-gray-100">
            {crossTopicMode ? 'Cross-Topic Regression' : 'Multilinear Regression'}
          </h3>
          {crossTopicMode && (
            <span className="text-xs px-2 py-0.5 rounded bg-blue-900/50 text-blue-300">
              {similarTopics.length} similar topics
            </span>
          )}
        </div>
        <button
          onClick={handleAnalyze}
          disabled={loading || (crossTopicMode ? similarTopics.length === 0 : featureFields.length === 0)}
          className="px-4 py-2 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50 flex items-center gap-2 font-medium"
        >
          {loading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          )}
          Analyze
        </button>
      </div>

      {/* Target selector */}
      <div className="p-4 border-b border-gray-700">
        <label className="block text-xs font-medium text-gray-400 mb-1">
          Target Variable (Y) - predict this using {crossTopicMode ? 'similar topics' : 'other fields'}
        </label>
        <select
          value={targetField || ''}
          onChange={(e) => {
            setTargetField(e.target.value);
            setRegression(null);
            hasAutoRun.current = false;
          }}
          disabled={loading}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:opacity-50"
        >
          {numericFields.map((field) => (
            <option key={field} value={field}>
              {field}
            </option>
          ))}
        </select>
        {crossTopicMode ? (
          similarTopics.length > 0 && (
            <div className="mt-3">
              <p className="text-xs text-gray-500 mb-2">Features from similar topics:</p>
              <div className="space-y-1">
                {similarTopics.map((t, i) => (
                  <div key={t.path} className="flex items-center gap-2 text-xs">
                    <span className="text-blue-400">{t.numericFields[0]}</span>
                    <span className="text-gray-600">from</span>
                    <span className="text-gray-400 truncate" title={t.path}>
                      {t.path.split('/').slice(-2).join('/')}
                    </span>
                    {t.similarity !== undefined && (
                      <span className="text-gray-600">
                        ({(t.similarity * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        ) : (
          featureFields.length > 0 && (
            <p className="mt-2 text-xs text-gray-500">
              Features (X): {featureFields.join(', ')}
            </p>
          )
        )}
      </div>

      {/* Results Area */}
      <div className="flex-1 p-4 overflow-y-auto">
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-purple-500 mx-auto mb-4"></div>
              <p className="text-sm text-gray-400">Running regression analysis...</p>
            </div>
          </div>
        ) : error ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center max-w-md">
              <svg className="w-12 h-12 mx-auto mb-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-sm text-red-400 mb-3">{error}</p>
              <button
                onClick={handleAnalyze}
                className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg"
              >
                Try Again
              </button>
            </div>
          </div>
        ) : regression ? (
          <div className="space-y-6">
            {/* Model Summary */}
            <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-xl p-5 border border-purple-700/30">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h4 className="text-lg font-semibold text-gray-100">Regression Model</h4>
                  <p className="text-sm text-gray-400 mt-1">
                    Predicting <span className="text-purple-400 font-medium">{targetField}</span>
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">Data Points</div>
                  <div className="text-2xl font-bold text-gray-200">{regression.dataPointsUsed}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                {/* R² Gauge */}
                <div className="flex flex-col items-center">
                  <div className="relative w-32 h-20">
                    <Doughnut data={r2GaugeData} options={r2GaugeOptions} />
                    <div className="absolute inset-0 flex items-end justify-center pb-1">
                      <span className={`text-2xl font-bold ${
                        regression.rSquared * 100 > 70 ? 'text-green-400' :
                        regression.rSquared * 100 > 40 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {(regression.rSquared * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <div className="text-center mt-2">
                    <div className="text-sm font-medium text-gray-300">R² Score</div>
                    <div className="text-xs text-gray-500">
                      {regression.rSquared * 100 > 70 ? 'Excellent fit' :
                       regression.rSquared * 100 > 40 ? 'Moderate fit' : 'Weak fit'}
                    </div>
                  </div>
                </div>

                {/* Quick Stats */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-400">Features</span>
                    <span className="text-sm font-medium text-gray-200">{regression.features.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-400">Intercept</span>
                    <span className="text-sm font-mono text-gray-200">{formatCoefficient(regression.intercept)}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-400">Significant (p&lt;0.05)</span>
                    <span className="text-sm font-medium text-green-400">
                      {regression.features.filter(f => f.pValue !== undefined && f.pValue < 0.05).length}/{regression.features.length}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Coefficient Chart */}
            {regression.features.length > 0 && (
              <div className="bg-gray-900/50 rounded-xl p-5 border border-gray-700/50">
                <h4 className="text-sm font-semibold text-gray-300 mb-4">Feature Coefficients</h4>
                <div style={{ height: `${Math.max(120, regression.features.length * 40)}px` }}>
                  <Bar data={coefficientChartData} options={coefficientChartOptions} />
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Positive coefficients (green) increase the target; negative (red) decrease it.
                </p>
              </div>
            )}

            {/* Model Equation */}
            <div className="bg-gray-900/50 rounded-xl p-5 border border-gray-700/50">
              <h4 className="text-sm font-semibold text-gray-300 mb-3">Model Equation</h4>
              <div className="bg-gray-950 rounded-lg p-4 overflow-x-auto">
                <code className="text-sm text-gray-300 whitespace-nowrap">
                  <span className="text-purple-400">{targetField}</span>
                  <span className="text-gray-500"> = </span>
                  <span className="text-blue-400">{formatCoefficient(regression.intercept)}</span>
                  {regression.features.map((f, i) => (
                    <span key={i}>
                      <span className="text-gray-500"> {f.coefficient >= 0 ? '+' : '-'} </span>
                      <span className="text-blue-400">{formatCoefficient(Math.abs(f.coefficient))}</span>
                      <span className="text-gray-500"> × </span>
                      <span className="text-green-400">{getFeatureLabel(f)}</span>
                    </span>
                  ))}
                </code>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
              <span>Analysis completed with {regression.dataPointsUsed} data points</span>
              {regression.trainedAt && (
                <span>Updated: {new Date(regression.trainedAt).toLocaleString()}</span>
              )}
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500 max-w-sm">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <p className="text-lg font-medium text-gray-400 mb-2">Ready to Analyze</p>
              <p className="text-sm">
                Click Analyze to run multilinear regression on the topic's numeric fields.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(TopicRegressionPanel, (prevProps, nextProps) => {
  return prevProps.topicPath === nextProps.topicPath &&
         JSON.stringify(prevProps.numericFields) === JSON.stringify(nextProps.numericFields);
});
