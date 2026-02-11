"""REST API wrapper for MCP Server tools.

Provides REST endpoints that wrap the MCP tools for use by services
that can't use the MCP protocol directly (like Schema Advisor).
"""
import logging
from typing import Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .clients.ingestor_client import get_ingestor_client
from .clients.postgres_client import get_postgres_client

logger = logging.getLogger(__name__)


async def similar_topics_any(request: Request) -> JSONResponse:
    """
    Find similar topics using vector similarity.

    POST /tools/similar_topics_any
    Body: {"topic": str, "k": int, "broker_filter": str}
    """
    try:
        body = await request.json()
        topic = body.get("topic", "")
        k = body.get("k", 20)
        broker_filter = body.get("broker_filter", "all")

        client = await get_ingestor_client()

        # Map broker_filter to broker param
        broker = None if broker_filter == "all" else broker_filter

        result = await client.similar_topics(
            query=topic,
            k=k,
            broker=broker
        )

        # Transform to expected format
        # Ingestor returns: path, text, score
        # Frontend expects: path, score (for SimilarTopic type)
        topics = []
        for item in result.get("results", []):
            topics.append({
                "path": item.get("path", item.get("topic", "")),
                "score": item.get("score", item.get("similarity", 0.0)),
                "broker": broker if broker else "uncurated",
            })

        return JSONResponse({
            "success": True,
            "topics": topics,
            "count": len(topics)
        })

    except Exception as e:
        logger.error(f"similar_topics_any error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "topics": []
        }, status_code=500)


async def similar_messages_any(request: Request) -> JSONResponse:
    """
    Find similar messages using vector similarity.

    POST /tools/similar_messages_any
    Body: {"topic": str, "payload": str, "k": int, "broker_filter": str}
    """
    try:
        body = await request.json()
        topic = body.get("topic", "")
        payload = body.get("payload", "")
        k = body.get("k", 50)
        broker_filter = body.get("broker_filter", "all")

        client = await get_ingestor_client()

        # Map broker_filter to broker param
        broker = None if broker_filter == "all" else broker_filter

        # Combine topic and payload for query
        query = f"{topic} {payload}" if payload else topic

        result = await client.similar_messages(
            query=query,
            k=k,
            broker=broker
        )

        # Transform to expected format
        # Ingestor returns: topicPath, payloadText, timestamp, score
        # Frontend expects: topicPath, payloadText, score (for SimilarMessage type)
        messages = []
        for item in result.get("results", []):
            messages.append({
                "topicPath": item.get("topicPath", item.get("topic", "")),
                "payloadText": item.get("payloadText", item.get("payload", "")),
                "score": item.get("score", item.get("similarity", 0.0)),
                "broker": broker if broker else "uncurated",
            })

        return JSONResponse({
            "success": True,
            "messages": messages,
            "count": len(messages)
        })

    except Exception as e:
        logger.error(f"similar_messages_any error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "messages": []
        }, status_code=500)


async def get_mapping_status(request: Request) -> JSONResponse:
    """
    Check if a mapping already exists for a raw topic.

    POST /tools/get_mapping_status
    Body: {"raw_topic": str}
    """
    try:
        body = await request.json()
        raw_topic = body.get("raw_topic", "")

        client = await get_postgres_client()
        mapping = await client.get_topic_mapping(source_topic=raw_topic)

        if mapping:
            return JSONResponse({
                "success": True,
                "exists": True,
                "mapping": mapping
            })
        else:
            return JSONResponse({
                "success": True,
                "exists": False,
                "mapping": None
            })

    except Exception as e:
        logger.error(f"get_mapping_status error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "exists": False
        }, status_code=500)


async def get_topic_tree(request: Request) -> JSONResponse:
    """
    Get topic tree structure.

    POST /tools/get_topic_tree
    Body: {"broker": str, "root_path": str}
    """
    try:
        body = await request.json()
        broker = body.get("broker", "curated")
        root_path = body.get("root_path", "")

        client = await get_ingestor_client()

        # Use hierarchical topics to build tree
        result = await client.hierarchical_topics(
            topic=root_path if root_path else "/",
            k=100,
            broker=broker
        )

        # Build a simple tree structure from results
        tree = {"root": root_path, "children": []}
        seen_paths = set()

        for item in result.get("results", []):
            topic = item.get("topic", "")
            if topic and topic not in seen_paths:
                seen_paths.add(topic)
                tree["children"].append({
                    "path": topic,
                    "messageCount": item.get("message_count", 0)
                })

        return JSONResponse({
            "success": True,
            "tree": tree
        })

    except Exception as e:
        logger.error(f"get_topic_tree error: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "tree": {}
        }, status_code=500)


async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "service": "mcp-server-rest"})


# Define REST routes
rest_routes = [
    Route("/tools/similar_topics_any", similar_topics_any, methods=["POST"]),
    Route("/tools/similar_messages_any", similar_messages_any, methods=["POST"]),
    Route("/tools/get_mapping_status", get_mapping_status, methods=["POST"]),
    Route("/tools/get_topic_tree", get_topic_tree, methods=["POST"]),
    Route("/health", health_check, methods=["GET"]),
]


def create_rest_app() -> Starlette:
    """Create the REST API Starlette application."""
    return Starlette(routes=rest_routes)
