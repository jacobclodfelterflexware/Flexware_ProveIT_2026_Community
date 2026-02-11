"""PostgreSQL client for middleware configuration tables."""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

from ..config import config

logger = logging.getLogger(__name__)


class PostgresClient:
    """Async PostgreSQL client for topic_mappings and key_transformations."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._schema = config.postgres.schema

    async def connect(self) -> None:
        """Create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=config.postgres.host,
                port=config.postgres.port,
                database=config.postgres.database,
                user=config.postgres.user,
                password=config.postgres.password,
                min_size=config.postgres.min_pool_size,
                max_size=config.postgres.max_pool_size
            )
            logger.info("PostgreSQL connection pool created")

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed")

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create the connection pool."""
        if self._pool is None:
            await self.connect()
        return self._pool

    def _row_to_dict(self, row: asyncpg.Record) -> Dict[str, Any]:
        """Convert asyncpg Record to dict with datetime serialization."""
        result = dict(row)
        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
        return result

    # =========================================================================
    # Topic Mappings CRUD
    # =========================================================================

    async def list_topic_mappings(
        self,
        source_topic_filter: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List topic mappings with optional filters.

        Args:
            source_topic_filter: LIKE pattern for source_topic
            is_active: Filter by active status
            limit: Max results
            offset: Pagination offset

        Returns:
            List of topic mapping dicts
        """
        pool = await self._get_pool()

        query = f"""
            SELECT id, source_topic, target_topic, is_active, description,
                   created_at, updated_at
            FROM {self._schema}.topic_mappings
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if source_topic_filter:
            query += f" AND source_topic LIKE ${param_idx}"
            params.append(source_topic_filter)
            param_idx += 1

        if is_active is not None:
            query += f" AND is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        rows = await pool.fetch(query, *params)
        return [self._row_to_dict(row) for row in rows]

    async def get_topic_mapping(
        self,
        id: Optional[int] = None,
        source_topic: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single topic mapping by ID or source_topic.

        Args:
            id: Mapping ID
            source_topic: Source topic path

        Returns:
            Topic mapping dict or None
        """
        pool = await self._get_pool()

        if id is not None:
            query = f"""
                SELECT id, source_topic, target_topic, is_active, description,
                       created_at, updated_at
                FROM {self._schema}.topic_mappings
                WHERE id = $1
            """
            row = await pool.fetchrow(query, id)
        elif source_topic:
            query = f"""
                SELECT id, source_topic, target_topic, is_active, description,
                       created_at, updated_at
                FROM {self._schema}.topic_mappings
                WHERE source_topic = $1
            """
            row = await pool.fetchrow(query, source_topic)
        else:
            return None

        return self._row_to_dict(row) if row else None

    async def create_topic_mapping(
        self,
        source_topic: str,
        target_topic: str,
        description: Optional[str] = None,
        is_active: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new topic mapping.

        Args:
            source_topic: Source MQTT topic
            target_topic: Target MQTT topic
            description: Human-readable description
            is_active: Whether mapping is active (default: False for HITL)

        Returns:
            Created mapping dict
        """
        pool = await self._get_pool()

        query = f"""
            INSERT INTO {self._schema}.topic_mappings
                (source_topic, target_topic, description, is_active)
            VALUES ($1, $2, $3, $4)
            RETURNING id, source_topic, target_topic, is_active, description,
                      created_at, updated_at
        """
        row = await pool.fetchrow(
            query, source_topic, target_topic, description, is_active
        )
        return self._row_to_dict(row)

    async def update_topic_mapping(
        self,
        id: Optional[int] = None,
        source_topic: Optional[str] = None,
        target_topic: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing topic mapping.

        Args:
            id: Mapping ID (or use source_topic)
            source_topic: Source topic to find mapping
            target_topic: New target topic
            description: New description
            is_active: New active status

        Returns:
            Updated mapping dict or None
        """
        pool = await self._get_pool()

        # Find the mapping first
        mapping = await self.get_topic_mapping(id=id, source_topic=source_topic)
        if not mapping:
            return None

        mapping_id = mapping["id"]

        # Build dynamic update
        updates = []
        params = []
        param_idx = 1

        if target_topic is not None:
            updates.append(f"target_topic = ${param_idx}")
            params.append(target_topic)
            param_idx += 1

        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1

        if is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if not updates:
            return mapping  # Nothing to update

        query = f"""
            UPDATE {self._schema}.topic_mappings
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING id, source_topic, target_topic, is_active, description,
                      created_at, updated_at
        """
        params.append(mapping_id)

        row = await pool.fetchrow(query, *params)
        return self._row_to_dict(row) if row else None

    async def delete_topic_mapping(
        self,
        id: Optional[int] = None,
        source_topic: Optional[str] = None
    ) -> bool:
        """
        Delete a topic mapping (cascades to key_transformations).

        Args:
            id: Mapping ID
            source_topic: Source topic to find mapping

        Returns:
            True if deleted, False if not found
        """
        pool = await self._get_pool()

        # Find the mapping first
        mapping = await self.get_topic_mapping(id=id, source_topic=source_topic)
        if not mapping:
            return False

        query = f"DELETE FROM {self._schema}.topic_mappings WHERE id = $1"
        result = await pool.execute(query, mapping["id"])
        return result == "DELETE 1"

    # =========================================================================
    # Key Transformations CRUD
    # =========================================================================

    async def list_key_transformations(
        self,
        topic_mapping_id: Optional[int] = None,
        source_topic: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        List key transformations for a topic mapping.

        Args:
            topic_mapping_id: Mapping ID
            source_topic: Source topic to find mapping
            is_active: Filter by active status

        Returns:
            List of key transformation dicts
        """
        pool = await self._get_pool()

        # Resolve mapping ID if source_topic provided
        if source_topic and not topic_mapping_id:
            mapping = await self.get_topic_mapping(source_topic=source_topic)
            if not mapping:
                return []
            topic_mapping_id = mapping["id"]

        query = f"""
            SELECT id, topic_mapping_id, source_key, target_key, json_path,
                   transform_order, is_active, created_at, updated_at
            FROM {self._schema}.key_transformations
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if topic_mapping_id:
            query += f" AND topic_mapping_id = ${param_idx}"
            params.append(topic_mapping_id)
            param_idx += 1

        if is_active is not None:
            query += f" AND is_active = ${param_idx}"
            params.append(is_active)
            param_idx += 1

        query += " ORDER BY transform_order, id"

        rows = await pool.fetch(query, *params)
        return [self._row_to_dict(row) for row in rows]

    async def get_key_transformation(
        self,
        id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single key transformation by ID.

        Args:
            id: Transformation ID

        Returns:
            Key transformation dict or None
        """
        pool = await self._get_pool()

        query = f"""
            SELECT id, topic_mapping_id, source_key, target_key, json_path,
                   transform_order, is_active, created_at, updated_at
            FROM {self._schema}.key_transformations
            WHERE id = $1
        """
        row = await pool.fetchrow(query, id)
        return self._row_to_dict(row) if row else None

    async def create_key_transformation(
        self,
        source_key: str,
        target_key: str,
        topic_mapping_id: Optional[int] = None,
        source_topic: Optional[str] = None,
        json_path: Optional[str] = None,
        transform_order: int = 0,
        is_active: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new key transformation.

        Args:
            source_key: Original key name
            target_key: New key name
            topic_mapping_id: Mapping ID (or use source_topic)
            source_topic: Source topic to find mapping
            json_path: JSON path for nested keys
            transform_order: Order of application
            is_active: Whether transformation is active

        Returns:
            Created transformation dict or None if mapping not found
        """
        pool = await self._get_pool()

        # Resolve mapping ID if source_topic provided
        if source_topic and not topic_mapping_id:
            mapping = await self.get_topic_mapping(source_topic=source_topic)
            if not mapping:
                return None
            topic_mapping_id = mapping["id"]

        if not topic_mapping_id:
            return None

        query = f"""
            INSERT INTO {self._schema}.key_transformations
                (topic_mapping_id, source_key, target_key, json_path,
                 transform_order, is_active)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, topic_mapping_id, source_key, target_key, json_path,
                      transform_order, is_active, created_at, updated_at
        """
        row = await pool.fetchrow(
            query, topic_mapping_id, source_key, target_key,
            json_path or "", transform_order, is_active
        )
        return self._row_to_dict(row) if row else None

    async def update_key_transformation(
        self,
        id: int,
        source_key: Optional[str] = None,
        target_key: Optional[str] = None,
        json_path: Optional[str] = None,
        transform_order: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing key transformation.

        Args:
            id: Transformation ID
            source_key: New source key
            target_key: New target key
            json_path: New JSON path
            transform_order: New transform order
            is_active: New active status

        Returns:
            Updated transformation dict or None
        """
        pool = await self._get_pool()

        # Check exists
        existing = await self.get_key_transformation(id)
        if not existing:
            return None

        # Build dynamic update
        updates = []
        params = []
        param_idx = 1

        if source_key is not None:
            updates.append(f"source_key = ${param_idx}")
            params.append(source_key)
            param_idx += 1

        if target_key is not None:
            updates.append(f"target_key = ${param_idx}")
            params.append(target_key)
            param_idx += 1

        if json_path is not None:
            updates.append(f"json_path = ${param_idx}")
            params.append(json_path)
            param_idx += 1

        if transform_order is not None:
            updates.append(f"transform_order = ${param_idx}")
            params.append(transform_order)
            param_idx += 1

        if is_active is not None:
            updates.append(f"is_active = ${param_idx}")
            params.append(is_active)
            param_idx += 1

        if not updates:
            return existing  # Nothing to update

        query = f"""
            UPDATE {self._schema}.key_transformations
            SET {', '.join(updates)}
            WHERE id = ${param_idx}
            RETURNING id, topic_mapping_id, source_key, target_key, json_path,
                      transform_order, is_active, created_at, updated_at
        """
        params.append(id)

        row = await pool.fetchrow(query, *params)
        return self._row_to_dict(row) if row else None

    async def delete_key_transformation(self, id: int) -> bool:
        """
        Delete a key transformation.

        Args:
            id: Transformation ID

        Returns:
            True if deleted, False if not found
        """
        pool = await self._get_pool()

        query = f"DELETE FROM {self._schema}.key_transformations WHERE id = $1"
        result = await pool.execute(query, id)
        return result == "DELETE 1"


# Global client instance
_client: Optional[PostgresClient] = None


async def get_postgres_client() -> PostgresClient:
    """Get or create the global PostgreSQL client."""
    global _client
    if _client is None:
        _client = PostgresClient()
        await _client.connect()
    return _client


async def close_postgres_client() -> None:
    """Close the global PostgreSQL client."""
    global _client
    if _client:
        await _client.close()
        _client = None
