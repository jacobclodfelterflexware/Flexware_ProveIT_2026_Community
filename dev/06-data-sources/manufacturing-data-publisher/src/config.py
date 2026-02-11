"""Configuration management for manufacturing data publisher."""
import os


class Config:
    """Application configuration."""

    # MQTT Broker Configuration - Curated
    MQTT_BROKER_CURATED_HOST = os.getenv(
        "MQTT_BROKER_CURATED_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    MQTT_BROKER_CURATED_PORT = int(os.getenv("MQTT_BROKER_CURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Broker Configuration - Uncurated
    MQTT_BROKER_UNCURATED_HOST = os.getenv(
        "MQTT_BROKER_UNCURATED_HOST",
        "YOUR_MQTT_UNCURATED_HOST"
    )
    MQTT_BROKER_UNCURATED_PORT = int(os.getenv("MQTT_BROKER_UNCURATED_PORT", "YOUR_MQTT_PORT"))

    # MQTT Authentication
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")

    # MQTT QoS
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

    # Health Check Configuration
    HEALTH_CHECK_PORT = int(os.getenv("HEALTH_CHECK_PORT", "YOUR_API_PORT_2"))

    # Publishing Configuration
    MACHINE_PUBLISH_INTERVAL_MIN = float(os.getenv("MACHINE_PUBLISH_INTERVAL_MIN", "1.0"))
    MACHINE_PUBLISH_INTERVAL_MAX = float(os.getenv("MACHINE_PUBLISH_INTERVAL_MAX", "10.0"))
    ENTERPRISE_PUBLISH_INTERVAL_MIN = float(os.getenv("ENTERPRISE_PUBLISH_INTERVAL_MIN", "5.0"))
    ENTERPRISE_PUBLISH_INTERVAL_MAX = float(os.getenv("ENTERPRISE_PUBLISH_INTERVAL_MAX", "60.0"))

    # Asset Configuration
    NUM_MACHINES = int(os.getenv("NUM_MACHINES", "100"))
    NUM_ENTERPRISE_SYSTEMS = int(os.getenv("NUM_ENTERPRISE_SYSTEMS", "50"))

    # ISA-95 Hierarchy for UNS topics
    ENTERPRISE = os.getenv("ENTERPRISE", "acme-manufacturing")
    SITE = os.getenv("SITE", "plant-01")

    @classmethod
    def display(cls):
        """Display current configuration."""
        print("=" * 60)
        print("Manufacturing Data Publisher Configuration")
        print("=" * 60)
        print(f"Curated Broker: {cls.MQTT_BROKER_CURATED_HOST}:{cls.MQTT_BROKER_CURATED_PORT}")
        print(f"Uncurated Broker: {cls.MQTT_BROKER_UNCURATED_HOST}:{cls.MQTT_BROKER_UNCURATED_PORT}")
        print(f"MQTT Username: {cls.MQTT_USERNAME}")
        print(f"Health Check Port: {cls.HEALTH_CHECK_PORT}")
        print(f"Number of Machines: {cls.NUM_MACHINES}")
        print(f"Number of Enterprise Systems: {cls.NUM_ENTERPRISE_SYSTEMS}")
        print(f"Machine Publish Interval: {cls.MACHINE_PUBLISH_INTERVAL_MIN}s - {cls.MACHINE_PUBLISH_INTERVAL_MAX}s")
        print(f"Enterprise Publish Interval: {cls.ENTERPRISE_PUBLISH_INTERVAL_MIN}s - {cls.ENTERPRISE_PUBLISH_INTERVAL_MAX}s")
        print(f"UNS Hierarchy: {cls.ENTERPRISE}/{cls.SITE}")
        print("=" * 60)
