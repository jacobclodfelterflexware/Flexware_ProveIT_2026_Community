"""HTTP client for the middleware REST API."""
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..config import config

logger = logging.getLogger(__name__)


class MiddlewareClientConfig:
    """Configuration for middleware API client."""
    def __init__(self):
        import os
        self.url = os.getenv(
            "MIDDLEWARE_URL",
            "http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT"
        )
        self.timeout = float(os.getenv("MIDDLEWARE_TIMEOUT", "30.0"))


class MiddlewareClient:
    """Async HTTP client for middleware REST API endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        self._config = MiddlewareClientConfig()
        self.base_url = (base_url or self._config.url).rstrip("/")
        self.timeout = timeout or self._config.timeout
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
        """Make a GET request to the middleware API."""
        client = await self._get_client()
        try:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from middleware: {e.response.status_code}")
            if e.response.status_code == 404:
                return {"error": "Not found", "status_code": 404}
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to middleware: {e}")
            raise

    async def _post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a POST request to the middleware API."""
        client = await self._get_client()
        try:
            response = await client.post(endpoint, json=json_data, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from middleware: {e.response.status_code}")
            if e.response.status_code == 404:
                return {"error": "Not found", "status_code": 404}
            if e.response.status_code == 409:
                return {"error": "Conflict - resource already exists", "status_code": 409}
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to middleware: {e}")
            raise

    async def _delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Make a DELETE request to the middleware API."""
        client = await self._get_client()
        try:
            response = await client.delete(endpoint, params=params)
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from middleware: {e.response.status_code}")
            if e.response.status_code == 404:
                return False
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to middleware: {e}")
            raise

    # =========================================================================
    # Unmapped Topics
    # =========================================================================

    async def list_unmapped_topics(
        self,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        order_by: str = "last_seen",
        order_desc: bool = True
    ) -> Dict[str, Any]:
        """
        List unmapped topics with pagination and filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records
            search: Search in topic names
            order_by: Order by field (last_seen, first_seen, message_count, topic)
            order_desc: Order descending

        Returns:
            Dict with topics list and total count
        """
        params = {
            "skip": skip,
            "limit": limit,
            "order_by": order_by,
            "order_desc": order_desc
        }
        if search:
            params["search"] = search
        return await self._get("/api/v1/unmapped/", params)

    async def get_unmapped_topic(self, unmapped_id: int) -> Dict[str, Any]:
        """
        Get a specific unmapped topic by ID.

        Args:
            unmapped_id: The unmapped topic ID

        Returns:
            Unmapped topic dict or error
        """
        return await self._get(f"/api/v1/unmapped/{unmapped_id}")

    async def quick_map_topic(
        self,
        unmapped_id: int,
        target_topic: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Quick-map an unmapped topic to a target topic.

        Args:
            unmapped_id: The unmapped topic ID
            target_topic: Target topic to map to
            description: Optional description

        Returns:
            Created mapping dict or error
        """
        json_data = {"target_topic": target_topic}
        if description:
            json_data["description"] = description
        return await self._post(f"/api/v1/unmapped/{unmapped_id}/quick-map", json_data)

    async def delete_unmapped_topic(self, unmapped_id: int) -> bool:
        """
        Delete/dismiss an unmapped topic.

        Args:
            unmapped_id: The unmapped topic ID

        Returns:
            True if deleted, False if not found
        """
        return await self._delete(f"/api/v1/unmapped/{unmapped_id}")

    async def clear_unmapped_topics(
        self,
        older_than_hours: Optional[int] = None
    ) -> bool:
        """
        Clear all unmapped topics, optionally by age.

        Args:
            older_than_hours: Only clear topics older than N hours

        Returns:
            True if operation succeeded
        """
        params = {}
        if older_than_hours is not None:
            params["older_than_hours"] = older_than_hours
        return await self._delete("/api/v1/unmapped/", params)

    # =========================================================================
    # Mapping Statistics
    # =========================================================================

    async def get_mapping_stats(self) -> Dict[str, Any]:
        """
        Get mapping statistics.

        Returns:
            Dict with statistics about mappings, transforms, and unmapped topics
        """
        # This calls the stats endpoint if available, otherwise aggregates
        try:
            return await self._get("/api/v1/stats")
        except Exception:
            # Fallback: compute basic stats from list endpoints
            return {
                "error": "Stats endpoint not available",
                "message": "Use individual list endpoints for counts"
            }


# Global client instance
_client: Optional[MiddlewareClient] = None


async def get_middleware_client() -> MiddlewareClient:
    """Get or create the global middleware client."""
    global _client
    if _client is None:
        _client = MiddlewareClient()
    return _client


async def close_middleware_client() -> None:
    """Close the global middleware client."""
    global _client
    if _client:
        await _client.close()
        _client = None
