import { getSession } from '@/lib/neo4j-client';
import { TopicTreeBuilder, SerializableTopicNode, TopicTreeStats } from '@/lib/topic-tree-builder';

interface Neo4jTopicData {
  path: string;
  messageCount: number;
  lastPayload: string | null;
  lastTimestamp: string | null;
  conformantCount: number;
  nonConformantCount: number;
  unboundCount: number;
  boundProposalId: string | null;
  boundProposalName: string | null;
}

/**
 * Build topic tree from Neo4j database
 * Optionally filter by broker name (broker connects to messages via FROM_BROKER)
 */
async function buildTreeFromNeo4j(broker?: string): Promise<{
  tree: SerializableTopicNode;
  stats: TopicTreeStats;
}> {
  const session = getSession();

  try {
    // Query topics with their latest message only (not full history)
    // Filter by broker through the Message->Broker relationship
    // Map broker param: 'uncurated' -> 'ProveITBroker', 'curated' -> 'curated'
    const brokerName = broker === 'uncurated' ? 'ProveITBroker' : broker === 'curated' ? 'curated' : null;

    const query = brokerName ? `
      MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)-[:FROM_BROKER]->(b:Broker {name: $brokerName})
      WITH t, m
      ORDER BY m.timestamp DESC
      WITH t, collect(m)[0] as latestMsg
      OPTIONAL MATCH (tb:TopicBinding {topicPath: t.path})
      OPTIONAL MATCH (sp:SchemaProposal {id: tb.proposalId})
      RETURN t.path as path,
             1 as messageCount,
             latestMsg.rawPayload as lastPayload,
             toString(latestMsg.timestamp) as lastTimestamp,
             CASE WHEN latestMsg.conformanceStatus = 'conformant' THEN 1 ELSE 0 END as conformantCount,
             CASE WHEN latestMsg.conformanceStatus = 'non_conformant' THEN 1 ELSE 0 END as nonConformantCount,
             CASE WHEN latestMsg.conformanceStatus = 'no_binding' OR latestMsg.conformanceStatus IS NULL THEN 1 ELSE 0 END as unboundCount,
             tb.proposalId as boundProposalId,
             sp.name as boundProposalName
      ORDER BY t.path
    ` : `
      MATCH (t:Topic)
      OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
      WITH t, m
      ORDER BY m.timestamp DESC
      WITH t, collect(m)[0] as latestMsg
      OPTIONAL MATCH (tb:TopicBinding {topicPath: t.path})
      OPTIONAL MATCH (sp:SchemaProposal {id: tb.proposalId})
      RETURN t.path as path,
             1 as messageCount,
             latestMsg.rawPayload as lastPayload,
             toString(latestMsg.timestamp) as lastTimestamp,
             CASE WHEN latestMsg.conformanceStatus = 'conformant' THEN 1 ELSE 0 END as conformantCount,
             CASE WHEN latestMsg.conformanceStatus = 'non_conformant' THEN 1 ELSE 0 END as nonConformantCount,
             CASE WHEN latestMsg.conformanceStatus = 'no_binding' OR latestMsg.conformanceStatus IS NULL THEN 1 ELSE 0 END as unboundCount,
             tb.proposalId as boundProposalId,
             sp.name as boundProposalName
      ORDER BY t.path
    `;

    const result = await session.run(query, brokerName ? { brokerName } : {});

    // Get actual total message count with a separate query
    const countQuery = brokerName
      ? `MATCH (m:Message)-[:FROM_BROKER]->(b:Broker {name: $brokerName}) RETURN count(m) as totalMessages`
      : `MATCH (m:Message) RETURN count(m) as totalMessages`;
    const countResult = await session.run(countQuery, brokerName ? { brokerName } : {});
    const totalMessageCount = (countResult.records[0]?.get('totalMessages') as { low: number })?.low || 0;

    const treeBuilder = new TopicTreeBuilder();

    for (const record of result.records) {
      const path = record.get('path') as string;
      const messageCount = (record.get('messageCount') as { low: number })?.low || 0;
      const lastPayload = record.get('lastPayload') as string | null;
      const lastTimestamp = record.get('lastTimestamp') as string | null;
      const conformantCount = (record.get('conformantCount') as { low: number })?.low || 0;
      const nonConformantCount = (record.get('nonConformantCount') as { low: number })?.low || 0;
      const unboundCount = (record.get('unboundCount') as { low: number })?.low || 0;
      const boundProposalId = record.get('boundProposalId') as string | null;
      const boundProposalName = record.get('boundProposalName') as string | null;

      // Add each message count to properly accumulate in the tree
      // We add empty messages first, then add the one with payload last so it becomes lastMessage
      if (messageCount > 0) {
        const timestamp = lastTimestamp ? new Date(lastTimestamp).getTime() : Date.now();

        // Add remaining message counts first (without payload data)
        for (let i = 1; i < messageCount; i++) {
          treeBuilder.addMessage(path, '', timestamp);
        }

        // Add the message with actual payload last so it becomes the lastMessage
        treeBuilder.addMessage(path, lastPayload || '', timestamp);
      }

      // Update the leaf node with conformance data
      const node = treeBuilder.findNode(path);
      if (node) {
        node.conformantCount = conformantCount;
        node.nonConformantCount = nonConformantCount;
        node.unboundCount = unboundCount;
        node.boundProposalId = boundProposalId || undefined;
        node.boundProposalName = boundProposalName || undefined;
      }
    }

    // Override totalMessages with actual count from database
    const stats = treeBuilder.getStats();
    stats.totalMessages = totalMessageCount;

    return {
      tree: treeBuilder.getSerializableTree(),
      stats,
    };
  } finally {
    await session.close();
  }
}

