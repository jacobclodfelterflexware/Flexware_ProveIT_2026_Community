"""MQTT bridge for subscribing and republishing messages with transformations."""
import asyncio
import json
import logging
import os
from typing import Optional

import aiomqtt

from .mapping_cache import MappingCache
from .transformer import MessageTransformer
from .topic_tree import TopicTreeBuilder


class MQTTConfig:
    """MQTT configuration from environment."""

    MQTT_BROKER_UNCURATED_HOST = os.getenv(
        "MQTT_BROKER_UNCURATED_HOST",
        "YOUR_MQTT_UNCURATED_HOST"
    )
    MQTT_BROKER_UNCURATED_PORT = int(os.getenv("MQTT_BROKER_UNCURATED_PORT", "YOUR_MQTT_PORT"))
    MQTT_BROKER_CURATED_HOST = os.getenv(
        "MQTT_BROKER_CURATED_HOST",
        "YOUR_MQTT_CURATED_HOST"
    )
    MQTT_BROKER_CURATED_PORT = int(os.getenv("MQTT_BROKER_CURATED_PORT", "YOUR_MQTT_PORT"))
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "YOUR_MQTT_USERNAME")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "YOUR_MQTT_PASSWORD")
    MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))

logger = logging.getLogger(__name__)


class MQTTBridge:
    """Bridges uncurated to curated MQTT broker with transformations."""

    def __init__(self, mapping_cache: MappingCache):
        self.mapping_cache = mapping_cache
        self.transformer = MessageTransformer()

        # Topic trees for both brokers
        self.uncurated_tree = TopicTreeBuilder()
        self.curated_tree = TopicTreeBuilder()

        # State
        self._subscriber_task: Optional[asyncio.Task] = None
        self._is_running = False
        self.is_uncurated_connected = False
        self.is_curated_connected = False

    async def start(self) -> None:
        """Start the MQTT bridge."""
        self._is_running = True
        self._subscriber_task = asyncio.create_task(self._bridge_loop())
        logger.info("MQTT bridge started")

    async def stop(self) -> None:
        """Stop the MQTT bridge."""
        self._is_running = False
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT bridge stopped")

    async def _bridge_loop(self) -> None:
        """Main bridge loop with reconnection logic."""
        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=MQTTConfig.MQTT_BROKER_UNCURATED_HOST,
                    port=MQTTConfig.MQTT_BROKER_UNCURATED_PORT,
                    username=MQTTConfig.MQTT_USERNAME,
                    password=MQTTConfig.MQTT_PASSWORD,
                    identifier="middleware-subscriber",
                ) as subscriber, aiomqtt.Client(
                    hostname=MQTTConfig.MQTT_BROKER_CURATED_HOST,
                    port=MQTTConfig.MQTT_BROKER_CURATED_PORT,
                    username=MQTTConfig.MQTT_USERNAME,
                    password=MQTTConfig.MQTT_PASSWORD,
                    identifier="middleware-publisher",
                ) as publisher:
                    self.is_uncurated_connected = True
                    self.is_curated_connected = True
                    logger.info(
                        f"Connected to MQTT brokers: "
                        f"uncurated={MQTTConfig.MQTT_BROKER_UNCURATED_HOST}:{MQTTConfig.MQTT_BROKER_UNCURATED_PORT}, "
                        f"curated={MQTTConfig.MQTT_BROKER_CURATED_HOST}:{MQTTConfig.MQTT_BROKER_CURATED_PORT}"
                    )

                    # Subscribe to all topics on uncurated broker
                    await subscriber.subscribe("#", qos=MQTTConfig.MQTT_QOS)
                    logger.info("Subscribed to all topics (#) on uncurated broker")

                    # Also subscribe to curated broker for tree building
                    curated_sub_task = asyncio.create_task(
                        self._subscribe_curated()
                    )

                    async for message in subscriber.messages:
                        await self._handle_message(message, publisher)

            except aiomqtt.MqttError as e:
                self.is_uncurated_connected = False
                self.is_curated_connected = False
                logger.error(f"MQTT error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                self.is_uncurated_connected = False
                self.is_curated_connected = False
                logger.exception(f"Unexpected error in bridge loop: {e}")
                await asyncio.sleep(5)

    async def _subscribe_curated(self) -> None:
        """Subscribe to curated broker to build its topic tree."""
        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=MQTTConfig.MQTT_BROKER_CURATED_HOST,
                    port=MQTTConfig.MQTT_BROKER_CURATED_PORT,
                    username=MQTTConfig.MQTT_USERNAME,
                    password=MQTTConfig.MQTT_PASSWORD,
                    identifier="middleware-curated-subscriber",
                ) as client:
                    await client.subscribe("#", qos=MQTTConfig.MQTT_QOS)
                    logger.info("Subscribed to curated broker for tree building")

                    async for message in client.messages:
                        topic = str(message.topic)
                        payload = message.payload.decode() if message.payload else ""
                        self.curated_tree.add_message(topic, payload)

            except aiomqtt.MqttError as e:
                logger.error(f"Curated subscriber error: {e}. Reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.exception(f"Error in curated subscriber: {e}")
                await asyncio.sleep(5)

    async def _handle_message(
        self,
        message: aiomqtt.Message,
        publisher: aiomqtt.Client,
    ) -> None:
        """Handle incoming MQTT message from uncurated broker."""
        source_topic = str(message.topic)
        payload_str = message.payload.decode() if message.payload else ""

        # Add to uncurated tree
        self.uncurated_tree.add_message(source_topic, payload_str)

        # Look up mapping in cache
        mapping = self.mapping_cache.get_mapping(source_topic)

        if mapping is None:
            # Track as unmapped topic (fire and forget)
            asyncio.create_task(
                self.mapping_cache.track_unmapped(source_topic, payload_str)
            )
            return

        if not mapping.get("is_active", True):
            return

        try:
            # Parse JSON payload
            try:
                payload = json.loads(payload_str) if payload_str else {}
            except json.JSONDecodeError:
                # Non-JSON payload - pass through as-is
                target_topic = mapping["target_topic"]
                await publisher.publish(
                    target_topic,
                    payload_str,
                    qos=MQTTConfig.MQTT_QOS,
                )
                self.mapping_cache.record_processed()
                logger.debug(f"Passed through non-JSON: {source_topic} -> {target_topic}")
                return

            # Transform keys if transformations exist
            key_transforms = mapping.get("key_transformations", [])
            if key_transforms:
                payload = self.transformer.transform(payload, key_transforms)
                self.mapping_cache.record_transformed()
            else:
                self.mapping_cache.record_processed()

            # Publish to curated broker
            target_topic = mapping["target_topic"]
            await publisher.publish(
                target_topic,
                json.dumps(payload),
                qos=MQTTConfig.MQTT_QOS,
            )
            logger.debug(f"Transformed: {source_topic} -> {target_topic}")

        except Exception as e:
            logger.error(f"Error transforming message from {source_topic}: {e}")

    def get_uncurated_tree(self) -> dict:
        """Get the uncurated topic tree."""
        return {
            "tree": self.uncurated_tree.get_tree(),
            "stats": self.uncurated_tree.get_stats(),
            "broker": "uncurated",
        }

    def get_curated_tree(self) -> dict:
        """Get the curated topic tree."""
        return {
            "tree": self.curated_tree.get_tree(),
            "stats": self.curated_tree.get_stats(),
            "broker": "curated",
        }
