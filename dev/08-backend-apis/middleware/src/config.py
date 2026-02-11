"""Configuration management for MQTT middleware application."""
import os


class Config:
    """Application configuration."""

    # MQTT Broker Configuration - Uncurated (source)
    MQTT_BROKER_UNCURATED_HOST = os.getenv(
        "MQTT_BROKER_UNCURATED_HOST",
        "YOUR_MQTT_UNCURATED_HOST"
    )
    MQTT_BROKER_UNCURATED_PORT = int(os.getenv("MQTT_BROKER_UNCURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Broker Configuration - Curated (target)
    MQTT_BROKER_CURATED_HOST = os.getenv(
        "MQTT_BROKER_CURATED_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    MQTT_BROKER_CURATED_PORT = int(os.getenv("MQTT_BROKER_CURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Authentication
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

    # PostgreSQL Configuration
    DB_HOST = os.getenv("DB_HOST", "YOUR_POSTGRES_HOST")
    DB_PORT = int(os.getenv("DB_PORT", "YOUR_POSTGRES_PORT"))
    DB_NAME = os.getenv("DB_NAME", "postgres")
    DB_USER = os.getenv("DB_USER", "YOUR_DB_USERNAME")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "YOUR_DB_PASSWORD")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "middleware")

    # Application Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "YOUR_API_PORT"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # SSE Configuration
    SSE_UPDATE_INTERVAL = float(os.getenv("SSE_UPDATE_INTERVAL", "2.0"))

    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    @classmethod
    def get_database_url(cls) -> str:
        """Get async database URL for SQLAlchemy."""
        return f"postgresql+asyncpg://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def get_sync_database_url(cls) -> str:
        """Get sync database URL for asyncpg LISTEN/NOTIFY."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def display(cls):
        """Display current configuration."""
        print("=" * 60)
        print("MQTT Middleware Configuration")
        print("=" * 60)
        print(f"Uncurated Broker: {cls.MQTT_BROKER_UNCURATED_HOST}:{cls.MQTT_BROKER_UNCURATED_PORT}")
        print(f"Curated Broker: {cls.MQTT_BROKER_CURATED_HOST}:{cls.MQTT_BROKER_CURATED_PORT}")
        print(f"MQTT Username: {cls.MQTT_USERNAME}")
        print(f"Database: {cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}")
        print(f"Database Schema: {cls.DB_SCHEMA}")
        print(f"API: {cls.API_HOST}:{cls.API_PORT}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print("=" * 60)
