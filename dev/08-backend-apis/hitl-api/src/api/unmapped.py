"""Unmapped topics API routes - list topics needing suggestions."""
import json
import logging

import aiohttp
from aiohttp import web

from config import config

logger = logging.getLogger(__name__)


def setup_unmapped_routes(app: web.Application, neo4j_driver):
    """Set up unmapped topics API routes."""

    async def list_unmapped_topics(request):
        """
        GET /api/v1/unmapped?page=1&pageSize=20

        List topics that don't have any mapping (proposed, approved, or rejected).
        These are candidates for AI suggestion.
        """
        page = int(request.query.get('page', 1))
        page_size = int(request.query.get('pageSize', 20))
        skip = (page - 1) * page_size

        query = """
        MATCH (t:Topic)
        WHERE NOT EXISTS {
          MATCH (s:SchemaMapping {rawTopic: t.path})
        }
        // Only include leaf topics (those with messages)
        AND EXISTS { (t)-[:HAS_MESSAGE]->() }
        WITH t
        OPTIONAL MATCH (t)-[:HAS_MESSAGE]->(m:Message)
        WITH t, m ORDER BY m.timestamp DESC
        WITH t, collect(m)[0] AS latestMessage, count(m) AS messageCount
        RETURN t.path AS topic,
               latestMessage.rawPayload AS samplePayload,
               toString(latestMessage.timestamp) AS lastSeen,
               messageCount
        ORDER BY latestMessage.timestamp DESC
        SKIP $skip LIMIT $limit
        """

        count_query = """
        MATCH (t:Topic)
        WHERE NOT EXISTS {
          MATCH (s:SchemaMapping {rawTopic: t.path})
        }
        AND EXISTS { (t)-[:HAS_MESSAGE]->() }
        RETURN count(t) AS total
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, skip=skip, limit=page_size)
            topics = []
            async for record in result:
                topics.append({
                    'topic': record['topic'],
                    'samplePayload': record['samplePayload'],
                    'lastSeen': record['lastSeen'],
                    'messageCount': record['messageCount']
                })

            count_result = await session.run(count_query)
            count_record = await count_result.single()
            total = count_record['total'] if count_record else 0

        return web.json_response({
            'topics': topics,
            'total': total,
            'page': page,
            'pageSize': page_size
        })

    async def trigger_suggestion(request):
        """
        POST /api/v1/unmapped/suggest

        Trigger Schema Advisor to generate a mapping suggestion for a topic.

        Request body:
        {
            "topic": "building/sensor/temp",
            "payload": "{\"t\": 21.5}"  // optional, will use latest from Neo4j if not provided
        }
        """
        try:
            body = await request.json()
        except:
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        topic = body.get('topic')
        if not topic:
            return web.json_response({'error': 'topic is required'}, status=400)

        payload = body.get('payload')

        # If no payload provided, fetch latest from Neo4j
        if not payload:
            query = """
            MATCH (t:Topic {path: $topic})-[:HAS_MESSAGE]->(m:Message)
            RETURN m.rawPayload AS payload
            ORDER BY m.timestamp DESC
            LIMIT 1
            """
            async with neo4j_driver.session() as session:
                result = await session.run(query, topic=topic)
                record = await result.single()
                payload = record['payload'] if record else '{}'

        # Call Schema Advisor
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.schema_advisor_url}/api/v1/suggest",
                    json={
                        "raw_topic": topic,
                        "raw_payload": payload,
                        "created_by": "hitl-ui"
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()

                    if resp.status == 200 and result.get('success'):
                        logger.info(f"Schema suggestion created for {topic}: {result.get('mapping_id')}")
                        return web.json_response({
                            'success': True,
                            'mapping_id': result.get('mapping_id'),
                            'suggestion': result.get('suggestion'),
                            'topic': topic
                        })
                    else:
                        logger.warning(f"Schema suggestion failed for {topic}: {result.get('error')}")
                        return web.json_response({
                            'success': False,
                            'error': result.get('error', 'Unknown error'),
                            'topic': topic
                        }, status=400)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}',
                'topic': topic
            }, status=503)

    async def trigger_batch_suggestions(request):
        """
        POST /api/v1/unmapped/suggest-batch

        Trigger Schema Advisor for multiple unmapped topics.

        Request body:
        {
            "limit": 10  // max topics to process
        }
        """
        try:
            body = await request.json()
        except:
            body = {}

        limit = min(body.get('limit', 10), 50)  # Cap at 50

        # Get unmapped topics (leaf topics with messages)
        query = """
        MATCH (t:Topic)
        WHERE NOT EXISTS {
          MATCH (s:SchemaMapping {rawTopic: t.path})
        }
        AND EXISTS { (t)-[:HAS_MESSAGE]->() }
        WITH t
        MATCH (t)-[:HAS_MESSAGE]->(m:Message)
        WITH t, m ORDER BY m.timestamp DESC
        WITH t, collect(m)[0] AS latestMessage
        RETURN t.path AS topic, latestMessage.rawPayload AS payload
        LIMIT $limit
        """

        topics_to_process = []
        async with neo4j_driver.session() as session:
            result = await session.run(query, limit=limit)
            async for record in result:
                topics_to_process.append({
                    'topic': record['topic'],
                    'payload': record['payload'] or '{}'
                })

        if not topics_to_process:
            return web.json_response({
                'success': True,
                'processed': 0,
                'results': [],
                'message': 'No unmapped topics found'
            })

        # Process each topic
        results = []
        async with aiohttp.ClientSession() as session:
            for item in topics_to_process:
                try:
                    async with session.post(
                        f"{config.schema_advisor_url}/api/v1/suggest",
                        json={
                            "raw_topic": item['topic'],
                            "raw_payload": item['payload'],
                            "created_by": "hitl-batch"
                        },
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        result = await resp.json()
                        results.append({
                            'topic': item['topic'],
                            'success': result.get('success', False),
                            'mapping_id': result.get('mapping_id'),
                            'error': result.get('error')
                        })
                except Exception as e:
                    results.append({
                        'topic': item['topic'],
                        'success': False,
                        'error': str(e)
                    })

        successful = sum(1 for r in results if r['success'])
        logger.info(f"Batch suggestion completed: {successful}/{len(results)} successful")

        return web.json_response({
            'success': True,
            'processed': len(results),
            'successful': successful,
            'results': results
        })

    # ========== Conversation Routes ==========

    async def start_conversation(request):
        """
        POST /api/v1/unmapped/conversation/start

        Start a conversational schema suggestion session.

        Request body:
        {
            "topic": "building/sensor/temp",
            "payload": "{\"t\": 21.5}"  // optional
        }
        """
        try:
            body = await request.json()
        except:
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        topic = body.get('topic')
        if not topic:
            return web.json_response({'error': 'topic is required'}, status=400)

        payload = body.get('payload')

        # If no payload provided, fetch latest from Neo4j
        if not payload:
            # First try: exact topic match
            query = """
            MATCH (t:Topic {path: $topic})-[:HAS_MESSAGE]->(m:Message)
            RETURN m.rawPayload AS payload
            ORDER BY m.timestamp DESC
            LIMIT 1
            """
            async with neo4j_driver.session() as session:
                result = await session.run(query, topic=topic)
                record = await result.single()
                payload = record['payload'] if record else None

            # Fallback: find message from sibling topic (same parent path, same metric type)
            if not payload:
                # Extract parent path and metric name from topic
                # e.g., "acme/plant/assembly/line/cell/robot_026/speed" -> parent="acme/plant/assembly/line/cell", metric="speed"
                topic_parts = topic.rsplit('/', 2)  # Split into [grandparent, device, metric]
                if len(topic_parts) >= 2:
                    parent_prefix = '/'.join(topic_parts[:-1])  # Everything except last part
                    metric_name = topic_parts[-1]  # Last part (e.g., "speed", "temperature")

                    fallback_query = """
                    MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
                    WHERE t.path STARTS WITH $parentPrefix
                      AND t.path ENDS WITH $metricName
                      AND t.path <> $originalTopic
                    RETURN m.rawPayload AS payload, t.path AS sourceTopic
                    ORDER BY m.timestamp DESC
                    LIMIT 1
                    """
                    async with neo4j_driver.session() as session:
                        result = await session.run(
                            fallback_query,
                            parentPrefix=parent_prefix,
                            metricName='/' + metric_name,
                            originalTopic=topic
                        )
                        record = await result.single()
                        if record and record['payload']:
                            payload = record['payload']
                            logger.info(f"Using sample payload from sibling topic: {record['sourceTopic']}")

            # Final fallback: empty object
            if not payload:
                payload = '{}'

        # Call Schema Advisor conversation endpoint
        try:
            async with aiohttp.ClientSession() as session:
                request_body = {
                    "raw_topic": topic,
                    "raw_payload": payload,
                    "created_by": body.get("created_by", "hitl-ui")
                }
                # Pass through initial_suggestion if provided (from preview)
                if body.get("initial_suggestion"):
                    request_body["initial_suggestion"] = body["initial_suggestion"]

                async with session.post(
                    f"{config.schema_advisor_url}/api/v1/conversation/start",
                    json=request_body,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()
                    return web.json_response(result, status=resp.status)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}'
            }, status=503)

    async def conversation_message(request):
        """
        POST /api/v1/conversation/{id}/message

        Send a message to continue a conversation.

        Request body:
        {
            "message": "The sensor is in the machining area"
        }
        """
        conversation_id = request.match_info['id']

        try:
            body = await request.json()
        except:
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.schema_advisor_url}/api/v1/conversation/{conversation_id}/message",
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()
                    return web.json_response(result, status=resp.status)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}'
            }, status=503)

    async def accept_conversation_proposal(request):
        """
        POST /api/v1/conversation/{id}/accept

        Accept the current proposal and create a mapping.

        Request body (optional):
        {
            "edits": {
                "curatedTopic": "...",
                "payloadMapping": {...}
            }
        }
        """
        conversation_id = request.match_info['id']

        try:
            body = await request.json()
        except:
            body = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.schema_advisor_url}/api/v1/conversation/{conversation_id}/accept",
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()
                    return web.json_response(result, status=resp.status)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}'
            }, status=503)

    async def get_conversation(request):
        """
        GET /api/v1/conversation/{id}

        Get conversation details and history.
        """
        conversation_id = request.match_info['id']

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{config.schema_advisor_url}/api/v1/conversation/{conversation_id}",
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()
                    return web.json_response(result, status=resp.status)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}'
            }, status=503)

    async def preview_suggestion(request):
        """
        POST /api/v1/unmapped/preview-suggest

        Preview a normalization suggestion for an arbitrary topic/payload.
        Does NOT create a mapping - returns the suggestion with similar topics/messages.

        Request body:
        {
            "topic": "factory/line1/sensor/temp",
            "payload": "{\"t\": 45.2, \"unit\": \"C\"}"
        }

        Response:
        {
            "success": true,
            "similar_topics": [...],
            "similar_messages": [...],
            "suggestion": {
                "suggestedFullTopicPath": "...",
                "payloadMapping": {...},
                "confidence": "high|medium|low",
                "rationale": "..."
            }
        }
        """
        try:
            body = await request.json()
        except:
            return web.json_response({'error': 'Invalid JSON'}, status=400)

        topic = body.get('topic')
        if not topic:
            return web.json_response({'error': 'topic is required'}, status=400)

        payload = body.get('payload', '{}')

        # Call Schema Advisor preview endpoint
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.schema_advisor_url}/api/v1/preview-suggest",
                    json={
                        "raw_topic": topic,
                        "raw_payload": payload
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    result = await resp.json()
                    return web.json_response(result, status=resp.status)

        except aiohttp.ClientError as e:
            logger.error(f"Failed to reach Schema Advisor: {e}")
            return web.json_response({
                'success': False,
                'error': f'Schema Advisor unavailable: {str(e)}'
            }, status=503)

    # Register routes
    app.router.add_get('/api/v1/unmapped', list_unmapped_topics)
    app.router.add_post('/api/v1/unmapped/suggest', trigger_suggestion)
    app.router.add_post('/api/v1/unmapped/suggest-batch', trigger_batch_suggestions)
    app.router.add_post('/api/v1/unmapped/preview-suggest', preview_suggestion)

    # Conversation routes
    app.router.add_post('/api/v1/unmapped/conversation/start', start_conversation)
    app.router.add_post('/api/v1/conversation/{id}/message', conversation_message)
    app.router.add_post('/api/v1/conversation/{id}/accept', accept_conversation_proposal)
    app.router.add_get('/api/v1/conversation/{id}', get_conversation)
