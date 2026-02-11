"""MQTT bridge that subscribes to curated broker and republishes under VirtualFactory2.0/ prefix."""
import asyncio
import logging

import aiomqtt

from config import config

logger = logging.getLogger(__name__)

# EMQX ACL blocks global '#' subscription.
# Subscribe to known topic prefixes instead.
SUBSCRIBE_PREFIXES = [
    "data-publisher-curated/#",
]


class MQTTBridge:
    """
    Subscribes to curated broker topic prefixes and republishes
    under VirtualFactory2.0/telemetry/{original_topic}.
    """

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._is_running = False
        self.is_connected = False
        self.messages_bridged = 0
        self.messages_filtered = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._bridge_loop())
        logger.info("MQTT bridge started")

    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT bridge stopped")

    async def _bridge_loop(self) -> None:
        """Main bridge loop with reconnection."""
        prefix = config.topic_prefix

        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=config.mqtt_host,
                    port=config.mqtt_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier="vf2-bridge-sub"
                ) as subscriber, aiomqtt.Client(
                    hostname=config.mqtt_host,
                    port=config.mqtt_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier="vf2-bridge-pub"
                ) as publisher:
                    self.is_connected = True
                    logger.info(f"Bridge connected to {config.mqtt_host}")

                    for sub_topic in SUBSCRIBE_PREFIXES:
                        await subscriber.subscribe(sub_topic, qos=config.mqtt_qos)
                        logger.info(f"Bridge subscribed to: {sub_topic}")

                    async for message in subscriber.messages:
                        topic = str(message.topic)

                        # Skip our own messages to avoid loops
                        if topic.startswith(f"{prefix}/"):
                            self.messages_filtered += 1
                            continue

                        # Republish under prefix
                        new_topic = f"{prefix}/telemetry/{topic}"
                        await publisher.publish(
                            new_topic,
                            message.payload,
                            qos=config.mqtt_qos
                        )
                        self.messages_bridged += 1

            except aiomqtt.MqttError as e:
                self.is_connected = False
                logger.error(f"Bridge MQTT error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                self.is_connected = False
                logger.exception(f"Bridge unexpected error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    def get_stats(self) -> dict:
        return {
            "connected": self.is_connected,
            "messages_bridged": self.messages_bridged,
            "messages_filtered": self.messages_filtered
        }
