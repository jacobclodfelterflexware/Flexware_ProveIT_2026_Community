"""Curated Republisher main entry point."""
import asyncio
import logging
import signal

from config import config
from services.mapping_cache import MappingCache
from services.neo4j_writer import Neo4jWriter
from services.mqtt_bridge import MQTTBridge
from health import start_health_server

logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CuratedRepublisher:
    """Main application orchestrating all services."""

    def __init__(self):
        self.mapping_cache = MappingCache()
        self.neo4j_writer = Neo4jWriter()
        self.mqtt_bridge = MQTTBridge(
            mapping_cache=self.mapping_cache,
            neo4j_writer=self.neo4j_writer
        )
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting Curated Republisher...")

        await self.mapping_cache.start()
        await self.neo4j_writer.start()
        await self.mqtt_bridge.start()

        # Start health server
        asyncio.create_task(start_health_server(self))

        logger.info("Curated Republisher started successfully")

    async def stop(self) -> None:
        """Stop all services."""
        logger.info("Stopping Curated Republisher...")

        await self.mqtt_bridge.stop()
        await self.neo4j_writer.stop()
        await self.mapping_cache.stop()

        logger.info("Curated Republisher stopped")

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
        mqtt_healthy = (
            self.mqtt_bridge.is_uncurated_connected and
            self.mqtt_bridge.is_curated_connected
        )
        return {
            "status": "healthy" if mqtt_healthy else "degraded",
            "uncurated_connected": self.mqtt_bridge.is_uncurated_connected,
            "curated_connected": self.mqtt_bridge.is_curated_connected,
            "mapping_cache": self.mapping_cache.get_stats(),
            "bridge": self.mqtt_bridge.get_stats(),
            "neo4j_writer": self.neo4j_writer.get_stats()
        }


async def main():
    app = CuratedRepublisher()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.shutdown)

    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
