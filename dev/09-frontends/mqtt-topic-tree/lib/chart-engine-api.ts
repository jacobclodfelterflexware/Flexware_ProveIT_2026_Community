/**
 * Chart Engine API client
 */

export interface ChartPreferences {
  chart_types?: string[];
  time_window?: string;
  max_series?: number;
}

export interface ChartGenerateRequest {
  query: string;
  conversation_id?: string;
  preferences?: ChartPreferences;
}

export interface ChartConfig {
  type: string;
  data: {
    labels?: string[];
    datasets?: Array<{
      label: string;
      data: Array<{ x: string | number; y: number }> | number[];
      borderColor?: string;
      backgroundColor?: string;
      fill?: boolean;
      tension?: number;
      [key: string]: unknown;
    }>;
    // For custom chart types
    value?: number;
    percentage?: number;
    min?: number;
    max?: number;
    unit?: string;
    color?: string;
    matrix?: number[][];
    sparklines?: Array<{
      topic: string;
      label: string;
      data: number[];
      current: number;
      min: number;
      max: number;
    }>;
    columns?: number;
  };
  options: Record<string, unknown>;
}

export interface RAGTopic {
  path: string;
  similarity: number;
  available_fields: string[];
  data_type: string;
}

export interface RAGContext {
  matching_topics: RAGTopic[];
  topic_hierarchy: Record<string, unknown>;
  time_range_available?: string;
  available_fields: string[];
}

export interface SampleValue {
  topic: string;
  value: number | string | null;
}

export interface InitialData {
  records: number;
  chart_id: string;
  sample_values?: SampleValue[];
}

export interface ParametersUsed {
  topics?: string[];
  fields?: string[];
  window?: string;
  topic?: string;
  field?: string;
  [key: string]: unknown;
}

export interface ChartGenerateResponse {
  chart_id: string;
  skill_used: string;
  chart_config: ChartConfig;
  initial_data: InitialData;
  stream_url: string;
  parameters_used: ParametersUsed;
  reasoning: string;
  rag_context?: RAGContext;
}

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  parameters_schema: Record<string, unknown>;
  chart_type: string;
  supports_streaming: boolean;
}

export interface StreamMessage {
  type: 'data_point' | 'error' | 'complete' | 'connected' | 'keepalive';
  timestamp?: string;
  series?: string;
  value?: number;
  error?: string;
}

const CHART_ENGINE_URL = '/api/chart-engine';

/**
 * Generate a chart from natural language query
 */
export async function generateChart(request: ChartGenerateRequest): Promise<ChartGenerateResponse> {
  const response = await fetch(`${CHART_ENGINE_URL}/generate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate chart');
  }

  return response.json();
}

/**
 * List available chart skills
 */
export async function listSkills(): Promise<SkillInfo[]> {
  const response = await fetch(`${CHART_ENGINE_URL}/skills`);

  if (!response.ok) {
    throw new Error('Failed to fetch skills');
  }

  const data = await response.json();
  return data.skills;
}

/**
 * Stop chart streaming
 */
export async function stopChart(chartId: string): Promise<void> {
  await fetch(`${CHART_ENGINE_URL}/${chartId}`, {
    method: 'DELETE',
  });
}

/**
 * Create SSE connection for chart updates
 * Uses named event listeners to match ml-predictor pattern
 */
export function subscribeToChart(
  chartId: string,
  onMessage: (message: StreamMessage) => void,
  onError?: (error: Event) => void
): EventSource {
  const eventSource = new EventSource(`${CHART_ENGINE_URL}/stream/${chartId}`);

  // Listen for named events (matching ml-predictor pattern)
  eventSource.addEventListener('connected', (event) => {
    try {
      const message: StreamMessage = JSON.parse((event as MessageEvent).data);
      onMessage(message);
    } catch (err) {
      console.error('Failed to parse connected event:', err);
    }
  });

  eventSource.addEventListener('data_point', (event) => {
    try {
      const message: StreamMessage = JSON.parse((event as MessageEvent).data);
      onMessage(message);
    } catch (err) {
      console.error('Failed to parse data_point event:', err);
    }
  });

  eventSource.addEventListener('keepalive', (event) => {
    try {
      const message: StreamMessage = JSON.parse((event as MessageEvent).data);
      onMessage(message);
    } catch (err) {
      console.error('Failed to parse keepalive event:', err);
    }
  });

  eventSource.addEventListener('error', (event) => {
    if (event instanceof MessageEvent && event.data) {
      try {
        const message: StreamMessage = JSON.parse(event.data);
        onMessage(message);
      } catch {
        onError?.(event);
      }
    }
  });

  eventSource.onerror = (event) => {
    onError?.(event);
  };

  return eventSource;
}
