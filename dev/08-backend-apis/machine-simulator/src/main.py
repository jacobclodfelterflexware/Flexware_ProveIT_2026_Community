"""Machine Simulator Service - FastAPI Application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import config
from .api import machines, suggestions, images, chat, kb_chat
from .services.machine_store import machine_store
from .services.publisher import publisher
from .models import MachineStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger.info("Machine Simulator service starting...")
    logger.info(f"Neo4j URI: {config.neo4j_uri}")
    logger.info(f"MQTT Host: {config.mqtt_host}:{config.mqtt_port}")

    # Connect to Neo4j
    await machine_store.connect()

    # Restore running machines from previous session
    try:
        running_machines = await machine_store.list_all(status=MachineStatus.RUNNING)
        if running_machines:
            logger.info(f"Restoring {len(running_machines)} running machine(s)...")
            for machine in running_machines:
                try:
                    await publisher.start_machine(machine)
                    logger.info(f"Restored machine: {machine.name} ({machine.id})")
                except Exception as e:
                    logger.error(f"Failed to restore machine {machine.name}: {e}")
        else:
            logger.info("No running machines to restore")
    except Exception as e:
        logger.error(f"Error restoring running machines: {e}")

    yield

    # Stop all running machines
    logger.info("Stopping all running machines...")
    await publisher.stop_all()

    # Disconnect from Neo4j
    await machine_store.close()
    logger.info("Machine Simulator service shutting down...")


app = FastAPI(
    title="Machine Simulator",
    description="Service for creating and running simulated industrial machines that publish MQTT telemetry",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(machines.router)
app.include_router(suggestions.router)
app.include_router(images.router)
app.include_router(chat.router)
app.include_router(kb_chat.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "machine-simulator"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "machine-simulator",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "machines": "/api/machines",
            "suggestions": "/api/suggestions",
            "images": "/api/images",
            "chat": "/api/chat",
            "kb_chat": "/api/kb-chat",
            "docs": "/docs"
        }
    }
