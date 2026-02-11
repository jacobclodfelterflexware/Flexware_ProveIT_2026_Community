"""Configuration management for PLCopen XML API."""
import os


class Config:
    """Application configuration."""

    # API Configuration
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "YOUR_API_PORT"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # XML Validation
    VALIDATE_SCHEMA = os.getenv("VALIDATE_SCHEMA", "false").lower() == "true"
    MAX_XML_SIZE_MB = int(os.getenv("MAX_XML_SIZE_MB", "10"))

    # PLCopen namespace
    PLCOPEN_NAMESPACE = "http://www.plcopen.org/xml/tc6_0201"

    @classmethod
    def display(cls):
        """Display current configuration."""
        print("=" * 60)
        print("PLCopen XML API Configuration")
        print("=" * 60)
        print(f"API: {cls.API_HOST}:{cls.API_PORT}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print(f"Schema Validation: {cls.VALIDATE_SCHEMA}")
        print(f"Max XML Size: {cls.MAX_XML_SIZE_MB} MB")
        print("=" * 60)
