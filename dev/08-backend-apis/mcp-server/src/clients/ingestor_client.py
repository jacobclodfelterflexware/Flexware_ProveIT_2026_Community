"""HTTP client for the uncurated-ingestor similarity API."""
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import config

logger = logging.getLogger(__name__)


class IngestorClient:
    """Async HTTP client for uncurated-ingestor API endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self.base_url = (base_url or config.ingestor.url).rstrip("/")
        self.timeout = timeout or config.ingestor.timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a GET request to the ingestor API."""
        client = await self._get_client()
        try:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from ingestor: {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to ingestor: {e}")
            raise

    async def similar_topics(
        self,
        query: str,
        k: int = 10,
        broker: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find similar topics using vector cosine similarity.

        Args:
            query: Query text to find similar topics for
            k: Number of results to return
            broker: Optional broker filter

        Returns:
            Dict with query, count, and results
        """
        params = {"q": query, "k": k}
        if broker:
            params["broker"] = broker
        return await self._get("/api/similar-topics", params)

    async def similar_messages(
        self,
        query: str,
        k: int = 10,
        broker: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find similar messages using vector cosine similarity.

        Args:
            query: Query text to find similar messages for
            k: Number of results to return
            broker: Optional broker filter

        Returns:
            Dict with query, count, and results
        """
        params = {"q": query, "k": k}
        if broker:
            params["broker"] = broker
        return await self._get("/api/similar-messages", params)

    async def combined_search(
        self,
        query: str,
        reference_topic: Optional[str] = None,
        reference_time: Optional[str] = None,
        k: int = 20,
        broker: str = "uncurated",
        weight_vector: float = 0.5,
        weight_hierarchy: float = 0.3,
        weight_temporal: float = 0.2
    ) -> Dict[str, Any]:
        """
        Combined similarity search with weighted vector, hierarchy, and temporal signals.

        Args:
            query: Query text for semantic similarity
            reference_topic: Reference topic for hierarchical similarity
            reference_time: ISO timestamp for temporal similarity
            k: Number of results
            broker: Broker filter
            weight_vector: Weight for vector similarity
            weight_hierarchy: Weight for hierarchy similarity
            weight_temporal: Weight for temporal similarity

        Returns:
            Dict with query, weights, count, and results with scores
        """
        params = {
            "q": query,
            "k": k,
            "broker": broker,
            "w_vector": weight_vector,
            "w_hierarchy": weight_hierarchy,
            "w_temporal": weight_temporal
        }
        if reference_topic:
            params["topic"] = reference_topic
        if reference_time:
            params["time"] = reference_time
        return await self._get("/api/combined-search", params)

    async def suggest_normalization(
        self,
        topic: str,
        payload: Optional[str] = None,
        k: int = 5,
        broker: str = "uncurated"
    ) -> Dict[str, Any]:
        """
        Get RAG context for LLM normalization suggestions.

        Args:
            topic: New topic path to get suggestions for
            payload: Sample payload JSON string
            k: Number of similar topics to analyze
            broker: Broker filter

        Returns:
            Dict with inputTopic, similarTopics, namingPatterns, and llmContext
        """
        params = {"topic": topic, "k": k, "broker": broker}
        if payload:
            params["payload"] = payload
        return await self._get("/api/suggest-normalization", params)

    async def hierarchical_topics(
        self,
        topic: str,
        k: int = 20,
        broker: str = "uncurated"
    ) -> Dict[str, Any]:
        """
        Find topics sharing parent segments (siblings/cousins).

        Args:
            topic: Topic path to find related topics for
            k: Number of results
            broker: Broker filter

        Returns:
            Dict with topic, count, and results
        """
        params = {"topic": topic, "k": k, "broker": broker}
        return await self._get("/api/hierarchical-topics", params)

    async def related_topics(
        self,
        topic: str,
        broker: str = "uncurated"
    ) -> Dict[str, Any]:
        """
        Find all related topics: siblings, parent, cousins.

        Args:
            topic: Topic path to find related topics for
            broker: Broker filter

        Returns:
            Dict with topic, parent, siblings, cousins
        """
        params = {"topic": topic, "broker": broker}
        return await self._get("/api/related-topics", params)

    async def temporal_messages(
        self,
        time: Optional[str] = None,
        window: int = 5,
        k: int = 50,
        broker: str = "uncurated"
    ) -> Dict[str, Any]:
        """
        Find messages within a time window.

        Args:
            time: ISO timestamp (default: now)
            window: Window size in minutes
            k: Number of results
            broker: Broker filter

        Returns:
            Dict with referenceTime, windowMinutes, count, and results
        """
        params = {"window": window, "k": k, "broker": broker}
        if time:
            params["time"] = time
        return await self._get("/api/temporal-messages", params)


# Global client instance
_client: Optional[IngestorClient] = None


async def get_ingestor_client() -> IngestorClient:
    """Get or create the global ingestor client."""
    global _client
    if _client is None:
        _client = IngestorClient()
    return _client


async def close_ingestor_client() -> None:
    """Close the global ingestor client."""
    global _client
    if _client:
        await _client.close()
        _client = None
