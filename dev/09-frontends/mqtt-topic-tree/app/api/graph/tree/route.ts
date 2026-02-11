// GET /api/graph/tree
// Returns hierarchical topic structure from Neo4j
// Client IDs are now the root level of the topic hierarchy

import { NextResponse } from 'next/server';
import { getSession } from '@/lib/neo4j-client';

interface DataTypes {
  numeric: boolean;
  string: boolean;
  boolean: boolean;
  object: boolean;
  array: boolean;
}

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;       // Direct messages on this topic
  totalMessageCount?: number;  // Sum of self + all descendant messages
  hasNumericData?: boolean;    // Whether this topic has numeric fields (eligible for ML)
  hasMLReadyDescendant?: boolean; // True if any child/grandchild is ML-ready (20+ msgs with numeric data)
  hasVariance?: boolean | null;  // true=varying, false=static, null=indeterminate (JSON payloads)
  dataTypes?: DataTypes;       // What data types are present in this topic's payloads
}

// Get all topic paths from Neo4j with sample payload to detect numeric fields
// Uses CALL subqueries with LIMIT to avoid loading all messages
// Second CALL subquery checks variance: min/max of numericValue over last 50 messages
const TREE_QUERY = `
MATCH (t:Topic)
OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
WITH t.path AS path, count(m) AS messageCount
CALL {
  WITH path
  MATCH (topic:Topic {path: path})-[:HAS_MESSAGE]->(msg:Message)
  RETURN msg.rawPayload AS samplePayload
  LIMIT 1
}
CALL {
  WITH path
  MATCH (topic:Topic {path: path})-[:HAS_MESSAGE]->(msg:Message)
  WHERE msg.numericValue IS NOT NULL
  WITH msg ORDER BY msg.timestamp DESC LIMIT 50
  RETURN min(msg.numericValue) AS minValue, max(msg.numericValue) AS maxValue,
         count(msg.numericValue) AS numericSampleCount
}
RETURN path, messageCount, samplePayload, minValue, maxValue, numericSampleCount
ORDER BY path
`;

// Analyze all data types present in a payload
function analyzePayloadTypes(payloadStr: string | null): DataTypes {
  const types: DataTypes = { numeric: false, string: false, boolean: false, object: false, array: false };
  if (!payloadStr) return types;

  try {
    const payload = JSON.parse(payloadStr);

    if (typeof payload === 'number') {
      types.numeric = true;
    } else if (typeof payload === 'string') {
      types.string = true;
    } else if (typeof payload === 'boolean') {
      types.boolean = true;
    } else if (Array.isArray(payload)) {
      types.array = true;
      // Also analyze array contents
      for (const item of payload) {
        if (typeof item === 'number') types.numeric = true;
        else if (typeof item === 'string') types.string = true;
        else if (typeof item === 'boolean') types.boolean = true;
        else if (typeof item === 'object') types.object = true;
      }
    } else if (typeof payload === 'object' && payload !== null) {
      // Analyze object fields
      const excludedFields = ['timestamp', 'time', 'ts', 'created_at', 'updated_at'];
      for (const [key, value] of Object.entries(payload)) {
        const keyLower = key.toLowerCase();
        if (typeof value === 'number' && !excludedFields.includes(keyLower)) {
          types.numeric = true;
        } else if (typeof value === 'string') {
          types.string = true;
        } else if (typeof value === 'boolean') {
          types.boolean = true;
        } else if (Array.isArray(value)) {
          types.array = true;
        } else if (typeof value === 'object' && value !== null) {
          types.object = true;
        }
      }
    }
  } catch {
    // Try parsing as a plain number
    const num = parseFloat(payloadStr);
    if (!isNaN(num)) {
      types.numeric = true;
    } else {
      // Plain unparseable string
      types.string = true;
    }
  }

  return types;
}

// Check if a payload contains numeric data (wrapper for backward compatibility)
function hasNumericFields(payloadStr: string | null): boolean {
  return analyzePayloadTypes(payloadStr).numeric;
}

// Helper to extract a Neo4j number (handles Integer objects and plain numbers)
function toNumber(val: unknown): number | null {
  if (val === null || val === undefined) return null;
  if (typeof val === 'number') return val;
  if (typeof val === 'object' && val !== null && 'toNumber' in val) {
    return (val as { toNumber: () => number }).toNumber();
  }
  const n = Number(val);
  return isNaN(n) ? null : n;
}

