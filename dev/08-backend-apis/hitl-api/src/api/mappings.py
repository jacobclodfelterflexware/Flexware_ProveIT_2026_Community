"""Mappings API routes for HITL approval workflow."""
import json
import logging

from aiohttp import web

logger = logging.getLogger(__name__)


def setup_mapping_routes(app: web.Application, neo4j_driver):
    """Set up mapping management API routes."""

    async def list_mappings(request):
        """
        GET /api/v1/mappings?status=proposed&page=1&pageSize=20

        List schema mappings filtered by status.
        """
        status = request.query.get('status', 'proposed')
        page = int(request.query.get('page', 1))
        page_size = int(request.query.get('pageSize', 20))
        skip = (page - 1) * page_size

        query = """
        MATCH (s:SchemaMapping)
        WHERE s.status = $status
        RETURN s {
          .id, .rawTopic, .curatedTopic, .payloadMappingJson,
          .status, .confidence, .notes, .createdBy,
          createdAt: toString(s.createdAt)
        } AS mapping
        ORDER BY s.createdAt DESC
        SKIP $skip LIMIT $limit
        """

        count_query = """
        MATCH (s:SchemaMapping)
        WHERE s.status = $status
        RETURN count(s) AS total
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, status=status, skip=skip, limit=page_size)
            mappings = []
            async for record in result:
                m = dict(record['mapping'])
                m['payloadMapping'] = json.loads(m.pop('payloadMappingJson', '{}') or '{}')
                mappings.append(m)

            count_result = await session.run(count_query, status=status)
            count_record = await count_result.single()
            total = count_record['total'] if count_record else 0

        return web.json_response({
            'mappings': mappings,
            'total': total,
            'page': page,
            'pageSize': page_size
        })

    async def get_mapping(request):
        """
        GET /api/v1/mappings/{id}

        Get detailed mapping info including recent messages.
        """
        mapping_id = request.match_info['id']

        query = """
        MATCH (s:SchemaMapping {id: $id})
        OPTIONAL MATCH (s)-[:RAW_TOPIC]->(raw:Topic)
        OPTIONAL MATCH (raw)-[:HAS_MESSAGE]->(m:Message)
        WITH s, raw, m ORDER BY m.timestamp DESC
        WITH s, raw, collect(m)[..5] AS recentMessages
        RETURN s {
          .id, .rawTopic, .curatedTopic, .payloadMappingJson,
          .status, .confidence, .notes, .createdBy,
          createdAt: toString(s.createdAt)
        } AS mapping,
        [msg IN recentMessages | {
          rawPayload: msg.rawPayload,
          payloadText: msg.payloadText,
          timestamp: toString(msg.timestamp)
        }] AS recentMessages
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, id=mapping_id)
            record = await result.single()

            if not record:
                return web.json_response({'error': 'Not found'}, status=404)

            mapping = dict(record['mapping'])
            mapping['payloadMapping'] = json.loads(mapping.pop('payloadMappingJson', '{}') or '{}')

            return web.json_response({
                'mapping': mapping,
                'recentMessages': record['recentMessages'] or []
            })

    async def approve_mapping(request):
        """
        POST /api/v1/mappings/{id}/approve

        Approve a mapping, optionally with edits.
        """
        mapping_id = request.match_info['id']

        try:
            body = await request.json()
        except:
            body = {}

        edited_curated = body.get('editedCuratedTopic')
        edited_payload = body.get('editedPayloadMapping')
        notes = body.get('notes', '')

        updates = ["s.status = 'approved'", "s.updatedAt = datetime()"]
        params = {'id': mapping_id}

        if edited_curated:
            updates.append("s.curatedTopic = $editedCurated")
            params['editedCurated'] = edited_curated

        if edited_payload:
            updates.append("s.payloadMappingJson = $editedPayloadJson")
            params['editedPayloadJson'] = json.dumps(edited_payload)

        if notes:
            updates.append("s.notes = coalesce(s.notes, '') + ' | Approved: ' + $notes")
            params['notes'] = notes

        query = f"""
        MATCH (s:SchemaMapping {{id: $id}})
        SET {', '.join(updates)}

        WITH s
        MATCH (raw:Topic {{path: s.rawTopic, broker: "uncurated"}})
        MERGE (cur:Topic {{path: s.curatedTopic, broker: "curated"}})
        ON CREATE SET cur.createdAt = datetime()

        MERGE (raw)-[r:ROUTES_TO]->(cur)
        SET r.mappingId = s.id, r.status = "approved"

        RETURN s {{
          .id, .rawTopic, .curatedTopic, .payloadMappingJson,
          .status, .confidence, .notes
        }} AS mapping
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, **params)
            record = await result.single()

            if not record:
                return web.json_response({'error': 'Not found'}, status=404)

            mapping = dict(record['mapping'])
            mapping['payloadMapping'] = json.loads(mapping.pop('payloadMappingJson', '{}') or '{}')

            logger.info(f"Approved mapping {mapping_id}: {mapping['rawTopic']} -> {mapping['curatedTopic']}")
            return web.json_response(mapping)

    async def reject_mapping(request):
        """
        POST /api/v1/mappings/{id}/reject

        Reject a mapping with required notes.
        """
        mapping_id = request.match_info['id']

        try:
            body = await request.json()
        except:
            return web.json_response({'error': 'Notes required'}, status=400)

        notes = body.get('notes', '')
        if not notes:
            return web.json_response({'error': 'Notes required for rejection'}, status=400)

        query = """
        MATCH (s:SchemaMapping {id: $id})
        SET s.status = "rejected",
            s.updatedAt = datetime(),
            s.notes = coalesce(s.notes, '') + " | Rejected: " + $notes

        WITH s
        OPTIONAL MATCH (raw:Topic {path: s.rawTopic, broker: "uncurated"})
        OPTIONAL MATCH (cur:Topic {path: s.curatedTopic, broker: "curated"})
        OPTIONAL MATCH (raw)-[r:ROUTES_TO {mappingId: s.id}]->(cur)
        SET r.status = "rejected"

        RETURN s {
          .id, .rawTopic, .curatedTopic, .status, .notes
        } AS mapping
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, id=mapping_id, notes=notes)
            record = await result.single()

            if not record:
                return web.json_response({'error': 'Not found'}, status=404)

            logger.info(f"Rejected mapping {mapping_id}")
            return web.json_response(dict(record['mapping']))

    async def preview_transformation(request):
        """
        POST /api/v1/mappings/{id}/preview

        Preview how a payload would be transformed.
        """
        mapping_id = request.match_info['id']

        try:
            body = await request.json()
            sample_payload = body.get('payload', '{}')
        except:
            return web.json_response({'error': 'Invalid request'}, status=400)

        query = """
        MATCH (s:SchemaMapping {id: $id})
        RETURN s.payloadMappingJson AS mappingJson
        """

        async with neo4j_driver.session() as session:
            result = await session.run(query, id=mapping_id)
            record = await result.single()

            if not record:
                return web.json_response({'error': 'Not found'}, status=404)

            mapping = json.loads(record['mappingJson'] or '{}')

        try:
            original = json.loads(sample_payload)
            transformed = {}

            for key, value in original.items():
                new_key = mapping.get(key, key)
                transformed[new_key] = value

            return web.json_response({
                'original': original,
                'transformed': transformed
            })
        except json.JSONDecodeError:
            return web.json_response({'error': 'Invalid JSON payload'}, status=400)

    # Register routes
    app.router.add_get('/api/v1/mappings', list_mappings)
    app.router.add_get('/api/v1/mappings/{id}', get_mapping)
    app.router.add_post('/api/v1/mappings/{id}/approve', approve_mapping)
    app.router.add_post('/api/v1/mappings/{id}/reject', reject_mapping)
    app.router.add_post('/api/v1/mappings/{id}/preview', preview_transformation)
