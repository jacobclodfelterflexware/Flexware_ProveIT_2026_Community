import { ConformanceStatus, deriveConformanceStatus } from '@/types/conformance';

export interface TopicNode {
  name: string;
  fullPath: string;
  children: Map<string, TopicNode>;
  messageCount: number;
  lastMessage?: {
    payload: string;
    timestamp: number;
  };
  isLeaf: boolean;
  // Conformance properties
  conformanceStatus?: ConformanceStatus;
  conformantCount: number;
  nonConformantCount: number;
  unboundCount: number;
  boundProposalId?: string;
  boundProposalName?: string;
}

export interface TopicTreeStats {
  totalTopics: number;
  totalMessages: number;
  lastUpdate: number;
}

export class TopicTreeBuilder {
  private root: TopicNode;
  private stats: TopicTreeStats;

  constructor() {
    this.root = {
      name: 'root',
      fullPath: '',
      children: new Map(),
      messageCount: 0,
      isLeaf: false,
      conformantCount: 0,
      nonConformantCount: 0,
      unboundCount: 0,
    };
    this.stats = {
      totalTopics: 0,
      totalMessages: 0,
      lastUpdate: Date.now(),
    };
  }

  addMessage(topic: string, payload: string, timestamp: number): void {
    const parts = topic.split('/').filter(part => part.length > 0);

    if (parts.length === 0) {
      return;
    }

    let currentNode = this.root;
    let currentPath = '';

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      currentPath = currentPath ? `${currentPath}/${part}` : part;

      if (!currentNode.children.has(part)) {
        const newNode: TopicNode = {
          name: part,
          fullPath: currentPath,
          children: new Map(),
          messageCount: 0,
          isLeaf: i === parts.length - 1,
          conformantCount: 0,
          nonConformantCount: 0,
          unboundCount: 0,
        };
        currentNode.children.set(part, newNode);
        this.stats.totalTopics++;
      }

      currentNode = currentNode.children.get(part)!;
      currentNode.messageCount++;

      // Update leaf node with message data
      if (i === parts.length - 1) {
        currentNode.isLeaf = true;
        currentNode.lastMessage = {
          payload: payload, // Don't truncate - show full payload
          timestamp,
        };
      }
    }

    this.stats.totalMessages++;
    this.stats.lastUpdate = timestamp;
  }

  private truncatePayload(payload: string, maxLength: number = 200): string {
    if (payload.length <= maxLength) {
      return payload;
    }
    return payload.substring(0, maxLength) + '...';
  }

  getTree(): TopicNode {
    return this.root;
  }

  getStats(): TopicTreeStats {
    return { ...this.stats };
  }

  getSerializableTree(): SerializableTopicNode {
    return this.nodeToSerializable(this.root);
  }

  private nodeToSerializable(node: TopicNode): SerializableTopicNode {
    // Process children first to aggregate conformance stats
    const children = Array.from(node.children.values()).map(child =>
      this.nodeToSerializable(child)
    );

    // For non-leaf nodes, aggregate conformance counts from children
    let conformantCount = node.conformantCount;
    let nonConformantCount = node.nonConformantCount;
    let unboundCount = node.unboundCount;

    if (!node.isLeaf && children.length > 0) {
      conformantCount = children.reduce((sum, c) => sum + c.conformantCount, 0);
      nonConformantCount = children.reduce((sum, c) => sum + c.nonConformantCount, 0);
      unboundCount = children.reduce((sum, c) => sum + c.unboundCount, 0);
    }

    // Derive conformance status
    const conformanceStatus = deriveConformanceStatus({
      conformantCount,
      nonConformantCount,
      unboundCount
    });

    return {
      name: node.name,
      fullPath: node.fullPath,
      children,
      messageCount: node.messageCount,
      lastMessage: node.lastMessage,
      isLeaf: node.isLeaf,
      conformanceStatus,
      conformantCount,
      nonConformantCount,
      unboundCount,
      boundProposalId: node.boundProposalId,
      boundProposalName: node.boundProposalName,
    };
  }

  clear(): void {
    this.root = {
      name: 'root',
      fullPath: '',
      children: new Map(),
      messageCount: 0,
      isLeaf: false,
      conformantCount: 0,
      nonConformantCount: 0,
      unboundCount: 0,
    };
    this.stats = {
      totalTopics: 0,
      totalMessages: 0,
      lastUpdate: Date.now(),
    };
  }

  findNode(topicPath: string): TopicNode | null {
    const parts = topicPath.split('/').filter(part => part.length > 0);
    let currentNode = this.root;

    for (const part of parts) {
      const child = currentNode.children.get(part);
      if (!child) {
        return null;
      }
      currentNode = child;
    }

    return currentNode;
  }

  getTopicCount(): number {
    return this.stats.totalTopics;
  }

  getMessageCount(): number {
    return this.stats.totalMessages;
  }
}

export interface SerializableTopicNode {
  name: string;
  fullPath: string;
  children: SerializableTopicNode[];
  messageCount: number;
  lastMessage?: {
    payload: string;
    timestamp: number;
  };
  isLeaf: boolean;
  // Conformance properties
  conformanceStatus?: ConformanceStatus;
  conformantCount: number;
  nonConformantCount: number;
  unboundCount: number;
  boundProposalId?: string;
  boundProposalName?: string;
}
