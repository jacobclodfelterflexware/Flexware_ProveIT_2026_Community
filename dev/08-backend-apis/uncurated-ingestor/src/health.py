import asyncio
import logging
from aiohttp import web

from datetime import datetime

from neo4j import AsyncGraphDatabase
from config import config
from embedding import embed
from neo4j_utils import (
    similar_topics,
    similar_messages,
    similar_topics_hierarchical,
    similar_messages_temporal,
    similar_combined,
    find_related_topics,
    get_rag_context_for_topic,
)

logger = logging.getLogger(__name__)


async def start_health_server(app) -> None:
    """Start HTTP server for health checks and API endpoints."""

    async def alive_handler(request):
        return web.json_response({"alive": True})

    async def health_handler(request):
        health = app.get_health()
        status = 200 if health["status"] == "healthy" else 503
        return web.json_response(health, status=status)

    async def ready_handler(request):
        if app.subscriber.is_connected:
            return web.json_response({"ready": True})
        return web.json_response({"ready": False}, status=503)

    async def stats_handler(request):
        return web.json_response({
            "ingestion": app.ingestion.get_stats(),
            "cleanup": app.cleanup.get_stats(),
            "mqtt": {
                "connected": app.subscriber.is_connected,
                "messages_received": app.subscriber.messages_received
            }
        })

    async def similar_topics_handler(request):
        """
        Find similar topics using vector search.

        Query params:
            q: Query text to find similar topics for
            k: Number of results (default: 10)
            broker: Filter by broker (optional)
        """
        query_text = request.query.get("q")
        if not query_text:
            return web.json_response(
                {"error": "Missing required query parameter 'q'"},
                status=400
            )

        k = int(request.query.get("k", "10"))
        broker = request.query.get("broker")

        try:
            # Generate embedding for query text
            query_embedding = embed(query_text)

            # Search for similar topics
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                results = await similar_topics(
                    session,
                    query_embedding=query_embedding,
                    k=k,
                    broker=broker
                )
            await driver.close()

            return web.json_response({
                "query": query_text,
                "count": len(results),
                "results": results
            })
        except Exception as e:
            logger.error(f"Similar topics search error: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def similar_messages_handler(request):
        """
        Find similar messages using vector search.

        Query params:
            q: Query text to find similar messages for
            k: Number of results (default: 10)
            broker: Filter by broker (optional)
        """
        query_text = request.query.get("q")
        if not query_text:
            return web.json_response(
                {"error": "Missing required query parameter 'q'"},
                status=400
            )

        k = int(request.query.get("k", "10"))
        broker = request.query.get("broker")

        try:
            # Generate embedding for query text
            query_embedding = embed(query_text)

            # Search for similar messages
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                results = await similar_messages(
                    session,
                    query_embedding=query_embedding,
                    k=k,
                    broker=broker
                )
            await driver.close()

            # Convert Neo4j DateTime objects to ISO strings
            serializable_results = []
            for r in results:
                item = dict(r)
                if "timestamp" in item and item["timestamp"] is not None:
                    item["timestamp"] = item["timestamp"].isoformat()
                serializable_results.append(item)

            return web.json_response({
                "query": query_text,
                "count": len(serializable_results),
                "results": serializable_results
            })
        except Exception as e:
            logger.error(f"Similar messages search error: {e}")
            return web.json_response(
                {"error": str(e)},
                status=500
            )

    async def hierarchical_topics_handler(request):
        """
        Find topics that share parent segments (siblings/cousins in hierarchy).

        Query params:
            topic: Topic path to find related topics for
            k: Number of results (default: 20)
        """
        topic_path = request.query.get("topic")
        if not topic_path:
            return web.json_response(
                {"error": "Missing required query parameter 'topic'"},
                status=400
            )

        k = int(request.query.get("k", "20"))

        try:
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                results = await similar_topics_hierarchical(
                    session,
                    topic_path=topic_path,
                    k=k
                )
            await driver.close()

            return web.json_response({
                "topic": topic_path,
                "count": len(results),
                "results": results
            })
        except Exception as e:
            logger.error(f"Hierarchical topics search error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def temporal_messages_handler(request):
        """
        Find messages within a time window of a reference timestamp.

        Query params:
            time: ISO timestamp (default: now)
            window: Window size in minutes (default: 5)
            k: Number of results (default: 50)
            broker: Filter by broker (default: uncurated)
        """
        time_str = request.query.get("time")
        if time_str:
            reference_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        else:
            reference_time = datetime.utcnow()

        window_minutes = int(request.query.get("window", "5"))
        k = int(request.query.get("k", "50"))
        broker = request.query.get("broker", "uncurated")

        try:
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                results = await similar_messages_temporal(
                    session,
                    reference_time=reference_time,
                    window_minutes=window_minutes,
                    broker=broker,
                    k=k
                )
            await driver.close()

            # Convert timestamps
            serializable_results = []
            for r in results:
                item = dict(r)
                if "timestamp" in item and item["timestamp"] is not None:
                    item["timestamp"] = item["timestamp"].isoformat()
                serializable_results.append(item)

            return web.json_response({
                "referenceTime": reference_time.isoformat(),
                "windowMinutes": window_minutes,
                "count": len(serializable_results),
                "results": serializable_results
            })
        except Exception as e:
            logger.error(f"Temporal messages search error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def combined_search_handler(request):
        """
        Combined similarity search using vector, hierarchy, and temporal signals.

        Query params:
            q: Query text for semantic similarity
            topic: Reference topic for hierarchical similarity (optional)
            time: Reference timestamp for temporal similarity (optional)
            k: Number of results (default: 20)
            broker: Filter by broker (default: uncurated)
            w_vector: Weight for vector similarity (default: 0.5)
            w_hierarchy: Weight for hierarchy similarity (default: 0.3)
            w_temporal: Weight for temporal similarity (default: 0.2)
        """
        query_text = request.query.get("q")
        if not query_text:
            return web.json_response(
                {"error": "Missing required query parameter 'q'"},
                status=400
            )

        reference_topic = request.query.get("topic")
        time_str = request.query.get("time")
        reference_time = None
        if time_str:
            reference_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

        k = int(request.query.get("k", "20"))
        broker = request.query.get("broker", "uncurated")

        # Parse weights
        weights = {
            "vector": float(request.query.get("w_vector", "0.5")),
            "hierarchy": float(request.query.get("w_hierarchy", "0.3")),
            "temporal": float(request.query.get("w_temporal", "0.2")),
        }

        try:
            query_embedding = embed(query_text)

            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                results = await similar_combined(
                    session,
                    query_embedding=query_embedding,
                    reference_topic=reference_topic,
                    reference_time=reference_time,
                    broker=broker,
                    k=k,
                    weights=weights
                )
            await driver.close()

            # Convert timestamps
            serializable_results = []
            for r in results:
                item = dict(r)
                if "timestamp" in item and item["timestamp"] is not None:
                    item["timestamp"] = item["timestamp"].isoformat()
                serializable_results.append(item)

            return web.json_response({
                "query": query_text,
                "referenceTopic": reference_topic,
                "referenceTime": reference_time.isoformat() if reference_time else None,
                "weights": weights,
                "count": len(serializable_results),
                "results": serializable_results
            })
        except Exception as e:
            logger.error(f"Combined search error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def related_topics_handler(request):
        """
        Find all related topics: siblings, parent, cousins.

        Query params:
            topic: Topic path to find related topics for
            broker: Filter by broker (default: uncurated)
        """
        topic_path = request.query.get("topic")
        if not topic_path:
            return web.json_response(
                {"error": "Missing required query parameter 'topic'"},
                status=400
            )

        broker = request.query.get("broker", "uncurated")

        try:
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                result = await find_related_topics(
                    session,
                    topic_path=topic_path,
                    broker=broker
                )
            await driver.close()

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Related topics search error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def suggest_normalization_handler(request):
        """
        Get RAG context for LLM to suggest topic normalization.

        This endpoint returns topic-to-topic similarity results formatted as
        RAG context for an LLM to suggest:
        - Where the topic should go in the hierarchy
        - How to normalize the topic path naming
        - How to rename/standardize payload key-value pairs

        Query params:
            topic: New topic path (required)
            payload: Sample payload JSON string (optional)
            k: Number of similar topics to return (default: 5)
            broker: Filter by broker (default: uncurated)
        """
        topic_path = request.query.get("topic")
        if not topic_path:
            return web.json_response(
                {"error": "Missing required query parameter 'topic'"},
                status=400
            )

        sample_payload = request.query.get("payload")
        k = int(request.query.get("k", "5"))
        broker = request.query.get("broker", "uncurated")

        try:
            # Generate embedding for the topic path
            topic_embedding = embed(topic_path)

            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                result = await get_rag_context_for_topic(
                    session,
                    topic_path=topic_path,
                    topic_embedding=topic_embedding,
                    sample_payload=sample_payload,
                    k=k
                )
            await driver.close()

            return web.json_response(result)
        except Exception as e:
            logger.error(f"Suggest normalization error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    http_app = web.Application()
    http_app.router.add_get("/alive", alive_handler)
    http_app.router.add_get("/health", health_handler)
    http_app.router.add_get("/ready", ready_handler)
    http_app.router.add_get("/stats", stats_handler)
    # Original vector-only endpoints
    http_app.router.add_get("/api/similar-topics", similar_topics_handler)
    http_app.router.add_get("/api/similar-messages", similar_messages_handler)
    # New enhanced endpoints
    http_app.router.add_get("/api/hierarchical-topics", hierarchical_topics_handler)
    http_app.router.add_get("/api/temporal-messages", temporal_messages_handler)
    http_app.router.add_get("/api/combined-search", combined_search_handler)
    http_app.router.add_get("/api/related-topics", related_topics_handler)
    # RAG endpoint for LLM normalization suggestions
    http_app.router.add_get("/api/suggest-normalization", suggest_normalization_handler)

    async def graph_handler(request):
        """
        Return topic graph structure for 3D visualization.

        Returns nodes (topics) and links (CHILD_OF relationships).
        Only returns topic hierarchy, not messages.

        Query params:
            limit: Maximum number of nodes (default: 500)
            broker: Filter by broker (optional)
        """
        limit = int(request.query.get("limit", "500"))
        broker = request.query.get("broker")

        try:
            driver = AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=(config.neo4j_user, config.neo4j_password)
            )
            async with driver.session() as session:
                # Build broker filter
                broker_filter = ""
                if broker:
                    broker_filter = f"AND t.path STARTS WITH '{broker}'"

                # Query topics with their parent relationships
                result = await session.run(f"""
                    MATCH (t:Topic)
                    WHERE NOT t.path CONTAINS '/message/'
                    {broker_filter}
                    OPTIONAL MATCH (t)-[:CHILD_OF]->(parent:Topic)
                    WITH t, parent
                    ORDER BY t.path
                    LIMIT $limit
                    RETURN t.path as id,
                           t.name as name,
                           size(split(t.path, '/')) as depth,
                           parent.path as parent
                """, {"limit": limit})
                records = await result.data()
            await driver.close()

            # Build nodes and links
            nodes = []
            links = []
            seen_ids = set()

            for r in records:
                topic_id = r["id"]
                if topic_id and topic_id not in seen_ids:
                    nodes.append({
                        "id": topic_id,
                        "name": r["name"] or topic_id.split("/")[-1],
                        "depth": r["depth"] or 1
                    })
                    seen_ids.add(topic_id)

                # Add link to parent
                if r["parent"]:
                    links.append({
                        "source": topic_id,
                        "target": r["parent"]
                    })

            return web.json_response({
                "nodes": nodes,
                "links": links,
                "count": len(nodes)
            })
        except Exception as e:
            logger.error(f"Graph endpoint error: {e}")
            return web.json_response({"error": str(e)}, status=500)

    # Graph visualization endpoint
    http_app.router.add_get("/api/graph", graph_handler)

    runner = web.AppRunner(http_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("API server started on port 8080")
