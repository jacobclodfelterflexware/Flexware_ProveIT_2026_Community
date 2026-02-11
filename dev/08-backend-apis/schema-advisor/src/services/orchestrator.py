"""Schema suggestion orchestration - the main workflow logic."""
import json
import uuid
import logging
from typing import Any

from neo4j import AsyncGraphDatabase

from config import config
from services.mcp_client import MCPClient
from services.llm_client import LLMClient
from prompts.schema_suggestion import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class SchemaOrchestrator:
    """Orchestrates schema suggestion workflow."""

    def __init__(self):
        self.mcp = MCPClient()
        self.llm = LLMClient()
        self._driver = None

    async def start(self):
        """Initialize Neo4j connection."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        logger.info("SchemaOrchestrator initialized")

    async def stop(self):
        """Close connections."""
        if self._driver:
            await self._driver.close()

    async def suggest_schema(
        self,
        raw_topic: str,
        raw_payload: str,
        created_by: str = "schema-advisor",
        preview_only: bool = False
    ) -> dict[str, Any]:
        """
        Main entry point: suggest a schema mapping for a raw topic.

        Args:
            raw_topic: The raw MQTT topic path
            raw_payload: The raw JSON payload
            created_by: User/system that initiated the request
            preview_only: If True, return suggestion without storing in Neo4j

        Returns:
            {
                "success": bool,
                "mapping_id": str (if successful and not preview_only),
                "suggestion": dict (LLM output),
                "similar_topics": list (if preview_only),
                "similar_messages": list (if preview_only),
                "error": str (if failed)
            }
        """
        logger.info(f"Processing schema suggestion for: {raw_topic} (preview={preview_only})")

        # 1. Check if mapping already exists (skip for preview mode)
        if not preview_only:
            existing = await self.mcp.get_mapping_status(raw_topic)
            if existing:
                return {
                    "success": False,
                    "error": "Mapping already exists",
                    "existing_mapping": existing
                }

        # 2. Gather context from MCP tools
        # For preview mode, search uncurated data; otherwise search all
        broker_filter = "uncurated" if preview_only else "all"

        similar_topics = await self.mcp.similar_topics(
            topic=raw_topic,
            k=config.similar_topics_k,
            broker_filter=broker_filter
        )

        similar_messages = await self.mcp.similar_messages(
            topic=raw_topic,
            payload=raw_payload,
            k=config.similar_messages_k,
            broker_filter=broker_filter
        )

        curated_tree = await self.mcp.get_topic_tree(
            broker="curated",
            root_path=self._extract_root(raw_topic)
        )

        # 3. Build LLM prompt
        user_prompt = build_user_prompt(
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            similar_topics=similar_topics,
            similar_messages=similar_messages,
            curated_tree=curated_tree
        )

        # 4. Call LLM
        suggestion = await self.llm.suggest_schema(SYSTEM_PROMPT, user_prompt)

        if not suggestion:
            return {
                "success": False,
                "error": "LLM failed to generate suggestion"
            }

        # 5. Validate suggestion
        if not self._validate_suggestion(suggestion):
            return {
                "success": False,
                "error": "Invalid LLM response format",
                "raw_suggestion": suggestion
            }

        # 6. For preview mode, return suggestion with context but don't store
        if preview_only:
            logger.info(f"Preview suggestion generated for {raw_topic}")
            return {
                "success": True,
                "suggestion": suggestion,
                "similar_topics": similar_topics,
                "similar_messages": similar_messages,
                "raw_topic": raw_topic
            }

        # 7. Create SchemaMapping in Neo4j
        mapping_id = await self._create_proposal(
            raw_topic=raw_topic,
            suggestion=suggestion,
            created_by=created_by
        )

        if not mapping_id:
            return {
                "success": False,
                "error": "Failed to create mapping in Neo4j"
            }

        logger.info(f"Created proposal {mapping_id} for {raw_topic}")

        return {
            "success": True,
            "mapping_id": mapping_id,
            "suggestion": suggestion,
            "raw_topic": raw_topic
        }

    def _extract_root(self, topic: str) -> str:
        """Extract root segment for tree filtering."""
        parts = topic.split("/")
        return parts[0] if parts else ""

    def _validate_suggestion(self, suggestion: dict) -> bool:
        """Validate LLM suggestion has required fields."""
        required = [
            "suggestedFullTopicPath",
            "payloadMapping",
            "confidence"
        ]
        return all(k in suggestion for k in required)

    async def _create_proposal(
        self,
        raw_topic: str,
        suggestion: dict,
        created_by: str
    ) -> str | None:
        """Create SchemaMapping node in Neo4j."""
        mapping_id = str(uuid.uuid4())

        query = """
        // Create the mapping
        CREATE (s:SchemaMapping {
          id: $mappingId,
          rawTopic: $rawTopic,
          curatedTopic: $curatedTopic,
          payloadMappingJson: $payloadMappingJson,
          status: "proposed",
          createdAt: datetime(),
          createdBy: $createdBy,
          notes: $notes,
          confidence: $confidence
        })

        // Ensure topics exist
        MERGE (raw:Topic {path: $rawTopic, broker: "uncurated"})
        ON CREATE SET raw.createdAt = datetime()

        MERGE (cur:Topic {path: $curatedTopic, broker: "curated"})
        ON CREATE SET cur.createdAt = datetime()

        // Create relationships
        MERGE (s)-[:RAW_TOPIC]->(raw)
        MERGE (s)-[:CURATED_TOPIC]->(cur)
        MERGE (raw)-[r:ROUTES_TO]->(cur)
        SET r.mappingId = s.id,
            r.status = "proposed"

        RETURN s.id AS id
        """

        try:
            async with self._driver.session() as session:
                result = await session.run(
                    query,
                    mappingId=mapping_id,
                    rawTopic=raw_topic,
                    curatedTopic=suggestion["suggestedFullTopicPath"],
                    payloadMappingJson=json.dumps(suggestion.get("payloadMapping", {})),
                    createdBy=created_by,
                    notes=suggestion.get("rationale", ""),
                    confidence=suggestion.get("confidence", "medium")
                )
                record = await result.single()
                return record["id"] if record else None

        except Exception as e:
            logger.error(f"Neo4j error creating proposal: {e}")
            return None

    async def suggest_for_unmapped_topics(
        self,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Process multiple unmapped topics.

        Queries Neo4j for topics without approved mappings and suggests schemas.
        """
        # Find unmapped topics
        query = """
        MATCH (t:Topic {broker: "uncurated"})
        WHERE NOT EXISTS {
          MATCH (s:SchemaMapping {rawTopic: t.path})
          WHERE s.status IN ["proposed", "approved"]
        }
        WITH t
        MATCH (t)-[:HAS_MESSAGE]->(m:Message)
        WITH t, m ORDER BY m.timestamp DESC
        WITH t, collect(m)[0] AS latestMessage
        RETURN t.path AS topic, latestMessage.rawPayload AS payload
        LIMIT $limit
        """

        results = []
        async with self._driver.session() as session:
            result = await session.run(query, limit=limit)
            records = [dict(r) async for r in result]

        for record in records:
            suggestion_result = await self.suggest_schema(
                raw_topic=record["topic"],
                raw_payload=record["payload"] or "{}",
                created_by="batch-advisor"
            )
            results.append(suggestion_result)

        return results
