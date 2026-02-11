"""Writes curated Topic/Message nodes and lineage relationships to Neo4j."""
import asyncio
import logging
import uuid
from datetime import datetime

from neo4j import AsyncGraphDatabase

from config import config

logger = logging.getLogger(__name__)


class Neo4jWriter:
    """Writes curated Topic/Message nodes and lineage relationships."""

    def __init__(self):
        self._driver = None

        # Stats
        self.topics_written = 0
        self.messages_written = 0
        self.lineage_created = 0
        self.errors = 0

    async def start(self) -> None:
        """Initialize Neo4j connection."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        logger.info("Neo4j writer started")

    async def stop(self) -> None:
        """Close connection."""
        if self._driver:
            await self._driver.close()
        logger.info("Neo4j writer stopped")

    async def write_curated_message(
        self,
        curated_topic: str,
        normalized_payload: str,
        mapping_id: str,
        raw_message_id: str | None = None
    ) -> str | None:
        """
        Write curated Topic/Message to Neo4j and create lineage.

        Args:
            curated_topic: The curated topic path
            normalized_payload: Transformed JSON payload string
            mapping_id: The SchemaMapping ID used
            raw_message_id: Optional ID of the raw message for lineage

        Returns:
            The curated message ID, or None on failure
        """
        if not config.write_to_neo4j:
            return None

        try:
            curated_message_id = f"{datetime.utcnow().isoformat()}-{uuid.uuid4().hex[:8]}"

            async with self._driver.session() as session:
                # Upsert curated Topic
                await session.run("""
                    MERGE (t:Topic {path: $path, broker: "curated"})
                    ON CREATE SET
                      t.createdAt = datetime()
                    ON MATCH SET
                      t.updatedAt = datetime()
                """,
                    path=curated_topic
                )
                self.topics_written += 1

                # Create curated Message
                await session.run("""
                    MATCH (t:Topic {path: $topicPath, broker: "curated"})
                    CREATE (m:Message {
                      messageId: $messageId,
                      rawPayload: $rawPayload,
                      timestamp: datetime(),
                      broker: "curated"
                    })
                    MERGE (t)-[:HAS_MESSAGE]->(m)
                """,
                    topicPath=curated_topic,
                    messageId=curated_message_id,
                    rawPayload=normalized_payload
                )
                self.messages_written += 1

                # Create lineage relationship if raw message ID provided
                if config.create_lineage and raw_message_id:
                    result = await session.run("""
                        MATCH (rm:Message {messageId: $rawMessageId, broker: "uncurated"})
                        MATCH (cm:Message {messageId: $curatedMessageId, broker: "curated"})
                        MERGE (rm)-[r:NORMALIZED_AS]->(cm)
                        SET r.mappingId = $mappingId,
                            r.transformedAt = datetime()
                        RETURN r
                    """,
                        rawMessageId=raw_message_id,
                        curatedMessageId=curated_message_id,
                        mappingId=mapping_id
                    )
                    record = await result.single()
                    if record:
                        self.lineage_created += 1

            return curated_message_id

        except Exception as e:
            logger.error(f"Neo4j write error: {e}")
            self.errors += 1
            return None

    def get_stats(self) -> dict:
        """Get writer statistics."""
        return {
            "topics_written": self.topics_written,
            "messages_written": self.messages_written,
            "lineage_created": self.lineage_created,
            "errors": self.errors
        }
