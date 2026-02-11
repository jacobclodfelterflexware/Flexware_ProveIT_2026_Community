"""Tests for API endpoints using mock orchestrator."""
import asyncio
import json
import sys
sys.path.insert(0, '../src')

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from api.routes import setup_routes


class MockOrchestrator:
    """Mock orchestrator for testing."""

    async def start(self):
        pass

    async def stop(self):
        pass

    async def suggest_schema(self, raw_topic: str, raw_payload: str, created_by: str):
        if raw_topic == "error/topic":
            return {
                "success": False,
                "error": "Mapping already exists"
            }
        return {
            "success": True,
            "mapping_id": "test-uuid-1234",
            "suggestion": {
                "suggestedFullTopicPath": "normalized/topic/path",
                "payloadMapping": {"t": "temperature"},
                "confidence": "high",
                "rationale": "Test rationale"
            },
            "raw_topic": raw_topic
        }

    async def suggest_for_unmapped_topics(self, limit: int):
        return [
            {"success": True, "mapping_id": f"uuid-{i}"}
            for i in range(min(limit, 3))
        ]


class TestAPIRoutes(AioHTTPTestCase):
    """Test API endpoints."""

    async def get_application(self):
        app = web.Application()
        self.orchestrator = MockOrchestrator()
        setup_routes(app, self.orchestrator)
        return app

    @unittest_run_loop
    async def test_health(self):
        """Health endpoint should return healthy."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "healthy"

    @unittest_run_loop
    async def test_ready(self):
        """Ready endpoint should return ready."""
        resp = await self.client.request("GET", "/ready")
        assert resp.status == 200
        data = await resp.json()
        assert data["ready"] is True

    @unittest_run_loop
    async def test_suggest_success(self):
        """Suggest endpoint should return mapping on success."""
        resp = await self.client.request(
            "POST",
            "/api/v1/suggest",
            json={
                "raw_topic": "building/sensor/temp",
                "raw_payload": '{"t": 21.5}'
            }
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert "mapping_id" in data
        assert data["suggestion"]["confidence"] == "high"

    @unittest_run_loop
    async def test_suggest_missing_topic(self):
        """Suggest endpoint should error without raw_topic."""
        resp = await self.client.request(
            "POST",
            "/api/v1/suggest",
            json={"raw_payload": '{"t": 21.5}'}
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data
        assert "raw_topic" in data["error"]

    @unittest_run_loop
    async def test_suggest_existing_mapping(self):
        """Suggest endpoint should return error for existing mapping."""
        resp = await self.client.request(
            "POST",
            "/api/v1/suggest",
            json={"raw_topic": "error/topic"}
        )
        assert resp.status == 400
        data = await resp.json()
        assert data["success"] is False

    @unittest_run_loop
    async def test_batch_suggest(self):
        """Batch suggest should process multiple topics."""
        resp = await self.client.request(
            "POST",
            "/api/v1/suggest/batch",
            json={"limit": 5}
        )
        assert resp.status == 200
        data = await resp.json()
        assert "processed" in data
        assert "results" in data
        assert data["processed"] == 3  # Mock returns max 3


if __name__ == "__main__":
    import unittest
    unittest.main()
