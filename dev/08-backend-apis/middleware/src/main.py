"""FastAPI application entry point for MQTT Middleware."""
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import init_db, close_db
from api import api_router
from api.streams import set_services
from api.schemas import HealthResponse
from services import MappingCache, MQTTBridge

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global service instances
mqtt_bridge: Optional[MQTTBridge] = None
mapping_cache: Optional[MappingCache] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global mqtt_bridge, mapping_cache

    logger.info("Starting MQTT Middleware...")
    Config.display()

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize mapping cache with LISTEN/NOTIFY
    mapping_cache = MappingCache()
    await mapping_cache.start()
    logger.info("Mapping cache initialized")

    # Initialize MQTT bridge
    mqtt_bridge = MQTTBridge(mapping_cache)
    await mqtt_bridge.start()
    logger.info("MQTT bridge initialized")

    # Set service references for SSE endpoints
    set_services(mqtt_bridge, mapping_cache)

    logger.info("MQTT Middleware started successfully")

    yield

    # Cleanup
    logger.info("Shutting down MQTT Middleware...")

    if mqtt_bridge:
        await mqtt_bridge.stop()
        logger.info("MQTT bridge stopped")

    if mapping_cache:
        await mapping_cache.stop()
        logger.info("Mapping cache stopped")

    await close_db()
    logger.info("Database connection closed")

    logger.info("MQTT Middleware shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="MQTT Topic Middleware",
    description="Topic mapping and transformation middleware for MQTT brokers",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return HealthResponse(
        status="healthy",
        mqtt_uncurated_connected=mqtt_bridge.is_uncurated_connected if mqtt_bridge else False,
        mqtt_curated_connected=mqtt_bridge.is_curated_connected if mqtt_bridge else False,
        database_connected=True,  # If we get here, DB is connected
        cache_ready=mapping_cache.is_ready if mapping_cache else False,
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "MQTT Topic Middleware",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=False,
    )
