"""VirtualFactory2.0 Publisher configuration."""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """VirtualFactory2.0 Publisher configuration."""

    # MQTT Curated Broker (source and target)
    mqtt_host: str = os.getenv(
        "MQTT_BROKER_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    mqtt_port: int = int(os.getenv("MQTT_BROKER_PORT", "YOUR_MQTT_PORT"))
    mqtt_username: str = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")
    mqtt_qos: int = int(os.getenv("MQTT_QOS", "1"))

    # EMQX REST API
    emqx_api_host: str = os.getenv(
        "EMQX_API_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    emqx_api_port: int = int(os.getenv("EMQX_API_PORT", "YOUR_EMQX_DASHBOARD_PORT"))
    emqx_api_key: str = os.getenv("EMQX_API_KEY", "")
    emqx_api_secret: str = os.getenv("EMQX_API_SECRET", "")

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASS", "YOUR_DB_PASSWORD")

    # Topic prefix
    topic_prefix: str = os.getenv("TOPIC_PREFIX", "VirtualFactory2.0")

    # Polling intervals (seconds)
    chat_poll_interval: int = int(os.getenv("CHAT_POLL_INTERVAL", "30"))
    ml_poll_interval: int = int(os.getenv("ML_POLL_INTERVAL", "300"))
    topic_poll_interval: int = int(os.getenv("TOPIC_POLL_INTERVAL", "120"))
    machine_poll_interval: int = int(os.getenv("MACHINE_POLL_INTERVAL", "60"))
    ladder_poll_interval: int = int(os.getenv("LADDER_POLL_INTERVAL", "60"))
    k8s_poll_interval: int = int(os.getenv("K8S_POLL_INTERVAL", "30"))
    broker_poll_interval: int = int(os.getenv("BROKER_POLL_INTERVAL", "30"))

    # Server
    health_port: int = int(os.getenv("HEALTH_PORT", "YOUR_API_PORT"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
