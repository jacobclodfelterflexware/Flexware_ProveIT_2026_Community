'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import type {
  GeneratedMachineResponse,
  FieldDefinition,
  FieldType,
  FormulaSuggestionResponse,
  IntervalSuggestionResponse,
  UnifiedSuggestionResponse,
  TopicSuggestion,
  TopicDefinition,
  SimilarTopicContext,
  GenerateLadderResponse,
} from '@/types/machines';
import {
  getFormulaSuggestions,
  getIntervalSuggestion,
  getUnifiedSuggestion,
  createMachine,
  startMachine,
  generateLadderLogic,
  saveLadderLogic,
  generateSMProfile,
  DuplicateMachineError,
} from '@/lib/machines-api';
import type { SMProfile } from '@/types/machines';
import TopicTreeBrowser from './TopicTreeBrowser';

// Dynamic import for GraphVisualization to avoid SSR/WebGL issues
const GraphVisualization = dynamic(() => import('./GraphVisualization'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
        <p className="text-gray-400 text-sm">Loading visualization...</p>
      </div>
    </div>
  )
});

interface ConnectWizardProps {
  machine: GeneratedMachineResponse;
  machineName: string;
  imageBase64?: string;
  autoPilotMode?: boolean;
  connectMode?: boolean;
  createdBy?: string;
  onClose: () => void;
  onComplete: (machineId?: string) => void;
}

// Multi-step wizard flow
type Step = 'topics' | 'schema' | 'formulas' | 'interval' | 'ladder' | 'smprofile' | 'confirm';

