// Transform Neo4j query results to NVL visualization format
import type {
  GraphData,
  NvlNode,
  NvlRelationship,
  GraphApiResponse,
} from '@/types/graph';

// Node type colors (dark theme compatible)
export const NODE_COLORS = {
  topic_uncurated: '#3b82f6', // Blue for uncurated topics
  topic_curated: '#22c55e',   // Green for curated topics
  message: '#f59e0b',         // Amber for messages
  schemaMapping: '#a855f7',   // Purple for schema mappings
  similar: '#ec4899',         // Pink for similar topics
  parent: '#6366f1',          // Indigo for parent segments
};

// Node sizes
const NODE_SIZES = {
  center: 40,       // Selected topic (larger)
  topic: 30,        // Other topics
  message: 20,      // Messages (smaller)
  schemaMapping: 25,
  parent: 25,       // Parent segments
};

/**
 * Extract the last segment of a topic path for display
 */
function extractTopicName(path: string): string {
  const parts = path.split('/');
  return parts[parts.length - 1] || path;
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

/**
 * Transform Neo4j API response to NVL-compatible graph format
 */
export function transformToNvlFormat(apiResponse: GraphApiResponse): GraphData {
  const nodes: NvlNode[] = [];
  const relationships: NvlRelationship[] = [];

  const { topic, messages, routings, similarTopics, parents } = apiResponse;

  // 1. Center topic node (selected)
  nodes.push({
    id: topic.id,
    caption: extractTopicName(topic.path),
    color: NODE_COLORS.topic_uncurated,
    size: NODE_SIZES.center,
    pinned: true, // Keep center node fixed
    nodeType: 'topic',
    path: topic.path,
  });

  // 2. Parent segment nodes (topic hierarchy)
  if (parents && parents.length > 0) {
    // Sort parents by path depth (shortest first = root)
    const sortedParents = [...parents].sort((a, b) =>
      (a.fullPath?.split('/').length || 0) - (b.fullPath?.split('/').length || 0)
    );

    // Create parent nodes and chain them together
    let prevNodeId = topic.id;
    for (const parent of sortedParents.reverse()) { // Start from immediate parent
      if (parent.id) {
        nodes.push({
          id: parent.id,
          caption: parent.name,
          color: NODE_COLORS.parent,
          size: NODE_SIZES.parent,
          nodeType: 'parent_segment',
          path: parent.fullPath,
        });

        relationships.push({
          id: `child-${prevNodeId}-${parent.id}`,
          from: prevNodeId,
          to: parent.id,
          caption: 'CHILD_OF',
          color: NODE_COLORS.parent,
          width: 2,
        });

        prevNodeId = parent.id;
      }
    }
  }

  // 2. Message nodes
  if (messages && messages.length > 0) {
    for (const msg of messages) {
      nodes.push({
        id: msg.id,
        caption: `Msg ${formatTimestamp(msg.timestamp)}`,
        color: NODE_COLORS.message,
        size: NODE_SIZES.message,
        nodeType: 'message',
        rawPayload: msg.rawPayload,
        payloadText: msg.payloadText,
        timestamp: msg.timestamp,
      });

      relationships.push({
        id: msg.relId,
        from: topic.id,
        to: msg.id,
        caption: 'HAS_MESSAGE',
        color: NODE_COLORS.message,
        width: 1,
      });
    }
  }

  // 3. Curated topic nodes (via ROUTES_TO)
  if (routings && routings.length > 0) {
    for (const routing of routings) {
      if (routing.id) {
        nodes.push({
          id: routing.id,
          caption: extractTopicName(routing.path),
          color: NODE_COLORS.topic_curated,
          size: NODE_SIZES.topic,
          nodeType: 'curated_topic',
          path: routing.path,
          broker: routing.broker,
          mappingId: routing.mappingId,
          mappingStatus: routing.mappingStatus,
          confidence: routing.confidence,
        });

        relationships.push({
          id: routing.relId,
          from: topic.id,
          to: routing.id,
          caption: 'ROUTES_TO',
          color: NODE_COLORS.schemaMapping,
          // Style based on mapping status
          width: routing.mappingStatus === 'approved' ? 3 : 1,
        });
      }
    }
  }

  // 4. Similar topics (from vector search)
  if (similarTopics && similarTopics.length > 0) {
    for (const similar of similarTopics) {
      const similarNode = similar.node;
      const score = similar.score;

      // Skip if this is the center topic
      if (similarNode.id === topic.id) continue;

      nodes.push({
        id: similarNode.id,
        caption: extractTopicName(similarNode.path),
        color: NODE_COLORS.similar,
        size: NODE_SIZES.topic,
        nodeType: 'similar_topic',
        path: similarNode.path,
        broker: similarNode.broker,
        similarityScore: score,
      });

      relationships.push({
        id: `sim-${topic.id}-${similarNode.id}`,
        from: topic.id,
        to: similarNode.id,
        caption: `${Math.round(score * 100)}%`,
        color: NODE_COLORS.similar,
        width: 1,
      });
    }
  }

  return { nodes, relationships };
}
