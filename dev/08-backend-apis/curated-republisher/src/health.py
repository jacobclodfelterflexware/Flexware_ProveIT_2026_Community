"""Health check HTTP server."""
from aiohttp import web


async def start_health_server(app) -> None:
    """Start HTTP server for health checks."""

    async def health_handler(request):
        health = app.get_health()
        status = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status)

    async def ready_handler(request):
        mqtt_ok = (
            app.mqtt_bridge.is_uncurated_connected and
            app.mqtt_bridge.is_curated_connected
        )
        cache_ok = app.mapping_cache.total_mappings >= 0

        if mqtt_ok and cache_ok:
            return web.json_response({"ready": True})
        return web.json_response({"ready": False}, status=503)

    http_app = web.Application()
    http_app.router.add_get("/health", health_handler)
    http_app.router.add_get("/ready", ready_handler)

    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
