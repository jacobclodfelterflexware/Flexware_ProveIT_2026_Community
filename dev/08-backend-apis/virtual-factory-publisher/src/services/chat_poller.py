"""Polls Neo4j for ProveITGPT chat histories and publishes new messages."""
import asyncio
import re
import logging
from datetime import datetime, timezone

from neo4j import AsyncDriver

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class ChatPoller:
    """
    Polls Neo4j for ProveITGPTChat conversations and publishes
    new messages since last poll (tracked by message count per chat).
    Uses the chat title as the MQTT topic slug.
    """

    def __init__(self, driver: AsyncDriver, publisher: MQTTPublisher):
        self.driver = driver
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False

        # Track last-seen message count per chat
        self._seen_message_counts: dict[str, int] = {}
        self._last_poll: datetime | None = None
        self.messages_published = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Chat poller started")

    async def stop(self) -> None:
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        prefix = config.topic_prefix
        while self._is_running:
            try:
                await self._poll_chats(prefix)
            except Exception as e:
                logger.error(f"Chat poll error: {e}")
            await asyncio.sleep(config.chat_poll_interval)

    async def _poll_chats(self, prefix: str) -> None:
        """Poll for ProveITGPT conversations with new messages."""
        query = """
        MATCH (c:ProveITGPTChat)
        OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:ProveITGPTMessage)
        WITH c, m ORDER BY m.orderIndex ASC
        WITH c, collect(m {
            .id, .role, .content,
            timestamp: toString(m.timestamp)
        }) AS messages
        RETURN c.id AS id,
               c.title AS title,
               toString(c.createdAt) AS createdAt,
               toString(c.updatedAt) AS updatedAt,
               messages
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                chat_id = record["id"]
                title = record["title"] or chat_id
                topic_slug = self._slugify(title)
                messages = [m for m in (record["messages"] or []) if m.get("id")]
                prev_count = self._seen_message_counts.get(chat_id, 0)

                if len(messages) <= prev_count:
                    continue

                # Publish only new messages
                new_messages = messages[prev_count:]
                for msg in new_messages:
                    topic = f"{prefix}/proveitgpt/{topic_slug}/messages"
                    payload = {
                        "chatId": chat_id,
                        "chatTitle": title,
                        "message": {
                            "id": msg["id"],
                            "role": msg["role"],
                            "content": msg["content"],
                            "timestamp": msg["timestamp"]
                        }
                    }

                    await self.publisher.publish(topic, payload)
                    self.messages_published += 1

                self._seen_message_counts[chat_id] = len(messages)

        self._last_poll = datetime.now(timezone.utc)

    @staticmethod
    def _slugify(title: str) -> str:
        """Convert a chat title to a safe MQTT topic segment."""
        slug = title.lower().strip()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s]+", "-", slug)
        slug = slug[:80]
        slug = slug.strip("-")
        return slug or "untitled"

    def get_stats(self) -> dict:
        return {
            "chats_tracked": len(self._seen_message_counts),
            "messages_published": self.messages_published,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None
        }
