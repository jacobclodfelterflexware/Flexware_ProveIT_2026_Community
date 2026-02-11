"""REST API routes for Schema Advisor."""
import json
import logging
from typing import Optional

from aiohttp import web

from services.orchestrator import SchemaOrchestrator
from services.conversation_service import ConversationService

logger = logging.getLogger(__name__)


def setup_routes(
    app: web.Application,
    orchestrator: SchemaOrchestrator,
    conversation_service: Optional[ConversationService] = None
):
    """Set up API routes."""

    async def suggest_schema(request):
        """
        POST /api/v1/suggest

        Request body:
        {
            "raw_topic": "building1/4F/room12/temp_sensor",
            "raw_payload": "{\"t\": 21.3, \"hum\": 44}",
            "created_by": "user@example.com"  (optional)
        }
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400
            )

        raw_topic = body.get("raw_topic")
        raw_payload = body.get("raw_payload", "{}")

        if not raw_topic:
            return web.json_response(
                {"error": "raw_topic is required"},
                status=400
            )

        result = await orchestrator.suggest_schema(
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            created_by=body.get("created_by", "api-user")
        )

        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)

    async def preview_suggest(request):
        """
        POST /api/v1/preview-suggest

        Preview a schema suggestion without creating a mapping.
        Returns the suggestion along with similar topics/messages for context.

        Request body:
        {
            "raw_topic": "factory/line1/sensor/temp",
            "raw_payload": "{\"t\": 45.2, \"unit\": \"C\"}"
        }

        Response:
        {
            "success": true,
            "suggestion": {...},
            "similar_topics": [...],
            "similar_messages": [...]
        }
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"error": "Invalid JSON"},
                status=400
            )

        raw_topic = body.get("raw_topic")
        raw_payload = body.get("raw_payload", "{}")

        if not raw_topic:
            return web.json_response(
                {"error": "raw_topic is required"},
                status=400
            )

        result = await orchestrator.suggest_schema(
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            created_by="preview",
            preview_only=True
        )

        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)

    async def batch_suggest(request):
        """
        POST /api/v1/suggest/batch

        Process multiple unmapped topics.

        Request body:
        {
            "limit": 10
        }
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            body = {}

        limit = body.get("limit", 10)

        results = await orchestrator.suggest_for_unmapped_topics(limit=limit)

        return web.json_response({
            "processed": len(results),
            "results": results
        })

    async def health(request):
        """GET /health"""
        return web.json_response({"status": "healthy"})

    async def ready(request):
        """GET /ready"""
        # Could add more sophisticated checks here
        return web.json_response({"ready": True})

    # ========== Conversation Routes ==========

    async def start_conversation(request):
        """
        POST /api/v1/conversation/start

        Start a new conversational schema mapping session.

        Request body:
        {
            "raw_topic": "building1/4F/room12/temp_sensor",
            "raw_payload": "{\"t\": 21.3}",
            "created_by": "user@example.com"  (optional)
        }
        """
        if not conversation_service:
            return web.json_response(
                {"error": "Conversation service not available"},
                status=503
            )

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        raw_topic = body.get("raw_topic")
        raw_payload = body.get("raw_payload", "{}")

        if not raw_topic:
            return web.json_response(
                {"error": "raw_topic is required"},
                status=400
            )

        result = await conversation_service.start_conversation(
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            created_by=body.get("created_by", "api-user"),
            initial_suggestion=body.get("initial_suggestion")
        )

        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)

    async def continue_conversation(request):
        """
        POST /api/v1/conversation/{id}/message

        Send a message to continue the conversation.

        Request body:
        {
            "message": "The sensor is located in the machining area"
        }
        """
        if not conversation_service:
            return web.json_response(
                {"error": "Conversation service not available"},
                status=503
            )

        conversation_id = request.match_info["id"]

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        message = body.get("message")
        if not message:
            return web.json_response(
                {"error": "message is required"},
                status=400
            )

        result = await conversation_service.continue_conversation(
            conversation_id=conversation_id,
            user_message=message
        )

        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)

    async def accept_proposal(request):
        """
        POST /api/v1/conversation/{id}/accept

        Accept the current proposal and create a SchemaMapping.

        Request body (optional edits):
        {
            "edits": {
                "curatedTopic": "edited/topic/path",
                "payloadMapping": {"t": "temperature_c"}
            }
        }
        """
        if not conversation_service:
            return web.json_response(
                {"error": "Conversation service not available"},
                status=503
            )

        conversation_id = request.match_info["id"]

        try:
            body = await request.json()
        except:
            body = {}

        result = await conversation_service.accept_proposal(
            conversation_id=conversation_id,
            edits=body.get("edits")
        )

        status = 200 if result.get("success") else 400
        return web.json_response(result, status=status)

    async def get_conversation(request):
        """
        GET /api/v1/conversation/{id}

        Get full conversation details and history.
        """
        if not conversation_service:
            return web.json_response(
                {"error": "Conversation service not available"},
                status=503
            )

        conversation_id = request.match_info["id"]
        result = await conversation_service.get_conversation(conversation_id)

        status = 200 if result.get("success") else 404
        return web.json_response(result, status=status)

    # Register routes
    app.router.add_post("/api/v1/suggest", suggest_schema)
    app.router.add_post("/api/v1/preview-suggest", preview_suggest)
    app.router.add_post("/api/v1/suggest/batch", batch_suggest)
    app.router.add_get("/health", health)
    app.router.add_get("/ready", ready)

    # Conversation routes
    app.router.add_post("/api/v1/conversation/start", start_conversation)
    app.router.add_post("/api/v1/conversation/{id}/message", continue_conversation)
    app.router.add_post("/api/v1/conversation/{id}/accept", accept_proposal)
    app.router.add_get("/api/v1/conversation/{id}", get_conversation)
