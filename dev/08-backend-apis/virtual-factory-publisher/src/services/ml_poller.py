"""Polls Neo4j for ML predictions and regressions."""
import asyncio
import json
import logging
from datetime import datetime, timezone

from neo4j import AsyncDriver

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class MLPoller:
    """
    Polls Neo4j for Prediction and Regression nodes.
    Publishes new or updated results.
    """

    def __init__(self, driver: AsyncDriver, publisher: MQTTPublisher):
        self.driver = driver
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False

        self._seen_predictions: set[str] = set()  # prediction IDs
        self._seen_regressions: set[str] = set()  # regression IDs
        self._last_poll: datetime | None = None
        self.predictions_published = 0
        self.regressions_published = 0

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("ML poller started")

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
                await self._poll_predictions(prefix)
                await self._poll_regressions(prefix)
            except Exception as e:
                logger.error(f"ML poll error: {e}")
            await asyncio.sleep(config.ml_poll_interval)

    async def _poll_predictions(self, prefix: str) -> None:
        query = """
        MATCH (m:SimulatedMachine)-[:HAS_PREDICTION]->(p:Prediction)
        RETURN p.id AS id,
               p.machineId AS machineId,
               m.name AS machineName,
               p.fieldName AS fieldName,
               p.topicPath AS topicPath,
               p.horizon AS horizon,
               p.predictions AS predictions,
               p.historical AS historical,
               p.modelMetrics AS modelMetrics,
               toString(p.trainedAt) AS trainedAt,
               p.dataPointsUsed AS dataPointsUsed
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                pred_id = record["id"]
                if pred_id in self._seen_predictions:
                    continue

                machine_name = record["machineName"] or record["machineId"]
                field_name = record["fieldName"]

                # Parse JSON-stored fields
                predictions = self._safe_json_loads(record["predictions"], [])
                historical = self._safe_json_loads(record["historical"], [])
                metrics = self._safe_json_loads(record["modelMetrics"], {})

                topic = f"{prefix}/predictions/{machine_name}/{field_name}"
                payload = {
                    "id": pred_id,
                    "machineId": record["machineId"],
                    "machineName": machine_name,
                    "fieldName": field_name,
                    "topicPath": record["topicPath"],
                    "horizon": record["horizon"],
                    "predictions": predictions,
                    "historical": historical,
                    "modelMetrics": metrics,
                    "trainedAt": record["trainedAt"],
                    "dataPointsUsed": record["dataPointsUsed"]
                }

                await self.publisher.publish(topic, payload)
                self.predictions_published += 1
                self._seen_predictions.add(pred_id)

    async def _poll_regressions(self, prefix: str) -> None:
        query = """
        MATCH (m:SimulatedMachine)-[:HAS_REGRESSION]->(r:Regression)
        RETURN r.id AS id,
               r.machineId AS machineId,
               m.name AS machineName,
               r.targetField AS targetField,
               r.targetTopic AS targetTopic,
               r.features AS features,
               r.intercept AS intercept,
               r.rSquared AS rSquared,
               r.correlationMatrix AS correlationMatrix,
               toString(r.trainedAt) AS trainedAt,
               r.dataPointsUsed AS dataPointsUsed
        """

        async with self.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                reg_id = record["id"]
                if reg_id in self._seen_regressions:
                    continue

                machine_name = record["machineName"] or record["machineId"]

                features = self._safe_json_loads(record["features"], [])
                corr_matrix = self._safe_json_loads(record["correlationMatrix"], {})

                topic = f"{prefix}/regressions/{machine_name}"
                payload = {
                    "id": reg_id,
                    "machineId": record["machineId"],
                    "machineName": machine_name,
                    "targetField": record["targetField"],
                    "targetTopic": record["targetTopic"],
                    "features": features,
                    "intercept": record["intercept"],
                    "rSquared": record["rSquared"],
                    "correlationMatrix": corr_matrix,
                    "trainedAt": record["trainedAt"],
                    "dataPointsUsed": record["dataPointsUsed"]
                }

                await self.publisher.publish(topic, payload)
                self.regressions_published += 1
                self._seen_regressions.add(reg_id)

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
            "predictions_published": self.predictions_published,
            "regressions_published": self.regressions_published,
            "predictions_tracked": len(self._seen_predictions),
            "regressions_tracked": len(self._seen_regressions),
            "last_poll": self._last_poll.isoformat() if self._last_poll else None
        }
