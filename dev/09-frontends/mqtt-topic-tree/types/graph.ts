// Graph visualization types for Neo4j NVL integration

export type NodeType = 'topic' | 'message' | 'schemaMapping' | 'similar_topic' | 'curated_topic' | 'parent_segment';

export interface NvlNode {
  id: string;
  caption: string;
  color: string;
  size: number;
  pinned?: boolean;
  // Custom properties
  nodeType?: NodeType;
  path?: string;
  broker?: string;
  clientId?: string;
  rawPayload?: string;
  payloadText?: string;
  timestamp?: string;
  mappingId?: string;
  mappingStatus?: string;
  confidence?: number;
  similarityScore?: number;
}

export interface NvlRelationship {
  id: string;
  from: string;
  to: string;
  caption: string;
  color?: string;
  width?: number;
}

export interface GraphData {
  nodes: NvlNode[];
  relationships: NvlRelationship[];
}

// Neo4j query result types
export interface Neo4jTopicNode {
  id: string;
  path: string;
  broker: string;
  clientId?: string;
  createdAt?: string;
}

export interface Neo4jMessageNode {
  id: string;
  rawPayload: string;
  payloadText: string;
  timestamp: string;
  relId: string;
}

export interface Neo4jRoutingNode {
  id: string;
  path: string;
  broker: string;
  relId: string;
  mappingId?: string;
  mappingStatus?: string;
  confidence?: number;
}

export interface Neo4jSimilarTopic {
  node: {
    id: string;
    path: string;
    broker: string;
  };
  score: number;
}

export interface Neo4jParentSegment {
  id: string;
  name: string;
  fullPath: string;
  relId: string;
}

export interface GraphApiResponse {
  topic: Neo4jTopicNode;
  messages: Neo4jMessageNode[];
  routings: Neo4jRoutingNode[];
  similarTopics: Neo4jSimilarTopic[];
  parents?: Neo4jParentSegment[];
}

// 3D Force Graph visualization metrics (for manual controls debugging)
export interface GraphMetrics {
  // Dimensions
  windowDimensions: { width: number; height: number; aspectRatio: string };
  containerDimensions: { width: number; height: number; aspectRatio: string };
  canvasDimensions: { width: number; height: number; aspectRatio: string };

  // Positions
  cameraPosition: { x: number; y: number; z: number };
  controlsTarget: { x: number; y: number; z: number };
  distance: number;

  // Graph data
  graphCenter: { x: number; y: number; z: number };
  nodeCount: number;

  // Diagnostics
  sizeMismatch?: {
    canvasWidth: number;
    containerWidth: number;
    horizontalOffset: number;
  };
}
