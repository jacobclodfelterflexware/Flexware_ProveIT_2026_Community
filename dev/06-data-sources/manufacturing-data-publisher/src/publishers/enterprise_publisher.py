"""Enterprise system data publisher."""
import threading
import time
import json
import random
import logging
from typing import List
from models.enterprise_models import EnterpriseSystem, create_enterprise_systems
from utils.mqtt_client import MQTTClient
from config import Config

logger = logging.getLogger(__name__)


class EnterprisePublisher:
    """Publisher for enterprise system data."""

    def __init__(
        self,
        mqtt_client_curated: MQTTClient,
        mqtt_client_uncurated: MQTTClient
    ):
        """Initialize enterprise system publisher.

        Args:
            mqtt_client_curated: MQTT client for curated data
            mqtt_client_uncurated: MQTT client for uncurated/raw data
        """
        self.mqtt_curated = mqtt_client_curated
        self.mqtt_uncurated = mqtt_client_uncurated
        self.systems: List[EnterpriseSystem] = []
        self.running = False
        self.threads: List[threading.Thread] = []

    def initialize_systems(self):
        """Create and initialize enterprise systems."""
        logger.info(f"Initializing {Config.NUM_ENTERPRISE_SYSTEMS} enterprise systems...")
        self.systems = create_enterprise_systems(Config.NUM_ENTERPRISE_SYSTEMS)
        logger.info(f"Created {len(self.systems)} enterprise systems")

        # Log system distribution
        system_types = {}
        vendors = {}
        for system in self.systems:
            stype = system.system_type.value
            system_types[stype] = system_types.get(stype, 0) + 1
            vendors[system.vendor] = vendors.get(system.vendor, 0) + 1

        logger.info("Enterprise system distribution:")
        for stype, count in sorted(system_types.items()):
            logger.info(f"  {stype}: {count}")

        logger.info("Vendor distribution:")
        for vendor, count in sorted(vendors.items()):
            logger.info(f"  {vendor}: {count}")

    def _publish_system_loop(self, system: EnterpriseSystem):
        """Publishing loop for a single enterprise system.

        Args:
            system: Enterprise system to publish data for
        """
        publish_interval = random.uniform(
            Config.ENTERPRISE_PUBLISH_INTERVAL_MIN,
            Config.ENTERPRISE_PUBLISH_INTERVAL_MAX
        )

        logger.info(
            f"Starting publisher for {system.system_id} ({system.vendor}) "
            f"(interval: {publish_interval:.1f}s, UNS: {system.use_uns_topic})"
        )

        while self.running:
            try:
                # Update system data
                system.update_data()

                # Get data
                system_data = system.get_data()

                # Generate topic
                data_topic = system.get_mqtt_topic("data", Config.ENTERPRISE)
                status_topic = system.get_mqtt_topic("status", Config.ENTERPRISE)

                # Convert to JSON
                data_json = json.dumps(system_data)

                # Status data (simplified)
                status_data = {
                    "timestamp": system_data["timestamp"],
                    "system_id": system.system_id,
                    "cpu_usage": system_data["cpu_usage"],
                    "memory_usage": system_data["memory_usage"],
                    "response_time_ms": system_data["response_time_ms"],
                    "active_connections": system_data["active_connections"]
                }
                status_json = json.dumps(status_data)

                # Publish to uncurated broker only
                # Curated data flows through the curated-republisher pipeline
                # which validates and transforms data based on approved mappings
                self.mqtt_uncurated.publish(data_topic, data_json)
                self.mqtt_uncurated.publish(status_topic, status_json)

                # Publish system-specific metrics to uncurated for detailed monitoring
                if random.random() < 0.2:  # 20% of the time
                    # Publish health metrics individually
                    for metric in ["cpu_usage", "memory_usage", "response_time_ms"]:
                        metric_topic = system.get_mqtt_topic(metric, Config.ENTERPRISE)
                        metric_value = {
                            "timestamp": system_data["timestamp"],
                            "system_id": system.system_id,
                            "value": system_data[metric]
                        }
                        self.mqtt_uncurated.publish(
                            metric_topic,
                            json.dumps(metric_value)
                        )

                # Sleep until next publish
                time.sleep(publish_interval)

            except Exception as e:
                logger.error(f"Error publishing data for {system.system_id}: {e}")
                time.sleep(5)  # Brief pause before retrying

    def start(self):
        """Start publishing enterprise system data."""
        if self.running:
            logger.warning("Enterprise publisher already running")
            return

        self.running = True
        logger.info("Starting enterprise system publishers...")

        # Create a thread for each system
        for system in self.systems:
            thread = threading.Thread(
                target=self._publish_system_loop,
                args=(system,),
                daemon=True,
                name=f"System-{system.system_id}"
            )
            thread.start()
            self.threads.append(thread)

        logger.info(f"Started {len(self.threads)} enterprise system publisher threads")

    def stop(self):
        """Stop publishing enterprise system data."""
        logger.info("Stopping enterprise system publishers...")
        self.running = False

        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)

        self.threads.clear()
        logger.info("Enterprise system publishers stopped")

    def get_stats(self):
        """Get publisher statistics.

        Returns:
            Dictionary with publisher stats
        """
        system_types = {}
        for system in self.systems:
            stype = system.system_type.value
            system_types[stype] = system_types.get(stype, 0) + 1

        return {
            "total_systems": len(self.systems),
            "active_threads": len([t for t in self.threads if t.is_alive()]),
            "system_type_distribution": system_types,
            "uncurated_connected": self.mqtt_uncurated.is_connected() if self.mqtt_uncurated else False
        }
