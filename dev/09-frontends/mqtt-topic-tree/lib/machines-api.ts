/**
 * API client for Machine Simulator service
 */

import type {
  MachineDefinition,
  MachineListResponse,
  MachineStatusResponse,
  GeneratedMachineResponse,
  GenerateRandomRequest,
  GeneratePromptedRequest,
  CreateMachineRequest,
  SchemaSuggestionResponse,
  FormulaSuggestionResponse,
  IntervalSuggestionResponse,
  TopicSuggestionResponse,
  UnifiedSuggestionResponse,
  FieldDefinition,
  SimilarTopicContext,
  GenerateLadderResponse,
  LadderRung,
  SMProfile,
} from '@/types/machines';

// Base URL for machine simulator API (via k8s service or proxy)
const API_BASE = process.env.NEXT_PUBLIC_MACHINE_SIMULATOR_URL || '/api/machines-proxy';

/**
 * Error thrown when attempting to create a machine with a duplicate name.
 */
export class DuplicateMachineError extends Error {
  constructor(name: string) {
    super(`A machine with name '${name}' already exists`);
    this.name = 'DuplicateMachineError';
  }
}

/**
 * Generate a random machine using LLM
 */
export async function generateRandomMachine(
  request?: GenerateRandomRequest
): Promise<GeneratedMachineResponse> {
  const response = await fetch(`${API_BASE}/generate/random`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request || {}),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate machine');
  }

  return response.json();
}

/**
 * Generate a machine from user prompt
 */
export async function generatePromptedMachine(
  request: GeneratePromptedRequest
): Promise<GeneratedMachineResponse> {
  const response = await fetch(`${API_BASE}/generate/prompted`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate machine');
  }

  return response.json();
}

/**
 * List all machines
 */
export async function listMachines(status?: string): Promise<MachineListResponse> {
  const params = status ? `?status=${status}` : '';
  const response = await fetch(`${API_BASE}${params}`);

  if (!response.ok) {
    throw new Error('Failed to fetch machines');
  }

  return response.json();
}

/**
 * Get a single machine by ID
 */
export async function getMachine(id: string): Promise<MachineDefinition> {
  const response = await fetch(`${API_BASE}/${id}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Machine not found');
    }
    throw new Error('Failed to fetch machine');
  }

  return response.json();
}

/**
 * Get a machine by creator name (most recent)
 */
export async function getMachineByCreator(name: string): Promise<MachineDefinition> {
  const response = await fetch(`${API_BASE}/by-creator/${encodeURIComponent(name)}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('No machine found for this creator');
    }
    throw new Error('Failed to fetch machine by creator');
  }

  return response.json();
}

/**
 * Create a new machine (after approval)
 */
export async function createMachine(
  request: CreateMachineRequest
): Promise<MachineDefinition> {
  const response = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (response.status === 409) {
    throw new DuplicateMachineError(request.name);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to create machine');
  }

  return response.json();
}

/**
 * Update a machine
 */
export async function updateMachine(
  id: string,
  request: CreateMachineRequest
): Promise<MachineDefinition> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to update machine');
  }

  return response.json();
}

/**
 * Delete a machine
 */
export async function deleteMachine(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete machine');
  }
}

/**
 * Start a machine (begin publishing)
 */
export async function startMachine(id: string): Promise<{ success: boolean; status: string }> {
  const response = await fetch(`${API_BASE}/${id}/start`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to start machine');
  }

  return response.json();
}

/**
 * Stop a machine (stop publishing)
 */
export async function stopMachine(id: string): Promise<{ success: boolean; status: string }> {
  const response = await fetch(`${API_BASE}/${id}/stop`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to stop machine');
  }

  return response.json();
}

/**
 * Get machine status
 */
export async function getMachineStatus(id: string): Promise<MachineStatusResponse> {
  const response = await fetch(`${API_BASE}/${id}/status`);

  if (!response.ok) {
    throw new Error('Failed to fetch machine status');
  }

  return response.json();
}

// Suggestion API

const SUGGESTIONS_BASE = process.env.NEXT_PUBLIC_MACHINE_SIMULATOR_URL
  ? `${process.env.NEXT_PUBLIC_MACHINE_SIMULATOR_URL.replace('/api/machines', '/api/suggestions')}`
  : '/api/suggestions-proxy';

/**
 * Get schema suggestion for a machine definition
 */
export async function getSchemaSuggestion(
  topicPath: string,
  fields: FieldDefinition[]
): Promise<SchemaSuggestionResponse> {
  const response = await fetch(`${SUGGESTIONS_BASE}/schema`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_path: topicPath, fields }),
  });

  if (!response.ok) {
    throw new Error('Failed to get schema suggestion');
  }

  return response.json();
}

/**
 * Get formula suggestions for fields
 */
export async function getFormulaSuggestions(
  topicPath: string,
  fields: FieldDefinition[],
  machineName?: string,
  similarTopics?: SimilarTopicContext[],
  sourceField?: string
): Promise<FormulaSuggestionResponse> {
  const response = await fetch(`${SUGGESTIONS_BASE}/formulas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic_path: topicPath,
      fields,
      machine_name: machineName,
      similar_topics: similarTopics,
      source_field: sourceField,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to get formula suggestions');
  }

  return response.json();
}

/**
 * Get interval suggestion for a topic
 */
export async function getIntervalSuggestion(
  topicPath: string
): Promise<IntervalSuggestionResponse> {
  const response = await fetch(`${SUGGESTIONS_BASE}/interval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic_path: topicPath }),
  });

  if (!response.ok) {
    throw new Error('Failed to get interval suggestion');
  }

  return response.json();
}

