/**
 * Types for Schema Conformance Monitoring
 */

// Conformance status values
export type ConformanceStatus = 'conformant' | 'non_conformant' | 'no_binding' | 'mixed';

// JSON Schema field types
export type FieldType = 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object' | 'null';

/**
 * Schema field definition
 */
export interface FieldSchema {
  type: FieldType;
  required?: boolean;
  description?: string;
}

/**
 * Expected schema definition (simplified JSON Schema)
 */
export interface ExpectedSchema {
  type: 'object';
  properties: Record<string, FieldSchema>;
  additionalProperties: boolean;
}

/**
 * Schema Proposal - a reusable schema definition
 */
export interface SchemaProposal {
  id: string;
  name: string;
  folder: string;
  description?: string;
  expectedSchema: ExpectedSchema;
  version: number;
  createdAt: string;
  updatedAt?: string;
  createdBy: string;
  // Populated when fetching single proposal
  boundTopics?: string[];
}

/**
 * Topic Binding - links a topic path to a schema proposal
 */
export interface TopicBinding {
  id: string;
  topicPath: string;
  proposalId: string;
  boundAt: string;
  boundBy: string;
  // Populated from join
  proposalName?: string;
}

/**
 * Conformance stats for a topic
 */
export interface TopicConformanceStats {
  conformantCount: number;
  nonConformantCount: number;
  unboundCount: number;
  boundProposalId?: string;
  boundProposalName?: string;
}

/**
 * Message with conformance info
 */
export interface ConformantMessage {
  messageId: string;
  rawPayload: string;
  timestamp: string;
  conformanceStatus: ConformanceStatus;
  conformanceErrors?: string[];
  boundProposalId?: string;
}

// API Response types

export interface SchemaProposalListResponse {
  proposals: SchemaProposal[];
  folders: string[];
  total: number;
  page: number;
  pageSize: number;
}

export interface TopicBindingListResponse {
  bindings: TopicBinding[];
}

export interface CreateProposalRequest {
  name: string;
  folder?: string;
  description?: string;
  expectedSchema: ExpectedSchema;
}

export interface UpdateProposalRequest {
  name?: string;
  folder?: string;
  description?: string;
  expectedSchema?: ExpectedSchema;
}

export interface CreateBindingRequest {
  topicPath: string;
  proposalId: string;
}

export interface SuccessResponse {
  success: true;
  id?: string;
  version?: number;
}

export interface ErrorResponse {
  success?: false;
  error: string;
}

/**
 * Helper to create an empty schema
 */
export function createEmptySchema(): ExpectedSchema {
  return {
    type: 'object',
    properties: {},
    additionalProperties: false
  };
}

/**
 * Helper to add a field to a schema
 */
export function addFieldToSchema(
  schema: ExpectedSchema,
  name: string,
  type: FieldType,
  required: boolean = false,
  description?: string
): ExpectedSchema {
  return {
    ...schema,
    properties: {
      ...schema.properties,
      [name]: {
        type,
        required,
        description
      }
    }
  };
}

/**
 * Helper to count fields in a schema
 */
export function countSchemaFields(schema: ExpectedSchema): {
  total: number;
  required: number;
} {
  const properties = schema.properties || {};
  const total = Object.keys(properties).length;
  const required = Object.values(properties).filter(f => f.required).length;
  return { total, required };
}

/**
 * Helper to derive aggregate conformance status
 */
export function deriveConformanceStatus(stats: TopicConformanceStats): ConformanceStatus {
  const { conformantCount, nonConformantCount, unboundCount } = stats;

  const hasConformant = conformantCount > 0;
  const hasNonConformant = nonConformantCount > 0;

  if (hasConformant && hasNonConformant) {
    return 'mixed';
  } else if (hasNonConformant) {
    return 'non_conformant';
  } else if (hasConformant) {
    return 'conformant';
  }
  return 'no_binding';
}
