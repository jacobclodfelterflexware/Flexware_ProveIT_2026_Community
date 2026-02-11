/**
 * ML Predictor API client
 */

const ML_API_BASE = process.env.NEXT_PUBLIC_ML_API_URL || '/api/ml-proxy';

// ============== Types ==============

export interface PredictionPoint {
  date: string;
  value: number;
  lower: number;
  upper: number;
}

export interface PredictionMetrics {
  rmse?: number;
  mae?: number;
  mape?: number;
}

export interface PredictionResponse {
  machineId: string;
  field: string;
  topic: string;
  horizon: string;
  predictions: PredictionPoint[];
  historical: PredictionPoint[];
  metrics: PredictionMetrics;
  trainedAt?: string;
  dataPointsUsed: number;
}

export interface FeatureInfo {
  machineId: string;
  machineName?: string;
  topic: string;
  field: string;
  coefficient: number;
  pValue?: number;
  importance?: number;
}

export interface RegressionResponse {
  machineId: string;
  targetField: string;
  targetTopic: string;
  features: FeatureInfo[];
  intercept: number;
  rSquared: number;
  correlationMatrix: Record<string, Record<string, number>>;
  trainedAt?: string;
  dataPointsUsed: number;
}

export interface CorrelationEntry {
  sourceMachineId: string;
  sourceMachineName?: string;
  sourceTopic: string;
  sourceField: string;
  targetField: string;
  correlation: number;
  pValue?: number;
}

export interface CorrelationsResponse {
  machineId: string;
  field: string;
  correlations: CorrelationEntry[];
}

export interface AvailableMachine {
  machineId: string;
  name: string;
  status: string;
  fieldsByTopic: Record<string, string[]>;
}

export interface TopicWithFields {
  path: string;
  fields: string[];
}

export interface AllAvailableFieldsResponse {
  topics: TopicWithFields[];
}

export interface FeatureSelection {
  topic: string;
  field: string;
}

export interface FieldsByTopic {
  machineId: string;
  fieldsByTopic: Record<string, string[]>;
}

// ============== API Functions ==============

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${ML_API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get time series prediction for a machine field
 */
export async function getPrediction(
  machineId: string,
  field: string,
  topic: string,
  horizon: 'day' | 'week' | 'month' = 'week',
  forceRefresh = false
): Promise<PredictionResponse> {
  const params = new URLSearchParams({
    field,
    topic,
    horizon,
    force_refresh: String(forceRefresh),
  });

  return fetchApi<PredictionResponse>(`/predict/${machineId}?${params}`);
}

/**
 * Get list of predictable fields for a machine
 */
export async function getPredictableFields(machineId: string): Promise<FieldsByTopic> {
  return fetchApi<FieldsByTopic>(`/predict/${machineId}/fields`);
}

/**
 * Get historical data for a field
 */
export async function getHistoricalData(
  machineId: string,
  field: string,
  topic: string,
  days = 30
): Promise<{ machineId: string; field: string; topic: string; data: PredictionPoint[] }> {
  const params = new URLSearchParams({
    field,
    topic,
    days: String(days),
  });

  return fetchApi(`/predict/${machineId}/history?${params}`);
}

/**
 * Get regression analysis for a machine field
 */
export async function getRegression(
  machineId: string,
  targetField: string,
  targetTopic: string,
  includeSimilar = true,
  additionalMachineIds?: string[],
  forceRefresh = false
): Promise<RegressionResponse> {
  const params = new URLSearchParams({
    targetField,
    targetTopic,
    includeSimilar: String(includeSimilar),
    force_refresh: String(forceRefresh),
  });

  if (additionalMachineIds?.length) {
    params.set('additionalMachineIds', additionalMachineIds.join(','));
  }

  return fetchApi<RegressionResponse>(`/regression/${machineId}?${params}`);
}

/**
 * Get correlation analysis for a field
 */
export async function getCorrelations(
  machineId: string,
  field: string,
  topic: string,
  source: 'similar' | 'manual' | 'all' = 'all',
  machineIds?: string[]
): Promise<CorrelationsResponse> {
  const params = new URLSearchParams({
    field,
    topic,
    source,
  });

  if (machineIds?.length) {
    params.set('machine_ids', machineIds.join(','));
  }

  return fetchApi<CorrelationsResponse>(`/correlations/${machineId}?${params}`);
}

/**
 * Get list of machines available for correlation analysis
 */
export async function getAvailableMachines(machineId: string): Promise<{ machines: AvailableMachine[] }> {
  return fetchApi(`/regression/${machineId}/available-machines`);
}

// localStorage cache key and TTL for available fields
const AVAILABLE_FIELDS_CACHE_KEY = 'ml-available-fields-cache';
const AVAILABLE_FIELDS_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Get all available topics and fields from Neo4j
 * Uses localStorage cache with 5-minute TTL to persist across page refreshes
 */
export async function getAllAvailableFields(): Promise<AllAvailableFieldsResponse> {
  const now = Date.now();

  // Check localStorage cache (persists across page refreshes)
  if (typeof window !== 'undefined') {
    try {
      const cached = localStorage.getItem(AVAILABLE_FIELDS_CACHE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        if ((now - timestamp) < AVAILABLE_FIELDS_CACHE_TTL_MS) {
          return data;
        }
      }
    } catch {
      // Ignore localStorage errors
    }
  }

  // Fetch fresh data
  const response = await fetchApi<AllAvailableFieldsResponse>('/regression/available-fields');

  // Save to localStorage
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem(AVAILABLE_FIELDS_CACHE_KEY, JSON.stringify({
        data: response,
        timestamp: now,
      }));
    } catch {
      // Ignore localStorage errors (quota exceeded, etc.)
    }
  }

  return response;
}

/**
 * Clear the available fields cache (used when cache is stale)
 */
export function clearAvailableFieldsCache(): void {
  if (typeof window !== 'undefined') {
    try {
      localStorage.removeItem(AVAILABLE_FIELDS_CACHE_KEY);
    } catch {
      // Ignore errors
    }
  }
}

/**
 * Check for cached regression result without training
 * Returns the cached result if found, or null if no cache exists
 */
export async function getCachedRegression(
  machineId: string,
  targetTopic: string,
  targetField: string,
  features: FeatureSelection[]
): Promise<RegressionResponse | null> {
  const params = new URLSearchParams({
    targetTopic,
    targetField,
    features: JSON.stringify(features),
  });

  try {
    const result = await fetchApi<RegressionResponse | null>(`/regression/${machineId}/cached?${params}`);
    return result;
  } catch {
    // No cache found or error - return null
    return null;
  }
}


/**
 * Clear cached predictions/regressions for a machine
 */
export async function clearCache(machineId: string): Promise<{ machineId: string; deletedCount: number; message: string }> {
  return fetchApi(`/train/${machineId}/cache`, {
    method: 'DELETE',
  });
}

