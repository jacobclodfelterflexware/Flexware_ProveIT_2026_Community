import os
from dataclasses import dataclass


@dataclass
class Config:
    """Service configuration from environment."""

    # MQTT Uncurated Broker
    mqtt_host: str = os.getenv(
        "MQTT_BROKER_UNCURATED_HOST",
        "YOUR_MQTT_UNCURATED_HOST"
    )
    mqtt_port: int = int(os.getenv("MQTT_BROKER_UNCURATED_PORT", "YOUR_MQTT_PORT"))
    mqtt_username: str = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")
    mqtt_client_id: str = os.getenv("MQTT_CLIENT_ID", "uncurated-ingestor")
    mqtt_qos: int = int(os.getenv("MQTT_QOS", "1"))

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASS", "YOUR_DB_PASSWORD")

    # Embedding
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Retention
    message_retention_hours: int = int(os.getenv("MESSAGE_RETENTION_HOURS", "1"))
    cleanup_interval_minutes: int = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "5"))

    # Service
    health_port: int = int(os.getenv("HEALTH_PORT", "YOUR_API_PORT"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Performance
    batch_size: int = int(os.getenv("BATCH_SIZE", "10"))
    batch_timeout_ms: int = int(os.getenv("BATCH_TIMEOUT_MS", "100"))

    # Conformance checking
    binding_cache_refresh_seconds: int = int(os.getenv("BINDING_CACHE_REFRESH_SECONDS", "30"))
    conformance_enabled: bool = os.getenv("CONFORMANCE_ENABLED", "true").lower() == "true"

    # Broker identification (for Neo4j relationships)
    broker_name: str = os.getenv("BROKER_NAME", "uncurated")


config = Config()
