/**
 * API client for schema conformance operations
 */

import {
  SchemaProposal,
  TopicBinding,
  SchemaProposalListResponse,
  TopicBindingListResponse,
  CreateProposalRequest,
  UpdateProposalRequest,
  CreateBindingRequest,
  SuccessResponse,
  ErrorResponse,
} from '@/types/conformance';

const API_BASE = '/api/schemas';

/**
 * Fetch list of schema proposals
 */
export async function fetchProposals(options?: {
  folder?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<SchemaProposalListResponse> {
  const params = new URLSearchParams();
  if (options?.folder) params.set('folder', options.folder);
  if (options?.search) params.set('search', options.search);
  if (options?.page) params.set('page', String(options.page));
  if (options?.pageSize) params.set('pageSize', String(options.pageSize));

  const response = await fetch(`${API_BASE}/proposals?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch proposals');
  }
  return response.json();
}

/**
 * Fetch a single schema proposal by ID
 */
export async function fetchProposal(id: string): Promise<SchemaProposal> {
  const response = await fetch(`${API_BASE}/proposals/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch proposal');
  }
  return response.json();
}

/**
 * Create a new schema proposal
 */
export async function createProposal(
  data: CreateProposalRequest
): Promise<SuccessResponse | ErrorResponse> {
  const response = await fetch(`${API_BASE}/proposals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}

/**
 * Update an existing schema proposal
 */
export async function updateProposal(
  id: string,
  data: UpdateProposalRequest
): Promise<SuccessResponse | ErrorResponse> {
  const response = await fetch(`${API_BASE}/proposals/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}

/**
 * Delete a schema proposal
 */
export async function deleteProposal(id: string): Promise<SuccessResponse | ErrorResponse> {
  const response = await fetch(`${API_BASE}/proposals/${id}`, {
    method: 'DELETE',
  });
  return response.json();
}

/**
 * Fetch list of topic bindings
 */
export async function fetchBindings(options?: {
  proposalId?: string;
  topicPath?: string;
}): Promise<TopicBindingListResponse> {
  const params = new URLSearchParams();
  if (options?.proposalId) params.set('proposalId', options.proposalId);
  if (options?.topicPath) params.set('topicPath', options.topicPath);

  const response = await fetch(`${API_BASE}/bindings?${params}`);
  if (!response.ok) {
    throw new Error('Failed to fetch bindings');
  }
  return response.json();
}

/**
 * Create a new topic binding
 */
export async function createBinding(
  data: CreateBindingRequest
): Promise<SuccessResponse | ErrorResponse> {
  const response = await fetch(`${API_BASE}/bindings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return response.json();
}

/**
 * Delete a topic binding
 */
export async function deleteBinding(options: {
  id?: string;
  topicPath?: string;
}): Promise<SuccessResponse | ErrorResponse> {
  const params = new URLSearchParams();
  if (options.id) params.set('id', options.id);
  if (options.topicPath) params.set('topicPath', options.topicPath);

  const response = await fetch(`${API_BASE}/bindings?${params}`, {
    method: 'DELETE',
  });
  return response.json();
}
