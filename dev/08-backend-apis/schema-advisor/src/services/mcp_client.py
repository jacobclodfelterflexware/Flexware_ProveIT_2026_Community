"""MCP Server client for similarity search and topic tree queries."""
import aiohttp
import logging
from typing import Any

from config import config

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for MCP Server tools."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or config.mcp_url

    async def similar_topics(
        self,
        topic: str,
        k: int = 20,
        broker_filter: str = "all"
    ) -> list[dict[str, Any]]:
        """Find similar topics."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/tools/similar_topics_any",
                json={
                    "topic": topic,
                    "k": k,
                    "broker_filter": broker_filter
                }
            ) as resp:
                result = await resp.json()

        if result.get("success"):
            return result.get("topics", [])
        else:
            logger.error(f"similar_topics error: {result.get('error')}")
            return []

    async def similar_messages(
        self,
        topic: str,
        payload: str,
        k: int = 50,
        broker_filter: str = "all"
    ) -> list[dict[str, Any]]:
        """Find similar messages."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/tools/similar_messages_any",
                json={
                    "topic": topic,
                    "payload": payload,
                    "k": k,
                    "broker_filter": broker_filter
                }
            ) as resp:
                result = await resp.json()

        if result.get("success"):
            return result.get("messages", [])
        else:
            logger.error(f"similar_messages error: {result.get('error')}")
            return []

    async def get_mapping_status(self, raw_topic: str) -> dict[str, Any] | None:
        """Check if mapping already exists."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/tools/get_mapping_status",
                json={"raw_topic": raw_topic}
            ) as resp:
                result = await resp.json()

        if result.get("success") and result.get("exists"):
            return result.get("mapping")
        return None

    async def get_topic_tree(
        self,
        broker: str = "curated",
        root_path: str = ""
    ) -> dict[str, Any]:
        """Get topic tree structure."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/tools/get_topic_tree",
                json={
                    "broker": broker,
                    "root_path": root_path
                }
            ) as resp:
                result = await resp.json()

        return result.get("tree", {}) if result.get("success") else {}
