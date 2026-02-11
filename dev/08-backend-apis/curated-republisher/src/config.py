"""Curated Republisher configuration."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Curated Republisher configuration."""

    # MQTT Uncurated Broker (source)
    mqtt_uncurated_host: str = os.getenv(
        "MQTT_BROKER_UNCURATED_HOST",
        "YOUR_MQTT_UNCURATED_HOST"
    )
    mqtt_uncurated_port: int = int(os.getenv("MQTT_BROKER_UNCURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Curated Broker (target)
    mqtt_curated_host: str = os.getenv(
        "MQTT_BROKER_CURATED_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    mqtt_curated_port: int = int(os.getenv("MQTT_BROKER_CURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Auth (shared)
    mqtt_username: str = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")
    mqtt_qos: int = int(os.getenv("MQTT_QOS", "1"))

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASS", "YOUR_DB_PASSWORD")

    # Embedding
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Caching
    mapping_cache_ttl_seconds: int = int(os.getenv("MAPPING_CACHE_TTL", "60"))
    mapping_refresh_interval: int = int(os.getenv("MAPPING_REFRESH_INTERVAL", "30"))

    # Server
    health_port: int = int(os.getenv("HEALTH_PORT", "YOUR_API_PORT"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Performance
    write_to_neo4j: bool = os.getenv("WRITE_TO_NEO4J", "true").lower() == "true"
    create_lineage: bool = os.getenv("CREATE_LINEAGE", "true").lower() == "true"


config = Config()
