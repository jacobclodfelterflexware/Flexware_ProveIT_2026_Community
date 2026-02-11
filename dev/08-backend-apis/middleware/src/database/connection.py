"""Database connection management."""
import logging
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base


class Config:
    """Minimal config for database connection."""

    DB_HOST = os.getenv("DB_HOST", "YOUR_POSTGRES_HOST")
    DB_PORT = int(os.getenv("DB_PORT", "YOUR_POSTGRES_PORT"))
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "YOUR_DB_USERNAME")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "YOUR_DB_PASSWORD")

    @classmethod
    def get_database_url(cls) -> str:
        """Get async database URL for SQLAlchemy."""
        return f"postgresql+asyncpg://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    Config.get_database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for ORM models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection."""
    logger.info(f"Connecting to database at {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    # Test connection
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: None)
    logger.info("Database connection established")


async def close_db() -> None:
    """Close database connection."""
    await engine.dispose()
    logger.info("Database connection closed")
