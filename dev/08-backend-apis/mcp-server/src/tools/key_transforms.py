"""MCP tools for key transformation management."""
from typing import Optional

from mcp.server.fastmcp import FastMCP

from ..clients.postgres_client import get_postgres_client


def register_transform_tools(mcp: FastMCP) -> None:
    """Register all key transformation tools with the MCP server."""

    @mcp.tool()
    async def list_key_transformations(
        topic_mapping_id: Optional[int] = None,
        source_topic: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> dict:
        """
        List key transformations, optionally filtered by topic mapping.

        Args:
            topic_mapping_id: Filter by parent topic mapping ID
            source_topic: Filter by source topic (alternative to mapping ID)
            is_active: Filter by active status

        Returns:
            Dictionary with 'transformations' list
        """
        client = await get_postgres_client()

        transformations = await client.list_key_transformations(
            topic_mapping_id=topic_mapping_id,
            source_topic=source_topic,
            is_active=is_active
        )

        return {
            "transformations": transformations,
            "total": len(transformations),
            "topic_mapping_id": topic_mapping_id,
            "source_topic": source_topic
        }

    @mcp.tool()
    async def get_key_transformation(transformation_id: int) -> dict:
        """
        Get a specific key transformation by its ID.

        Args:
            transformation_id: The unique identifier of the key transformation

        Returns:
            Key transformation object with id, topic_mapping_id, source_key,
            target_key, json_path, transform_order, is_active, etc.
        """
        client = await get_postgres_client()
        transformation = await client.get_key_transformation(id=transformation_id)

        if not transformation:
            return {"error": f"Key transformation with ID {transformation_id} not found"}

        return transformation

    @mcp.tool()
    async def create_key_transformation(
        source_key: str,
        target_key: str,
        topic_mapping_id: Optional[int] = None,
        source_topic: Optional[str] = None,
        json_path: Optional[str] = None,
        transform_order: int = 0,
        is_active: bool = True
    ) -> dict:
        """
        Create a new key transformation that renames a JSON key in the payload.

        Args:
            source_key: Original JSON key name in the payload
            target_key: New JSON key name after transformation
            topic_mapping_id: ID of the parent topic mapping
            source_topic: Source topic to find mapping (alternative to mapping ID)
            json_path: JSONPath for nested keys (e.g., 'data.sensors[*]')
            transform_order: Order of transformation application (lower = first)
            is_active: Whether this transformation is active

        Returns:
            Created transformation with assigned ID
        """
        client = await get_postgres_client()

        # Validate that we have either mapping ID or source topic
        if not topic_mapping_id and not source_topic:
            return {
                "error": "Either topic_mapping_id or source_topic must be provided"
            }

        transformation = await client.create_key_transformation(
            source_key=source_key,
            target_key=target_key,
            topic_mapping_id=topic_mapping_id,
            source_topic=source_topic,
            json_path=json_path,
            transform_order=transform_order,
            is_active=is_active
        )

        if not transformation:
            return {
                "error": "Failed to create transformation. Topic mapping not found."
            }

        return {
            "message": "Key transformation created successfully",
            "transformation": transformation
        }

    @mcp.tool()
    async def update_key_transformation(
        transformation_id: int,
        source_key: Optional[str] = None,
        target_key: Optional[str] = None,
        json_path: Optional[str] = None,
        transform_order: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> dict:
        """
        Update an existing key transformation.

        Args:
            transformation_id: The ID of the transformation to update
            source_key: New source key name (optional)
            target_key: New target key name (optional)
            json_path: New JSON path (optional)
            transform_order: New transform order (optional)
            is_active: New active status (optional)

        Returns:
            Updated transformation object
        """
        client = await get_postgres_client()

        # Check if transformation exists
        existing = await client.get_key_transformation(id=transformation_id)
        if not existing:
            return {"error": f"Key transformation with ID {transformation_id} not found"}

        updated = await client.update_key_transformation(
            id=transformation_id,
            source_key=source_key,
            target_key=target_key,
            json_path=json_path,
            transform_order=transform_order,
            is_active=is_active
        )

        return {
            "message": "Key transformation updated successfully",
            "transformation": updated
        }

    @mcp.tool()
    async def delete_key_transformation(transformation_id: int) -> dict:
        """
        Delete a key transformation.

        Args:
            transformation_id: The ID of the transformation to delete

        Returns:
            Confirmation of deletion or error message
        """
        client = await get_postgres_client()

        # Check if transformation exists
        existing = await client.get_key_transformation(id=transformation_id)
        if not existing:
            return {"error": f"Key transformation with ID {transformation_id} not found"}

        success = await client.delete_key_transformation(id=transformation_id)

        if success:
            return {
                "message": f"Key transformation {transformation_id} deleted successfully",
                "deleted_transformation": existing
            }
        else:
            return {"error": f"Failed to delete key transformation {transformation_id}"}
