"""ML Predictor Service - FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.models.schemas import HealthResponse
from src.database import init_neo4j, close_neo4j, get_neo4j_driver
from src.jobs.background_training import background_training_loop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_neo4j()
    training_task = asyncio.create_task(background_training_loop())
    yield
    training_task.cancel()
    try:
        await training_task
    except asyncio.CancelledError:
        pass
    await close_neo4j()


# Create FastAPI application
app = FastAPI(
    title="ML Predictor Service",
    description="Machine learning predictions and regression analysis for machine telemetry",
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

# Import and include routers after app creation to avoid circular imports
from src.api import predictions, regression, training, transforms

app.include_router(predictions.router, prefix="/api", tags=["Predictions"])
app.include_router(regression.router, prefix="/api", tags=["Regression"])
app.include_router(training.router, prefix="/api", tags=["Training"])
app.include_router(transforms.router, prefix="/api", tags=["Transforms"])


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Check service health and Neo4j connectivity."""
    neo4j_connected = False
    driver = get_neo4j_driver()

    if driver:
        try:
            async with driver.session() as session:
                result = await session.run("RETURN 1 as n")
                await result.single()
                neo4j_connected = True
        except Exception as e:
            logger.warning(f"Neo4j health check failed: {e}")

    return HealthResponse(
        status="healthy" if neo4j_connected else "degraded",
        neo4j_connected=neo4j_connected,
        version="1.0.0"
    )


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {"service": "ml-predictor", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
