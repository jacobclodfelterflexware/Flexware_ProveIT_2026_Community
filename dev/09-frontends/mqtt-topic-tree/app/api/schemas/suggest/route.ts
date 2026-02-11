import { getSession } from '@/lib/neo4j-client';

interface SimilarMessage {
  topicPath: string;
  payload: string;
  similarity: number;
  boundProposalId: string | null;
  boundProposalName: string | null;
}

interface SuggestedField {
  name: string;
  type: string;
  required: boolean;
  source: 'similar' | 'payload' | 'removed';
}

interface SuggestionResponse {
  similarMessages: SimilarMessage[];
  suggestedSchema: {
    fields: SuggestedField[];
    basedOn: 'similar_schema' | 'payload_analysis' | 'no_data';
    similarSchemaId?: string;
    similarSchemaName?: string;
    confidence: 'high' | 'medium' | 'low';
    similarity: number;
  };
  payloadFields: Array<{ name: string; type: string; value: unknown }>;
}

/**
 * Infer JSON type from a value
 */
function inferType(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  const t = typeof value;
  if (t === 'number') {
    return Number.isInteger(value) ? 'integer' : 'number';
  }
  return t; // string, boolean, object
}

/**
 * Calculate similarity between two sets of keys
 */
function calculateKeySimilarity(keys1: string[], keys2: string[]): number {
  if (keys1.length === 0 && keys2.length === 0) return 1;
  if (keys1.length === 0 || keys2.length === 0) return 0;

  const set1 = new Set(keys1);
  const set2 = new Set(keys2);
  const intersection = keys1.filter(k => set2.has(k)).length;
  const union = new Set([...keys1, ...keys2]).size;

  return intersection / union; // Jaccard similarity
}

/**
 * POST /api/schemas/suggest
 * Analyze a topic/payload and suggest a schema based on similar messages
 */
