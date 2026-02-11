"""MCP tools for topic mapping management."""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..clients.postgres_client import get_postgres_client


def register_mapping_tools(mcp: FastMCP) -> None:
    """Register all topic mapping tools with the MCP server."""

    @mcp.tool()
    async def list_topic_mappings(
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        search: Optional[str] = None
    ) -> dict:
        """
        List all topic mappings with pagination and filtering.

        Args:
            skip: Number of records to skip for pagination
            limit: Maximum number of records to return (max 1000)
            is_active: Filter by active status (True/False/None for all)
            search: Search text to match in source or target topics (LIKE pattern)

        Returns:
            Dictionary with 'mappings' list and 'total' count
        """
        client = await get_postgres_client()
        limit = min(limit, 1000)

        # Convert search to LIKE pattern if provided
        source_filter = f"%{search}%" if search else None

        mappings = await client.list_topic_mappings(
            source_topic_filter=source_filter,
            is_active=is_active,
            limit=limit,
            offset=skip
        )

        return {
            "mappings": mappings,
            "total": len(mappings),
            "skip": skip,
            "limit": limit
        }

    @mcp.tool()
    async def get_topic_mapping(mapping_id: int) -> dict:
        """
        Get a specific topic mapping by its ID.

        Args:
            mapping_id: The unique identifier of the topic mapping

        Returns:
            Topic mapping object with id, source_topic, target_topic, is_active,
            description, created_at, and updated_at fields
        """
        client = await get_postgres_client()
        mapping = await client.get_topic_mapping(id=mapping_id)

        if not mapping:
            return {"error": f"Topic mapping with ID {mapping_id} not found"}

        return mapping

    @mcp.tool()
    async def get_mapping_by_source(source_topic: str) -> dict:
        """
        Find a topic mapping by its source topic path.

        Args:
            source_topic: The exact source topic path to search for

        Returns:
            Topic mapping object if found, or error message if not found
        """
        client = await get_postgres_client()
        mapping = await client.get_topic_mapping(source_topic=source_topic)

        if not mapping:
            return {"error": f"No mapping found for source topic: {source_topic}"}

        return mapping

    @mcp.tool()
    async def create_topic_mapping(
        source_topic: str,
        target_topic: str,
        description: Optional[str] = None,
        is_active: bool = False
    ) -> dict:
        """
        Create a new topic mapping from source to target.

        Args:
            source_topic: Source MQTT topic pattern to map from
            target_topic: Target MQTT topic to map to
            description: Human-readable description of this mapping
            is_active: Whether mapping is active immediately (default: False for HITL review)

        Returns:
            Created topic mapping with assigned ID
        """
        client = await get_postgres_client()

        # Check if mapping already exists
        existing = await client.get_topic_mapping(source_topic=source_topic)
        if existing:
            return {
                "error": f"Mapping already exists for source topic: {source_topic}",
                "existing_mapping": existing
            }

        mapping = await client.create_topic_mapping(
            source_topic=source_topic,
            target_topic=target_topic,
            description=description,
            is_active=is_active
        )

        return {
            "message": "Topic mapping created successfully",
            "mapping": mapping
        }

    @mcp.tool()
    async def update_topic_mapping(
        mapping_id: int,
        target_topic: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> dict:
        """
        Update an existing topic mapping.

        Args:
            mapping_id: The ID of the mapping to update
            target_topic: New target topic (optional)
            description: New description (optional)
            is_active: New active status (optional)

        Returns:
            Updated topic mapping object
        """
        client = await get_postgres_client()

        # Check if mapping exists
        existing = await client.get_topic_mapping(id=mapping_id)
        if not existing:
            return {"error": f"Topic mapping with ID {mapping_id} not found"}

        # Perform update
        updated = await client.update_topic_mapping(
            id=mapping_id,
            target_topic=target_topic,
            description=description,
            is_active=is_active
        )

        return {
            "message": "Topic mapping updated successfully",
            "mapping": updated
        }

    @mcp.tool()
    async def delete_topic_mapping(mapping_id: int) -> dict:
        """
        Delete a topic mapping and its associated key transformations.

        Args:
            mapping_id: The ID of the mapping to delete

        Returns:
            Confirmation of deletion or error message
        """
        client = await get_postgres_client()

        # Check if mapping exists
        existing = await client.get_topic_mapping(id=mapping_id)
        if not existing:
            return {"error": f"Topic mapping with ID {mapping_id} not found"}

        success = await client.delete_topic_mapping(id=mapping_id)

        if success:
            return {
                "message": f"Topic mapping {mapping_id} deleted successfully",
                "deleted_mapping": existing
            }
        else:
            return {"error": f"Failed to delete topic mapping {mapping_id}"}
