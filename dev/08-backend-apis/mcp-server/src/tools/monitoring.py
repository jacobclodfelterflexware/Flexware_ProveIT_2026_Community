"""MCP tools for monitoring and statistics."""
from mcp.server.fastmcp import FastMCP

from ..clients.postgres_client import get_postgres_client
from ..clients.middleware_client import get_middleware_client


def register_monitoring_tools(mcp: FastMCP) -> None:
    """Register monitoring tools with the MCP server."""

    @mcp.tool()
    async def get_mapping_stats() -> dict:
        """
        Get current mapping statistics and system health overview.

        Provides counts and status information for:
        - Total topic mappings (active vs inactive)
        - Total key transformations
        - Unmapped topics awaiting review

        Returns:
            Dictionary with:
            - mappings: Total count and active/inactive breakdown
            - transformations: Total key transformation count
            - unmapped: Count of topics awaiting mapping
            - status: Overall system health indicator
        """
        postgres = await get_postgres_client()
        middleware = await get_middleware_client()

        # Get mapping counts
        all_mappings = await postgres.list_topic_mappings(limit=10000)
        active_mappings = [m for m in all_mappings if m.get("is_active")]
        inactive_mappings = [m for m in all_mappings if not m.get("is_active")]

        # Get transformation count
        all_transforms = await postgres.list_key_transformations()

        # Get unmapped count
        unmapped_result = await middleware.list_unmapped_topics(limit=1)
        unmapped_total = unmapped_result.get("total", 0)

        # Determine health status
        if unmapped_total > 100:
            status = "warning"
            status_message = f"High number of unmapped topics ({unmapped_total})"
        elif len(inactive_mappings) > len(active_mappings):
            status = "attention"
            status_message = "More inactive mappings than active"
        else:
            status = "healthy"
            status_message = "System operating normally"

        return {
            "mappings": {
                "total": len(all_mappings),
                "active": len(active_mappings),
                "inactive": len(inactive_mappings)
            },
            "transformations": {
                "total": len(all_transforms)
            },
            "unmapped": {
                "total": unmapped_total,
                "awaiting_review": unmapped_total
            },
            "status": status,
            "status_message": status_message
        }
