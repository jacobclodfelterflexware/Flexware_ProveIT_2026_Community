"""Shared MQTT publish client for all pollers."""
import asyncio
import json
import logging
from typing import Any

import aiomqtt

from config import config

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """
    Async MQTT publisher with persistent connection.

    Maintains its own connection loop and drains a message queue.
    Pollers call publish() which enqueues; the background loop sends.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._connected = False
        self.messages_published = 0
        self.messages_dropped = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._publish_loop())
        logger.info("MQTT publisher started")

    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT publisher stopped")

    async def publish(self, topic: str, payload: Any) -> None:
        """Enqueue a message for publishing. Payload will be JSON-serialized if not bytes/str."""
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload)
        elif isinstance(payload, bytes):
            data = payload
        else:
            data = str(payload)

        try:
            self._queue.put_nowait((topic, data))
        except asyncio.QueueFull:
            self.messages_dropped += 1
            logger.warning(f"Publish queue full, dropping message for {topic}")

    async def _publish_loop(self) -> None:
        """Persistent connection loop that drains the message queue."""
        while self._is_running:
            try:
                async with aiomqtt.Client(
                    hostname=config.mqtt_host,
                    port=config.mqtt_port,
                    username=config.mqtt_username,
                    password=config.mqtt_password,
                    identifier="vf2-publisher"
                ) as client:
                    self._connected = True
                    logger.info(f"Publisher connected to {config.mqtt_host}")

                    while self._is_running:
                        try:
                            topic, data = await asyncio.wait_for(
                                self._queue.get(), timeout=1.0
                            )
                            await client.publish(topic, data, qos=config.mqtt_qos)
                            self.messages_published += 1
                        except asyncio.TimeoutError:
                            # No messages in queue, keep connection alive
                            continue

            except aiomqtt.MqttError as e:
                self._connected = False
                logger.error(f"Publisher MQTT error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                self._connected = False
                logger.exception(f"Publisher unexpected error: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    def get_stats(self) -> dict:
        return {
            "connected": self._connected,
            "messages_published": self.messages_published,
            "messages_dropped": self.messages_dropped,
            "queue_size": self._queue.qsize()
        }