export async function POST(request: Request) {
  const session = getSession();

  try {
    const body = await request.json();
    const { topicPath, payload } = body;

    if (!topicPath) {
      return Response.json({ error: 'topicPath is required' }, { status: 400 });
    }

    // Parse the payload if provided
    let parsedPayload: Record<string, unknown> = {};
    let payloadFields: Array<{ name: string; type: string; value: unknown }> = [];

    if (payload) {
      try {
        parsedPayload = typeof payload === 'string' ? JSON.parse(payload) : payload;
        if (typeof parsedPayload === 'object' && parsedPayload !== null && !Array.isArray(parsedPayload)) {
          payloadFields = Object.entries(parsedPayload).map(([name, value]) => ({
            name,
            type: inferType(value),
            value,
          }));
        }
      } catch {
        // Not valid JSON, can't analyze
      }
    }

    const payloadKeys = payloadFields.map(f => f.name);

    // Find similar messages by looking at messages with similar payload structure
    // We'll query recent messages and compare their payload keys
    const result = await session.run(`
      MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
      WHERE t.path <> $topicPath
      AND m.rawPayload IS NOT NULL
      AND m.rawPayload <> ''
      OPTIONAL MATCH (tb:TopicBinding {topicPath: t.path})
      OPTIONAL MATCH (sp:SchemaProposal {id: tb.proposalId})
      WITH t, m, tb, sp
      ORDER BY m.timestamp DESC
      WITH t.path as topicPath,
           collect(m.rawPayload)[0] as latestPayload,
           tb.proposalId as boundProposalId,
           sp.name as boundProposalName,
           sp.expectedSchema as boundSchema
      RETURN topicPath, latestPayload, boundProposalId, boundProposalName, boundSchema
      LIMIT 100
    `, { topicPath });

    // Calculate similarity for each message
    const similarMessages: (SimilarMessage & { schema?: string })[] = [];

    for (const record of result.records) {
      const msgTopicPath = record.get('topicPath') as string;
      const msgPayload = record.get('latestPayload') as string;
      const boundProposalId = record.get('boundProposalId') as string | null;
      const boundProposalName = record.get('boundProposalName') as string | null;
      const boundSchema = record.get('boundSchema') as string | null;

      try {
        const parsed = JSON.parse(msgPayload);
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          const msgKeys = Object.keys(parsed);
          const similarity = calculateKeySimilarity(payloadKeys, msgKeys);

          if (similarity > 0.1) { // Only include if at least 10% similar
            similarMessages.push({
              topicPath: msgTopicPath,
              payload: msgPayload,
              similarity,
              boundProposalId,
              boundProposalName,
              schema: boundSchema || undefined,
            });
          }
        }
      } catch {
        // Skip non-JSON payloads
      }
    }

    // Sort by similarity descending
    similarMessages.sort((a, b) => b.similarity - a.similarity);

    // Take top 10
    const topSimilar = similarMessages.slice(0, 10);

    // Find the best matching schema
    let suggestedSchema: SuggestionResponse['suggestedSchema'];

    // Look for the most similar message that has a bound schema
    const bestWithSchema = topSimilar.find(m => m.boundProposalId && m.schema);

    if (bestWithSchema && bestWithSchema.similarity >= 0.5) {
      // Use the similar schema as the base
      try {
        const schemaObj = JSON.parse(bestWithSchema.schema!);
        const schemaProperties = schemaObj.properties || {};
        const requiredFields = new Set(schemaObj.required || []);

        const fields: SuggestedField[] = [];

        // Add fields from the similar schema
        for (const [fieldName, fieldDef] of Object.entries(schemaProperties)) {
          const def = fieldDef as { type?: string; required?: boolean };
          fields.push({
            name: fieldName,
            type: def.type || 'string',
            required: requiredFields.has(fieldName),
            source: 'similar',
          });
        }

        // Mark payload fields not in the schema as 'removed'
        for (const pf of payloadFields) {
          if (!schemaProperties[pf.name]) {
            fields.push({
              name: pf.name,
              type: pf.type,
              required: false,
              source: 'removed',
            });
          }
        }

        suggestedSchema = {
          fields,
          basedOn: 'similar_schema',
          similarSchemaId: bestWithSchema.boundProposalId!,
          similarSchemaName: bestWithSchema.boundProposalName!,
          confidence: bestWithSchema.similarity >= 0.8 ? 'high' : 'medium',
          similarity: bestWithSchema.similarity,
        };
      } catch {
        // Fall through to payload analysis
        suggestedSchema = buildFromPayload(payloadFields);
      }
    } else if (payloadFields.length > 0) {
      // No similar schema found, analyze the payload directly
      suggestedSchema = buildFromPayload(payloadFields);
    } else {
      // No data to work with
      suggestedSchema = {
        fields: [],
        basedOn: 'no_data',
        confidence: 'low',
        similarity: 0,
      };
    }

    const response: SuggestionResponse = {
      similarMessages: topSimilar.map(m => ({
        topicPath: m.topicPath,
        payload: m.payload,
        similarity: m.similarity,
        boundProposalId: m.boundProposalId,
        boundProposalName: m.boundProposalName,
      })),
      suggestedSchema,
      payloadFields,
    };

    return Response.json(response);
  } catch (error) {
    console.error('[Schema Suggest] Error:', error);
    return Response.json({ error: 'Failed to generate suggestion' }, { status: 500 });
  } finally {
    await session.close();
  }
}

function buildFromPayload(payloadFields: Array<{ name: string; type: string; value: unknown }>): SuggestionResponse['suggestedSchema'] {
  return {
    fields: payloadFields.map(f => ({
      name: f.name,
      type: f.type,
      required: true, // Assume all fields are required when inferring from payload
      source: 'payload' as const,
    })),
    basedOn: 'payload_analysis',
    confidence: 'low',
    similarity: 0,
  };
}

export const dynamic = 'force-dynamic';
