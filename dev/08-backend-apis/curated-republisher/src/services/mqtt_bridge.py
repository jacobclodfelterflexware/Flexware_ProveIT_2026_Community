"""MQTT bridge that transforms and republishes messages."""
import asyncio
import logging

import aiomqtt

from config import config
from services.mapping_cache import MappingCache
from services.transformer import PayloadTransformer
from services.neo4j_writer import Neo4jWriter

logger = logging.getLogger(__name__)


class MQTTBridge:
    """
    Bridges uncurated to curated broker with transformations.

    Only processes messages that have approved mappings.
    """

    def __init__(
        self,
        mapping_cache: MappingCache,
        neo4j_writer: Neo4jWriter
    ):
        self.mapping_cache = mapping_cache
        self.neo4j_writer = neo4j_writer
        self.transformer = PayloadTransformer()

        self._subscriber_task: asyncio.Task | None = None
        self._is_running = False

        # Connection state
        self.is_uncurated_connected = False
        self.is_curated_connected = False

        # Stats
        self.messages_received = 0
        self.messages_transformed = 0
        self.messages_dropped = 0

    async def start(self) -> None:
        """Start the bridge."""
        self._is_running = True
        self._subscriber_task = asyncio.create_task(self._bridge_loop())
        logger.info("MQTT bridge started")

    async def stop(self) -> None:
        """Stop the bridge."""
        self._is_running = False
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT bridge stopped")

    async def _bridge_loop(self) -> None:
        """Main bridge loop with reconnection."""
        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=config.mqtt_uncurated_host,
                    port=config.mqtt_uncurated_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier="curated-republisher-sub"
                ) as subscriber, aiomqtt.Client(
                    hostname=config.mqtt_curated_host,
                    port=config.mqtt_curated_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier="curated-republisher-pub"
                ) as publisher:
                    self.is_uncurated_connected = True
                    self.is_curated_connected = True

                    logger.info(
                        f"Connected to brokers - "
                        f"Uncurated: {config.mqtt_uncurated_host}, "
                        f"Curated: {config.mqtt_curated_host}"
                    )

                    # Subscribe to all topics
                    await subscriber.subscribe("#", qos=config.mqtt_qos)
                    logger.info("Subscribed to uncurated broker (#)")

                    async for message in subscriber.messages:
                        await self._handle_message(message, publisher)

            except aiomqtt.MqttError as e:
                self.is_uncurated_connected = False
                self.is_curated_connected = False
                logger.error(f"MQTT error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                self.is_uncurated_connected = False
                self.is_curated_connected = False
                logger.exception(f"Unexpected error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def _handle_message(
        self,
        message: aiomqtt.Message,
        publisher: aiomqtt.Client
    ) -> None:
        """Handle an incoming message from uncurated broker."""
        self.messages_received += 1

        raw_topic = str(message.topic)
        raw_payload = message.payload or b""

        # Look up mapping
        mapping = self.mapping_cache.get_mapping(raw_topic)

        if mapping is None:
            # No approved mapping - drop silently
            self.messages_dropped += 1
            return

        try:
            # Transform payload
            curated_topic = mapping["curatedTopic"]
            payload_mapping = mapping["payloadMapping"]
            mapping_id = mapping["mappingId"]

            transformed_dict, transformed_json = self.transformer.transform(
                raw_payload,
                payload_mapping
            )

            # Publish to curated broker
            await publisher.publish(
                curated_topic,
                transformed_json,
                qos=config.mqtt_qos
            )

            self.messages_transformed += 1

            # Write to Neo4j (async, don't block)
            if config.write_to_neo4j:
                asyncio.create_task(
                    self.neo4j_writer.write_curated_message(
                        curated_topic=curated_topic,
                        normalized_payload=transformed_json,
                        mapping_id=mapping_id,
                        raw_message_id=None  # Could extract from metadata if needed
                    )
                )

            logger.debug(f"Transformed: {raw_topic} -> {curated_topic}")

        except Exception as e:
            logger.error(f"Error processing {raw_topic}: {e}")

    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            "messages_received": self.messages_received,
            "messages_transformed": self.messages_transformed,
            "messages_dropped": self.messages_dropped,
            "transform_rate": self.messages_transformed / max(1, self.messages_received)
        }
