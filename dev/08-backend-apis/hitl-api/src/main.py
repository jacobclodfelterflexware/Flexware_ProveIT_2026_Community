"""HITL API main entry point."""
import asyncio
import logging
import signal

from aiohttp import web
from aiohttp_cors import setup as cors_setup, ResourceOptions
from neo4j import AsyncGraphDatabase

from config import config
from api.mappings import setup_mapping_routes
from api.unmapped import setup_unmapped_routes

logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_app() -> web.Application:
    """Create and configure the application."""
    app = web.Application()

    # Initialize Neo4j driver
    driver = AsyncGraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password)
    )
    app['neo4j'] = driver

    # Setup routes
    setup_mapping_routes(app, driver)
    setup_unmapped_routes(app, driver)

    # Health check
    async def health(request):
        return web.json_response({'status': 'healthy'})

    async def ready(request):
        # Check Neo4j connection
        try:
            async with driver.session() as session:
                await session.run("RETURN 1")
            return web.json_response({'ready': True})
        except Exception as e:
            return web.json_response({'ready': False, 'error': str(e)}, status=503)

    app.router.add_get('/health', health)
    app.router.add_get('/ready', ready)

    # Setup CORS
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        )
    })

    # Apply CORS to all routes
    for route in list(app.router.routes()):
        cors.add(route)

    # Cleanup on shutdown
    async def cleanup(app):
        await app['neo4j'].close()
        logger.info("Neo4j connection closed")

    app.on_cleanup.append(cleanup)

    return app


async def main():
    """Main entry point."""
    app = await create_app()

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.host, config.port)
    await site.start()

    logger.info(f"HITL API running on {config.host}:{config.port}")

    # Wait for shutdown
    shutdown_event = asyncio.Event()

    def handle_signal():
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await shutdown_event.wait()

    await runner.cleanup()
    logger.info("HITL API shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
