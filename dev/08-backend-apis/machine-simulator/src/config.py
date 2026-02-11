"""Configuration for machine-simulator service."""

import os


class Config:
    """Application configuration from environment variables."""

    # Service
    service_name: str = "machine-simulator"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "YOUR_API_PORT"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Neo4j
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "YOUR_DB_PASSWORD")

    # MQTT - Curated Broker (where we publish)
    mqtt_host: str = os.getenv("MQTT_HOST", "YOUR_MQTT_CURATED_HOST")
    mqtt_port: int = int(os.getenv("MQTT_PORT", "YOUR_MQTT_PORT"))
    mqtt_username: str = os.getenv("MQTT_USERNAME", "")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "")
    mqtt_client_id: str = os.getenv("MQTT_CLIENT_ID", "machine-simulator")

    # LLM (OpenAI)
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))

    # OpenAI (Image Generation)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    image_model: str = os.getenv("IMAGE_MODEL", "dall-e-3")
    image_size: str = os.getenv("IMAGE_SIZE", "1024x1024")

    # Ingestor API (for semantic similarity)
    ingestor_url: str = os.getenv("INGESTOR_URL", "http://unYOUR_CURATED_INGESTOR_HOST:YOUR_API_PORT")

    # Similarity thresholds
    schema_similarity_threshold: float = float(os.getenv("SCHEMA_SIMILARITY_THRESHOLD", "0.5"))

    # Default publishing settings
    default_publish_interval_ms: int = int(os.getenv("DEFAULT_PUBLISH_INTERVAL_MS", "5000"))
    min_publish_interval_ms: int = int(os.getenv("MIN_PUBLISH_INTERVAL_MS", "1000"))
    max_publish_interval_ms: int = int(os.getenv("MAX_PUBLISH_INTERVAL_MS", "60000"))

    # SparkMES settings
    sparkmes_topic_suffix: str = os.getenv("SPARKMES_TOPIC_SUFFIX", "sparkmes")
    sparkmes_default_cycle_time: float = float(os.getenv("SPARKMES_CYCLE_TIME", "30.0"))
    sparkmes_default_scrap_rate: float = float(os.getenv("SPARKMES_SCRAP_RATE", "0.01"))


config = Config()
