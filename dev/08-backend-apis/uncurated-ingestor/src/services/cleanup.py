import asyncio
import logging

from neo4j import AsyncGraphDatabase

from config import config

logger = logging.getLogger(__name__)


class CleanupService:
    """Periodically deletes old uncurated messages to enforce retention."""

    def __init__(self):
        self._driver = None
        self._task: asyncio.Task | None = None
        self._is_running = False
        self.total_deleted = 0

    async def start(self) -> None:
        """Start the cleanup service."""
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        self._is_running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(
            f"Cleanup service started. "
            f"Retention: {config.message_retention_hours}h, "
            f"Interval: {config.cleanup_interval_minutes}m"
        )

    async def stop(self) -> None:
        """Stop the cleanup service."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._driver:
            await self._driver.close()
        logger.info("Cleanup service stopped")

    async def _cleanup_loop(self) -> None:
        """Periodically run cleanup."""
        while self._is_running:
            try:
                await self._run_cleanup()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

            await asyncio.sleep(config.cleanup_interval_minutes * 60)

    async def _run_cleanup(self) -> None:
        """Delete messages older than retention period."""
        query = """
        MATCH (m:Message)
        WHERE m.timestamp < datetime() - duration({hours: $hours})
        WITH m LIMIT 1000
        DETACH DELETE m
        RETURN count(m) AS deleted
        """

        total_deleted_batch = 0
        async with self._driver.session() as session:
            while True:
                result = await session.run(
                    query,
                    hours=config.message_retention_hours
                )
                record = await result.single()
                deleted = record["deleted"] if record else 0

                if deleted == 0:
                    break

                total_deleted_batch += deleted
                self.total_deleted += deleted
                logger.debug(f"Deleted {deleted} old messages")

        if total_deleted_batch > 0:
            logger.info(
                f"Cleanup completed: deleted {total_deleted_batch} messages "
                f"older than {config.message_retention_hours}h"
            )

    def get_stats(self) -> dict:
        """Get cleanup statistics."""
        return {
            "total_deleted": self.total_deleted,
            "retention_hours": config.message_retention_hours
        }
