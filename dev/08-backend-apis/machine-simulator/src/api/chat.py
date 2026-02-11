"""Chat API endpoints for machine-specific conversations."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services import chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # 'user', 'assistant', or 'system'
    content: str


class HistoricalMessage(BaseModel):
    """A historical MQTT message."""
    topic: str
    payload: dict
    timestamp: str


class GraphRelationships(BaseModel):
    """Graph relationships for a topic."""
    parent_topics: list[str] = []
    child_topics: list[str] = []


class HistoricalContext(BaseModel):
    """Historical context for a machine."""
    recent_messages: list[HistoricalMessage] = []
    graph_relationships: GraphRelationships = GraphRelationships()


class SimilarTopic(BaseModel):
    """A similar topic from RAG search."""
    topic_path: str
    similarity: float
    field_names: list[str] = []
    historical_payloads: list[dict] = []


class RAGContext(BaseModel):
    """RAG context from similarity search."""
    query: str
    similar_topics: list[SimilarTopic] = []


class PredictionMetrics(BaseModel):
    """Prediction model metrics."""
    rmse: Optional[float] = None
    mae: Optional[float] = None
    mape: Optional[float] = None


class PredictionPoint(BaseModel):
    """A single prediction point."""
    date: str
    value: float
    lower: float
    upper: float


class PredictionContext(BaseModel):
    """Time series prediction context."""
    field: str
    topic: str
    horizon: str
    predictions: list[PredictionPoint] = []
    metrics: PredictionMetrics = PredictionMetrics()
    dataPointsUsed: int = 0


class RegressionFeature(BaseModel):
    """A feature in the regression model."""
    topic: str
    field: str
    coefficient: float
    pValue: Optional[float] = None
    importance: Optional[float] = None


class RegressionContext(BaseModel):
    """Linear regression context."""
    targetField: str
    targetTopic: str
    features: list[RegressionFeature] = []
    intercept: float = 0
    rSquared: float = 0
    correlationMatrix: dict = {}
    dataPointsUsed: int = 0


class MLContext(BaseModel):
    """ML insights context."""
    prediction: Optional[PredictionContext] = None
    regression: Optional[RegressionContext] = None


class MachineContext(BaseModel):
    """Machine context for chat."""
    id: Optional[str] = None
    name: str
    machine_type: Optional[str] = None
    description: Optional[str] = None
    status: str = "draft"
    publish_interval_ms: int = 5000
    topic_path: Optional[str] = None
    topics: list[dict] = []
    fields: list[dict] = []
    similarity_results: list[dict] = []


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    machine_context: MachineContext
    historical_context: Optional[HistoricalContext] = None
    rag_context: Optional[RAGContext] = None
    ml_context: Optional[MLContext] = None
    conversation_history: list[ChatMessage] = []
    user_message: str
    stream: bool = True


class ChatResponse(BaseModel):
    """Response for non-streaming chat."""
    content: str
    role: str = "assistant"


@router.post("/completion")
async def chat_completion(request: ChatRequest):
    """Process a chat message and return response.

    If stream=true (default), returns a Server-Sent Events stream.
    If stream=false, returns a single JSON response.
    """
    if not request.user_message:
        raise HTTPException(status_code=400, detail="user_message is required")

    logger.info(f"Chat request for machine: {request.machine_context.name}")
    logger.info(f"User message: {request.user_message[:100]}...")
    logger.info(f"Stream mode: {request.stream}")

    # Convert Pydantic models to dicts
    machine_context = request.machine_context.model_dump()
    historical_context = request.historical_context.model_dump() if request.historical_context else {}
    rag_context = request.rag_context.model_dump() if request.rag_context else None
    ml_context = request.ml_context.model_dump() if request.ml_context else None
    conversation_history = [msg.model_dump() for msg in request.conversation_history]

    try:
        if request.stream:
            # Streaming response
            async def event_generator():
                try:
                    async for chunk in chat_service.chat_stream(
                        machine_context=machine_context,
                        historical_context=historical_context,
                        rag_context=rag_context,
                        ml_context=ml_context,
                        conversation_history=conversation_history,
                        user_message=request.user_message,
                    ):
                        # Send each chunk as SSE event
                        yield f"data: {json.dumps({'content': chunk})}\n\n"

                    # Send done event
                    yield f"data: {json.dumps({'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            # Non-streaming response
            content = await chat_service.chat(
                machine_context=machine_context,
                historical_context=historical_context,
                rag_context=rag_context,
                ml_context=ml_context,
                conversation_history=conversation_history,
                user_message=request.user_message,
            )
            return ChatResponse(content=content)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")
