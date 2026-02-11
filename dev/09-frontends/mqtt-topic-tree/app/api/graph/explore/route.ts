import { getSession } from '@/lib/neo4j-client';
import { NODE_COLORS } from '@/lib/graph-transformer';
import { Node as Neo4jNode, Relationship as Neo4jRelationship, Path, Integer } from 'neo4j-driver';

interface TransformedNode {
  id: string;
  caption: string;
  color: string;
  size: number;
  nodeType: string;
  properties: Record<string, unknown>;
}

interface TransformedRelationship {
  id: string;
  from: string;
  to: string;
  caption: string;
  color: string;
  width: number;
}

function intToString(value: Integer | number | string): string {
  if (typeof value === 'object' && 'toNumber' in value) {
    return value.toString();
  }
  return String(value);
}

function getNodeLabel(node: Neo4jNode): string {
  const labels = node.labels;
  if (labels.includes('Topic')) return 'topic';
  if (labels.includes('TopicSegment')) return 'topicSegment';
  if (labels.includes('Message')) return 'message';
  if (labels.includes('SchemaMapping')) return 'schemaMapping';
  return 'unknown';
}

function getNodeColor(nodeType: string): string {
  switch (nodeType) {
    case 'topic':
    case 'topicSegment':
      // All topics now use the same color - client IDs are root segments
      return NODE_COLORS.topic_uncurated;
    case 'message':
      return NODE_COLORS.message;
    case 'schemaMapping':
      return NODE_COLORS.schemaMapping;
    default:
      return '#6b7280'; // gray
  }
}

