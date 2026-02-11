"""Polls Neo4j for ladder logic programs and publishes rungs, ioMapping, rationale as individual sub-topics."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from neo4j import AsyncDriver

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class LadderPoller:
    """
    Polls Neo4j for LadderLogic nodes linked to SimulatedMachines
    and publishes each component as a separate sub-topic.
    """

    def __init__(self, driver: AsyncDriver, publisher: MQTTPublisher):
        self.driver = driver
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._seen_machines: set[str] = set()
        self._last_poll: datetime | None = None
        self.programs_published = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Ladder logic poller started")

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
                await self._poll_ladder_logic(prefix)
            except Exception as e:
                logger.error(f"Ladder poll error: {e}")
            await asyncio.sleep(config.ladder_poll_interval)

    async def _poll_ladder_logic(self, prefix: str) -> None:
        query = """
        MATCH (m:SimulatedMachine)-[:HAS_LADDER_LOGIC]->(l:LadderLogic)
        RETURN m.id AS machineId,
               m.name AS machineName,
               m.machineType AS machineType,
               l.rungs AS rungs,
               l.ioMapping AS ioMapping,
               l.rationale AS rationale,
               toString(l.createdAt) AS createdAt
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                machine_id = record["machineId"]
                machine_name = record["machineName"] or machine_id
                base = f"{prefix}/machines/{machine_name}/ladder-logic"

                rungs = self._safe_json_loads(record["rungs"], [])
                io_mapping = self._safe_json_loads(record["ioMapping"], {})

                # Publish each component as its own sub-topic
                await self.publisher.publish(f"{base}/rungs", rungs)
                await self.publisher.publish(f"{base}/ioMapping", io_mapping)

                if record["rationale"]:
                    await self.publisher.publish(
                        f"{base}/rationale", record["rationale"]
                    )

                if machine_id not in self._seen_machines:
                    self._seen_machines.add(machine_id)
                    self.programs_published += 1

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
            "programs_tracked": len(self._seen_machines),
            "programs_published": self.programs_published,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
        }
