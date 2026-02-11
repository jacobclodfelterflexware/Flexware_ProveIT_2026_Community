import asyncio
import logging
import signal

from config import config
from services.mqtt_subscriber import MQTTSubscriber
from services.ingestion import IngestionService
from services.cleanup import CleanupService
from health import start_health_server

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UncuratedIngestor:
    """Main application orchestrating all services."""

    def __init__(self):
        self.ingestion = IngestionService()
        self.cleanup = CleanupService()
        self.subscriber = MQTTSubscriber(
            message_handler=self.ingestion.ingest
        )
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start all services."""
        logger.info("Starting Uncurated Ingestor...")

        # Start services
        await self.ingestion.start()
        await self.cleanup.start()
        await self.subscriber.start()

        # Start health server
        asyncio.create_task(start_health_server(self))

        logger.info("Uncurated Ingestor started successfully")

    async def stop(self) -> None:
        """Stop all services."""
        logger.info("Stopping Uncurated Ingestor...")

        await self.subscriber.stop()
        await self.ingestion.stop()
        await self.cleanup.stop()

        logger.info("Uncurated Ingestor stopped")

    async def run(self) -> None:
        """Run until shutdown signal."""
        await self.start()

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        await self.stop()

    def shutdown(self) -> None:
        """Trigger shutdown."""
        self._shutdown_event.set()

    def get_health(self) -> dict:
        """Get overall health status."""
        return {
            "status": "healthy" if self.subscriber.is_connected else "degraded",
            "mqtt_connected": self.subscriber.is_connected,
            "messages_received": self.subscriber.messages_received,
            "ingestion": self.ingestion.get_stats(),
            "cleanup": self.cleanup.get_stats()
        }


async def main():
    app = UncuratedIngestor()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, app.shutdown)

    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
