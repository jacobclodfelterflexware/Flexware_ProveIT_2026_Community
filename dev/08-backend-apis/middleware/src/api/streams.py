"""SSE streaming endpoints for topic trees and statistics."""
import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


SSE_UPDATE_INTERVAL = float(os.getenv("SSE_UPDATE_INTERVAL", "2.0"))

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["Streaming"])

# Global references to services (set by main.py)
mqtt_bridge = None
mapping_cache = None


def set_services(bridge, cache) -> None:
    """Set service references for streaming endpoints."""
    global mqtt_bridge, mapping_cache
    mqtt_bridge = bridge
    mapping_cache = cache


async def _generate_sse(
    request: Request,
    data_func,
    event_name: str = "data",
) -> AsyncGenerator[str, None]:
    """Generate SSE stream with periodic updates."""
    while True:
        # Check if client disconnected
        if await request.is_disconnected():
            break

        try:
            data = data_func()
            yield f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
        except Exception as e:
            logger.error(f"Error generating SSE data: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        await asyncio.sleep(SSE_UPDATE_INTERVAL)


@router.get("/uncurated")
async def stream_uncurated(request: Request):
    """Stream uncurated broker topic tree via SSE."""
    if mqtt_bridge is None:
        return StreamingResponse(
            iter(["event: error\ndata: {\"error\": \"Service not ready\"}\n\n"]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _generate_sse(request, mqtt_bridge.get_uncurated_tree, "tree"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/curated")
async def stream_curated(request: Request):
    """Stream curated broker topic tree via SSE."""
    if mqtt_bridge is None:
        return StreamingResponse(
            iter(["event: error\ndata: {\"error\": \"Service not ready\"}\n\n"]),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _generate_sse(request, mqtt_bridge.get_curated_tree, "tree"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stats")
async def stream_stats(request: Request):
    """Stream mapping statistics via SSE."""
    if mapping_cache is None:
        return StreamingResponse(
            iter(["event: error\ndata: {\"error\": \"Service not ready\"}\n\n"]),
            media_type="text/event-stream",
        )

    async def generate_stats():
        while True:
            if await request.is_disconnected():
                break

            try:
                stats = await mapping_cache.get_full_stats()
                yield f"event: stats\ndata: {json.dumps(stats)}\n\n"
            except Exception as e:
                logger.error(f"Error generating stats: {e}")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(SSE_UPDATE_INTERVAL)

    return StreamingResponse(
        generate_stats(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