// Cache for tree data to avoid hammering Neo4j (per broker)
const treeCache: Map<string, {
  tree: SerializableTopicNode;
  stats: TopicTreeStats;
  timestamp: number;
}> = new Map();

const CACHE_TTL_MS = 5000; // Refresh every 5 seconds

async function getCachedTree(broker?: string): Promise<{
  tree: SerializableTopicNode;
  stats: TopicTreeStats;
}> {
  const now = Date.now();
  const cacheKey = broker || 'all';
  const cached = treeCache.get(cacheKey);

  if (cached && (now - cached.timestamp) < CACHE_TTL_MS) {
    return { tree: cached.tree, stats: cached.stats };
  }

  try {
    const data = await buildTreeFromNeo4j(broker);
    treeCache.set(cacheKey, {
      ...data,
      timestamp: now,
    });
    return data;
  } catch (error) {
    console.error(`[Neo4j] Error building tree:`, error);
    // Return cached data if available, even if stale
    if (cached) {
      return { tree: cached.tree, stats: cached.stats };
    }
    throw error;
  }
}

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  // Parse broker parameter from URL
  const url = new URL(request.url);
  const broker = url.searchParams.get('broker') || undefined;

  const stream = new ReadableStream({
    async start(controller) {
      let isRunning = true;

      // Handle client disconnect
      request.signal.addEventListener('abort', () => {
        console.log(`[SSE] Client disconnected from topic tree (broker: ${broker || 'all'})`);
        isRunning = false;
        controller.close();
      });

      const sendTree = async () => {
        try {
          const { tree, stats } = await getCachedTree(broker);
          const data = JSON.stringify({ tree, stats });
          controller.enqueue(encoder.encode(`event: tree\ndata: ${data}\n\n`));
        } catch (error) {
          console.error('[SSE] Error fetching tree:', error);
          const errorMessage = error instanceof Error ? error.message : 'Unknown error';
          controller.enqueue(
            encoder.encode(`event: error\ndata: ${JSON.stringify({ error: errorMessage })}\n\n`)
          );
        }
      };

      const sendConnectionStatus = (connected: boolean) => {
        const data = JSON.stringify({ connected });
        controller.enqueue(encoder.encode(`event: connection\ndata: ${data}\n\n`));
      };

      try {
        // Send initial connection status (always connected since we're reading from DB)
        sendConnectionStatus(true);

        // Send initial tree immediately
        await sendTree();

        // Send tree updates periodically
        while (isRunning) {
          await new Promise(resolve => setTimeout(resolve, 5000));
          if (isRunning) {
            await sendTree();
          }
        }
      } catch (error) {
        console.error('[SSE] Error in stream:', error);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        controller.enqueue(
          encoder.encode(`event: error\ndata: ${JSON.stringify({ error: errorMessage })}\n\n`)
        );
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}

export const dynamic = 'force-dynamic';
