"""Polls EMQX broker REST API for stats, metrics, and client info, publishes to MQTT."""
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

from config import config
from services.mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


class BrokerPoller:
    """
    Polls EMQX broker REST API (v5) for broker stats, metrics,
    and connected clients. Publishes under VirtualFactory2.0/broker/...
    """

    def __init__(self, publisher: MQTTPublisher):
        self.publisher = publisher
        self._task: asyncio.Task | None = None
        self._is_running = False
        self._last_poll: datetime | None = None
        self.polls_completed = 0

        self._base_url = (
            f"http://{config.emqx_api_host}:{config.emqx_api_port}/api/v5"
        )
        self._auth = aiohttp.BasicAuth(
            config.emqx_api_key, config.emqx_api_secret
        )

    async def start(self) -> None:
        self._is_running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Broker poller started")

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
                await self._poll_broker(prefix)
            except Exception as e:
                logger.error(f"Broker poll error: {e}")
            await asyncio.sleep(config.broker_poll_interval)

    async def _poll_broker(self, prefix: str) -> None:
        base = f"{prefix}/broker"

        async with aiohttp.ClientSession(auth=self._auth) as session:
            # Stats (connections, topics, subscriptions)
            stats = await self._fetch_json(session, f"{self._base_url}/stats")
            if stats and isinstance(stats, list) and len(stats) > 0:
                node_stats = stats[0]
                await self.publisher.publish(f"{base}/stats", {
                    "connections": node_stats.get("connections.count", 0),
                    "connectionsMax": node_stats.get("connections.max", 0),
                    "liveConnections": node_stats.get("live_connections.count", 0),
                    "topics": node_stats.get("topics.count", 0),
                    "topicsMax": node_stats.get("topics.max", 0),
                    "subscribers": node_stats.get("subscribers.count", 0),
                    "subscriptions": node_stats.get("subscriptions.count", 0),
                    "sessions": node_stats.get("sessions.count", 0),
                    "retainedMessages": node_stats.get("retained.count", 0),
                })

            # Metrics (messages, bytes, packets)
            metrics = await self._fetch_json(session, f"{self._base_url}/metrics")
            if metrics and isinstance(metrics, list) and len(metrics) > 0:
                node_metrics = metrics[0]
                await self.publisher.publish(f"{base}/metrics/messages", {
                    "received": node_metrics.get("messages.publish", 0),
                    "delivered": node_metrics.get("messages.delivered", 0),
                    "dropped": node_metrics.get("messages.dropped", 0),
                    "droppedNoSubscriber": node_metrics.get(
                        "messages.dropped.no_subscribers", 0
                    ),
                    "acked": node_metrics.get("messages.acked", 0),
                    "qos0Received": node_metrics.get("messages.qos0.received", 0),
                    "qos0Sent": node_metrics.get("messages.qos0.sent", 0),
                    "qos1Received": node_metrics.get("messages.qos1.received", 0),
                    "qos1Sent": node_metrics.get("messages.qos1.sent", 0),
                })

                await self.publisher.publish(f"{base}/metrics/bytes", {
                    "received": node_metrics.get("bytes.received", 0),
                    "sent": node_metrics.get("bytes.sent", 0),
                })

                await self.publisher.publish(f"{base}/metrics/auth", {
                    "authSuccess": node_metrics.get("authentication.success", 0),
                    "authFailure": node_metrics.get("authentication.failure", 0),
                    "authzAllow": node_metrics.get("authorization.allow", 0),
                    "authzDeny": node_metrics.get("authorization.deny", 0),
                })

            # Connected clients
            clients = await self._fetch_json(
                session, f"{self._base_url}/clients?limit=100"
            )
            if clients and isinstance(clients, dict):
                client_list = clients.get("data", [])
                for c in client_list:
                    client_id = c.get("clientid", "unknown")
                    await self.publisher.publish(
                        f"{base}/clients/{client_id}", {
                            "connected": c.get("connected", False),
                            "ipAddress": c.get("ip_address", ""),
                            "protoVer": c.get("proto_ver", 0),
                            "keepalive": c.get("keepalive", 0),
                            "subscriptions": c.get("subscriptions_cnt", 0),
                            "messagesReceived": c.get("recv_msg", 0),
                            "messagesSent": c.get("send_msg", 0),
                            "bytesReceived": c.get("recv_oct", 0),
                            "bytesSent": c.get("send_oct", 0),
                            "connectedAt": c.get("connected_at", ""),
                        }
                    )

        self.polls_completed += 1
        self._last_poll = datetime.now(timezone.utc)

    async def _fetch_json(self, session: aiohttp.ClientSession, url: str):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning(f"Broker API {url} returned {resp.status}")
                return None
        except Exception as e:
            logger.warning(f"Broker API request failed: {e}")
            return None

    def get_stats(self) -> dict:
        return {
            "polls_completed": self.polls_completed,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
        }
