"""Polls Neo4j for machine info, SM Profile, image, and similar topics — publishes each as individual sub-topics."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from neo4j import AsyncDriver

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class MachinePoller:
    """
    Polls Neo4j for SimulatedMachine nodes and publishes
    machine metadata as individual sub-topics under machines/{name}/.
    """

    def __init__(self, driver: AsyncDriver, publisher: MQTTPublisher):
        self.driver = driver
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._seen_machines: set[str] = set()
        self._last_poll: datetime | None = None
        self.machines_published = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Machine poller started")

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
                await self._poll_machines(prefix)
            except Exception as e:
                logger.error(f"Machine poll error: {e}")
            await asyncio.sleep(config.machine_poll_interval)

    async def _poll_machines(self, prefix: str) -> None:
        query = """
        MATCH (m:SimulatedMachine)
        RETURN m.id AS id,
               m.name AS name,
               m.description AS description,
               m.machineType AS machineType,
               m.imageBase64 AS imageBase64,
               m.createdBy AS createdBy,
               toString(m.createdAt) AS createdAt,
               m.status AS status,
               m.topicPath AS topicPath,
               m.publishIntervalMs AS publishIntervalMs,
               m.similarityResults AS similarityResults,
               m.smprofile AS smprofile
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                machine_id = record["id"]
                machine_name = record["name"] or machine_id
                base = f"{prefix}/machines/{machine_name}"

                # Publish each info field as its own sub-topic
                info_fields = {
                    "id": machine_id,
                    "name": machine_name,
                    "description": record["description"],
                    "machineType": record["machineType"],
                    "createdBy": record["createdBy"],
                    "createdAt": record["createdAt"],
                    "status": record["status"],
                    "topicPath": record["topicPath"],
                    "publishIntervalMs": record["publishIntervalMs"],
                }
                for field, value in info_fields.items():
                    if value is not None:
                        await self.publisher.publish(
                            f"{base}/info/{field}", str(value)
                        )

                # Publish machine image
                image = record["imageBase64"]
                if image:
                    await self.publisher.publish(f"{base}/image", image)

                # Publish similar topics
                similarity_raw = record["similarityResults"]
                if similarity_raw:
                    similar = self._safe_json_loads(similarity_raw, [])
                    if similar:
                        await self.publisher.publish(
                            f"{base}/similar-topics",
                            {"machineName": machine_name, "similarTopics": similar},
                        )

                # Publish CESMII SM Profile fields as individual sub-topics
                smprofile_raw = record["smprofile"]
                if smprofile_raw:
                    smprofile = self._safe_json_loads(smprofile_raw, {})
                    for field, value in smprofile.items():
                        if field.startswith("$"):
                            continue
                        if value is not None:
                            await self.publisher.publish(
                                f"{base}/smprofile/{field}", str(value)
                            )

                if machine_id not in self._seen_machines:
                    self._seen_machines.add(machine_id)
                    self.machines_published += 1

        self._last_poll = datetime.now(timezone.utc)

    @staticmethod
    def _safe_json_loads(value, default):
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default

    def get_stats(self) -> dict:
        return {
            "machines_tracked": len(self._seen_machines),
            "machines_published": self.machines_published,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
        }
