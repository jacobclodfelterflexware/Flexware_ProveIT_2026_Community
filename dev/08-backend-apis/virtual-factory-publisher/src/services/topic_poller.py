"""Polls Neo4j for the topic tree hierarchy and publishes it."""
import asyncio
import logging
from datetime import datetime, timezone

from neo4j import AsyncDriver

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class TopicPoller:
    """
    Polls Neo4j for the curated topic tree and publishes
    the hierarchy and stats.
    """

    def __init__(self, driver: AsyncDriver, publisher: MQTTPublisher):
        self.driver = driver
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._last_poll: datetime | None = None
        self._last_topic_count: int = 0
        self.updates_published = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Topic poller started")

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
                await self._poll_topics(prefix)
            except Exception as e:
                logger.error(f"Topic poll error: {e}")
            await asyncio.sleep(config.topic_poll_interval)

    async def _poll_topics(self, prefix: str) -> None:
        # Get all curated topics with their parent relationships
        query = """
        MATCH (t:Topic {broker: 'curated'})
        OPTIONAL MATCH (t)-[:CHILD_OF]->(parent:Topic)
        RETURN t.path AS path,
               t.name AS name,
               t.depth AS depth,
               parent.path AS parentPath
        ORDER BY t.depth, t.path
        """

        topics = []
        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                topics.append({
                    "path": record["path"],
                    "name": record["name"],
                    "depth": record["depth"],
                    "parentPath": record["parentPath"]
                })

        # Build tree structure
        tree = self._build_tree(topics)

        # Publish full topic tree
        topic = f"{prefix}/discovery/topics"
        payload = {
            "totalTopics": len(topics),
            "tree": tree,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.publisher.publish(topic, payload)
        self.updates_published += 1
        self._last_topic_count = len(topics)
        self._last_poll = datetime.now(timezone.utc)

    @staticmethod
    def _build_tree(topics: list[dict]) -> list[dict]:
        """Build a nested tree from flat topic list."""
        nodes: dict[str, dict] = {}
        roots = []

        for t in topics:
            path = t["path"]
            nodes[path] = {
                "path": path,
                "name": t["name"],
                "depth": t["depth"],
                "children": []
            }

        for t in topics:
            path = t["path"]
            parent = t["parentPath"]
            if parent and parent in nodes:
                nodes[parent]["children"].append(nodes[path])
            else:
                roots.append(nodes[path])

        return roots

    def get_stats(self) -> dict:
        return {
            "topics_tracked": self._last_topic_count,
            "updates_published": self.updates_published,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None
        }
