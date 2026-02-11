"""Configuration for MCP Server."""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IngestorConfig:
    """Configuration for the uncurated-ingestor API client."""
    url: str = field(
        default_factory=lambda: os.getenv(
            "INGESTOR_URL",
            "http://unYOUR_CURATED_INGESTOR_HOST:YOUR_API_PORT"
        )
    )
    timeout: float = field(
        default_factory=lambda: float(os.getenv("INGESTOR_TIMEOUT", "30.0"))
    )


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL connection."""
    host: str = field(
        default_factory=lambda: os.getenv(
            "POSTGRES_HOST",
            "YOUR_K8S_SERVICE_HOST"
        )
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_PORT", "YOUR_POSTGRES_PORT"))
    )
    database: str = field(
        default_factory=lambda: os.getenv("POSTGRES_DB", "middleware")
    )
    user: str = field(
        default_factory=lambda: os.getenv("POSTGRES_USER", "middleware")
    )
    password: str = field(
        default_factory=lambda: os.getenv("POSTGRES_PASS", "")
    )
    schema: str = field(
        default_factory=lambda: os.getenv("POSTGRES_SCHEMA", "middleware")
    )
    min_pool_size: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_MIN_POOL", "2"))
    )
    max_pool_size: int = field(
        default_factory=lambda: int(os.getenv("POSTGRES_MAX_POOL", "10"))
    )

    @property
    def dsn(self) -> str:
        """Return PostgreSQL connection string."""
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
        )


@dataclass
class ServerConfig:
    """Configuration for the MCP server itself."""
    host: str = field(
        default_factory=lambda: os.getenv("MCP_HOST", "0.0.0.0")
    )
    port: int = field(
        default_factory=lambda: int(os.getenv("MCP_PORT", "YOUR_API_PORT"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )


@dataclass
class Config:
    """Main configuration container."""
    ingestor: IngestorConfig = field(default_factory=IngestorConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


# Global config instance
config = Config()
