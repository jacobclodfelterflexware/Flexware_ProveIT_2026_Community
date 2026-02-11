"""FastAPI application for PLCopen XML Import/Export."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import Config
from api import api_router
from api.schemas import HealthResponse

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting PLCopen XML API...")
    Config.display()
    yield
    logger.info("PLCopen XML API shutdown complete")


app = FastAPI(
    title="PLCopen XML API",
    description="Import, export, and validate PLCopen IEC 61131-3 XML files for LLM integration",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return HealthResponse(status="healthy")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "PLCopen XML API",
        "version": "1.0.0",
        "description": "Import, export, and validate PLCopen IEC 61131-3 XML files",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "validate": "POST /api/v1/plcopen/validate",
            "import": "POST /api/v1/plcopen/import",
            "export": "POST /api/v1/plcopen/export",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=Config.API_HOST, port=Config.API_PORT, reload=False)
