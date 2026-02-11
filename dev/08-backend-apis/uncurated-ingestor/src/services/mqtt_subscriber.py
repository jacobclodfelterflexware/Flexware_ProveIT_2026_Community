import asyncio
import logging
from typing import Callable, Awaitable

import aiomqtt

from config import config

logger = logging.getLogger(__name__)

# Handler receives: topic, payload, client_id (extracted from topic path)
MessageHandler = Callable[[str, bytes, str], Awaitable[None]]


class MQTTSubscriber:
    """Subscribes to uncurated MQTT broker and forwards messages."""

    def __init__(self, message_handler: MessageHandler):
        self.message_handler = message_handler
        self._is_running = False
        self._task: asyncio.Task | None = None
        self.is_connected = False
        self.messages_received = 0

    async def start(self) -> None:
        """Start the subscriber."""
        self._is_running = True
        self._task = asyncio.create_task(self._subscribe_loop())
        logger.info("MQTT subscriber started")

    async def stop(self) -> None:
        """Stop the subscriber."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT subscriber stopped")

    async def _subscribe_loop(self) -> None:
        """Main subscription loop with reconnection."""
        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=config.mqtt_host,
                    port=config.mqtt_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier=config.mqtt_client_id,
                ) as client:
                    self.is_connected = True
                    logger.info(
                        f"Connected to MQTT broker: {config.mqtt_host}:{config.mqtt_port}"
                    )

                    # Subscribe to $ingest/# for internal republished messages
                    await client.subscribe("$ingest/#", qos=config.mqtt_qos)
                    logger.info("Subscribed to $ingest/#")

                    # Also subscribe to # for external bridged messages
                    await client.subscribe("#", qos=config.mqtt_qos)
                    logger.info("Subscribed to # (all topics)")

                    async for message in client.messages:
                        full_topic = str(message.topic)
                        payload = message.payload if isinstance(message.payload, bytes) else bytes(message.payload)

                        # Parse topic based on format:
                        # - $ingest/{client_id}/{original_topic}: internal republished messages
                        # - Other topics: external bridged messages (client_id = "unknown")
                        client_id = "unknown"
                        original_topic = full_topic

                        if full_topic.startswith("$ingest/"):
                            remainder = full_topic[8:]  # Remove "$ingest/" prefix
                            # First segment is client_id, rest is original topic
                            slash_idx = remainder.find("/")
                            if slash_idx > 0:
                                client_id = remainder[:slash_idx]
                                original_topic = remainder[slash_idx + 1:]
                            else:
                                # No slash found - entire remainder is client_id, no topic
                                client_id = remainder
                                original_topic = ""
                        # For raw topics (bridged messages), client_id stays "unknown"
                        # and ingestion.py will apply fallback logic based on topic path

                        self.messages_received += 1

                        try:
                            await self.message_handler(original_topic, payload, client_id)
                        except Exception as e:
                            logger.error(f"Error handling message on {original_topic}: {e}")

            except aiomqtt.MqttError as e:
                self.is_connected = False
                logger.error(f"MQTT error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                self.is_connected = False
                logger.exception(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
