"""Database connection management."""

import logging
from neo4j import AsyncGraphDatabase

from src.config import get_settings

logger = logging.getLogger(__name__)

# Global Neo4j driver
_neo4j_driver = None


async def init_neo4j():
    """Initialize the Neo4j driver."""
    global _neo4j_driver
    settings = get_settings()

    logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}")
    _neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    # Verify connection
    try:
        async with _neo4j_driver.session() as session:
            result = await session.run("RETURN 1 as n")
            await result.single()
        logger.info("Neo4j connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")


async def close_neo4j():
    """Close the Neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver:
        await _neo4j_driver.close()
        logger.info("Neo4j connection closed")
        _neo4j_driver = None


def get_neo4j_driver():
    """Get the Neo4j driver instance."""
    return _neo4j_driver
