"""Schema Advisor configuration."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Schema Advisor configuration."""

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "YOUR_OPENAI_MODEL")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))

    # MCP Server
    mcp_url: str = os.getenv(
        "MCP_URL",
        "http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT"
    )

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASS", "YOUR_DB_PASSWORD")

    # Server
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "YOUR_API_PORT"))

    # Limits
    similar_topics_k: int = int(os.getenv("SIMILAR_TOPICS_K", "20"))
    similar_messages_k: int = int(os.getenv("SIMILAR_MESSAGES_K", "50"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
