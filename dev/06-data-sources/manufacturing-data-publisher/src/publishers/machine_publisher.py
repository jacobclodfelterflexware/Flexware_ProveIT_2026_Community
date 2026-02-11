"""Machine asset data publisher."""
import threading
import time
import json
import random
import logging
from typing import List
from models.machine_models import MachineAsset, create_machine_fleet
from utils.mqtt_client import MQTTClient
from config import Config

logger = logging.getLogger(__name__)


class MachinePublisher:
    """Publisher for machine asset telemetry data."""

    def __init__(
        self,
        mqtt_client_curated: MQTTClient,
        mqtt_client_uncurated: MQTTClient
    ):
        """Initialize machine publisher.

        Args:
            mqtt_client_curated: MQTT client for curated data
            mqtt_client_uncurated: MQTT client for uncurated/raw data
        """
        self.mqtt_curated = mqtt_client_curated
        self.mqtt_uncurated = mqtt_client_uncurated
        self.machines: List[MachineAsset] = []
        self.running = False
        self.threads: List[threading.Thread] = []

    def initialize_machines(self):
        """Create and initialize machine fleet."""
        logger.info(f"Initializing {Config.NUM_MACHINES} machine assets...")
        self.machines = create_machine_fleet(Config.NUM_MACHINES)
        logger.info(f"Created {len(self.machines)} machines")

        # Log machine distribution
        machine_types = {}
        for machine in self.machines:
            mtype = machine.machine_type.value
            machine_types[mtype] = machine_types.get(mtype, 0) + 1

        logger.info("Machine distribution:")
        for mtype, count in sorted(machine_types.items()):
            logger.info(f"  {mtype}: {count}")

    def _publish_machine_loop(self, machine: MachineAsset):
        """Publishing loop for a single machine.

        Args:
            machine: Machine asset to publish data for
        """
        publish_interval = random.uniform(
            Config.MACHINE_PUBLISH_INTERVAL_MIN,
            Config.MACHINE_PUBLISH_INTERVAL_MAX
        )

        logger.info(
            f"Starting publisher for {machine.asset_id} "
            f"(interval: {publish_interval:.1f}s, UNS: {machine.use_uns_topic})"
        )

        while self.running:
            try:
                # Update machine state and telemetry
                machine.update_state()
                machine.update_telemetry()

                # Get data
                telemetry_data = machine.get_telemetry_data()
                state_data = machine.get_state_data()

                # Generate topics
                telemetry_topic = machine.get_mqtt_topic(
                    "telemetry",
                    Config.ENTERPRISE,
                    Config.SITE
                )
                state_topic = machine.get_mqtt_topic(
                    "state",
                    Config.ENTERPRISE,
                    Config.SITE
                )

                # Convert to JSON
                telemetry_json = json.dumps(telemetry_data)
                state_json = json.dumps(state_data)

                # Publish to uncurated broker only
                # Curated data flows through the curated-republisher pipeline
                # which validates and transforms data based on approved mappings
                self.mqtt_uncurated.publish(telemetry_topic, telemetry_json)
                self.mqtt_uncurated.publish(state_topic, state_json)

                # Also publish individual metrics to uncurated for granular access
                if random.random() < 0.3:  # 30% of the time, publish individual metrics
                    for metric_name in ["temperature", "vibration", "speed", "power_consumption"]:
                        metric_topic = machine.get_mqtt_topic(
                            metric_name,
                            Config.ENTERPRISE,
                            Config.SITE
                        )
                        metric_value = {
                            "timestamp": telemetry_data["timestamp"],
                            "asset_id": machine.asset_id,
                            "value": telemetry_data[metric_name]
                        }
                        self.mqtt_uncurated.publish(
                            metric_topic,
                            json.dumps(metric_value)
                        )

                # Sleep until next publish
                time.sleep(publish_interval)

            except Exception as e:
                logger.error(f"Error publishing data for {machine.asset_id}: {e}")
                time.sleep(5)  # Brief pause before retrying

    def start(self):
        """Start publishing machine data."""
        if self.running:
            logger.warning("Machine publisher already running")
            return

        self.running = True
        logger.info("Starting machine data publishers...")

        # Create a thread for each machine
        for machine in self.machines:
            thread = threading.Thread(
                target=self._publish_machine_loop,
                args=(machine,),
                daemon=True,
                name=f"Machine-{machine.asset_id}"
            )
            thread.start()
            self.threads.append(thread)

        logger.info(f"Started {len(self.threads)} machine publisher threads")

    def stop(self):
        """Stop publishing machine data."""
        logger.info("Stopping machine publishers...")
        self.running = False

        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)

        self.threads.clear()
        logger.info("Machine publishers stopped")

    def get_stats(self):
        """Get publisher statistics.

        Returns:
            Dictionary with publisher stats
        """
        state_counts = {}
        for machine in self.machines:
            state = machine.state.value
            state_counts[state] = state_counts.get(state, 0) + 1

        return {
            "total_machines": len(self.machines),
            "active_threads": len([t for t in self.threads if t.is_alive()]),
            "state_distribution": state_counts,
            "uncurated_connected": self.mqtt_uncurated.is_connected() if self.mqtt_uncurated else False
        }
