"""HITL API configuration."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """HITL API configuration."""

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASS", "YOUR_DB_PASSWORD")

    # Schema Advisor URL (to trigger suggestions)
    schema_advisor_url: str = os.getenv(
        "SCHEMA_ADVISOR_URL",
        "http://YOUR_SCHEMA_ADVISOR_HOST:YOUR_API_PORT"
    )

    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "YOUR_API_PORT"))

    # CORS
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
