"""Schema Advisor main entry point."""
import asyncio
import logging
import signal

from aiohttp import web

from config import config
from services.orchestrator import SchemaOrchestrator
from services.conversation_service import ConversationService
from api.routes import setup_routes

logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    # Initialize orchestrator
    orchestrator = SchemaOrchestrator()
    await orchestrator.start()

    # Initialize conversation service (reuses orchestrator's connections)
    conversation_service = ConversationService(
        driver=orchestrator._driver,
        mcp=orchestrator.mcp,
        llm=orchestrator.llm
    )
    logger.info("ConversationService initialized")

    # Create app
    app = web.Application()
    setup_routes(app, orchestrator, conversation_service)

    # Start server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()

    logger.info(f"Schema Advisor running on {config.host}:{config.port}")

    # Wait for shutdown
    shutdown_event = asyncio.Event()

    def handle_signal():
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await shutdown_event.wait()

    # Cleanup
    await runner.cleanup()
    await orchestrator.stop()
    logger.info("Schema Advisor shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
