"""MCP tools for hierarchical and temporal queries."""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..clients.ingestor_client import get_ingestor_client


def register_hierarchical_tools(mcp: FastMCP) -> None:
    """Register all hierarchical and temporal query tools with the MCP server."""

    @mcp.tool()
    async def find_hierarchical_topics(
        topic: str,
        k: int = 20,
        broker: str = "uncurated"
    ) -> dict:
        """
        Find topics that share parent segments (siblings and cousins).

        Given a topic like 'factory/line1/machine1/temperature', this finds
        other topics under 'factory/line1/machine1' (siblings) and
        'factory/line1' (cousins).

        Useful for understanding the topic hierarchy and finding related sensors
        or data points on the same machine or production line.

        Args:
            topic: Topic path to find related topics for
            k: Maximum number of results (default: 20, max: 100)
            broker: Broker filter ('uncurated' or 'curated')

        Returns:
            Dictionary with topic, count, and hierarchically related results
        """
        client = await get_ingestor_client()
        k = min(k, 100)

        result = await client.hierarchical_topics(
            topic=topic,
            k=k,
            broker=broker
        )

        return result

    @mcp.tool()
    async def find_related_topics(
        topic: str,
        broker: str = "uncurated"
    ) -> dict:
        """
        Find all related topics: parent, siblings, and cousins.

        Provides a structured view of the topic's position in the hierarchy:
        - Parent: The immediate parent topic segment
        - Siblings: Other topics at the same level (same parent)
        - Cousins: Topics at the same level but different parents

        Args:
            topic: Topic path to analyze (e.g., 'factory/line1/machine1/temp')
            broker: Broker filter ('uncurated' or 'curated')

        Returns:
            Dictionary with:
            - topic: The input topic
            - parent: Parent topic path
            - siblings: List of sibling topics
            - cousins: List of cousin topics
        """
        client = await get_ingestor_client()

        result = await client.related_topics(
            topic=topic,
            broker=broker
        )

        return result

    @mcp.tool()
    async def get_temporal_messages(
        reference_time: Optional[str] = None,
        window_minutes: int = 5,
        k: int = 50,
        broker: str = "uncurated"
    ) -> dict:
        """
        Find messages within a time window around a reference point.

        Retrieves messages that occurred near a specific time. Useful for:
        - Investigating what was happening during an incident
        - Finding correlated events across different topics
        - Analyzing message patterns over time

        Args:
            reference_time: ISO timestamp to search around (default: now)
                Example: '2025-01-15T10:30:00Z'
            window_minutes: Size of time window in minutes (default: 5)
            k: Maximum number of messages (default: 50, max: 200)
            broker: Broker filter ('uncurated' or 'curated')

        Returns:
            Dictionary with:
            - referenceTime: The time searched around
            - windowMinutes: The window size used
            - count: Number of messages found
            - results: List of messages with timestamps
        """
        client = await get_ingestor_client()
        k = min(k, 200)

        result = await client.temporal_messages(
            time=reference_time,
            window=window_minutes,
            k=k,
            broker=broker
        )

        return result
