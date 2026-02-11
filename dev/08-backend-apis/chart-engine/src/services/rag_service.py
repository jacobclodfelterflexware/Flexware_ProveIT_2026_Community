import httpx
import logging
import re
from typing import Optional

from neo4j import AsyncGraphDatabase

from api.models import RAGContext, ChartPreferences

logger = logging.getLogger(__name__)


def extract_topic_path(query: str) -> Optional[str]:
    """
    Extract exact topic path from query if present.

    Suggestions generate queries like:
    "Show is_mixing trends over the last hour for Enterprise A/opto22/Utilities/.../is_mixing"

    This extracts the full path after "for ".
    """
    # Match paths after "for " that contain at least 2 slashes (indicating a real path)
    match = re.search(r'\bfor\s+([A-Za-z0-9][A-Za-z0-9_\-\s\.]*(?:/[A-Za-z0-9_\-\s\.]+){2,})', query, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


class RAGService:
    """
    RAG retrieval service that queries uncurated-ingestor for relevant topics and fields.
    """

    def __init__(
        self,
        ingestor_url: str,
        neo4j_uri: str = None,
        neo4j_user: str = None,
        neo4j_password: str = None
    ):
        self.ingestor_url = ingestor_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

        # Neo4j driver for direct topic verification
        self.neo4j_driver = None
        if neo4j_uri and neo4j_user and neo4j_password:
            self.neo4j_driver = AsyncGraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password)
            )

    async def retrieve_context(
        self,
        query: str,
        preferences: Optional[ChartPreferences] = None
    ) -> RAGContext:
        """
        Retrieve RAG context for a user query.

        1. Check for exact topic path in query (from suggestions)
        2. Search for similar topics (semantic similarity)
        3. Get topic hierarchy structure
        4. Extract available fields from matching topics
        """
        try:
            matching_topics = []

            # Step 1: Check for exact topic path in query
            exact_path = extract_topic_path(query)
            if exact_path:
                logger.info(f"Extracted exact path from query: {exact_path}")
                exact_match = await self._verify_topic_exists(exact_path)
                if exact_match:
                    # Use exact match as the primary topic
                    matching_topics = [exact_match]
                    logger.info(f"Using exact match topic: {exact_path}")

            # Step 2: Get semantic matches (either as supplement or primary)
            k = preferences.max_series * 2 if preferences and preferences.max_series else 20
            similar_topics = await self._search_similar_topics(query, k=k)

            if matching_topics:
                # We have an exact match - add semantic matches that aren't duplicates
                exact_paths = {t.get("path", t.get("topic")) for t in matching_topics}
                for topic in similar_topics:
                    topic_path = topic.get("path", topic.get("topic"))
                    if topic_path not in exact_paths:
                        matching_topics.append(topic)
            else:
                # No exact match found - use semantic matches only
                matching_topics = similar_topics

            # Get hierarchy for matching topics
            topic_hierarchy = await self._build_topic_hierarchy(matching_topics)

            # Extract available fields from recent messages
            available_fields = self._extract_fields(matching_topics)

            # Estimate time range
            time_range = self._estimate_time_range(matching_topics)

            return RAGContext(
                matching_topics=matching_topics,
                topic_hierarchy=topic_hierarchy,
                time_range_available=time_range,
                available_fields=available_fields
            )
        except Exception as e:
            logger.error(f"RAG retrieval error: {e}")
            return RAGContext(
                matching_topics=[],
                topic_hierarchy={},
                available_fields=[]
            )

    async def _search_similar_topics(self, query: str, k: int = 20) -> list[dict]:
        """Search for semantically similar topics."""
        try:
            response = await self.client.get(
                f"{self.ingestor_url}/api/similar-topics",
                params={"q": query, "k": k}
            )
            response.raise_for_status()
            data = response.json()

            # Enrich with recent message data to get available fields
            enriched = []
            for topic in data.get("results", []):
                # Get recent messages for this topic to discover fields
                topic_path = topic.get("path", topic.get("topic"))
                if topic_path:
                    fields = await self._get_topic_fields(topic_path)
                    topic["available_fields"] = fields
                    topic["data_type"] = "numeric" if any(f in fields for f in ["value", "count", "temperature", "pressure"]) else "mixed"
                enriched.append(topic)

            return enriched
        except Exception as e:
            logger.error(f"Similar topics search error: {e}")
            return []

    async def _verify_topic_exists(self, path: str) -> Optional[dict]:
        """
        Verify a topic path exists and return its info.

        Returns a topic dict with high similarity score if found, None otherwise.
        Uses Neo4j direct query for accurate verification.
        """
        if not self.neo4j_driver:
            logger.warning("Neo4j driver not configured, skipping topic verification")
            return None

        try:
            query = """
            MATCH (t:Topic {path: $path})
            OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
            WITH t, count(m) as msgCount, collect(m.rawPayload)[0..3] as samplePayloads
            RETURN t.path as path, msgCount, samplePayloads
            LIMIT 1
            """

            async with self.neo4j_driver.session() as session:
                result = await session.run(query, {"path": path})
                record = await result.single()

                if record and record["msgCount"] > 0:
                    # Extract fields from sample payloads
                    fields = set()
                    import json
                    for payload_str in record["samplePayloads"] or []:
                        if payload_str:
                            try:
                                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                                if isinstance(payload, dict):
                                    fields.update(payload.keys())
                            except (json.JSONDecodeError, TypeError):
                                pass

                    logger.info(f"Exact topic path verified in Neo4j: {path} ({record['msgCount']} messages)")
                    return {
                        "path": path,
                        "topic": path,
                        "similarity": 1.0,  # Exact match = highest confidence
                        "available_fields": list(fields) if fields else ["value"],
                        "data_type": "numeric" if any(f in fields for f in ["value", "count", "temperature", "pressure"]) else "mixed",
                        "exact_match": True,
                        "message_count": record["msgCount"]
                    }

        except Exception as e:
            logger.error(f"Neo4j topic verification failed for {path}: {e}")

        return None

    async def _get_topic_fields(self, topic_path: str) -> list[str]:
        """Get available fields from recent messages for a topic."""
        try:
            # Use suggest-normalization endpoint which returns recent messages
            response = await self.client.get(
                f"{self.ingestor_url}/api/suggest-normalization",
                params={"topic": topic_path, "k": 1}
            )
            response.raise_for_status()
            data = response.json()

            fields = set()
            for similar in data.get("similar_topics", []):
                for msg in similar.get("recent_messages", []):
                    if isinstance(msg.get("payload"), dict):
                        fields.update(msg["payload"].keys())

            # Also check sample_messages in the response
            for msg in data.get("sample_messages", []):
                if isinstance(msg.get("payload"), dict):
                    fields.update(msg["payload"].keys())

            return list(fields) if fields else ["value", "timestamp"]
        except Exception as e:
            logger.debug(f"Could not get fields for {topic_path}: {e}")
            return ["value", "timestamp"]

    async def _build_topic_hierarchy(self, topics: list[dict]) -> dict:
        """Build a hierarchy structure from matching topics."""
        hierarchy = {}

        for topic in topics:
            path = topic.get("path", topic.get("topic", ""))
            if not path:
                continue

            segments = path.split("/")

            # Build hierarchy dict
            current = hierarchy
            for i, segment in enumerate(segments[:-1]):
                if segment not in current:
                    current[segment] = {}
                current = current[segment]

            # Add leaf
            leaf = segments[-1] if segments else "unknown"
            if leaf not in current:
                current[leaf] = topic.get("available_fields", [])

        return hierarchy

    def _extract_fields(self, topics: list[dict]) -> list[str]:
        """Extract unique fields from all matching topics."""
        fields = set()
        for topic in topics:
            fields.update(topic.get("available_fields", []))
        return sorted(list(fields))

    def _estimate_time_range(self, topics: list[dict]) -> Optional[str]:
        """Estimate available time range from topic metadata."""
        # This would be enhanced with actual time range queries
        return "last 24 hours"

    async def get_combined_context(
        self,
        query: str,
        reference_topic: Optional[str] = None,
        k: int = 20
    ) -> RAGContext:
        """
        Get combined context using all similarity signals.
        """
        try:
            params = {"q": query, "k": k}
            if reference_topic:
                params["topic"] = reference_topic

            response = await self.client.get(
                f"{self.ingestor_url}/api/combined-search",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            return RAGContext(
                matching_topics=results,
                topic_hierarchy=await self._build_topic_hierarchy(results),
                available_fields=self._extract_fields(results)
            )
        except Exception as e:
            logger.error(f"Combined search error: {e}")
            return await self.retrieve_context(query)

    async def close(self):
        """Close the HTTP client and Neo4j driver."""
        await self.client.aclose()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
