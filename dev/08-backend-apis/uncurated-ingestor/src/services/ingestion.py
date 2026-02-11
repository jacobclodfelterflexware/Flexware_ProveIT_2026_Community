import asyncio
import json
import logging
from typing import List, Tuple, Optional, Any, Dict
from datetime import datetime
import uuid

from neo4j import AsyncGraphDatabase

from config import config

# Import from shared libraries
from embedding import make_embedding_text, embed_batch
from conformance import ConformanceChecker
from conformance.binding_cache import BindingCache

logger = logging.getLogger(__name__)


class IngestionService:
    """Handles message ingestion into Neo4j with embeddings and conformance checking."""

    def __init__(self):
        self._driver = None
        # Use asyncio.Queue to decouple message receipt from processing
        # Buffer ~10 seconds of data; excess will be dropped (aliased) at the broker
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._worker_task: asyncio.Task | None = None
        self._is_running = False

        # Conformance checking
        self._conformance_checker = ConformanceChecker()
        self._binding_cache: Optional[BindingCache] = None

        # Stats
        self.topics_upserted = 0
        self.messages_created = 0
        self.errors = 0
        self.conformant_count = 0
        self.non_conformant_count = 0
        self.unbound_count = 0
        self.queue_high_water = 0

    async def start(self) -> None:
        """Initialize the service."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        self._is_running = True
        # Start worker task that consumes from queue and processes batches
        self._worker_task = asyncio.create_task(self._batch_worker())

        # Start binding cache for conformance checking
        if config.conformance_enabled:
            self._binding_cache = BindingCache(
                refresh_interval_seconds=config.binding_cache_refresh_seconds
            )
            await self._binding_cache.start(self._driver)
            logger.info(
                f"Conformance checking enabled with {config.binding_cache_refresh_seconds}s cache refresh"
            )
        else:
            logger.info("Conformance checking disabled")

        logger.info("Ingestion service started")

    async def stop(self) -> None:
        """Shutdown the service."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Stop binding cache
        if self._binding_cache:
            await self._binding_cache.stop()

        # Process any remaining items in queue
        remaining = []
        while not self._queue.empty():
            try:
                remaining.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if remaining:
            logger.info(f"Processing {len(remaining)} remaining messages...")
            try:
                await self._process_batch(remaining)
            except Exception as e:
                logger.error(f"Error processing remaining batch: {e}")

        if self._driver:
            await self._driver.close()
        logger.info("Ingestion service stopped")

    async def ingest(self, topic: str, payload: bytes, client_id: str = "unknown") -> None:
        """
        Add a message to the ingestion queue (non-blocking).

        Messages are queued immediately and processed in batches by the worker.

        Args:
            topic: The MQTT topic path
            payload: Raw message payload bytes
            client_id: Publisher client ID from MQTT 5.0 user properties
        """
        # Always derive ClientId from topic path's first segment (enterprise level)
        first_segment = topic.split("/")[0] if "/" in topic else topic
        enterprise_name = first_segment.replace(" ", "")
        effective_client_id = f"ProveIT_Broker_{enterprise_name}"

        # Put into queue - this is fast and non-blocking (until queue is full)
        try:
            self._queue.put_nowait((topic, payload, effective_client_id, datetime.utcnow()))
            # Track high water mark
            qsize = self._queue.qsize()
            if qsize > self.queue_high_water:
                self.queue_high_water = qsize
        except asyncio.QueueFull:
            logger.warning("Ingestion queue full, dropping message")
            self.errors += 1

    async def _batch_worker(self) -> None:
        """Worker that consumes from queue and processes in batches."""
        while self._is_running:
            batch = []
            try:
                # Wait for at least one message
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=config.batch_timeout_ms / 1000.0
                )
                batch.append(item)

                # Collect more messages up to batch_size (non-blocking)
                while len(batch) < config.batch_size:
                    try:
                        item = self._queue.get_nowait()
                        batch.append(item)
                    except asyncio.QueueEmpty:
                        break

            except asyncio.TimeoutError:
                # No messages received within timeout, continue loop
                continue
            except asyncio.CancelledError:
                break

            # Process the batch
            if batch:
                try:
                    await self._process_batch(batch)
                except Exception as e:
                    logger.error(f"Batch processing error: {e}")
                    self.errors += len(batch)

    async def _process_batch(
        self,
        batch: List[Tuple[str, bytes, str, datetime]]
    ) -> None:
        """Process a batch of messages using batched Neo4j writes."""
        # Canonicalize all messages
        canonical_data = []
        for topic, payload, client_id, timestamp in batch:
            try:
                canonical = make_embedding_text(topic, payload)
                canonical_data.append({
                    "topic": topic,
                    "payload": payload,
                    "client_id": client_id,
                    "timestamp": timestamp,
                    "canonical": canonical
                })
            except Exception as e:
                logger.warning(f"Canonicalization error for {topic}: {e}")

        if not canonical_data:
            return

        # Generate embeddings in batch
        topic_texts = [d["canonical"].topic_text for d in canonical_data]
        combined_texts = [d["canonical"].combined_text for d in canonical_data]

        topic_embeddings = embed_batch(topic_texts)
        payload_embeddings = embed_batch(combined_texts)

        # Prepare batch data for Neo4j
        messages_data = []
        all_topic_paths = set()
        all_topic_hierarchy_data = []

        for i, data in enumerate(canonical_data):
            message_id = f"{data['timestamp'].isoformat()}-{uuid.uuid4().hex[:8]}"

            # Check conformance
            conformance_status, conformance_errors, bound_proposal_id = self._check_conformance(
                data["topic"], data["payload"]
            )

            # Update conformance stats
            if conformance_status == "conformant":
                self.conformant_count += 1
            elif conformance_status == "non_conformant":
                self.non_conformant_count += 1
            else:
                self.unbound_count += 1

            messages_data.append({
                "messageId": message_id,
                "topicPath": data["topic"],
                "clientId": data["client_id"],
                "rawPayload": data["payload"].decode("utf-8", errors="replace"),
                "payloadText": data["canonical"].payload_text,
                "embedding": payload_embeddings[i],
                "numericValue": data["canonical"].numeric_value,
                "timestamp": data["timestamp"].isoformat(),
                "conformanceStatus": conformance_status,
                "conformanceErrors": json.dumps(conformance_errors) if conformance_errors else None,
                "boundProposalId": bound_proposal_id
            })

            # Collect unique topic paths for hierarchy creation
            topic_path = data["topic"]
            if topic_path not in all_topic_paths:
                all_topic_paths.add(topic_path)
                segments = topic_path.split('/')
                for j in range(len(segments)):
                    path = '/'.join(segments[:j+1])
                    name = segments[j]
                    depth = j
                    all_topic_hierarchy_data.append({
                        'path': path,
                        'name': name,
                        'depth': depth,
                        'embedding': topic_embeddings[i] if j == len(segments) - 1 else None
                    })

        # Deduplicate topic hierarchy data (keep first occurrence)
        seen_paths = set()
        unique_hierarchy_data = []
        for item in all_topic_hierarchy_data:
            if item['path'] not in seen_paths:
                seen_paths.add(item['path'])
                unique_hierarchy_data.append(item)

        # Build parent-child pairs for all topics
        parent_child_pairs = []
        for topic_path in all_topic_paths:
            segments = topic_path.split('/')
            for j in range(1, len(segments)):
                parent_path = '/'.join(segments[:j])
                child_path = '/'.join(segments[:j+1])
                pair = {'parentPath': parent_path, 'childPath': child_path}
                if pair not in parent_child_pairs:
                    parent_child_pairs.append(pair)

        # Write to Neo4j using separate batched queries
        unique_client_ids = list(set(m["clientId"] for m in messages_data))

        async with self._driver.session() as session:
            try:
                # Query 1: Ensure Broker and ClientIds exist
                await session.run(
                    """
                    MERGE (b:Broker {name: $brokerName})
                    WITH b
                    UNWIND $clientIds AS cid
                    MERGE (c:ClientId {id: cid})
                    """,
                    brokerName=config.broker_name,
                    clientIds=unique_client_ids
                )

                # Query 2: Create/update Topic hierarchy nodes
                await session.run(
                    """
                    UNWIND $paths AS p
                    MERGE (t:Topic {path: p.path})
                    ON CREATE SET
                        t.name = p.name,
                        t.depth = p.depth,
                        t.text = p.path,
                        t.embedding = p.embedding,
                        t.createdAt = datetime()
                    ON MATCH SET
                        t.updatedAt = datetime(),
                        t.embedding = CASE WHEN t.embedding IS NULL AND p.embedding IS NOT NULL THEN p.embedding ELSE t.embedding END
                    """,
                    paths=unique_hierarchy_data
                )

                # Query 3: Create parent-child relationships
                if parent_child_pairs:
                    await session.run(
                        """
                        UNWIND $pairs AS pair
                        MATCH (child:Topic {path: pair.childPath})
                        MATCH (parent:Topic {path: pair.parentPath})
                        MERGE (child)-[:CHILD_OF]->(parent)
                        """,
                        pairs=parent_child_pairs
                    )

                # Query 4: Create messages with all relationships
                await session.run(
                    """
                    UNWIND $messages AS msg
                    MATCH (t:Topic {path: msg.topicPath})
                    MATCH (b:Broker {name: $brokerName})
                    MATCH (c:ClientId {id: msg.clientId})
                    CREATE (m:Message {
                        messageId: msg.messageId,
                        rawPayload: msg.rawPayload,
                        payloadText: msg.payloadText,
                        embedding: msg.embedding,
                        numericValue: msg.numericValue,
                        timestamp: datetime(msg.timestamp),
                        conformanceStatus: msg.conformanceStatus,
                        conformanceErrors: msg.conformanceErrors,
                        boundProposalId: msg.boundProposalId
                    })
                    MERGE (t)-[:HAS_MESSAGE]->(m)
                    MERGE (m)-[:FROM_BROKER]->(b)
                    MERGE (m)-[:PUBLISHED_BY]->(c)
                    """,
                    brokerName=config.broker_name,
                    messages=messages_data
                )

                self.messages_created += len(messages_data)
                self.topics_upserted += len(all_topic_paths)

            except Exception as e:
                logger.error(f"Batch Neo4j write error: {e}")
                self.errors += len(messages_data)

    def _check_conformance(
        self,
        topic_path: str,
        payload: bytes
    ) -> Tuple[str, List[str], Optional[str]]:
        """
        Check message conformance against bound schema.

        Args:
            topic_path: The topic path to check
            payload: Raw payload bytes

        Returns:
            Tuple of (status, errors, proposal_id)
            - status: "conformant", "non_conformant", or "no_binding"
            - errors: List of error messages (empty if conformant or no binding)
            - proposal_id: ID of the proposal checked against (None if no binding)
        """
        # If conformance checking is disabled or no cache, skip
        if not self._binding_cache:
            return ("no_binding", [], None)

        # Get binding for this topic
        binding = self._binding_cache.get_binding(topic_path)

        if binding is None:
            return ("no_binding", [], None)

        try:
            # Parse payload
            payload_dict, parse_error = self._conformance_checker.parse_payload(payload)

            if parse_error:
                return ("non_conformant", [parse_error], binding["proposalId"])

            # Check conformance
            is_conformant, errors = self._conformance_checker.check_conformance(
                payload_dict, binding["expectedSchema"]
            )

            status = "conformant" if is_conformant else "non_conformant"
            return (status, errors, binding["proposalId"])

        except Exception as e:
            logger.warning(f"Conformance check error for {topic_path}: {e}")
            return ("non_conformant", [f"Validation error: {str(e)}"], binding["proposalId"])

    def get_stats(self) -> dict:
        """Get service statistics."""
        stats = {
            "topics_upserted": self.topics_upserted,
            "messages_created": self.messages_created,
            "errors": self.errors,
            "queue_size": self._queue.qsize(),
            "queue_high_water": self.queue_high_water,
            "conformance": {
                "enabled": config.conformance_enabled,
                "conformant": self.conformant_count,
                "non_conformant": self.non_conformant_count,
                "unbound": self.unbound_count
            }
        }

        # Add binding cache stats if available
        if self._binding_cache:
            stats["conformance"]["bindings_cached"] = self._binding_cache.get_binding_count()

        return stats
