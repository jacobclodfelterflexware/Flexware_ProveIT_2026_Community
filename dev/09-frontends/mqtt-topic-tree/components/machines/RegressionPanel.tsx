'use client';

import { useEffect, useState, useMemo, useCallback, useRef, memo } from 'react';
import type { MachineDefinition } from '@/types/machines';
import {
  getAllAvailableFields,
  getPredictableFields,
  getCachedRegression,
  type RegressionResponse,
  type TopicWithFields,
  type FeatureSelection,
} from '@/lib/ml-api';
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

interface RegressionPanelProps {
  machine: MachineDefinition;
}

// Tree node structure
interface TreeNode {
  name: string;
  path: string;
  children: Map<string, TreeNode>;
  fields: string[];
  isLeaf: boolean;
}

// Build tree from flat topic list
function buildTopicTree(topics: TopicWithFields[]): TreeNode {
  const root: TreeNode = {
    name: 'root',
    path: '',
    children: new Map(),
    fields: [],
    isLeaf: false,
  };

  for (const topic of topics) {
    const parts = topic.path.split('/');
    let current = root;
    let currentPath = '';

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      currentPath = currentPath ? `${currentPath}/${part}` : part;

      if (!current.children.has(part)) {
        current.children.set(part, {
          name: part,
          path: currentPath,
          children: new Map(),
          fields: [],
          isLeaf: false,
        });
      }
      current = current.children.get(part)!;
    }

    current.isLeaf = true;
    current.fields = topic.fields;
  }

  return root;
}

// TreeBrowser component for selecting target or features
interface TreeBrowserProps {
  tree: TreeNode;
  selectedTopic: string | null;
  selectedField: string | null;
  onSelect: (topic: string, field: string) => void;
  multiSelect?: boolean;
  selectedFeatures?: FeatureSelection[];
  excludeTopic?: string | null;
  excludeField?: string | null;
}

