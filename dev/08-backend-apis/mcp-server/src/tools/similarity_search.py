"""MCP tools for vector similarity search."""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..clients.ingestor_client import get_ingestor_client


def register_similarity_tools(mcp: FastMCP) -> None:
    """Register all similarity search tools with the MCP server."""

    @mcp.tool()
    async def search_similar_topics(
        query: str,
        k: int = 10,
        broker: Optional[str] = None
    ) -> dict:
        """
        Find topics semantically similar to a query using vector cosine similarity.

        Uses embeddings to find topics with similar meaning, regardless of
        exact wording. Great for finding existing patterns when normalizing
        new topics.

        Args:
            query: Text query to find similar topics for (topic path or description)
            k: Number of similar topics to return (default: 10, max: 100)
            broker: Filter by broker ('uncurated', 'curated', or None for both)

        Returns:
            Dictionary with query, count, and results with similarity scores
        """
        client = await get_ingestor_client()
        k = min(k, 100)

        result = await client.similar_topics(
            query=query,
            k=k,
            broker=broker
        )

        return result

    @mcp.tool()
    async def search_similar_messages(
        query: str,
        k: int = 10,
        broker: Optional[str] = None
    ) -> dict:
        """
        Find messages semantically similar to a query using vector cosine similarity.

        Searches message payloads for semantic similarity. Useful for finding
        messages with similar content structure or values.

        Args:
            query: Text query to find similar messages for (payload content or description)
            k: Number of similar messages to return (default: 10, max: 100)
            broker: Filter by broker ('uncurated', 'curated', or None for both)

        Returns:
            Dictionary with query, count, and results with similarity scores
        """
        client = await get_ingestor_client()
        k = min(k, 100)

        result = await client.similar_messages(
            query=query,
            k=k,
            broker=broker
        )

        return result

    @mcp.tool()
    async def combined_search(
        query: str,
        reference_topic: Optional[str] = None,
        reference_time: Optional[str] = None,
        k: int = 20,
        broker: str = "uncurated",
        weight_vector: float = 0.5,
        weight_hierarchy: float = 0.3,
        weight_temporal: float = 0.2
    ) -> dict:
        """
        Advanced combined search using vector, hierarchical, and temporal signals.

        Combines three similarity signals for more relevant results:
        - Vector similarity: Semantic meaning of the query
        - Hierarchy similarity: Topic tree proximity (requires reference_topic)
        - Temporal similarity: Time proximity (requires reference_time)

        Args:
            query: Text for semantic similarity search
            reference_topic: Topic path for hierarchical similarity bonus (e.g., 'factory/line1/machine1')
            reference_time: ISO timestamp for temporal similarity bonus (e.g., '2025-01-15T10:30:00Z')
            k: Number of results to return (default: 20, max: 100)
            broker: Broker filter ('uncurated' or 'curated')
            weight_vector: Weight for vector similarity (0.0-1.0, default: 0.5)
            weight_hierarchy: Weight for hierarchy similarity (0.0-1.0, default: 0.3)
            weight_temporal: Weight for temporal similarity (0.0-1.0, default: 0.2)

        Returns:
            Combined results with breakdown of individual scores
        """
        client = await get_ingestor_client()
        k = min(k, 100)

        result = await client.combined_search(
            query=query,
            reference_topic=reference_topic,
            reference_time=reference_time,
            k=k,
            broker=broker,
            weight_vector=weight_vector,
            weight_hierarchy=weight_hierarchy,
            weight_temporal=weight_temporal
        )

        return result

    @mcp.tool()
    async def suggest_normalization(
        topic: str,
        payload: Optional[str] = None,
        k: int = 5,
        broker: str = "uncurated"
    ) -> dict:
        """
        Get RAG context for AI-assisted topic normalization suggestions.

        Analyzes a topic (and optionally its payload) to provide context for
        suggesting how to normalize it. Returns:
        - Similar existing topics for pattern matching
        - Naming conventions observed in the codebase
        - Structured context for LLM-based suggestions

        Args:
            topic: New topic path to get suggestions for
            payload: Sample JSON payload string for key analysis (optional)
            k: Number of similar topics to analyze (default: 5)
            broker: Broker filter (default: 'uncurated')

        Returns:
            Dictionary with:
            - inputTopic: The topic being analyzed
            - similarTopics: Related topics found via vector search
            - namingPatterns: Observed naming conventions
            - llmContext: Pre-formatted context for LLM prompts
        """
        client = await get_ingestor_client()
        k = min(k, 20)

        result = await client.suggest_normalization(
            topic=topic,
            payload=payload,
            k=k,
            broker=broker
        )

        return result
