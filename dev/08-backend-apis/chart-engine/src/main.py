import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import router
from services.rag_service import RAGService
from services.llm_service import LLMService
from services.skill_executor import SkillExecutor
from services.stream_manager import StreamManager
from skills.registry import SkillRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, cleanup on shutdown."""
    # Initialize services
    app.state.skill_registry = SkillRegistry()
    app.state.skill_registry.load_skills()

    app.state.rag_service = RAGService(
        ingestor_url=os.getenv("INGESTOR_URL", "http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT_3"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT"),
        neo4j_user=os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "YOUR_DB_PASSWORD")
    )

    app.state.llm_service = LLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4")
    )

    app.state.skill_executor = SkillExecutor(
        registry=app.state.skill_registry,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://YOUR_NEO4J_HOST:YOUR_NEO4J_BOLT_PORT"),
        neo4j_user=os.getenv("NEO4J_USER", "YOUR_NEO4J_USERNAME"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "YOUR_DB_PASSWORD")
    )

    app.state.stream_manager = StreamManager()

    print(f"Chart Engine started. Loaded {len(app.state.skill_registry.skills)} skills.")

    yield

    # Cleanup
    await app.state.skill_executor.close()
    await app.state.stream_manager.close()
    await app.state.rag_service.close()
    print("Chart Engine shutdown complete.")


app = FastAPI(
    title="Chart Engine",
    description="RAG-powered dynamic chart generation from natural language",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "chart-engine",
        "skills_loaded": len(app.state.skill_registry.skills) if hasattr(app.state, 'skill_registry') else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "YOUR_API_PORT_3")),
        reload=os.getenv("ENV", "production") == "development"
    )
