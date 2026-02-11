import asyncio
import logging
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from api.models import StreamMessage
from skills.base import ChartSkill

logger = logging.getLogger(__name__)


@dataclass
class ChartSubscription:
    """Subscription info for a chart."""
    chart_id: str
    topics: list[str]
    skill: ChartSkill
    parameters: dict = field(default_factory=dict)
    queues: list[asyncio.Queue] = field(default_factory=list)


class StreamManager:
    """
    Manages real-time streaming subscriptions for charts.

    In production, this would connect to MQTT or a message queue.
    For now, it provides the infrastructure for SSE streaming.
    """

    def __init__(self):
        self.subscriptions: dict[str, ChartSubscription] = {}
        self.topic_to_charts: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    def register_chart(
        self,
        chart_id: str,
        topics: list[str],
        skill: ChartSkill,
        parameters: dict = None
    ):
        """Register a chart for streaming updates."""
        subscription = ChartSubscription(
            chart_id=chart_id,
            topics=topics,
            skill=skill,
            parameters=parameters or {}
        )
        self.subscriptions[chart_id] = subscription

        # Map topics to chart
        for topic in topics:
            self.topic_to_charts[topic].add(chart_id)

        logger.info(f"Registered chart {chart_id} for topics: {topics}")

    def has_chart(self, chart_id: str) -> bool:
        """Check if a chart is registered."""
        return chart_id in self.subscriptions

    async def unregister_chart(self, chart_id: str):
        """Unregister a chart and clean up."""
        async with self._lock:
            if chart_id not in self.subscriptions:
                return

            subscription = self.subscriptions[chart_id]

            # Remove from topic mapping
            for topic in subscription.topics:
                self.topic_to_charts[topic].discard(chart_id)
                if not self.topic_to_charts[topic]:
                    del self.topic_to_charts[topic]

            # Close all queues
            for queue in subscription.queues:
                await queue.put(None)  # Signal end

            del self.subscriptions[chart_id]
            logger.info(f"Unregistered chart {chart_id}")

    async def subscribe(self, chart_id: str) -> AsyncIterator[StreamMessage]:
        """
        Subscribe to updates for a chart.
        Returns an async iterator of StreamMessages.
        """
        if chart_id not in self.subscriptions:
            yield StreamMessage(type="error", error="Chart not found")
            return

        subscription = self.subscriptions[chart_id]
        queue = asyncio.Queue()
        subscription.queues.append(queue)

        try:
            # Send initial connection message
            yield StreamMessage(type="connected", timestamp=self._now())

            # Wait for messages
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if message is None:
                        break
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield StreamMessage(type="keepalive", timestamp=self._now())

        finally:
            # Clean up queue
            if queue in subscription.queues:
                subscription.queues.remove(queue)

    async def publish_message(self, topic: str, payload: dict):
        """
        Publish a message to all charts subscribed to a topic.
        Called when new data arrives from MQTT.
        """
        chart_ids = self.topic_to_charts.get(topic, set())

        for chart_id in chart_ids:
            subscription = self.subscriptions.get(chart_id)
            if not subscription:
                continue

            # Transform message using skill
            transformed = subscription.skill.transform_message(
                topic, payload, subscription.parameters
            )

            if transformed:
                message = StreamMessage(
                    type="data_point",
                    timestamp=self._now(),
                    series=transformed.get("series", topic),
                    value=transformed.get("y")
                )

                # Send to all queues
                for queue in subscription.queues:
                    try:
                        await queue.put(message)
                    except Exception as e:
                        logger.error(f"Error sending to queue: {e}")

    async def close(self):
        """Close all subscriptions."""
        for chart_id in list(self.subscriptions.keys()):
            await self.unregister_chart(chart_id)

    def _now(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
