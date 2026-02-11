"""Configuration for ML Predictor service."""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Neo4j connection
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT")
    neo4j_user: str = os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "YOUR_DB_PASSWORD")

    # Machine Simulator API (to fetch machine definitions)
    machine_simulator_url: str = os.getenv(
        "MACHINE_SIMULATOR_URL",
        "http://YOUR_MACHINE_SIMULATOR_HOST:YOUR_API_PORT_3"
    )

    # OpenAI settings for view transform generation
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # AutoGluon settings
    training_time_limit: int = int(os.getenv("TRAINING_TIME_LIMIT", "300"))  # 5 minutes
    prediction_horizon_day: int = 48  # 30-minute intervals in a day
    prediction_horizon_week: int = 7  # days
    prediction_horizon_month: int = 30  # days

    # Data settings
    min_data_points: int = int(os.getenv("MIN_DATA_POINTS", "30"))  # Minimum days of data for training
    points_per_day: int = int(os.getenv("POINTS_PER_DAY", "5"))  # Expected data points per day

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
