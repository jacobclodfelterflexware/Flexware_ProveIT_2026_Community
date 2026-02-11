"""In-memory cache for topic mappings with PostgreSQL LISTEN/NOTIFY sync."""
import asyncio
import json
import logging
import os
from typing import Dict, Optional, List, Any
from datetime import datetime

import asyncpg
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from database import async_session, TopicMapping, UnmappedTopic

logger = logging.getLogger(__name__)


class MappingCache:
    """Caches topic mappings with real-time PostgreSQL notifications."""

    def __init__(self):
        self._mappings: Dict[str, dict] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._pg_conn: Optional[asyncpg.Connection] = None
        self.is_ready = False
        self._stats = {
            "messages_processed": 0,
            "messages_transformed": 0,
            "messages_dropped": 0,
        }

    async def start(self) -> None:
        """Start the cache and listen for changes."""
        await self._load_mappings()
        self._listen_task = asyncio.create_task(self._listen_for_changes())
        self.is_ready = True
        logger.info("Mapping cache started")

    async def stop(self) -> None:
        """Stop listening and clean up."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pg_conn:
            await self._pg_conn.close()
        self.is_ready = False
        logger.info("Mapping cache stopped")

    async def _load_mappings(self) -> None:
        """Load all active mappings from database."""
        async with async_session() as session:
            query = (
                select(TopicMapping)
                .where(TopicMapping.is_active == True)
                .options(selectinload(TopicMapping.key_transformations))
            )
            result = await session.execute(query)
            mappings = result.scalars().all()

            self._mappings.clear()
            for mapping in mappings:
                self._mappings[mapping.source_topic] = {
                    "id": mapping.id,
                    "target_topic": mapping.target_topic,
                    "is_active": mapping.is_active,
                    "key_transformations": [
                        {
                            "source_key": kt.source_key,
                            "target_key": kt.target_key,
                            "json_path": kt.json_path,
                            "transform_order": kt.transform_order,
                            "is_active": kt.is_active,
                        }
                        for kt in mapping.key_transformations
                        if kt.is_active
                    ],
                }

        logger.info(f"Loaded {len(self._mappings)} topic mappings into cache")

    async def _listen_for_changes(self) -> None:
        """Listen for PostgreSQL notifications."""
        # Get DB config from environment
        db_user = os.getenv("DB_USER", "YOUR_DB_USERNAME")
        db_password = os.getenv("DB_PASSWORD", "YOUR_DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "YOUR_POSTGRES_HOST")
        db_port = os.getenv("DB_PORT", "YOUR_POSTGRES_PORT")
        db_name = os.getenv("DB_NAME", "postgres")

        while True:
            try:
                # Build connection string for asyncpg
                conn_str = (
                    f"postgresql://{db_user}:{db_password}"
                    f"@{db_host}:{db_port}/{db_name}"
                )
                self._pg_conn = await asyncpg.connect(conn_str)

                # Add listener for mapping changes
                await self._pg_conn.add_listener(
                    "mapping_changes",
                    self._on_notification,
                )
                logger.info("Listening for mapping changes on PostgreSQL")

                # Keep connection alive with periodic pings
                while True:
                    await asyncio.sleep(30)
                    try:
                        await self._pg_conn.execute("SELECT 1")
                    except Exception:
                        break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Listen error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    def _on_notification(
        self,
        conn: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Handle PostgreSQL notification."""
        logger.info(f"Received notification on {channel}: {payload}")
        # Schedule reload (non-blocking)
        asyncio.create_task(self._load_mappings())

    def get_mapping(self, source_topic: str) -> Optional[dict]:
        """Get mapping for a source topic."""
        return self._mappings.get(source_topic)

    def get_all_mappings(self) -> Dict[str, dict]:
        """Get all cached mappings."""
        return self._mappings.copy()

    async def track_unmapped(self, topic: str, sample_payload: str) -> None:
        """Track an unmapped topic in the database."""
        self._stats["messages_dropped"] += 1

        try:
            async with async_session() as session:
                # Check if already exists
                result = await session.execute(
                    select(UnmappedTopic).where(UnmappedTopic.topic == topic)
                )
                unmapped = result.scalar_one_or_none()

                if unmapped:
                    # Update existing
                    unmapped.message_count += 1
                    unmapped.last_seen = datetime.utcnow()
                else:
                    # Parse sample payload
                    try:
                        sample = json.loads(sample_payload) if sample_payload else None
                    except json.JSONDecodeError:
                        sample = {"raw": sample_payload[:500] if sample_payload else None}

                    # Create new
                    unmapped = UnmappedTopic(
                        topic=topic,
                        sample_payload=sample,
                    )
                    session.add(unmapped)

                await session.commit()
        except Exception as e:
            logger.error(f"Error tracking unmapped topic {topic}: {e}")

    def record_transformed(self) -> None:
        """Record a successfully transformed message."""
        self._stats["messages_processed"] += 1
        self._stats["messages_transformed"] += 1

    def record_processed(self) -> None:
        """Record a processed message (may or may not be transformed)."""
        self._stats["messages_processed"] += 1

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "total_mappings": len(self._mappings),
            "active_mappings": sum(
                1 for m in self._mappings.values() if m.get("is_active", True)
            ),
            "total_transformations": sum(
                len(m.get("key_transformations", []))
                for m in self._mappings.values()
            ),
            **self._stats,
        }

    async def get_full_stats(self) -> dict:
        """Get full statistics including database counts."""
        stats = self.get_stats()

        try:
            async with async_session() as session:
                # Count unmapped topics
                result = await session.execute(
                    select(func.count()).select_from(UnmappedTopic)
                )
                stats["unmapped_topics"] = result.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting full stats: {e}")
            stats["unmapped_topics"] = 0

        return stats