function TreeBrowser({
  tree,
  selectedTopic,
  selectedField,
  onSelect,
  multiSelect = false,
  selectedFeatures = [],
  excludeTopic,
  excludeField
}: TreeBrowserProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  const toggleExpand = (path: string) => {
    setExpandedPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const isFeatureSelected = (topic: string, field: string) => {
    return selectedFeatures.some(f => f.topic === topic && f.field === field);
  };

  const renderNode = (node: TreeNode, depth: number = 0): React.ReactNode => {
    if (node.name === 'root') {
      return Array.from(node.children.values()).map(child => renderNode(child, 0));
    }

    const isExpanded = expandedPaths.has(node.path);
    const hasChildren = node.children.size > 0;
    const isSelected = selectedTopic === node.path;

    return (
      <div key={node.path}>
        <div
          className={`flex items-center gap-1 py-1 px-2 hover:bg-gray-800 cursor-pointer rounded ${
            isSelected && !multiSelect ? 'bg-purple-900/30' : ''
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => {
            if (hasChildren || node.isLeaf) {
              toggleExpand(node.path);
            }
          }}
        >
          {(hasChildren || node.isLeaf) ? (
            <svg
              className={`w-3 h-3 text-gray-500 transition-transform flex-shrink-0 ${isExpanded ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <span className="w-3" />
          )}

          {node.isLeaf ? (
            <svg className="w-4 h-4 text-purple-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          ) : (
            <svg className="w-4 h-4 text-yellow-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          )}

          <span className="text-sm text-gray-300 truncate">{node.name}</span>

          {node.isLeaf && node.fields.length > 0 && (
            <span className="ml-auto text-xs text-gray-500 flex-shrink-0">
              {node.fields.length} fields
            </span>
          )}
        </div>

        {isExpanded && (
          <div>
            {Array.from(node.children.values()).map(child => renderNode(child, depth + 1))}

            {node.isLeaf && node.fields.map(field => {
              const isExcluded = excludeTopic === node.path && excludeField === field;
              const isFieldSelected = multiSelect
                ? isFeatureSelected(node.path, field)
                : (selectedTopic === node.path && selectedField === field);

              if (isExcluded) return null;

              return (
                <div
                  key={`${node.path}:${field}`}
                  className={`flex items-center gap-2 py-1 px-2 hover:bg-gray-800 cursor-pointer rounded ${
                    isFieldSelected ? 'bg-purple-900/40' : ''
                  }`}
                  style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
                  onClick={() => onSelect(node.path, field)}
                >
                  {multiSelect ? (
                    <div className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center ${
                      isFieldSelected
                        ? 'bg-purple-600 border-purple-600'
                        : 'border-gray-600'
                    }`}>
                      {isFieldSelected && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                  ) : (
                    <div className={`w-3 h-3 rounded-full border-2 flex-shrink-0 ${
                      isFieldSelected
                        ? 'border-purple-500 bg-purple-500'
                        : 'border-gray-600'
                    }`} />
                  )}

                  <svg className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
                  </svg>

                  <span className="text-sm text-gray-200">{field}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="overflow-y-auto max-h-48">
      {renderNode(tree)}
    </div>
  );
}

// Regression Results Display Component
function RegressionResults({ regression, targetTopic, targetField }: {
  regression: RegressionResponse;
  targetTopic: string;
  targetField: string;
}) {
  const getTopicShortName = (topic: string) => topic.split('/').pop() || topic;

  // Get display name for a feature - use topic name if field is just "value"
  const getFeatureDisplayName = (topic: string, field: string) => {
    if (field === 'value') {
      return getTopicShortName(topic);
    }
    return field;
  };

  // Prepare data for coefficient bar chart
  const coefficientChartData = useMemo(() => {
    const sortedFeatures = [...regression.features].sort((a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient));

    return {
      labels: sortedFeatures.map(f => getFeatureDisplayName(f.topic, f.field)),
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
  }, [regression.features]);

  const coefficientChartOptions = {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
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
          label: (context: any) => {
            const feature = regression.features.find(f => getFeatureDisplayName(f.topic, f.field) === context.label);
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
        grid: {
          color: 'rgba(75, 85, 99, 0.3)',
        },
        ticks: {
          color: '#9ca3af',
        },
        title: {
          display: true,
          text: 'Coefficient Value',
          color: '#9ca3af',
        }
      },
      y: {
        grid: {
          display: false,
        },
        ticks: {
          color: '#e5e7eb',
          font: {
            size: 12,
          }
        }
      }
    }
  };

  // R² gauge data
  const r2Percentage = regression.rSquared * 100;
  const r2GaugeData = {
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

  const r2GaugeOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: '75%',
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        enabled: false,
      }
    }
  };

  // Format coefficient for display
  const formatCoefficient = (value: number) => {
    if (Math.abs(value) < 0.001) return value.toExponential(2);
    return value.toFixed(4);
  };

  return (
    <div className="space-y-6">
      {/* Model Summary Header */}
      <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-xl p-5 border border-purple-700/30">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h4 className="text-lg font-semibold text-gray-100">Regression Model</h4>
            <p className="text-sm text-gray-400 mt-1">
              Predicting <span className="text-purple-400 font-medium">{targetField === 'value' ? getTopicShortName(targetTopic) : targetField}</span>
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">Data Points</div>
            <div className="text-2xl font-bold text-gray-200">{regression.dataPointsUsed}</div>
          </div>
        </div>

        {/* R² Gauge and Stats */}
        <div className="grid grid-cols-2 gap-6">
          {/* R² Gauge */}
          <div className="flex flex-col items-center">
            <div className="relative w-32 h-20">
              <Doughnut data={r2GaugeData} options={r2GaugeOptions} />
              <div className="absolute inset-0 flex items-end justify-center pb-1">
                <span className={`text-2xl font-bold ${
                  r2Percentage > 70 ? 'text-green-400' :
                  r2Percentage > 40 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {r2Percentage.toFixed(1)}%
                </span>
              </div>
            </div>
            <div className="text-center mt-2">
              <div className="text-sm font-medium text-gray-300">R² Score</div>
              <div className="text-xs text-gray-500">
                {r2Percentage > 70 ? 'Excellent fit' :
                 r2Percentage > 40 ? 'Moderate fit' : 'Weak fit'}
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
      <div className="bg-gray-900/50 rounded-xl p-5 border border-gray-700/50">
        <h4 className="text-sm font-semibold text-gray-300 mb-4">Feature Coefficients</h4>
        <div style={{ height: `${Math.max(150, regression.features.length * 40)}px` }}>
          <Bar data={coefficientChartData} options={coefficientChartOptions} />
        </div>
        <p className="text-xs text-gray-500 mt-3">
          Positive coefficients (green) increase the target; negative (red) decrease it.
        </p>
      </div>

      {/* Detailed Coefficients Table */}
      <div className="bg-gray-900/50 rounded-xl p-5 border border-gray-700/50">
        <h4 className="text-sm font-semibold text-gray-300 mb-4">Coefficient Details</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Feature</th>
                <th className="text-left py-2 px-3 text-gray-400 font-medium">Source</th>
                <th className="text-right py-2 px-3 text-gray-400 font-medium">Coefficient</th>
                <th className="text-right py-2 px-3 text-gray-400 font-medium">p-value</th>
                <th className="text-center py-2 px-3 text-gray-400 font-medium">Sig.</th>
              </tr>
            </thead>
            <tbody>
              {regression.features.map((feature, idx) => {
                const isSignificant = feature.pValue !== undefined && feature.pValue < 0.05;
                return (
                  <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="py-3 px-3">
                      <span className="font-medium text-gray-200">{getFeatureDisplayName(feature.topic, feature.field)}</span>
                    </td>
                    <td className="py-3 px-3 text-gray-400">
                      {feature.machineName || (feature.field === 'value' ? '—' : getTopicShortName(feature.topic))}
                    </td>
                    <td className="py-3 px-3 text-right font-mono">
                      <span className={feature.coefficient >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {feature.coefficient >= 0 ? '+' : ''}{formatCoefficient(feature.coefficient)}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-gray-300">
                      {feature.pValue !== undefined
                        ? (feature.pValue < 0.001 ? '<0.001' : feature.pValue.toFixed(4))
                        : '—'}
                    </td>
                    <td className="py-3 px-3 text-center">
                      {isSignificant ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-green-500/20 text-green-400">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </span>
                      ) : (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-600/20 text-gray-500">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                          </svg>
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {/* Intercept row */}
              <tr className="bg-gray-800/30">
                <td className="py-3 px-3">
                  <span className="font-medium text-gray-400 italic">Intercept</span>
                </td>
                <td className="py-3 px-3 text-gray-500">—</td>
                <td className="py-3 px-3 text-right font-mono text-gray-300">
                  {formatCoefficient(regression.intercept)}
                </td>
                <td className="py-3 px-3 text-right text-gray-500">—</td>
                <td className="py-3 px-3 text-center text-gray-500">—</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Model Equation */}
      <div className="bg-gray-900/50 rounded-xl p-5 border border-gray-700/50">
        <h4 className="text-sm font-semibold text-gray-300 mb-3">Model Equation</h4>
        <div className="bg-gray-950 rounded-lg p-4 overflow-x-auto">
          <code className="text-sm text-gray-300 whitespace-nowrap">
            <span className="text-purple-400">{targetField === 'value' ? getTopicShortName(targetTopic) : targetField}</span>
            <span className="text-gray-500"> = </span>
            <span className="text-blue-400">{formatCoefficient(regression.intercept)}</span>
            {regression.features.map((f, i) => (
              <span key={i}>
                <span className="text-gray-500"> {f.coefficient >= 0 ? '+' : '-'} </span>
                <span className="text-blue-400">{formatCoefficient(Math.abs(f.coefficient))}</span>
                <span className="text-gray-500"> × </span>
                <span className="text-green-400">{getFeatureDisplayName(f.topic, f.field)}</span>
              </span>
            ))}
          </code>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
        <span>Analysis completed with {regression.dataPointsUsed} aligned data points</span>
        {regression.trainedAt && (
          <span>Updated: {new Date(regression.trainedAt).toLocaleString()}</span>
        )}
      </div>
    </div>
  );
}

function RegressionPanel({ machine }: RegressionPanelProps) {
  const [allTopics, setAllTopics] = useState<TopicWithFields[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(true);
  const [targetTopic, setTargetTopic] = useState<string | null>(null);
  const [targetField, setTargetField] = useState<string | null>(null);
  const [showTargetSelector, setShowTargetSelector] = useState(false);
  const [selectedFeatures, setSelectedFeatures] = useState<FeatureSelection[]>([]);
  const [showFeatureSelector, setShowFeatureSelector] = useState(false);
  const [regression, setRegression] = useState<RegressionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoAnalysisPending, setAutoAnalysisPending] = useState(true);
  const hasAutoRun = useRef(false);
  const hasLoadedTopics = useRef(false);

  const topicTree = useMemo(() => buildTopicTree(allTopics), [allTopics]);

  useEffect(() => {
    // Only load once per component mount
    if (hasLoadedTopics.current) return;
    hasLoadedTopics.current = true;

    async function loadTopics() {
      setLoadingTopics(true);
      try {
        // Load all available topics for the tree browser
        const response = await getAllAvailableFields();
        setAllTopics(response.topics);

        // Get machine's predictable fields (same API as PredictionPanel)
        if (machine.id) {
          const predictableFields = await getPredictableFields(machine.id);

          // Convert to machine topics format and collect value fields
          const allMachineFields: FeatureSelection[] = [];
          for (const [topicPath, fields] of Object.entries(predictableFields.fieldsByTopic)) {
            // Prefer 'value' field, fallback to first numeric-looking field
            const valueField = fields.find(f => f === 'value')
              || fields.find(f => !['timestamp', 'asset_id', 'machine_id', 'id'].includes(f))
              || fields[0];
            if (valueField) {
              allMachineFields.push({ topic: topicPath, field: valueField });
            }
          }

          if (allMachineFields.length > 0) {
            // Set first field as target
            const firstField = allMachineFields[0];
            setTargetTopic(firstField.topic);
            setTargetField(firstField.field);

            // Set remaining fields as features
            setSelectedFeatures(allMachineFields.slice(1));
          }
        }
      } catch (err) {
        console.error('Failed to load available fields:', err);
      } finally {
        setLoadingTopics(false);
      }
    }

    loadTopics();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTargetSelect = (topic: string, field: string) => {
    setTargetTopic(topic);
    setTargetField(field);
    setRegression(null);
    setShowTargetSelector(false);
    setSelectedFeatures(prev => prev.filter(f => !(f.topic === topic && f.field === field)));
  };

  const toggleFeature = useCallback((topic: string, field: string) => {
    if (topic === targetTopic && field === targetField) return;

    setSelectedFeatures(prev => {
      const exists = prev.some(f => f.topic === topic && f.field === field);
      if (exists) {
        return prev.filter(f => !(f.topic === topic && f.field === field));
      } else {
        return [...prev, { topic, field }];
      }
    });
  }, [targetTopic, targetField]);

  const removeFeature = useCallback((topic: string, field: string) => {
    setSelectedFeatures(prev => prev.filter(f => !(f.topic === topic && f.field === field)));
  }, []);

  const getTopicShortName = (topic: string) => topic.split('/').pop() || topic;

  // Auto-run analysis when machine fields are auto-selected on initial load
  // First check for cached results before training
  useEffect(() => {
    if (
      !loadingTopics &&
      !hasAutoRun.current &&
      targetTopic &&
      targetField &&
      selectedFeatures.length > 0 &&
      !loading &&
      machine.id
    ) {
      hasAutoRun.current = true;
      setAutoAnalysisPending(false); // Clear pending state - we're starting analysis

      // Check cache — models are trained automatically in the background
      getCachedRegression(machine.id, targetTopic, targetField, selectedFeatures)
        .then(cached => {
          if (cached) {
            setRegression(cached);
          }
          // No cache means model hasn't been trained yet — will appear automatically
        })
        .catch(() => {
          // Cache check failed — regression will appear once trained
        });
    } else if (!loadingTopics && !hasAutoRun.current && (!targetTopic || selectedFeatures.length === 0)) {
      // No valid fields to analyze - clear pending state and show empty state
      setAutoAnalysisPending(false);
    }
  }, [loadingTopics, targetTopic, targetField, selectedFeatures, loading, machine.id]);

  // Show loading spinner on initial load or while auto-analysis is pending
  if ((loadingTopics && allTopics.length === 0) || (autoAnalysisPending && !regression)) {
    return (
      <div className="min-h-[400px] flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500 mx-auto mb-3"></div>
          <p className="text-sm text-gray-500">
            {loadingTopics ? 'Loading available fields...' : 'Checking for analysis data...'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between flex-shrink-0">
        <h3 className="text-lg font-semibold text-gray-100">
          Multilinear Regression
        </h3>
      </div>

      {/* Controls - Collapsible when results shown */}
      <div className={`border-b border-gray-700 flex-shrink-0 ${regression ? 'bg-gray-900/50' : ''}`}>
        <div className="p-4 space-y-3">
          {/* Target Selection */}
          <div>
            <label className="block text-xs font-medium text-gray-400 mb-1">Target Variable (Y)</label>
            <button
              onClick={() => setShowTargetSelector(!showTargetSelector)}
              className="w-full text-left px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:border-gray-600 flex items-center justify-between"
            >
              {targetTopic && targetField ? (
                <span className="text-gray-200">
                  <span className="text-purple-400">{getTopicShortName(targetTopic)}</span>
                  <span className="text-gray-500 mx-1">/</span>
                  <span>{targetField}</span>
                </span>
              ) : (
                <span className="text-gray-500">Select target variable...</span>
              )}
              <svg className={`w-4 h-4 text-gray-500 transition-transform ${showTargetSelector ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showTargetSelector && (
              <div className="mt-2 bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
                <TreeBrowser
                  tree={topicTree}
                  selectedTopic={targetTopic}
                  selectedField={targetField}
                  onSelect={handleTargetSelect}
                />
              </div>
            )}
          </div>

          {/* Feature Selection */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-gray-400">Input Features (X)</label>
              <span className="text-xs text-gray-500">{selectedFeatures.length} selected</span>
            </div>

            {selectedFeatures.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {selectedFeatures.map((feat, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded-full text-xs"
                  >
                    <span className="text-purple-400">{getTopicShortName(feat.topic)}</span>
                    <span className="text-gray-500">/</span>
                    <span>{feat.field}</span>
                    <button
                      onClick={() => removeFeature(feat.topic, feat.field)}
                      className="ml-0.5 hover:text-purple-100"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                ))}
              </div>
            )}

            <button
              onClick={() => setShowFeatureSelector(!showFeatureSelector)}
              className="w-full text-left px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:border-gray-600 flex items-center justify-between"
            >
              <span>{showFeatureSelector ? 'Hide browser' : 'Browse topics to add features...'}</span>
              <svg className={`w-4 h-4 transition-transform ${showFeatureSelector ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showFeatureSelector && (
              <div className="mt-2 bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
                <TreeBrowser
                  tree={topicTree}
                  selectedTopic={null}
                  selectedField={null}
                  onSelect={toggleFeature}
                  multiSelect={true}
                  selectedFeatures={selectedFeatures}
                  excludeTopic={targetTopic}
                  excludeField={targetField}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results Area */}
      <div className="p-4 pb-6">
        {loading ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-purple-500 mx-auto mb-4"></div>
              <p className="text-sm text-gray-400">Running regression analysis...</p>
              <p className="text-xs text-gray-500 mt-1">This may take a few seconds</p>
            </div>
          </div>
        ) : error || (regression && regression.features.length === 0) ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-700 flex items-center justify-center">
                <span className="text-2xl font-bold text-gray-400">!</span>
              </div>
              <p className="text-sm">Not enough data for prediction</p>
              {regression && regression.dataPointsUsed !== undefined && (
                <p className="text-xs text-gray-600 mt-1">
                  {regression.dataPointsUsed} data points (need 30+)
                </p>
              )}
            </div>
          </div>
        ) : regression && regression.features.length > 0 && targetTopic && targetField ? (
          <RegressionResults
            regression={regression}
            targetTopic={targetTopic}
            targetField={targetField}
          />
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500 max-w-sm">
              <svg className="w-16 h-16 mx-auto mb-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              <p className="text-lg font-medium text-gray-400 mb-2">Awaiting Results</p>
              <p className="text-sm">
                Regression results will appear automatically once enough data has been collected.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Memoize to prevent re-renders when parent polls and recreates machine object
export default memo(RegressionPanel, (prevProps, nextProps) => {
  // Only re-render if machine ID changes
  return prevProps.machine.id === nextProps.machine.id;
});