export default function ConnectWizard({
  machine,
  machineName,
  imageBase64,
  autoPilotMode = false,
  connectMode = false,
  createdBy,
  onClose,
  onComplete,
}: ConnectWizardProps) {
  const [step, setStep] = useState<Step>('topics');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Auto-pilot state
  const [isAutoPilot, setIsAutoPilot] = useState(autoPilotMode);
  const [isConnectMode] = useState(connectMode);
  const [autoPilotCountdown, setAutoPilotCountdown] = useState(20);
  const [graphCountdown, setGraphCountdown] = useState(8); // Countdown for fullscreen graph view

  // Unified suggestion state
  const [unifiedSuggestion, setUnifiedSuggestion] = useState<UnifiedSuggestionResponse | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [showTreeBrowser, setShowTreeBrowser] = useState(false);
  const [browsingTopicIndex, setBrowsingTopicIndex] = useState<number | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showGraphFullscreen, setShowGraphFullscreen] = useState(!connectMode); // Skip graph for connect mode
  const [graphReady, setGraphReady] = useState(false); // Track when graph layout is complete

  // Multi-topic state (when topic_pattern === 'split_by_metric')
  const [selectedTopics, setSelectedTopics] = useState<TopicSuggestion[]>([]);
  const [isMultiTopic, setIsMultiTopic] = useState(false);

  // Field name editing state
  const [editingField, setEditingField] = useState<{topicIdx: number, fieldIdx: number} | null>(null);

  // Placeholder parameter state
  const [placeholderValues, setPlaceholderValues] = useState<Record<string, string>>({});
  const [placeholderSuggestions, setPlaceholderSuggestions] = useState<Record<string, string[]>>({});
  const [originalTopicPaths, setOriginalTopicPaths] = useState<string[]>([]); // Store original paths with placeholders

  // Skip and Add Level state
  const SKIP_VALUE = '__SKIP__';
  const [insertedLevels, setInsertedLevels] = useState<Record<string, string>>({}); // key = "after_{parentKey}"
  const [showAddLevel, setShowAddLevel] = useState<string | null>(null); // Which "after_X" is being edited

  // Hierarchy position mapping for suggestions
  const hierarchyPositions: Record<string, number> = {
    'enterprise': 1,
    'site': 2,
    'area': 3,
    'line': 4,
    'cell': 5,
  };

  // Get suggestions for a position from similar topics (for Add Level feature)
  const getSuggestionsForPosition = (position: number): string[] => {
    if (!unifiedSuggestion?.similar_results?.length) return [];
    const suggestions = new Set<string>();
    for (const result of unifiedSuggestion.similar_results) {
      const segments = result.topic_path.split('/');
      if (segments[position] && !segments[position].startsWith('{')) {
        suggestions.add(segments[position]);
      }
    }
    return Array.from(suggestions).slice(0, 5);
  };

  // Additional suggestions state
  const [formulaSuggestion, setFormulaSuggestion] = useState<FormulaSuggestionResponse | null>(null);
  const [intervalSuggestion, setIntervalSuggestion] = useState<IntervalSuggestionResponse | null>(null);

  // Final configuration
  const [fields, setFields] = useState<FieldDefinition[]>(machine.fields);
  const [publishInterval, setPublishInterval] = useState(machine.publish_interval_ms);
  const [useOriginalSchema, setUseOriginalSchema] = useState(false);

  // Ladder logic state
  const [ladderResponse, setLadderResponse] = useState<GenerateLadderResponse | null>(null);
  const [ladderLoading, setLadderLoading] = useState(false);
  const [ladderError, setLadderError] = useState<string | null>(null);

  // SM Profile state
  const [smprofileData, setSMProfileData] = useState<SMProfile | null>(null);
  const [smprofileLoading, setSMProfileLoading] = useState(false);
  const [smprofileError, setSMProfileError] = useState<string | null>(null);

  // Fetch unified suggestion on mount
  useEffect(() => {
    const fetchUnifiedSuggestion = async () => {
      setLoading(true);
      setIsSearching(true);
      setGraphReady(false);  // Reset graph ready state for new search
      setError(null);

      console.log('[Wizard] Fetching unified suggestion for:', {
        machine_type: machine.machine_type,
        machineName,
        fieldCount: machine.fields.length,
      });

      try {
        const result = await getUnifiedSuggestion(machine.machine_type, machineName, machine.fields);
        console.log('[Wizard] Unified suggestion received:', {
          suggested_topic: result.suggested_topic,
          confidence: result.confidence,
          similar_results_count: result.similar_results?.length || 0,
          suggested_fields_count: result.suggested_fields?.length || 0,
        });
        setUnifiedSuggestion(result);

        // Check if multi-topic pattern was detected
        const multiTopic = result.topic_pattern === 'split_by_metric' && result.suggested_topics?.length > 1;
        setIsMultiTopic(multiTopic);

        // Apply LLM suggestions regardless of confidence
        // Similarity-based suggestions are still useful for novel machines
        if (multiTopic && result.suggested_topics) {
          // Multi-topic mode
          setSelectedTopics(result.suggested_topics);
          // Store original paths with placeholders for the parameters step
          setOriginalTopicPaths(result.suggested_topics.map(t => t.topic_path));
          // Collect all fields from all topics for formula step
          const allFields = result.suggested_topics.flatMap(t => t.fields);
          setFields(allFields);
        } else {
          // Single topic mode
          if (result.suggested_topic) {
            setSelectedTopic(result.suggested_topic);
          }
          if (result.suggested_fields.length > 0) {
            setFields(result.suggested_fields);
          }
        }
      } catch (err) {
        console.error('[Wizard] Failed to fetch unified suggestion:', err);
        setError('Failed to fetch topic suggestions. The machine-simulator service may be unavailable.');
      } finally {
        setLoading(false);
        setIsSearching(false);
      }
    };

    fetchUnifiedSuggestion();
  }, [machine, machineName]);

  // Extract placeholder suggestions from similar topics
  useEffect(() => {
    if (!unifiedSuggestion?.similar_results?.length) return;

    const suggestions: Record<string, Set<string>> = {};

    // Known hierarchy positions based on topic structure:
    // 0: data-publisher-uncurated (prefix)
    // 1: enterprise
    // 2: site
    // 3: area
    // 4: line
    // 5: cell
    // 6+: device/metric
    const hierarchyMap: Record<number, string> = {
      1: 'enterprise',
      2: 'site',
      3: 'area',
      4: 'line',
      5: 'cell',
    };

    for (const result of unifiedSuggestion.similar_results) {
      const segments = result.topic_path.split('/');
      for (const [idx, key] of Object.entries(hierarchyMap)) {
        const value = segments[Number(idx)];
        if (value && !value.startsWith('{')) {
          if (!suggestions[key]) suggestions[key] = new Set();
          suggestions[key].add(value);
        }
      }
    }

    // Convert Sets to arrays
    const suggestionsArray: Record<string, string[]> = {};
    for (const [key, values] of Object.entries(suggestions)) {
      suggestionsArray[key] = Array.from(values).slice(0, 5);
    }
    setPlaceholderSuggestions(suggestionsArray);
  }, [unifiedSuggestion]);

  // Auto-pilot: Auto-fill current step when it changes
  useEffect(() => {
    if (!isAutoPilot) return;

    const autoFillCurrentStep = () => {
      switch (step) {
        case 'topics':
          // Use suggested topic (already set by unified suggestion fetch)
          if (isMultiTopic && selectedTopics.length === 0 && unifiedSuggestion?.suggested_topics) {
            setSelectedTopics(unifiedSuggestion.suggested_topics);
          } else if (!isMultiTopic && !selectedTopic && unifiedSuggestion?.suggested_topic) {
            setSelectedTopic(unifiedSuggestion.suggested_topic);
          }
          break;
        case 'schema':
          // Use suggested schema (already default)
          setUseOriginalSchema(false);
          break;
        case 'formulas':
          // Formulas are auto-applied from suggestions
          break;
        case 'interval':
          // Interval is auto-applied from suggestions
          break;
        case 'smprofile':
          // SM Profile auto-accepted (read-only)
          break;
      }
    };

    // Delay slightly to let state settle
    const timer = setTimeout(autoFillCurrentStep, 100);
    return () => clearTimeout(timer);
  }, [step, isAutoPilot, unifiedSuggestion, placeholderSuggestions]);

  // Auto-pilot: Reset countdown when step changes
  const [shouldAutoAdvance, setShouldAutoAdvance] = useState(false);

  useEffect(() => {
    setAutoPilotCountdown(20);
  }, [step]);

  // Auto-pilot: Countdown timer using setTimeout chain
  useEffect(() => {
    if (!isAutoPilot || loading || saving || ladderLoading || smprofileLoading || showGraphFullscreen) return;

    const timer = setTimeout(() => {
      setAutoPilotCountdown(prev => {
        if (prev <= 1) {
          setShouldAutoAdvance(true);
          return 20;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearTimeout(timer);
  }, [isAutoPilot, step, loading, saving, ladderLoading, smprofileLoading, showGraphFullscreen, autoPilotCountdown]);

  // Handle auto-advance in a separate effect
  useEffect(() => {
    if (!shouldAutoAdvance) return;
    setShouldAutoAdvance(false);

    if (step === 'confirm') {
      handleSave();
    } else if (canProceed()) {
      handleContinue();
    }
  }, [shouldAutoAdvance]);

  // Auto-pilot: Fullscreen graph countdown timer
  useEffect(() => {
    if (!isAutoPilot || !showGraphFullscreen || isSearching || !unifiedSuggestion || !graphReady) {
      setGraphCountdown(8); // Reset when conditions change
      return;
    }

    const timer = setInterval(() => {
      setGraphCountdown(prev => {
        if (prev <= 1) {
          setShowGraphFullscreen(false);
          return 8;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isAutoPilot, showGraphFullscreen, isSearching, unifiedSuggestion, graphReady]);

  // Build similar topics context for formula suggestions
  const buildSimilarTopicsContext = (): SimilarTopicContext[] | undefined => {
    if (!unifiedSuggestion?.similar_results) return undefined;
    return unifiedSuggestion.similar_results.map(r => ({
      topic_path: r.topic_path,
      similarity: r.similarity,
      field_names: r.field_names,
      // Extract payload objects from HistoricalPayload wrappers
      historical_payloads: r.historical_payloads?.map(hp => hp.payload),
    }));
  };

  // Fetch formula and interval suggestions when moving past unified step
  const fetchAdditionalSuggestions = async (topicPath: string, sourceField?: string) => {
    setLoading(true);
    setError(null);

    try {
      const similarContext = buildSimilarTopicsContext();

      const [formulas, intervalRes] = await Promise.all([
        getFormulaSuggestions(topicPath, fields, machineName, similarContext, sourceField).catch(() => null),
        getIntervalSuggestion(topicPath).catch(() => null),
      ]);

      setFormulaSuggestion(formulas);
      setIntervalSuggestion(intervalRes);

      // Apply interval suggestion
      if (intervalRes && intervalRes.based_on === 'similar_topics') {
        setPublishInterval(intervalRes.suggested_interval_ms);
      }

      // Apply formula/static value suggestions to fields
      if (formulas && formulas.suggestions.length > 0) {
        setFields(currentFields =>
          currentFields.map(field => {
            const suggestion = formulas.suggestions.find(s => s.field_name === field.name);
            if (suggestion) {
              const updatedType = suggestion.field_type ? { type: suggestion.field_type as FieldType } : {};
              if (suggestion.is_static && suggestion.static_value != null) {
                return { ...field, ...updatedType, static_value: suggestion.static_value, formula: undefined };
              } else if (suggestion.formula && !field.formula) {
                return { ...field, ...updatedType, formula: suggestion.formula, static_value: undefined };
              }
            }
            return field;
          })
        );
      }
    } catch (err) {
      setError('Failed to fetch additional suggestions. You can proceed with default values.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch formula suggestions for multi-topic mode (one call per topic)
  const fetchMultiTopicFormulaSuggestions = async () => {
    setLoading(true);
    setError(null);

    try {
      const similarContext = buildSimilarTopicsContext();
      const updatedTopics = [...selectedTopics];

      // Fetch formulas for each topic
      for (let i = 0; i < updatedTopics.length; i++) {
        const topic = updatedTopics[i];
        const formulas = await getFormulaSuggestions(
          topic.topic_path,
          topic.fields,
          machineName,
          similarContext,
          topic.source_field
        ).catch(() => null);

        if (formulas && formulas.suggestions.length > 0) {
          // Apply suggestions to topic fields
          updatedTopics[i] = {
            ...topic,
            fields: topic.fields.map(field => {
              const suggestion = formulas.suggestions.find(s => s.field_name === field.name);
              if (suggestion) {
                const updatedType = suggestion.field_type ? { type: suggestion.field_type as FieldType } : {};
                if (suggestion.is_static && suggestion.static_value != null) {
                  return { ...field, ...updatedType, static_value: suggestion.static_value, formula: undefined };
                } else if (suggestion.formula) {
                  return { ...field, ...updatedType, formula: suggestion.formula, static_value: undefined };
                }
              }
              return field;
            }),
          };
        }
      }

      setSelectedTopics(updatedTopics);

      // Also fetch interval suggestion from first topic
      const intervalRes = await getIntervalSuggestion(selectedTopics[0].topic_path).catch(() => null);
      setIntervalSuggestion(intervalRes);
      if (intervalRes && intervalRes.based_on === 'similar_topics') {
        setPublishInterval(intervalRes.suggested_interval_ms);
      }
    } catch (err) {
      setError('Failed to fetch formula suggestions. You can proceed with default values.');
    } finally {
      setLoading(false);
    }
  };

  const handleUnifiedConfirm = () => {
    if (isMultiTopic) {
      if (selectedTopics.length === 0) {
        setError('No topics selected');
        return;
      }
      // Check for unfilled placeholders
      if (hasUnfilledPlaceholders()) {
        setError('Please fill in all topic path parameters (yellow fields above) before continuing');
        return;
      }
      // Fetch formula suggestions for each topic
      fetchMultiTopicFormulaSuggestions();
    } else {
      if (!selectedTopic) {
        setError('Please select or enter a topic path');
        return;
      }
      fetchAdditionalSuggestions(selectedTopic);
    }
    setStep('formulas');
  };

  const handleTreeBrowserSelect = (topicPath: string) => {
    if (browsingTopicIndex !== null) {
      // Multi-topic mode: update the specific topic
      const updated = [...selectedTopics];
      updated[browsingTopicIndex] = { ...updated[browsingTopicIndex], topic_path: topicPath };
      setSelectedTopics(updated);
      setBrowsingTopicIndex(null);
    } else {
      // Single topic mode
      setSelectedTopic(topicPath);
    }
    setShowTreeBrowser(false);
  };

  const openTreeBrowserForTopic = (index: number) => {
    setBrowsingTopicIndex(index);
    setShowTreeBrowser(true);
  };

  const handleSchemaChoice = (useOriginal: boolean) => {
    setUseOriginalSchema(useOriginal);
    if (useOriginal) {
      setFields(machine.fields);
    } else if (unifiedSuggestion && unifiedSuggestion.suggested_fields.length > 0) {
      setFields(unifiedSuggestion.suggested_fields);
    }
  };

  const handleFormulaUpdate = (fieldName: string, formula: string) => {
    setFields(currentFields =>
      currentFields.map(f =>
        f.name === fieldName ? { ...f, formula } : f
      )
    );
  };

  const handleMultiTopicFormulaUpdate = (topicIndex: number, fieldName: string, formula: string) => {
    setSelectedTopics(currentTopics =>
      currentTopics.map((topic, idx) =>
        idx === topicIndex
          ? {
              ...topic,
              fields: topic.fields.map(f =>
                f.name === fieldName ? { ...f, formula } : f
              ),
            }
          : topic
      )
    );
  };

  const handleStaticValueUpdate = (fieldName: string, staticValue: string) => {
    setFields(currentFields =>
      currentFields.map(f =>
        f.name === fieldName ? { ...f, static_value: staticValue } : f
      )
    );
  };

  const handleMultiTopicStaticValueUpdate = (topicIndex: number, fieldName: string, staticValue: string) => {
    setSelectedTopics(currentTopics =>
      currentTopics.map((topic, idx) =>
        idx === topicIndex
          ? {
              ...topic,
              fields: topic.fields.map(f =>
                f.name === fieldName ? { ...f, static_value: staticValue } : f
              ),
            }
          : topic
      )
    );
  };

  // Handler for editing field names in multi-topic mode
  const handleFieldNameUpdate = (topicIdx: number, fieldIdx: number, newName: string) => {
    if (!newName.trim()) return; // Don't allow empty names
    setSelectedTopics(currentTopics =>
      currentTopics.map((topic, tIdx) =>
        tIdx === topicIdx
          ? {
              ...topic,
              fields: topic.fields.map((field, fIdx) =>
                fIdx === fieldIdx ? { ...field, name: newName.trim() } : field
              ),
            }
          : topic
      )
    );
  };

  // Handler for editing field names in single-topic mode
  const handleSingleTopicFieldNameUpdate = (fieldIdx: number, newName: string) => {
    if (!newName.trim()) return; // Don't allow empty names
    setFields(currentFields =>
      currentFields.map((field, idx) =>
        idx === fieldIdx ? { ...field, name: newName.trim() } : field
      )
    );
  };

  // Helper to detect which placeholders exist in ORIGINAL topic paths (not the current state)
  const detectPlaceholders = (): string[] => {
    const placeholders = new Set<string>();
    const regex = /\{\{(\w+)\}\}/g;
    // Use original paths so placeholders are always detected even after values are applied
    for (const path of originalTopicPaths) {
      let match;
      while ((match = regex.exec(path)) !== null) {
        placeholders.add(match[1]);
      }
    }
    return Array.from(placeholders);
  };

  // Helper to check if all placeholders have values (SKIP_VALUE counts as filled)
  const hasUnfilledPlaceholders = (): boolean => {
    const placeholders = detectPlaceholders();
    return placeholders.some(key => {
      const value = placeholderValues[key];
      return !value || (value.trim() === '' && value !== SKIP_VALUE);
    });
  };

  // Compute preview path with current placeholder values applied (handles skips and insertions)
  const getPreviewPath = (path: string): string => {
    let result = path;

    // First handle skips and replacements
    for (const [key, value] of Object.entries(placeholderValues)) {
      if (value === SKIP_VALUE) {
        // Remove the placeholder AND the preceding slash
        result = result.replace(new RegExp(`/\\{\\{${key}\\}\\}`, 'g'), '');
      } else if (value) {
        result = result.replace(new RegExp(`\\{\\{${key}\\}\\}`, 'g'), value);
      }
    }

    // Then insert custom levels
    for (const [afterKey, levelValue] of Object.entries(insertedLevels)) {
      if (levelValue && levelValue.trim()) {
        const parentKey = afterKey.replace('after_', '');
        const parentValue = placeholderValues[parentKey];
        if (parentValue && parentValue !== SKIP_VALUE) {
          // Insert after the parent value
          result = result.replace(parentValue, `${parentValue}/${levelValue}`);
        }
      }
    }

    return result;
  };

  // Apply all placeholder values to topic paths (called when leaving parameters step)
  const applyAllPlaceholderValues = () => {
    setSelectedTopics(currentTopics =>
      currentTopics.map((topic, idx) => ({
        ...topic,
        topic_path: getPreviewPath(originalTopicPaths[idx] || topic.topic_path),
      }))
    );
  };

  // Render topic path with placeholder highlighting
  const renderTopicPathWithHighlights = (path: string) => {
    const parts = path.split(/(\{\{[^}]+\}\})/);
    return parts.map((part, i) =>
      part.startsWith('{{') ? (
        <span key={i} className="bg-yellow-600/40 text-yellow-300 px-1 rounded font-semibold">
          {part}
        </span>
      ) : (
        <span key={i}>{part}</span>
      )
    );
  };

  // Get dynamic steps array
  const getSteps = (): { key: Step; label: string }[] => {
    return [
      { key: 'topics', label: 'Topics' },
      { key: 'schema', label: 'Schema' },
      ...(isConnectMode ? [] : [{ key: 'formulas' as Step, label: 'Formulas' }]),
      { key: 'interval', label: 'Interval' },
      ...(isConnectMode ? [] : [{ key: 'ladder' as Step, label: 'Ladder' }]),
      { key: 'smprofile', label: 'CESMII Model' },
      { key: 'confirm', label: 'Confirm' },
    ];
  };

  // Navigation helpers
  const getNextStep = (): Step => {
    switch (step) {
      case 'topics':
        return 'schema';
      case 'schema':
        return isConnectMode ? 'interval' : 'formulas';
      case 'formulas':
        return 'interval';
      case 'interval':
        return isConnectMode ? 'smprofile' : 'ladder';
      case 'ladder':
        return 'smprofile';
      case 'smprofile':
        return 'confirm';
      default:
        return 'confirm';
    }
  };

  const getPrevStep = (): Step => {
    switch (step) {
      case 'schema':
        return 'topics';
      case 'formulas':
        return 'schema';
      case 'interval':
        return isConnectMode ? 'schema' : 'formulas';
      case 'ladder':
        return 'interval';
      case 'smprofile':
        return isConnectMode ? 'interval' : 'ladder';
      case 'confirm':
        return 'smprofile';
      default:
        return 'topics';
    }
  };

  const canProceed = (): boolean => {
    switch (step) {
      case 'topics':
        return isMultiTopic ? selectedTopics.length > 0 : !!selectedTopic;
      case 'schema':
        return true;
      case 'formulas':
        return true;
      case 'interval':
        return publishInterval >= 1000;
      case 'ladder':
        return true; // Can proceed even if ladder generation fails
      case 'smprofile':
        return true; // Read-only, always can proceed
      default:
        return true;
    }
  };

  // Generate ladder logic for the machine
  const handleGenerateLadder = async () => {
    setLadderLoading(true);
    setLadderError(null);

    try {
      // For multi-topic machines, create fields named after topics (not the generic "value" fields)
      // Each topic becomes a single output, using the main value field's properties
      let allFields: FieldDefinition[];

      if (isMultiTopic && selectedTopics.length > 0) {
        allFields = selectedTopics.map(topic => {
          // Get the topic name from the MQTT topic path (NOT source_field which has suffixes)
          // This ensures ladder outputs match MQTT topics exactly for real-time value injection
          const topicName = topic.topic_path.split('/').pop() || 'value';

          // Find the main value field (usually "value" or first numeric/boolean field)
          const valueField = topic.fields.find(f => f.name === 'value')
            || topic.fields.find(f => f.type === 'number' || f.type === 'integer' || f.type === 'boolean')
            || topic.fields[0];

          // Create a field named after the topic, with the value field's properties
          return {
            ...valueField,
            name: topicName,
            description: valueField?.description || `${topicName} sensor value`,
          };
        });
      } else {
        allFields = fields;
      }

      // DEBUG: Log what we're sending to ladder generation
      console.log('[Wizard] ========== LADDER GENERATION DEBUG ==========');
      console.log('[Wizard] isMultiTopic:', isMultiTopic);
      console.log('[Wizard] selectedTopics count:', selectedTopics.length);
      console.log('[Wizard] selectedTopics details:', selectedTopics.map(t => ({
        topic_path: t.topic_path,
        source_field: t.source_field,
        fields: t.fields?.map(f => f.name),
      })));
      console.log('[Wizard] fields (original):', fields.map(f => ({ name: f.name, type: f.type })));
      console.log('[Wizard] allFields (sent to ladder):', allFields.map(f => ({ name: f.name, type: f.type })));
      console.log('[Wizard] machine_type:', machine.machine_type);
      console.log('[Wizard] ================================================');

      const result = await generateLadderLogic(
        machine.machine_type,
        allFields,
        machine.description
      );

      // DEBUG: Log the ladder generation response
      console.log('[Wizard] ========== LADDER RESPONSE ==========');
      console.log('[Wizard] Ladder outputs:', result.io_mapping?.outputs);
      console.log('[Wizard] Ladder inputs:', result.io_mapping?.inputs);
      console.log('[Wizard] Rungs count:', result.ladder_program?.rungs?.length);
      console.log('[Wizard] Full response:', JSON.stringify(result, null, 2));
      console.log('[Wizard] =======================================');

      setLadderResponse(result);
    } catch (err) {
      setLadderError(err instanceof Error ? err.message : 'Failed to generate ladder logic');
    } finally {
      setLadderLoading(false);
    }
  };

  // Generate SM Profile for the machine
  const handleGenerateSMProfile = async () => {
    setSMProfileLoading(true);
    setSMProfileError(null);
    try {
      const result = await generateSMProfile(
        machine.machine_type,
        machineName,
        machine.description
      );
      setSMProfileData(result.smprofile);
    } catch (err) {
      setSMProfileError(err instanceof Error ? err.message : 'Failed to generate SM Profile');
    } finally {
      setSMProfileLoading(false);
    }
  };

  // Handle Continue button click
  const handleContinue = async () => {
    setError(null);

    // Fetch formula suggestions when leaving schema step
    if (step === 'schema') {
      if (isMultiTopic) {
        await fetchMultiTopicFormulaSuggestions();
      } else {
        await fetchAdditionalSuggestions(selectedTopic);
      }
    }

    // Generate ladder logic when entering ladder step (or in background for connect mode)
    const nextStep = getNextStep();
    if ((nextStep === 'ladder' || (nextStep === 'confirm' && isConnectMode)) && !ladderResponse) {
      handleGenerateLadder();
    }

    // Generate SM Profile when entering smprofile step
    if (nextStep === 'smprofile' && !smprofileData) {
      handleGenerateSMProfile();
    }

    setStep(nextStep);
  };

  const incrementMachineName = (name: string): string => {
    // Match trailing number pattern: "cnc-mill-001" -> "cnc-mill-002"
    const match = name.match(/^(.*?)(\d+)$/);
    if (match) {
      const prefix = match[1];
      const num = parseInt(match[2], 10) + 1;
      const padded = String(num).padStart(match[2].length, '0');
      return `${prefix}${padded}`;
    }
    // No trailing number: "cnc-mill" -> "cnc-mill-002"
    return `${name}-002`;
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);

    const MAX_RETRIES = 5;
    let currentName = machineName;

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        // Include similarity results for detail page visualization
        const similarityResults = unifiedSuggestion?.similar_results || [];

        let createdMachine;
        if (isMultiTopic && selectedTopics.length > 0) {
          // Multi-topic mode: convert TopicSuggestion[] to TopicDefinition[]
          const topics: TopicDefinition[] = selectedTopics.map(ts => ({
            topic_path: ts.topic_path,
            fields: ts.fields,
          }));

          createdMachine = await createMachine({
            name: currentName,
            description: machine.description,
            machine_type: machine.machine_type,
            topics,
            publish_interval_ms: publishInterval,
            image_base64: imageBase64,
            similarity_results: similarityResults,
            // SparkMES from LLM generation
            sparkmes_enabled: true,
            sparkmes: machine.sparkmes,
            smprofile: smprofileData || undefined,
            created_by: createdBy,
          });
        } else {
          // Single topic mode
          createdMachine = await createMachine({
            name: currentName,
            description: machine.description,
            machine_type: machine.machine_type,
            topic_path: selectedTopic,
            fields,
            publish_interval_ms: publishInterval,
            image_base64: imageBase64,
            similarity_results: similarityResults,
            // SparkMES from LLM generation
            sparkmes_enabled: true,
            sparkmes: machine.sparkmes,
            smprofile: smprofileData || undefined,
            created_by: createdBy,
          });
        }

        // Save ladder logic if we have it
        if (ladderResponse && createdMachine?.id) {
          try {
            await saveLadderLogic(createdMachine.id, {
              rungs: ladderResponse.ladder_program.rungs,
              io_mapping: ladderResponse.io_mapping,
              rationale: ladderResponse.rationale,
            });
          } catch (ladderErr) {
            console.error('Failed to save ladder logic:', ladderErr);
            // Don't fail the whole operation if ladder save fails
          }
        }

        // Auto-start the machine after creation
        if (createdMachine?.id) {
          try {
            await startMachine(createdMachine.id);
          } catch (startErr) {
            console.error('Failed to auto-start machine:', startErr);
            // Don't block navigation if start fails — user can start manually
          }
        }

        onComplete(createdMachine?.id);
        return;
      } catch (err) {
        if (err instanceof DuplicateMachineError && attempt < MAX_RETRIES - 1) {
          // Auto-increment name and retry
          const newName = incrementMachineName(currentName);
          console.log(`[ConnectWizard] Duplicate name '${currentName}', trying '${newName}'`);
          currentName = newName;
          continue;
        }
        setError(err instanceof Error ? err.message : 'Failed to save machine');
        break;
      }
    }

    setSaving(false);
  };

  const renderStepIndicator = () => {
    const steps = getSteps();
    const currentIndex = steps.findIndex(s => s.key === step);

    return (
      <div className="flex items-center justify-center gap-1 mb-6 flex-wrap">
        {steps.map((s, idx) => (
          <div key={s.key} className="flex items-center">
            <div
              className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                idx < currentIndex
                  ? 'bg-green-600 text-white'
                  : idx === currentIndex
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-400'
              }`}
            >
              {idx < currentIndex ? '✓' : idx + 1}
            </div>
            <span
              className={`ml-1 text-xs ${
                idx === currentIndex ? 'text-gray-100' : 'text-gray-500'
              }`}
            >
              {s.label}
            </span>
            {idx < steps.length - 1 && (
              <div className="w-4 h-px bg-gray-600 mx-2" />
            )}
          </div>
        ))}
      </div>
    );
  };

  // Fullscreen graph is shown until user clicks "Continue to Configuration"
  // Don't auto-switch - require explicit user action

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className={`bg-gray-800 rounded-lg shadow-xl border border-gray-700 w-full max-h-[90vh] overflow-hidden flex ${
        showGraphFullscreen ? 'max-w-4xl' : 'max-w-6xl'
      }`}>
        {/* Fullscreen Graph Mode - shown until user clicks Continue */}
        {showGraphFullscreen ? (
          <div className="w-full h-[80vh] relative">
            {/* Header overlay */}
            <div className="absolute top-0 left-0 right-0 z-20 bg-gradient-to-b from-gray-900/90 to-transparent p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-gray-100">Connect Machine</h2>
                  <p className="text-sm text-gray-400">{machineName}</p>
                </div>
                <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Full Graph with auto-rotation - wrapped for proper sizing */}
            <div className="w-full h-full" ref={(el) => {
              if (el) {
                console.log('[Wizard] GraphVisualization container dimensions:', {
                  width: el.clientWidth,
                  height: el.clientHeight,
                  offsetWidth: el.offsetWidth,
                  offsetHeight: el.offsetHeight
                });
              }
            }}>
              <GraphVisualization
                similarResults={unifiedSuggestion?.similar_results || []}
                suggestedTopic={isMultiTopic ? selectedTopics[0]?.topic_path : selectedTopic}
                isSearching={isSearching}
                enableAutoRotate={true}
                onLayoutReady={() => setGraphReady(true)}
              />
            </div>

            {/* Error overlay - shown when API call fails */}
            {error && (
              <div className="absolute top-20 left-4 right-4 z-30 bg-red-900/95 backdrop-blur border border-red-700 rounded-lg p-4 shadow-xl">
                <div className="flex items-start gap-3">
                  <svg className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <div className="flex-1">
                    <h3 className="text-red-300 font-medium">Connection Error</h3>
                    <p className="text-red-400 text-sm mt-1">{error}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Continue button overlay - shown when search completes AND graph has rendered */}
            {!isSearching && unifiedSuggestion && graphReady && (
              <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-20 flex flex-col items-center gap-2">
                {isAutoPilot && (
                  <div className="bg-gradient-to-r from-purple-900/80 to-pink-900/80 border border-purple-500 rounded-lg px-4 py-2 flex items-center gap-2">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                    <span className="text-purple-300 text-sm">AUTO-PILOT: Continuing in {graphCountdown}s...</span>
                  </div>
                )}
                <button
                  onClick={() => setShowGraphFullscreen(false)}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg shadow-lg transition-all flex items-center gap-2 text-lg"
                >
                  Continue to Configuration
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            )}

            {/* Fallback UI - shown when search completes but API failed (no suggestion) */}
            {!isSearching && !unifiedSuggestion && !loading && (
              <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-20 flex flex-col items-center gap-3">
                <div className="bg-gray-900/95 backdrop-blur border border-gray-700 rounded-lg px-4 py-3 text-center">
                  <p className="text-gray-300 text-sm">Could not load topic suggestions</p>
                  <p className="text-gray-500 text-xs mt-1">You can still configure topics manually</p>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => {
                      setError(null);
                      setIsSearching(true);
                      getUnifiedSuggestion(machine.machine_type, machineName, machine.fields)
                        .then((result) => {
                          console.log('[Wizard] Retry succeeded:', result);
                          setUnifiedSuggestion(result);
                        })
                        .catch((err) => {
                          console.error('[Wizard] Retry failed:', err);
                          setError('Failed to fetch topic suggestions. The machine-simulator service may be unavailable.');
                        })
                        .finally(() => {
                          setIsSearching(false);
                        });
                    }}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-all flex items-center gap-2"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Retry
                  </button>
                  <button
                    onClick={() => setShowGraphFullscreen(false)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all flex items-center gap-2"
                  >
                    Continue Manually
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
        <>
        {/* Left Panel - Wizard */}
        <div className="flex-1 flex flex-col min-w-0 border-r border-gray-700">
          {/* Header */}
          <div className="border-b border-gray-700 px-6 py-4 flex-shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-gray-100">Connect Machine</h2>
                <p className="text-sm text-gray-400">{machineName}</p>
              </div>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-200">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Step Indicator */}
          <div className="px-6 pt-4 flex-shrink-0">
            {renderStepIndicator()}
          </div>

          {/* Content */}
          <div className="p-6 overflow-y-auto flex-1">
          {/* Auto-Pilot Indicator */}
          {isAutoPilot && (
            <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 border border-purple-500 rounded-lg p-3 mb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse" />
                <span className="text-purple-300 font-medium">AUTO-PILOT ACTIVE</span>
                <span className="text-purple-400">
                  {loading ? (isConnectMode ? 'Extracting PLC Logic...' : 'Loading...') : saving ? 'Saving...' : ladderLoading ? (isConnectMode ? 'MCP PLC Interlock Computing...' : 'Generating ladder logic...') : `Continuing in ${autoPilotCountdown}s...`}
                </span>
              </div>
              <button
                onClick={() => setIsAutoPilot(false)}
                className="px-3 py-1 bg-purple-700 hover:bg-purple-600 text-white rounded text-sm transition-colors"
              >
                Take Control
              </button>
            </div>
          )}

          {error && (
            <div className="bg-red-900/20 border border-red-500 rounded p-3 mb-4">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {loading ? (
            <div className="text-center text-gray-400 py-12">
              {step === 'topics' ? 'Analyzing similar machines...' : 'Preparing suggestions...'}
            </div>
          ) : (
            <>
              {/* STEP 1: Topics */}
              {step === 'topics' && (
                <div className="space-y-4">
                  {/* Compact Confidence Banner */}
                  {unifiedSuggestion && (
                    <div className={`p-3 rounded-lg border flex items-center justify-between ${
                      unifiedSuggestion.confidence === 'high'
                        ? 'border-green-600/50 bg-green-900/10'
                        : unifiedSuggestion.confidence === 'medium'
                        ? 'border-yellow-600/50 bg-yellow-900/10'
                        : 'border-gray-600/50 bg-gray-900/10'
                    }`}>
                      <span className={`text-sm ${
                        unifiedSuggestion.confidence === 'high' ? 'text-green-400' :
                        unifiedSuggestion.confidence === 'medium' ? 'text-yellow-400' : 'text-gray-400'
                      }`}>
                        {isMultiTopic
                          ? `Split-by-metric pattern: ${selectedTopics.length} topics`
                          : unifiedSuggestion.confidence === 'low' ? 'Novel machine - generated from similar topics' : 'Topic suggestion ready'}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        unifiedSuggestion.confidence === 'high' ? 'bg-green-600 text-white' :
                        unifiedSuggestion.confidence === 'medium' ? 'bg-yellow-600 text-white' :
                        'bg-gray-600 text-white'
                      }`}>
                        {unifiedSuggestion.confidence.toUpperCase()}
                      </span>
                    </div>
                  )}

                  {/* Multi-topic: Show suggested topics with inline editing */}
                  {isMultiTopic && selectedTopics.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-300 mb-3">Suggested Topics</h3>
                      <div className="space-y-2 max-h-72 overflow-y-auto">
                        {selectedTopics.map((topic, idx) => {
                          const segments = topic.topic_path.split('/');
                          return (
                            <div key={idx} className="p-3 bg-gray-900 border border-purple-600/30 rounded-lg">
                              <div className="flex items-center gap-2">
                                {!isAutoPilot ? (
                                  <div className="font-mono text-sm flex-1 flex flex-wrap items-center gap-0.5">
                                    {segments.map((seg, segIdx) => (
                                      <span key={segIdx} className="flex items-center">
                                        {segIdx > 0 && <span className="text-gray-600 mx-0.5">/</span>}
                                        {segIdx === 0 ? (
                                          <span className="text-gray-500">{seg}</span>
                                        ) : (
                                          <input
                                            type="text"
                                            value={seg}
                                            onChange={(e) => {
                                              const newSegments = [...segments];
                                              newSegments[segIdx] = e.target.value;
                                              const newPath = newSegments.join('/');
                                              setSelectedTopics(prev => prev.map((t, i) =>
                                                i === idx ? { ...t, topic_path: newPath } : t
                                              ));
                                            }}
                                            className="bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5 text-gray-100 text-sm font-mono focus:outline-none focus:border-blue-500 hover:border-gray-500 transition-colors"
                                            style={{ width: `${Math.max(seg.length * 8 + 16, 40)}px` }}
                                          />
                                        )}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="font-mono text-sm text-gray-100 flex-1 truncate">
                                    {topic.topic_path}
                                  </span>
                                )}
                                {topic.source_field && (
                                  <span className="text-xs text-purple-400 whitespace-nowrap flex-shrink-0">← {topic.source_field}</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {!isAutoPilot && (
                        <p className="text-xs text-gray-500 mt-2">
                          Click any segment to edit the topic path hierarchy.
                        </p>
                      )}
                    </div>
                  )}

                  {/* Single topic mode */}
                  {!isMultiTopic && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-300 mb-3">Topic Path</h3>

                      {unifiedSuggestion?.suggested_topic && (
                        <div className="mb-3 p-3 bg-blue-900/20 border border-blue-600/50 rounded-lg">
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="text-xs text-blue-400 uppercase">Suggested</span>
                              <p className="font-mono text-gray-100 text-sm">{unifiedSuggestion.suggested_topic}</p>
                            </div>
                            <button
                              onClick={() => setSelectedTopic(unifiedSuggestion.suggested_topic!)}
                              className={`px-3 py-1 rounded text-sm ${
                                selectedTopic === unifiedSuggestion.suggested_topic
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                              }`}
                            >
                              {selectedTopic === unifiedSuggestion.suggested_topic ? 'Selected' : 'Use This'}
                            </button>
                          </div>
                        </div>
                      )}

                      <button
                        onClick={() => {
                          setBrowsingTopicIndex(null);
                          setShowTreeBrowser(true);
                        }}
                        className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors border border-gray-600 text-sm"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                        </svg>
                        Browse Topic Tree
                      </button>

                      {selectedTopic && (
                        <div className="mt-3 p-3 bg-gray-900 rounded border border-green-700/50 flex items-center justify-between">
                          <div>
                            <span className="text-xs text-green-400">Selected:</span>
                            <p className="font-mono text-gray-100 text-sm">{selectedTopic}</p>
                          </div>
                          <button onClick={() => setSelectedTopic('')} className="text-gray-500 hover:text-gray-300">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Top 10 Similarity Results - Always Visible */}
                  {unifiedSuggestion && unifiedSuggestion.similar_results.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                        <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                        Top {Math.min(10, unifiedSuggestion.similar_results.length)} Similar Topics
                      </h4>
                      <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
                        <div className="max-h-60 overflow-y-auto">
                          {unifiedSuggestion.similar_results.slice(0, 10).map((result, idx) => (
                            <div
                              key={idx}
                              className="p-3 border-b border-gray-800 last:border-0 flex items-center justify-between gap-4 hover:bg-gray-800/50"
                            >
                              <div className="flex-1 min-w-0">
                                <span className="font-mono text-sm text-gray-300 truncate block">
                                  {result.topic_path}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {result.field_names.length} fields: {result.field_names.slice(0, 3).join(', ')}
                                  {result.field_names.length > 3 && '...'}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <div className={`px-2 py-1 rounded text-xs font-medium ${
                                  result.similarity >= 0.7
                                    ? 'bg-green-900/50 text-green-400 border border-green-700/50'
                                    : result.similarity >= 0.4
                                      ? 'bg-yellow-900/50 text-yellow-400 border border-yellow-700/50'
                                      : 'bg-gray-800 text-gray-400 border border-gray-700'
                                }`}>
                                  {(result.similarity * 100).toFixed(0)}%
                                </div>
                                <span className="text-xs text-gray-600 w-5 text-right">#{idx + 1}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Navigation */}
                  <div className="flex justify-end pt-4">
                    <button
                      onClick={handleContinue}
                      disabled={!canProceed()}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* STEP 2: Schema */}
              {step === 'schema' && (
                <div className="space-y-4">
                  <h3 className="text-sm font-medium text-gray-300">Field Schema</h3>

                  {/* Schema choice buttons */}
                  {unifiedSuggestion && unifiedSuggestion.suggested_fields.length > 0 && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSchemaChoice(false)}
                        className={`flex-1 px-3 py-2 rounded text-sm ${
                          !useOriginalSchema ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        Use Suggested Schema
                      </button>
                      <button
                        onClick={() => handleSchemaChoice(true)}
                        className={`flex-1 px-3 py-2 rounded text-sm ${
                          useOriginalSchema ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        Use Original Schema
                      </button>
                    </div>
                  )}

                  {/* Fields display */}
                  <p className="text-xs text-gray-500">Click any field to edit its name:</p>

                  {isMultiTopic && selectedTopics.length > 0 ? (
                    <div className="space-y-3">
                      {selectedTopics.map((topic, topicIdx) => (
                        <div key={topicIdx} className="bg-gray-900 border border-gray-700 rounded-lg p-3">
                          <p className="font-mono text-xs text-purple-400 mb-2 truncate">{topic.topic_path.split('/').pop()}</p>
                          <div className="flex flex-wrap gap-2">
                            {topic.fields.map((field, fieldIdx) => (
                              editingField?.topicIdx === topicIdx && editingField?.fieldIdx === fieldIdx ? (
                                <span key={fieldIdx} className="inline-flex items-center">
                                  <input
                                    type="text"
                                    autoFocus
                                    defaultValue={field.name}
                                    onBlur={(e) => {
                                      handleFieldNameUpdate(topicIdx, fieldIdx, e.target.value);
                                      setEditingField(null);
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') {
                                        handleFieldNameUpdate(topicIdx, fieldIdx, e.currentTarget.value);
                                        setEditingField(null);
                                      }
                                      if (e.key === 'Escape') setEditingField(null);
                                    }}
                                    className="bg-gray-700 border border-purple-500 rounded px-2 py-0.5 text-sm text-gray-100 w-28 focus:outline-none"
                                  />
                                  <span className="text-gray-500 ml-1 text-xs">({field.type})</span>
                                </span>
                              ) : (
                                <span
                                  key={fieldIdx}
                                  onClick={() => setEditingField({ topicIdx, fieldIdx })}
                                  className="group px-2 py-1 bg-gray-800 rounded text-sm text-gray-300 cursor-pointer hover:bg-purple-900/30 hover:text-purple-300 border border-transparent hover:border-purple-500/50 transition-all inline-flex items-center gap-1"
                                >
                                  {field.name}
                                  <span className="text-gray-500 group-hover:text-purple-400 text-xs">({field.type})</span>
                                  <svg className="w-3 h-3 text-gray-600 group-hover:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                  </svg>
                                </span>
                              )
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3">
                      <div className="flex flex-wrap gap-2">
                        {fields.map((field, idx) => (
                          editingField?.topicIdx === -1 && editingField?.fieldIdx === idx ? (
                            <span key={idx} className="inline-flex items-center">
                              <input
                                type="text"
                                autoFocus
                                defaultValue={field.name}
                                onBlur={(e) => {
                                  handleSingleTopicFieldNameUpdate(idx, e.target.value);
                                  setEditingField(null);
                                }}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    handleSingleTopicFieldNameUpdate(idx, e.currentTarget.value);
                                    setEditingField(null);
                                  }
                                  if (e.key === 'Escape') setEditingField(null);
                                }}
                                className="bg-gray-700 border border-purple-500 rounded px-2 py-0.5 text-sm text-gray-100 w-28 focus:outline-none"
                              />
                              <span className="text-gray-500 ml-1 text-xs">({field.type})</span>
                            </span>
                          ) : (
                            <span
                              key={idx}
                              onClick={() => setEditingField({ topicIdx: -1, fieldIdx: idx })}
                              className="group px-2 py-1 bg-gray-800 rounded text-sm text-gray-300 cursor-pointer hover:bg-purple-900/30 hover:text-purple-300 border border-transparent hover:border-purple-500/50 transition-all inline-flex items-center gap-1"
                            >
                              {field.name}
                              <span className="text-gray-500 group-hover:text-purple-400 text-xs">({field.type})</span>
                              <svg className="w-3 h-3 text-gray-600 group-hover:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </span>
                          )
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Navigation */}
                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleContinue}
                      disabled={!canProceed()}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* Formulas Step */}
              {step === 'formulas' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-medium text-gray-300 mb-3">
                      Configure Values for All Fields
                    </h3>
                    <p className="text-sm text-gray-400 mb-4">
                      Static fields use fixed values. Dynamic fields use formulas with: t (timestamp), i (iteration), random()
                    </p>

                    {isMultiTopic ? (
                      /* Multi-topic mode: show ALL fields grouped by topic */
                      <div className="space-y-4">
                        {selectedTopics.map((topic, topicIdx) => (
                          <div key={topicIdx} className="border border-purple-700/50 rounded-lg p-3">
                            <p className="font-mono text-xs text-purple-400 mb-3">
                              {topic.topic_path}
                              {topic.source_field && <span className="ml-2 text-gray-500">← {topic.source_field}</span>}
                            </p>
                            <div className="space-y-3">
                              {topic.fields.map((field, fieldIdx) => {
                                const suggestion = formulaSuggestion?.suggestions.find(s => s.field_name === field.name);
                                const isStatic = suggestion?.is_static || field.name === 'asset_id';
                                const isTimestamp = field.name === 'timestamp';

                                return (
                                  <div key={fieldIdx} className={`bg-gray-900 border rounded-lg p-3 ${isStatic ? 'border-green-700/50' : 'border-gray-700'}`}>
                                    <div className="flex items-center justify-between mb-2">
                                      <span className="font-medium text-gray-200">{field.name}</span>
                                      <div className="flex items-center gap-2">
                                        <span className={`text-xs px-1.5 py-0.5 rounded ${isStatic ? 'bg-green-900/50 text-green-400' : 'bg-blue-900/50 text-blue-400'}`}>
                                          {isStatic ? 'static' : 'dynamic'}
                                        </span>
                                        <span className="text-xs text-gray-500">{field.type}</span>
                                      </div>
                                    </div>
                                    {isStatic && !isTimestamp ? (
                                      <input
                                        type="text"
                                        value={String(field.static_value || '')}
                                        onChange={(e) => handleMultiTopicStaticValueUpdate(topicIdx, field.name, e.target.value)}
                                        placeholder={suggestion?.static_value || 'Enter static value...'}
                                        className="w-full bg-gray-800 border border-green-600/50 rounded px-3 py-2 text-gray-100 text-sm focus:outline-none focus:border-green-500"
                                      />
                                    ) : (
                                      <input
                                        type="text"
                                        value={field.formula || ''}
                                        onChange={(e) => handleMultiTopicFormulaUpdate(topicIdx, field.name, e.target.value)}
                                        placeholder={suggestion?.formula || (isTimestamp ? 't' : 'Enter formula...')}
                                        className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 text-sm font-mono focus:outline-none focus:border-blue-500"
                                      />
                                    )}
                                    {suggestion?.rationale && (
                                      <p className="text-xs text-gray-500 mt-1">{suggestion.rationale}</p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      /* Single topic mode: show ALL fields */
                      <div className="space-y-3">
                        {fields.map((field, idx) => {
                          const suggestion = formulaSuggestion?.suggestions.find(s => s.field_name === field.name);
                          const isStatic = suggestion?.is_static || field.name === 'asset_id';
                          const isTimestamp = field.name === 'timestamp';

                          return (
                            <div key={idx} className={`bg-gray-900 border rounded-lg p-3 ${isStatic ? 'border-green-700/50' : 'border-gray-700'}`}>
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-medium text-gray-200">{field.name}</span>
                                <div className="flex items-center gap-2">
                                  <span className={`text-xs px-1.5 py-0.5 rounded ${isStatic ? 'bg-green-900/50 text-green-400' : 'bg-blue-900/50 text-blue-400'}`}>
                                    {isStatic ? 'static' : 'dynamic'}
                                  </span>
                                  <span className="text-xs text-gray-500">{field.type}</span>
                                </div>
                              </div>
                              {isStatic && !isTimestamp ? (
                                <input
                                  type="text"
                                  value={String(field.static_value || '')}
                                  onChange={(e) => handleStaticValueUpdate(field.name, e.target.value)}
                                  placeholder={suggestion?.static_value || 'Enter static value...'}
                                  className="w-full bg-gray-800 border border-green-600/50 rounded px-3 py-2 text-gray-100 text-sm focus:outline-none focus:border-green-500"
                                />
                              ) : (
                                <input
                                  type="text"
                                  value={field.formula || ''}
                                  onChange={(e) => handleFormulaUpdate(field.name, e.target.value)}
                                  placeholder={suggestion?.formula || (isTimestamp ? 't' : 'Enter formula...')}
                                  className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 text-sm font-mono focus:outline-none focus:border-blue-500"
                                />
                              )}
                              {suggestion?.rationale && (
                                <p className="text-xs text-gray-500 mt-1">{suggestion.rationale}</p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => setStep(getNextStep())}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* Interval Step */}
              {step === 'interval' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-medium text-gray-300 mb-3">
                      Publish Interval
                    </h3>
                    <p className="text-sm text-gray-400 mb-4">
                      How often should this machine publish messages?
                    </p>

                    {intervalSuggestion && intervalSuggestion.based_on === 'similar_topics' && (
                      <div className="mb-4 p-3 bg-blue-900/20 border border-blue-600/50 rounded-lg">
                        <p className="text-sm text-blue-400">
                          Based on similar topics, suggested interval: {intervalSuggestion.suggested_interval_ms}ms
                        </p>
                      </div>
                    )}

                    <div className="flex items-center gap-4">
                      <input
                        type="range"
                        min="1000"
                        max="60000"
                        step="1000"
                        value={publishInterval}
                        onChange={(e) => setPublishInterval(parseInt(e.target.value))}
                        className="flex-1"
                      />
                      <input
                        type="number"
                        value={publishInterval}
                        onChange={(e) => setPublishInterval(Math.max(1000, Math.min(60000, parseInt(e.target.value) || 1000)))}
                        className="w-24 bg-gray-800 border border-gray-600 rounded px-3 py-2 text-gray-100 text-sm text-center focus:outline-none focus:border-blue-500"
                      />
                      <span className="text-gray-400 text-sm">ms</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Current: {(publishInterval / 1000).toFixed(1)} seconds between messages
                    </p>
                  </div>

                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleContinue}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* Ladder Logic Step */}
              {step === 'ladder' && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-medium text-gray-300 mb-2">
                      {isConnectMode ? 'PLC Interlock Configuration' : 'Ladder Logic Generation'}
                    </h3>
                    <p className="text-sm text-gray-400 mb-4">
                      {isConnectMode
                        ? 'Computing interlock logic from connected PLC tag data. This will be displayed as a real-time visualization on the machine page.'
                        : 'Generate Ladder Logic for the Simulated Machine'}
                    </p>

                    {ladderError && (
                      <div className="mb-4 p-3 bg-red-900/20 border border-red-600/50 rounded-lg">
                        <p className="text-sm text-red-400">{ladderError}</p>
                        <button
                          onClick={handleGenerateLadder}
                          className="mt-2 text-sm text-red-300 underline hover:text-red-200"
                        >
                          Try again
                        </button>
                      </div>
                    )}

                    {ladderLoading && (
                      <div className="flex items-center gap-3 p-4 bg-gray-900 rounded-lg border border-gray-700">
                        <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-purple-500" />
                        <span className="text-gray-300">{isConnectMode ? 'MCP PLC Interlock Computing...' : 'Generating ladder logic with MCP...'}</span>
                      </div>
                    )}

                    {ladderResponse && !ladderLoading && (
                      <div className="space-y-4">
                        {/* Success banner */}
                        <div className="p-3 bg-green-900/20 border border-green-600/50 rounded-lg flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <span className="text-green-400 text-sm">
                              Generated {ladderResponse.ladder_program.rungs.length} rungs
                            </span>
                          </div>
                          <button
                            onClick={handleGenerateLadder}
                            className="text-sm text-gray-400 hover:text-gray-200"
                          >
                            Regenerate
                          </button>
                        </div>

                        {/* I/O Summary */}
                        <div className="grid grid-cols-3 gap-3">
                          <div className="bg-gray-900 rounded p-3 border border-gray-700">
                            <span className="text-xs text-green-400 uppercase">Inputs</span>
                            <p className="text-lg font-semibold text-gray-100">
                              {ladderResponse.io_mapping.inputs.length}
                            </p>
                          </div>
                          <div className="bg-gray-900 rounded p-3 border border-gray-700">
                            <span className="text-xs text-red-400 uppercase">Outputs</span>
                            <p className="text-lg font-semibold text-gray-100">
                              {ladderResponse.io_mapping.outputs.length}
                            </p>
                          </div>
                          <div className="bg-gray-900 rounded p-3 border border-gray-700">
                            <span className="text-xs text-yellow-400 uppercase">Internal</span>
                            <p className="text-lg font-semibold text-gray-100">
                              {ladderResponse.io_mapping.internal.length}
                            </p>
                          </div>
                        </div>

                        {/* Rationale */}
                        {ladderResponse.rationale && (
                          <div className="p-3 bg-gray-900 rounded border border-gray-700">
                            <span className="text-xs text-gray-500 uppercase">Design Rationale</span>
                            <p className="text-sm text-gray-300 mt-1">{ladderResponse.rationale}</p>
                          </div>
                        )}

                        {/* Rungs Preview */}
                        <div className="bg-gray-900 rounded border border-gray-700 overflow-hidden">
                          <div className="px-3 py-2 border-b border-gray-700">
                            <span className="text-xs text-gray-500 uppercase">Rungs Preview</span>
                          </div>
                          <div className="max-h-48 overflow-y-auto p-2 space-y-2">
                            {ladderResponse.ladder_program.rungs.slice(0, 5).map((rung, idx) => (
                              <div key={idx} className="p-2 bg-gray-800 rounded text-sm">
                                <div className="text-gray-300 font-medium text-xs mb-1">
                                  {idx + 1}. {rung.description}
                                </div>
                                <div className="flex flex-wrap gap-1">
                                  {rung.elements.map((elem, elemIdx) => (
                                    <span
                                      key={elemIdx}
                                      className={`px-1.5 py-0.5 rounded text-xs font-mono ${
                                        elem.type === 'contact' ? 'bg-green-900/50 text-green-300' :
                                        elem.type === 'inverted_contact' ? 'bg-yellow-900/50 text-yellow-300' :
                                        elem.type === 'output' ? 'bg-red-900/50 text-red-300' :
                                        elem.type === 'analog_output' ? 'bg-blue-900/50 text-blue-300' :
                                        elem.type === 'counter' ? 'bg-purple-900/50 text-purple-300' :
                                        'bg-gray-700 text-gray-300'
                                      }`}
                                    >
                                      {elem.type === 'contact' ? '[ ]' :
                                       elem.type === 'inverted_contact' ? '[/]' :
                                       elem.type === 'output' ? '( )' :
                                       elem.type === 'analog_output' ? '[A]' :
                                       elem.type === 'counter' ? '[CTR]' :
                                       elem.type} {elem.name}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ))}
                            {ladderResponse.ladder_program.rungs.length > 5 && (
                              <div className="text-center text-xs text-gray-500 py-1">
                                +{ladderResponse.ladder_program.rungs.length - 5} more rungs
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {!ladderResponse && !ladderLoading && !ladderError && (
                      <button
                        onClick={handleGenerateLadder}
                        className="w-full py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        {isConnectMode ? 'Compute Interlocks' : 'Generate Ladder Logic'}
                      </button>
                    )}
                  </div>

                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => setStep(getNextStep())}
                      disabled={ladderLoading}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {ladderResponse ? 'Continue' : 'Skip'}
                    </button>
                  </div>
                </div>
              )}

              {/* SM Profile Step */}
              {step === 'smprofile' && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-100 mb-1">CESMII Model</h3>
                  <p className="text-sm text-gray-400 mb-4">
                    OPC UA Machine Identification profile for this machine
                  </p>

                  {smprofileLoading && (
                    <div className="flex items-center justify-center py-12">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-3"></div>
                        <p className="text-gray-400 text-sm">Generating SM Profile...</p>
                      </div>
                    </div>
                  )}

                  {smprofileError && (
                    <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 mb-4">
                      <p className="text-red-400 text-sm">{smprofileError}</p>
                      <button
                        onClick={handleGenerateSMProfile}
                        className="mt-2 px-3 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded"
                      >
                        Retry
                      </button>
                    </div>
                  )}

                  {smprofileData && !smprofileLoading && (
                    <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
                      <div className="px-4 py-2 bg-gray-800 border-b border-gray-700">
                        <span className="text-xs text-gray-400 font-mono">{smprofileData.$namespace}</span>
                      </div>
                      <table className="w-full text-sm">
                        <tbody className="divide-y divide-gray-700">
                          {Object.entries(smprofileData)
                            .filter(([key]) => key !== '$namespace')
                            .map(([key, value]) => (
                              <tr key={key}>
                                <td className="px-4 py-2 text-gray-400 font-mono text-xs w-1/3">{key}</td>
                                <td className="px-4 py-2 text-gray-200 font-mono text-xs">{String(value)}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => setStep(getNextStep())}
                      disabled={smprofileLoading}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* Confirm Step */}
              {step === 'confirm' && (
                <div className="space-y-4">
                  <h3 className="text-sm font-medium text-gray-300 mb-3">
                    Confirm Configuration
                  </h3>

                  <div className="bg-gray-900 rounded-lg p-4 border border-gray-700 space-y-3">
                    <div>
                      <span className="text-sm text-gray-500">Name:</span>
                      <span className="ml-2 text-gray-100">{machineName}</span>
                    </div>
                    <div>
                      <span className="text-sm text-gray-500">Type:</span>
                      <span className="ml-2 text-gray-100">{machine.machine_type}</span>
                    </div>

                    {/* Topics display - multi or single */}
                    {isMultiTopic && selectedTopics.length > 0 ? (
                      <div>
                        <span className="text-sm text-gray-500">Topics ({selectedTopics.length}):</span>
                        <div className="mt-1 space-y-2">
                          {selectedTopics.map((topic, idx) => (
                            <div key={idx} className="p-2 bg-gray-800 rounded">
                              <p className="font-mono text-sm text-gray-100">{topic.topic_path}</p>
                              <p className="text-xs text-gray-500">
                                Fields: {topic.fields.map(f => f.name).join(', ')}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div>
                        <span className="text-sm text-gray-500">Topic:</span>
                        <span className="ml-2 font-mono text-gray-100">{selectedTopic}</span>
                      </div>
                    )}

                    <div>
                      <span className="text-sm text-gray-500">Interval:</span>
                      <span className="ml-2 text-gray-100">{publishInterval}ms ({(publishInterval / 1000).toFixed(1)}s)</span>
                    </div>
                    {!isMultiTopic && (
                      <div>
                        <span className="text-sm text-gray-500">Fields:</span>
                        <div className="mt-1 flex flex-wrap gap-2">
                          {fields.map((f, idx) => (
                            <span key={idx} className="px-2 py-1 bg-gray-800 rounded text-xs text-gray-300">
                              {f.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-between pt-4">
                    <button
                      onClick={() => setStep(getPrevStep())}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition-colors disabled:opacity-50"
                    >
                      {saving ? 'Saving...' : 'Create & Start Machine'}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        </div>

        </>
        )}
      </div>

      {/* Topic Tree Browser Modal */}
      {showTreeBrowser && (
        <TopicTreeBrowser
          onSelect={handleTreeBrowserSelect}
          onClose={() => setShowTreeBrowser(false)}
        />
      )}
    </div>
  );
}
