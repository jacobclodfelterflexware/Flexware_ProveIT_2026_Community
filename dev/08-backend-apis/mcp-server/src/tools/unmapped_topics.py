"""MCP tools for unmapped topic management."""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..clients.middleware_client import get_middleware_client


def register_unmapped_tools(mcp: FastMCP) -> None:
    """Register all unmapped topic tools with the MCP server."""

    @mcp.tool()
    async def list_unmapped_topics(
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        order_by: str = "last_seen"
    ) -> dict:
        """
        List unmapped topics with pagination and filtering.

        Unmapped topics are MQTT topics that have been observed but don't have
        a mapping configured yet. These are candidates for normalization.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return (max 1000)
            search: Search text to filter topic names
            order_by: Field to order by (last_seen, first_seen, message_count, topic)

        Returns:
            Dictionary with 'topics' list and 'total' count
        """
        client = await get_middleware_client()
        limit = min(limit, 1000)

        result = await client.list_unmapped_topics(
            skip=skip,
            limit=limit,
            search=search,
            order_by=order_by
        )

        return result

    @mcp.tool()
    async def get_unmapped_topic(unmapped_id: int) -> dict:
        """
        Get details of a specific unmapped topic by ID.

        Args:
            unmapped_id: The unique identifier of the unmapped topic

        Returns:
            Unmapped topic object with id, topic, first_seen, last_seen,
            message_count, and sample_payload fields
        """
        client = await get_middleware_client()
        result = await client.get_unmapped_topic(unmapped_id)

        if "error" in result:
            return {"error": f"Unmapped topic with ID {unmapped_id} not found"}

        return result

    @mcp.tool()
    async def quick_map_topic(
        unmapped_id: int,
        target_topic: str,
        description: Optional[str] = None
    ) -> dict:
        """
        Quick-map an unmapped topic to a target topic.

        This creates a new topic mapping from the unmapped topic's source
        to the specified target, and removes it from the unmapped list.
        The new mapping is created with is_active=True.

        Args:
            unmapped_id: ID of the unmapped topic to map
            target_topic: Target MQTT topic to map to (normalized path)
            description: Optional description for the new mapping

        Returns:
            Created topic mapping object
        """
        client = await get_middleware_client()
        result = await client.quick_map_topic(
            unmapped_id=unmapped_id,
            target_topic=target_topic,
            description=description
        )

        if "error" in result:
            if result.get("status_code") == 404:
                return {"error": f"Unmapped topic with ID {unmapped_id} not found"}
            elif result.get("status_code") == 409:
                return {"error": "A mapping for this source topic already exists"}
            return result

        return {
            "message": "Topic mapped successfully",
            "mapping": result
        }

    @mcp.tool()
    async def delete_unmapped_topic(unmapped_id: int) -> dict:
        """
        Delete/dismiss an unmapped topic without creating a mapping.

        Use this to ignore topics that don't need normalization (e.g., system
        topics, test topics, or duplicates).

        Args:
            unmapped_id: ID of the unmapped topic to delete

        Returns:
            Confirmation of deletion or error message
        """
        client = await get_middleware_client()
        success = await client.delete_unmapped_topic(unmapped_id)

        if success:
            return {
                "message": f"Unmapped topic {unmapped_id} deleted successfully"
            }
        else:
            return {"error": f"Unmapped topic with ID {unmapped_id} not found"}

    @mcp.tool()
    async def clear_unmapped_topics(
        older_than_hours: Optional[int] = None
    ) -> dict:
        """
        Clear all unmapped topics, optionally filtering by age.

        Use with caution - this removes unmapped topics from the review queue.
        Consider using older_than_hours to only clear stale entries.

        Args:
            older_than_hours: Only clear topics not seen in N hours (optional)
                If not provided, clears ALL unmapped topics.

        Returns:
            Confirmation message
        """
        client = await get_middleware_client()
        success = await client.clear_unmapped_topics(older_than_hours)

        if success:
            if older_than_hours:
                return {
                    "message": f"Cleared unmapped topics older than {older_than_hours} hours"
                }
            else:
                return {"message": "All unmapped topics cleared"}
        else:
            return {"error": "Failed to clear unmapped topics"}
