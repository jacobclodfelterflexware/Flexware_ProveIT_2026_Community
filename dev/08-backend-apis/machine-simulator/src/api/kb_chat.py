"""Knowledge base chat API endpoints for ProveITGPT."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.kb_chat_service import kb_chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb-chat", tags=["knowledge-base"])


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str
    content: str


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


class KBChatRequest(BaseModel):
    """Request body for knowledge base chat endpoint."""
    graph_summary: Optional[dict] = None
    rag_context: Optional[RAGContext] = None
    conversation_history: list[ChatMessage] = []
    user_message: str
    stream: bool = True


class KBChatResponse(BaseModel):
    """Response for non-streaming chat."""
    content: str
    role: str = "assistant"


@router.post("/completion")
async def kb_chat_completion(request: KBChatRequest):
    """Process a knowledge base chat message and return response.

    If stream=true (default), returns a Server-Sent Events stream.
    If stream=false, returns a single JSON response.
    """
    if not request.user_message:
        raise HTTPException(status_code=400, detail="user_message is required")

    logger.info(f"[ProveITGPT] KB chat request: {request.user_message[:100]}...")
    logger.info(f"[ProveITGPT] Stream mode: {request.stream}")

    rag_context = request.rag_context.model_dump() if request.rag_context else None
    conversation_history = [msg.model_dump() for msg in request.conversation_history]

    try:
        if request.stream:
            async def event_generator():
                try:
                    async for chunk in kb_chat_service.chat_stream(
                        graph_summary=request.graph_summary,
                        rag_context=rag_context,
                        conversation_history=conversation_history,
                        user_message=request.user_message,
                    ):
                        yield f"data: {json.dumps({'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'done': True})}\n\n"
                except Exception as e:
                    logger.error(f"[ProveITGPT] Streaming error: {e}")
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
            content = await kb_chat_service.chat(
                graph_summary=request.graph_summary,
                rag_context=rag_context,
                conversation_history=conversation_history,
                user_message=request.user_message,
            )
            return KBChatResponse(content=content)

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"[ProveITGPT] Chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")
