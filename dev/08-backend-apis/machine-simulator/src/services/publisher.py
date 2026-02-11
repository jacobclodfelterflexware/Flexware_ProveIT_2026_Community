"""MQTT Publisher service for simulated machines."""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional

import paho.mqtt.client as mqtt

from ..config import config
from ..models import MachineDefinition, MachineStatus, TopicDefinition, FieldDefinition
from .formula_engine import formula_engine
from .sparkmes_generator import sparkmes_generator

logger = logging.getLogger(__name__)


class MachinePublisher:
    """Service for publishing simulated machine data to MQTT."""

    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._running_machines: Dict[str, asyncio.Task] = {}
        self._machine_stats: Dict[str, dict] = {}

    def _ensure_connected(self):
        """Ensure MQTT client is connected."""
        logger.info(f"_ensure_connected called: client={self._client is not None}, connected={self._connected}")

        if self._client is None or not self._connected:
            client_id = f"machine-simulator-{int(time.time())}"
            logger.info(f"Creating new MQTT client with id: {client_id}")

            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
                protocol=mqtt.MQTTv5
            )

            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect

            logger.info(f"Connecting to MQTT broker at {config.mqtt_host}:{config.mqtt_port}")
            try:
                self._client.connect(config.mqtt_host, config.mqtt_port, keepalive=60)
                logger.info("MQTT connect() called successfully, starting loop...")
            except Exception as e:
                logger.error(f"MQTT connect() failed with exception: {e}")
                raise

            self._client.loop_start()
            logger.info("MQTT loop_start() called, waiting for connection callback...")

            # Wait for connection
            for i in range(50):  # 5 second timeout
                if self._connected:
                    logger.info(f"Connection confirmed after {i * 0.1:.1f}s")
                    break
                time.sleep(0.1)

            if not self._connected:
                logger.error(f"MQTT connection timeout after 5s - connected={self._connected}")
                raise RuntimeError("Failed to connect to MQTT broker")
        else:
            logger.info("Already connected to MQTT broker, reusing connection")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """Handle MQTT connection."""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self._connected = True
        else:
            logger.error(f"MQTT connection failed: {reason_code}")

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        """Handle MQTT disconnection."""
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")
        self._connected = False

    def _generate_payload_for_fields(self, fields: list[FieldDefinition], iteration: int, t: float) -> dict:
        """Generate a payload for a list of field definitions."""
        payload = {}

        for field in fields:
            try:
                value = formula_engine.generate_value(
                    field_type=field.type.value,
                    formula=field.formula,
                    static_value=field.static_value,
                    min_value=field.min_value,
                    max_value=field.max_value,
                    t=t,
                    i=iteration
                )
                payload[field.name] = value
            except Exception as e:
                logger.error(f"Error generating value for field {field.name}: {e}")
                payload[field.name] = None

        return payload

    def _generate_payload(self, machine: MachineDefinition, iteration: int) -> dict:
        """Generate a payload based on machine field definitions (backward compat)."""
        t = time.time()
        return self._generate_payload_for_fields(machine.fields, iteration, t)

    async def _publish_loop(self, machine: MachineDefinition):
        """Main publishing loop for a machine. Supports multi-topic machines."""
        machine_id = machine.id
        interval_seconds = machine.publish_interval_ms / 1000.0
        iteration = 0

        # Get all topics (handles both single and multi-topic machines)
        all_topics = machine.get_all_topics()
        topic_paths = [t.topic_path for t in all_topics]

        # Warn and exit if no topics configured
        if not all_topics:
            logger.warning(f"Machine {machine_id} ({machine.name}) has no topics to publish! "
                          f"Check that topics or topic_path/fields are configured.")
            self._running_machines.discard(machine_id)
            return

        # Initialize stats
        self._machine_stats[machine_id] = {
            "messages_published": 0,
            "sparkmes_published": 0,
            "started_at": datetime.utcnow().isoformat(),
            "last_error": None,
            "topic_count": len(all_topics),
            "last_payloads": {},  # topic_path -> payload dict
            "last_sparkmes_payload": None,
            "smprofile_published": False,
        }

        logger.info(f"Starting publish loop for machine {machine_id} ({machine.name}) "
                    f"on {len(all_topics)} topic(s): {topic_paths} every {interval_seconds}s")

        try:
            self._ensure_connected()
            logger.info(f"[{machine_id}] MQTT connection confirmed, connected={self._connected}, client={self._client is not None}")

            # Publish SM Profile once as a retained message (static metadata)
            if machine.smprofile:
                for topic_def in all_topics:
                    smprofile_topic = f"{topic_def.topic_path}/SMProfiles"
                    smprofile_json = json.dumps(machine.smprofile)
                    try:
                        result = self._client.publish(smprofile_topic, smprofile_json, qos=1, retain=True)
                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            self._machine_stats[machine_id]["smprofile_published"] = True
                            logger.info(f"[{machine_id}] SMProfile published (retained) to {smprofile_topic}")
                        else:
                            logger.warning(f"[{machine_id}] SMProfile FAILED to {smprofile_topic}: rc={result.rc}")
                    except Exception as e:
                        logger.error(f"[{machine_id}] SMProfile publish error: {e}")

            while True:
                try:
                    t = time.time()

                    # Log connection status periodically (every 10 iterations)
                    if iteration % 10 == 0:
                        logger.info(f"[{machine_id}] Iteration {iteration}, connected={self._connected}, "
                                   f"messages_published={self._machine_stats[machine_id]['messages_published']}")

                    # Publish to each topic with its own payload
                    aggregated_telemetry = {}
                    for topic_def in all_topics:
                        payload = self._generate_payload_for_fields(topic_def.fields, iteration, t)
                        payload_json = json.dumps(payload)
                        aggregated_telemetry.update(payload)

                        logger.info(f"[{machine_id}] Publishing to topic: {topic_def.topic_path}")

                        result = self._client.publish(
                            topic_def.topic_path,
                            payload_json,
                            qos=1
                        )

                        if result.rc == mqtt.MQTT_ERR_SUCCESS:
                            self._machine_stats[machine_id]["messages_published"] += 1
                            self._machine_stats[machine_id]["last_published_at"] = datetime.utcnow().isoformat()
                            self._machine_stats[machine_id]["last_payloads"][topic_def.topic_path] = payload
                            logger.info(f"[{machine_id}] SUCCESS published to {topic_def.topic_path}: {payload_json[:200]}")
                        else:
                            logger.warning(f"[{machine_id}] FAILED publish to {topic_def.topic_path}: rc={result.rc}")

                    # Publish SparkMES once per cycle as individual topics per tag
                    if machine.sparkmes_enabled and machine.sparkmes:
                        try:
                            # Compute base topic from common prefix of all topic paths
                            base_topic = os.path.commonprefix(
                                [t.topic_path for t in all_topics]
                            ).rstrip("/")

                            sparkmes_payload = sparkmes_generator.generate_payload(
                                machine_id=machine_id,
                                sparkmes_template=machine.sparkmes,
                                telemetry=aggregated_telemetry,
                                iteration=iteration,
                                t=t,
                                cycle_time_seconds=config.sparkmes_default_cycle_time,
                                scrap_rate=config.sparkmes_default_scrap_rate
                            )

                            # Flatten tag hierarchy and publish each value individually
                            flat_tags = sparkmes_generator.flatten_tags(
                                sparkmes_payload.get("tags", [])
                            )
                            for tag_path, value in flat_tags:
                                sparkmes_topic = f"{base_topic}/sparkmes/{tag_path}"
                                sparkmes_result = self._client.publish(
                                    sparkmes_topic, json.dumps(value), qos=1
                                )
                                if sparkmes_result.rc != mqtt.MQTT_ERR_SUCCESS:
                                    logger.warning(
                                        f"[{machine_id}] SparkMES FAILED to {sparkmes_topic}: rc={sparkmes_result.rc}"
                                    )

                            self._machine_stats[machine_id]["sparkmes_published"] += 1
                            self._machine_stats[machine_id]["last_sparkmes_payload"] = sparkmes_payload
                            logger.info(
                                f"[{machine_id}] SparkMES published {len(flat_tags)} tags to {base_topic}/sparkmes/"
                            )
                        except Exception as e:
                            logger.error(f"[{machine_id}] SparkMES publish error: {e}")
                            # Continue - don't fail telemetry because of SparkMES

                    iteration += 1

                except Exception as e:
                    logger.error(f"Error in publish loop for {machine_id}: {e}")
                    self._machine_stats[machine_id]["last_error"] = str(e)

                await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logger.info(f"Publish loop cancelled for machine {machine_id}")
            raise
        except Exception as e:
            logger.error(f"Fatal error in publish loop for {machine_id}: {e}")
            self._machine_stats[machine_id]["last_error"] = str(e)

    async def start_machine(self, machine: MachineDefinition):
        """Start publishing for a machine."""
        machine_id = machine.id
        if machine_id in self._running_machines:
            logger.warning(f"Machine {machine_id} is already running")
            return

        # Create and store the task
        task = asyncio.create_task(self._publish_loop(machine))
        self._running_machines[machine_id] = task
        logger.info(f"Started machine {machine_id}")

    async def stop_machine(self, machine_id: str):
        """Stop publishing for a machine."""
        if machine_id not in self._running_machines:
            logger.warning(f"Machine {machine_id} is not running")
            return

        # Cancel the task
        task = self._running_machines.pop(machine_id)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Clear retained SM Profile messages
        if self._client and self._connected:
            stats = self._machine_stats.get(machine_id, {})
            for topic_path in stats.get("last_payloads", {}).keys():
                smprofile_topic = f"{topic_path}/SMProfiles"
                try:
                    self._client.publish(smprofile_topic, "", qos=1, retain=True)
                    logger.info(f"Cleared retained SMProfile from {smprofile_topic}")
                except Exception as e:
                    logger.warning(f"Failed to clear SMProfile from {smprofile_topic}: {e}")

        # Reset SparkMES state
        sparkmes_generator.reset_state(machine_id)

        logger.info(f"Stopped machine {machine_id}")

    def get_machine_stats(self, machine_id: str) -> Optional[dict]:
        """Get publishing statistics for a machine."""
        return self._machine_stats.get(machine_id)

    def is_running(self, machine_id: str) -> bool:
        """Check if a machine is currently running."""
        return machine_id in self._running_machines

    async def stop_all(self):
        """Stop all running machines."""
        machine_ids = list(self._running_machines.keys())
        for machine_id in machine_ids:
            await self.stop_machine(machine_id)

        # Disconnect MQTT client
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False


# Singleton instance
publisher = MachinePublisher()