// Build tree structure from flat paths
function buildTree(paths: { path: string; messageCount: number; hasNumericData: boolean; hasVariance: boolean | null; dataTypes: DataTypes }[]): TreeNode[] {
  const root: TreeNode[] = [];
  const nodeMap = new Map<string, TreeNode>();

  // First pass: create all nodes
  for (const { path, messageCount, hasNumericData, hasVariance, dataTypes } of paths) {
    const parts = path.split('/');
    let currentPath = '';

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const parentPath = currentPath;
      currentPath = currentPath ? `${currentPath}/${part}` : part;

      if (!nodeMap.has(currentPath)) {
        const node: TreeNode = {
          name: part,
          fullPath: currentPath,
          children: [],
          isLeaf: i === parts.length - 1,
          messageCount: i === parts.length - 1 ? messageCount : 0,
          hasNumericData: i === parts.length - 1 ? hasNumericData : false,
          hasVariance: i === parts.length - 1 ? hasVariance : undefined,
          dataTypes: i === parts.length - 1 ? dataTypes : undefined,
        };
        nodeMap.set(currentPath, node);

        // Add to parent or root
        if (parentPath) {
          const parent = nodeMap.get(parentPath);
          if (parent) {
            parent.children.push(node);
            parent.isLeaf = false; // Parent is no longer a leaf
          }
        } else {
          root.push(node);
        }
      } else if (i === parts.length - 1) {
        // Update existing node with message count and numeric data flag if it's the actual topic
        const existingNode = nodeMap.get(currentPath);
        if (existingNode) {
          existingNode.messageCount = messageCount;
          existingNode.hasNumericData = hasNumericData;
          existingNode.hasVariance = hasVariance;
          existingNode.dataTypes = dataTypes;
        }
      }
    }
  }

  // Sort children alphabetically at each level
  function sortChildren(nodes: TreeNode[]) {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    for (const node of nodes) {
      if (node.children.length > 0) {
        sortChildren(node.children);
      }
    }
  }

  // Compute totalMessageCount recursively (self + all descendants)
  function computeTotalMessageCount(node: TreeNode): number {
    const childTotal = node.children.reduce(
      (sum, child) => sum + computeTotalMessageCount(child),
      0
    );
    node.totalMessageCount = (node.messageCount ?? 0) + childTotal;
    return node.totalMessageCount;
  }

  // Compute ML-ready status recursively
  // A node is ML-ready if it's a leaf with numeric data and 20+ messages
  // A parent has hasMLReadyDescendant=true if it or any child has ML-ready data
  const MIN_MESSAGES_FOR_ML = 20;
  function computeMLReadyStatus(node: TreeNode): boolean {
    const selfMLReady = node.isLeaf &&
      (node.hasNumericData ?? false) &&
      (node.messageCount ?? 0) >= MIN_MESSAGES_FOR_ML;

    // IMPORTANT: Must process ALL children, not use some() which short-circuits
    // Using reduce to ensure every child's hasMLReadyDescendant gets computed
    const childHasMLReady = node.children.reduce(
      (acc, child) => computeMLReadyStatus(child) || acc,
      false
    );

    node.hasMLReadyDescendant = selfMLReady || childHasMLReady;
    return node.hasMLReadyDescendant;
  }

  sortChildren(root);

  // Compute total message counts after building the tree
  for (const node of root) {
    computeTotalMessageCount(node);
  }

  // Compute ML-ready status for all nodes
  for (const node of root) {
    computeMLReadyStatus(node);
  }

  return root;
}

export async function GET() {
  const session = getSession();

  try {
    const result = await session.run(TREE_QUERY);

    const paths = result.records.map((record) => {
      const messageCount = (record.get('messageCount') as { toNumber?: () => number })?.toNumber?.() ||
                    Number(record.get('messageCount')) || 0;
      const samplePayload = record.get('samplePayload') as string | null;
      const dataTypes = analyzePayloadTypes(samplePayload);
      const hasNumericData = dataTypes.numeric;
      const minValue = toNumber(record.get('minValue'));
      const maxValue = toNumber(record.get('maxValue'));
      const numericSampleCount = toNumber(record.get('numericSampleCount')) ?? 0;

      // Determine variance: true=varying, false=static, null=indeterminate
      let hasVariance: boolean | null = null;
      if (numericSampleCount > 0) {
        hasVariance = minValue !== maxValue;
      }
      // If numericSampleCount === 0 but hasNumericData (JSON payload), leave as null (assume varying)

      return { path: record.get('path') as string, messageCount, hasNumericData, hasVariance, dataTypes };
    });

    const tree = buildTree(paths);

    return NextResponse.json({
      tree,
      totalTopics: paths.length,
    });
  } catch (error) {
    console.error('[Graph Tree API] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch topic tree', details: (error as Error).message },
      { status: 500 }
    );
  } finally {
    await session.close();
  }
}

export const dynamic = 'force-dynamic';