function getNodeCaption(node: Neo4jNode, nodeType: string): string {
  const props = node.properties;
  switch (nodeType) {
    case 'topicSegment':
      return props.name as string || 'Segment';
    case 'topic':
      const path = props.path as string;
      const parts = path?.split('/') || [];
      return parts[parts.length - 1] || path || 'Topic';
    case 'message':
      const ts = props.timestamp as string;
      if (ts) {
        try {
          const date = new Date(ts);
          return `Msg ${date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
        } catch {
          return 'Message';
        }
      }
      return 'Message';
    case 'schemaMapping':
      return props.targetTopic as string || 'Mapping';
    default:
      return 'Node';
  }
}

function getNodeSize(nodeType: string): number {
  switch (nodeType) {
    case 'topic':
    case 'topicSegment':
      return 30;
    case 'message':
      return 20;
    case 'schemaMapping':
      return 25;
    default:
      return 25;
  }
}

function getRelationshipColor(type: string): string {
  switch (type) {
    case 'HAS_MESSAGE':
      return NODE_COLORS.message;
    case 'ROUTES_TO':
      return NODE_COLORS.schemaMapping;
    case 'SIMILAR_TO':
      return NODE_COLORS.similar;
    case 'CHILD_OF':
      return '#60a5fa'; // blue-400 for hierarchy
    default:
      return '#6b7280';
  }
}

function getNodeDedupeKey(node: Neo4jNode, nodeType: string): string {
  // Use path/fullPath for deduplication to handle duplicate nodes in Neo4j
  const props = node.properties;
  if (nodeType === 'topicSegment' && props.fullPath) {
    return `segment:${props.fullPath}`;
  }
  if (nodeType === 'topic' && props.path) {
    return `topic:${props.path}`;
  }
  // Fall back to Neo4j identity for other node types
  return intToString(node.identity);
}

function transformNode(node: Neo4jNode): TransformedNode {
  const nodeType = getNodeLabel(node);
  const dedupeKey = getNodeDedupeKey(node, nodeType);

  return {
    id: dedupeKey,
    caption: getNodeCaption(node, nodeType),
    color: getNodeColor(nodeType),
    size: getNodeSize(nodeType),
    nodeType,
    properties: Object.fromEntries(
      Object.entries(node.properties).map(([k, v]) => {
        if (v && typeof v === 'object' && 'toNumber' in v) {
          return [k, (v as Integer).toNumber()];
        }
        return [k, v];
      })
    ),
  };
}

function transformRelationship(rel: Neo4jRelationship): TransformedRelationship {
  return {
    id: intToString(rel.identity),
    from: intToString(rel.start),
    to: intToString(rel.end),
    caption: rel.type,
    color: getRelationshipColor(rel.type),
    width: rel.type === 'ROUTES_TO' ? 2 : 1,
  };
}

function isNode(value: unknown): value is Neo4jNode {
  return value !== null && typeof value === 'object' && 'labels' in value && 'properties' in value;
}

function isRelationship(value: unknown): value is Neo4jRelationship {
  return value !== null && typeof value === 'object' && 'type' in value && 'start' in value && 'end' in value;
}

function isPath(value: unknown): value is Path {
  return value !== null && typeof value === 'object' && 'segments' in value;
}

export async function POST(request: Request) {
  const session = getSession();

  try {
    const { query, params } = await request.json();

    if (!query) {
      return Response.json({ error: 'Query is required' }, { status: 400 });
    }

    console.log('[Graph Explore] Running query:', query.substring(0, 100) + '...');

    // No broker parameter needed - client IDs are now root segments
    const queryParams = params || {};

    const result = await session.run(query, queryParams);

    const nodes = new Map<string, TransformedNode>();
    const rawRelationships: Neo4jRelationship[] = [];
    // Map from Neo4j identity to dedupe key for relationship remapping
    const nodeIdMap = new Map<string, string>();

    // First pass: collect all nodes and build ID mapping
    const processNode = (node: Neo4jNode) => {
      const transformed = transformNode(node);
      const neo4jId = intToString(node.identity);
      nodeIdMap.set(neo4jId, transformed.id);
      nodes.set(transformed.id, transformed);
    };

    for (const record of result.records) {
      const values: unknown[] = [];
      for (let i = 0; i < record.keys.length; i++) {
        values.push(record.get(record.keys[i]));
      }
      for (const value of values) {
        // Handle null values
        if (value === null) continue;

        // Handle nodes
        if (isNode(value)) {
          processNode(value);
        }
        // Handle relationships - collect for second pass
        else if (isRelationship(value)) {
          rawRelationships.push(value);
        }
        // Handle paths
        else if (isPath(value)) {
          for (const segment of value.segments) {
            processNode(segment.start);
            processNode(segment.end);
            rawRelationships.push(segment.relationship);
          }
        }
        // Handle map objects (like {rel: r, msg: m})
        else if (typeof value === 'object' && value !== null) {
          const obj = value as Record<string, unknown>;
          for (const v of Object.values(obj)) {
            if (isNode(v)) {
              processNode(v);
            } else if (isRelationship(v)) {
              rawRelationships.push(v);
            }
          }
        }
      }
    }

    // Second pass: transform relationships with remapped node IDs
    const relationships: TransformedRelationship[] = [];
    const seenRelKeys = new Set<string>();

    for (const rel of rawRelationships) {
      const fromNeo4jId = intToString(rel.start);
      const toNeo4jId = intToString(rel.end);
      const fromId = nodeIdMap.get(fromNeo4jId) || fromNeo4jId;
      const toId = nodeIdMap.get(toNeo4jId) || toNeo4jId;

      // Create a unique key based on remapped IDs to dedupe relationships
      const relKey = `${fromId}-${rel.type}-${toId}`;
      if (!seenRelKeys.has(relKey)) {
        seenRelKeys.add(relKey);
        relationships.push({
          id: relKey,
          from: fromId,
          to: toId,
          caption: rel.type,
          color: getRelationshipColor(rel.type),
          width: rel.type === 'ROUTES_TO' ? 2 : 1,
        });
      }
    }

    console.log(`[Graph Explore] Found ${nodes.size} nodes and ${relationships.length} relationships`);

    return Response.json({
      nodes: Array.from(nodes.values()),
      relationships,
    });
  } catch (error) {
    console.error('[Graph Explore] Error:', error);
    const message = error instanceof Error ? error.message : 'Unknown error';
    return Response.json({ error: message }, { status: 500 });
  } finally {
    await session.close();
  }
}
