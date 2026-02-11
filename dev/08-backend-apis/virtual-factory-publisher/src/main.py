"""VirtualFactory2.0 Publisher main entry point."""
import asyncio
import logging
import signal

from neo4j import AsyncGraphDatabase

from config import config
from services.mqtt_bridge import MQTTBridge
from services.mqtt_publisher import MQTTPublisher
from services.chat_poller import ChatPoller
from services.ml_poller import MLPoller
from services.topic_poller import TopicPoller
from services.machine_poller import MachinePoller
from services.ladder_poller import LadderPoller
from services.k8s_poller import K8sPoller
from services.broker_poller import BrokerPoller
from api.health import start_health_server

logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class VirtualFactoryPublisher:
    """Main application orchestrating the MQTT bridge and all Neo4j pollers."""

    def __init__(self):
        self._driver = None
        self.publisher = MQTTPublisher()
        self.bridge = MQTTBridge()
        self.chat_poller: ChatPoller | None = None
        self.ml_poller: MLPoller | None = None
        self.topic_poller: TopicPoller | None = None
        self.machine_poller: MachinePoller | None = None
        self.ladder_poller: LadderPoller | None = None
        self.k8s_poller: K8sPoller | None = None
        self.broker_poller: BrokerPoller | None = None
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting VirtualFactory2.0 Publisher...")
        logger.info(f"Topic prefix: {config.topic_prefix}")

        # Init Neo4j driver
        self._driver = AsyncGraphDatabase.driver(
            config.neo4j_uri,
            auth=(config.neo4j_user, config.neo4j_password)
        )
        logger.info(f"Neo4j driver initialized: {config.neo4j_uri}")

        # Init pollers
        self.chat_poller = ChatPoller(self._driver, self.publisher)
        self.ml_poller = MLPoller(self._driver, self.publisher)
        self.topic_poller = TopicPoller(self._driver, self.publisher)
        self.machine_poller = MachinePoller(self._driver, self.publisher)
        self.ladder_poller = LadderPoller(self._driver, self.publisher)
        self.k8s_poller = K8sPoller(self.publisher)
        self.broker_poller = BrokerPoller(self.publisher)

        # Start MQTT publisher (shared by all pollers)
        await self.publisher.start()

        # Start MQTT bridge (real-time telemetry)
        await self.bridge.start()

        # Start all pollers
        await self.chat_poller.start()
        await self.ml_poller.start()
        await self.topic_poller.start()
        await self.machine_poller.start()
        await self.ladder_poller.start()
        await self.k8s_poller.start()
        await self.broker_poller.start()

        # Start health server
        asyncio.create_task(start_health_server(self))

        logger.info("VirtualFactory2.0 Publisher started successfully")

    async def stop(self) -> None:
        """Stop all services."""
        logger.info("Stopping VirtualFactory2.0 Publisher...")

        # Stop pollers
        if self.broker_poller:
            await self.broker_poller.stop()
        if self.k8s_poller:
            await self.k8s_poller.stop()
        if self.ladder_poller:
            await self.ladder_poller.stop()
        if self.machine_poller:
            await self.machine_poller.stop()
        if self.topic_poller:
            await self.topic_poller.stop()
        if self.ml_poller:
            await self.ml_poller.stop()
        if self.chat_poller:
            await self.chat_poller.stop()

        # Stop bridge and publisher
        await self.bridge.stop()
        await self.publisher.stop()

        # Close Neo4j
        if self._driver:
            await self._driver.close()

        logger.info("VirtualFactory2.0 Publisher stopped")

    async def run(self) -> None:
        """Run until shutdown signal."""
        await self.start()
        await self._shutdown_event.wait()
        await self.stop()

    def shutdown(self) -> None:
        """Trigger shutdown."""
        self._shutdown_event.set()

    def get_health(self) -> dict:
        """Get overall health status."""
        bridge_ok = self.bridge.is_connected
        return {
            "status": "healthy" if bridge_ok else "degraded",
            "bridge": self.bridge.get_stats(),
            "publisher": self.publisher.get_stats(),
            "pollers": {
                "chat": self.chat_poller.get_stats() if self.chat_poller else None,
                "ml": self.ml_poller.get_stats() if self.ml_poller else None,
                "topics": self.topic_poller.get_stats() if self.topic_poller else None,
                "machines": self.machine_poller.get_stats() if self.machine_poller else None,
                "ladder": self.ladder_poller.get_stats() if self.ladder_poller else None,
                "k8s": self.k8s_poller.get_stats() if self.k8s_poller else None,
                "broker": self.broker_poller.get_stats() if self.broker_poller else None,
            }
        }


async def main():
    app = VirtualFactoryPublisher()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.shutdown)

    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