/**
 * Get topic suggestion based on machine type, name, and fields
 */
export async function getTopicSuggestion(
  machineType: string,
  machineName: string,
  fields: FieldDefinition[]
): Promise<TopicSuggestionResponse> {
  const response = await fetch(`${SUGGESTIONS_BASE}/topic`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ machine_type: machineType, machine_name: machineName, fields }),
  });

  if (!response.ok) {
    throw new Error('Failed to get topic suggestion');
  }

  return response.json();
}

/**
 * Get unified topic + schema suggestion based on machine type, name, and fields.
 * Uses 60% topic semantic similarity + 40% field Jaccard similarity.
 * Returns LLM-suggested topic and schema, plus historical payloads for top similar topics.
 *
 * Includes a 30-second timeout to prevent hanging when backend LLM calls are slow.
 */
export async function getUnifiedSuggestion(
  machineType: string,
  machineName: string,
  fields: FieldDefinition[]
): Promise<UnifiedSuggestionResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

  try {
    const response = await fetch(`${SUGGESTIONS_BASE}/unified`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ machine_type: machineType, machine_name: machineName, fields }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error('Failed to get unified suggestion');
    }

    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timed out after 30 seconds. The machine-simulator service may be slow or unavailable.');
    }
    throw error;
  }
}

// Image Generation API

const IMAGES_BASE = '/api/images-proxy';

export interface GenerateImageRequest {
  machine_type: string;
  description?: string;
  fields?: Array<{ name: string; type: string }>;
}

export interface GenerateImageResponse {
  image_base64: string;
  prompt_used?: string;
}

/**
 * Generate an image for a machine
 */
export async function generateMachineImage(
  request: GenerateImageRequest
): Promise<GenerateImageResponse> {
  const response = await fetch(`${IMAGES_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate image');
  }

  return response.json();
}

// Ladder Logic API

/**
 * Generate ladder logic for a machine based on its type and fields.
 * Uses LLM to create plausible ladder rungs where machine fields become I/O.
 */
export async function generateLadderLogic(
  machineType: string,
  fields: FieldDefinition[],
  description?: string
): Promise<GenerateLadderResponse> {
  const response = await fetch(`${API_BASE}/generate/ladder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      machine_type: machineType,
      fields,
      description,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate ladder logic');
  }

  return response.json();
}

// SM Profile API

/**
 * Generate a CESMII SM Profile (Machine Identification) for a machine
 */
export async function generateSMProfile(
  machineType: string,
  machineName: string,
  description?: string
): Promise<{ smprofile: SMProfile }> {
  const response = await fetch(`${API_BASE}/generate/smprofile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      machine_type: machineType,
      machine_name: machineName,
      description,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to generate SM Profile');
  }

  return response.json();
}

// PLCOpen Ladder API (direct access)
const PLCOPEN_BASE = '/api/plcopen';

/**
 * Load ladder rungs into the PLCOpen simulator
 */
export async function loadLadderProgram(rungs: LadderRung[]): Promise<{
  success: boolean;
  message: string;
  rung_count: number;
  variables: string[];
}> {
  const response = await fetch(`${PLCOPEN_BASE}/simulate/ladder/load-json`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rungs }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to load ladder program');
  }

  return response.json();
}

/**
 * Start the ladder simulator with auto-simulation enabled
 */
export async function startLadderSimulator(): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${PLCOPEN_BASE}/simulate/ladder/start`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to start ladder simulator');
  }

  // Also enable auto-simulation so inputs pulse automatically
  await fetch(`${PLCOPEN_BASE}/simulate/ladder/auto-sim/start`, {
    method: 'POST',
  });

  return response.json();
}

/**
 * Stop the ladder simulator
 */
export async function stopLadderSimulator(): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${PLCOPEN_BASE}/simulate/ladder/stop`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to stop ladder simulator');
  }

  return response.json();
}

// ============== Ladder Logic Storage API ==============

import type { LadderLogicData } from '@/types/machines';

/**
 * Save ladder logic for a machine.
 * Stores the ladder configuration in Neo4j associated with the machine.
 */
export async function saveLadderLogic(
  machineId: string,
  ladderData: {
    rungs: LadderRung[];
    io_mapping: { inputs: string[]; outputs: string[]; internal: string[] };
    rationale?: string;
  }
): Promise<LadderLogicData> {
  const response = await fetch(`${API_BASE}/${machineId}/ladder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rungs: ladderData.rungs,
      io_mapping: ladderData.io_mapping,
      rationale: ladderData.rationale,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to save ladder logic');
  }

  return response.json();
}

/**
 * Get ladder logic for a machine.
 * Returns the stored ladder configuration, or null if none exists.
 */
export async function getLadderLogic(machineId: string): Promise<LadderLogicData | null> {
  const response = await fetch(`${API_BASE}/${machineId}/ladder`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to get ladder logic');
  }

  return response.json();
}

/**
 * Delete ladder logic for a machine.
 */
export async function deleteLadderLogic(machineId: string): Promise<{ success: boolean }> {
  const response = await fetch(`${API_BASE}/${machineId}/ladder`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to delete ladder logic');
  }

  return response.json();
}

/**
 * Set I/O values in the ladder simulator from external sources (e.g., MQTT).
 * This allows real broker values to be displayed in the ladder visualization.
 */
export async function setLadderIOValues(
  values: Record<string, number | boolean>
): Promise<{ success: boolean; updated: string[] }> {
  const response = await fetch(`${PLCOPEN_BASE}/simulate/ladder/io`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ values }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Failed to set ladder I/O values');
  }

  return response.json();
}
