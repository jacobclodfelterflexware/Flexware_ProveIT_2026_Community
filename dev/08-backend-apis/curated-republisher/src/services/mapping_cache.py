"""Caches approved schema mappings from Neo4j."""
import asyncio
import json
import logging
from typing import Any
from datetime import datetime

from neo4j import AsyncGraphDatabase

from config import config

logger = logging.getLogger(__name__)


class MappingCache:
    """
    Caches approved schema mappings from Neo4j.

    Periodically refreshes to pick up newly approved mappings.
    """

    def __init__(self):
        self._driver = None
        self._cache: dict[str, dict[str, Any]] = {}
        self._last_refresh: datetime | None = None
        self._refresh_task: asyncio.Task | None = None
        self._is_running = False

        # Stats
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_mappings = 0

    async def start(self) -> None:
        """Initialize and start background refresh."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        self._is_running = True

        # Initial load
        await self._refresh_cache()

        # Start background refresh
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("Mapping cache started")

    async def stop(self) -> None:
        """Stop and clean up."""
        self._is_running = False
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        if self._driver:
            await self._driver.close()
        logger.info("Mapping cache stopped")

    async def _refresh_loop(self) -> None:
        """Periodically refresh the cache."""
        while self._is_running:
            await asyncio.sleep(config.mapping_refresh_interval)
            try:
                await self._refresh_cache()
            except Exception as e:
                logger.error(f"Cache refresh error: {e}")

    async def _refresh_cache(self) -> None:
        """Load all approved mappings from Neo4j."""
        query = """
        MATCH (s:SchemaMapping {status: "approved"})
        RETURN s.rawTopic AS rawTopic,
               s.curatedTopic AS curatedTopic,
               s.payloadMappingJson AS payloadMappingJson,
               s.id AS mappingId
        """

        new_cache: dict[str, dict[str, Any]] = {}

        async with self._driver.session() as session:
            result = await session.run(query)
            async for record in result:
                raw_topic = record["rawTopic"]
                new_cache[raw_topic] = {
                    "curatedTopic": record["curatedTopic"],
                    "payloadMapping": json.loads(record["payloadMappingJson"] or "{}"),
                    "mappingId": record["mappingId"]
                }

        self._cache = new_cache
        self._last_refresh = datetime.utcnow()
        self.total_mappings = len(new_cache)
        logger.debug(f"Refreshed mapping cache: {self.total_mappings} mappings")

    def get_mapping(self, raw_topic: str) -> dict[str, Any] | None:
        """
        Get approved mapping for a raw topic.

        Returns:
            {
                "curatedTopic": str,
                "payloadMapping": dict,
                "mappingId": str
            }
            or None if no approved mapping exists.
        """
        mapping = self._cache.get(raw_topic)
        if mapping:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        return mapping

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_mappings": self.total_mappings,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None
        }
