"""Prediction API endpoints.

Predictions are trained automatically in the background and cached permanently.
These endpoints only return cached results — they never trigger training.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.database import get_neo4j_driver
from src.models.schemas import PredictionResponse, PredictionMetrics
from src.services.data_fetcher import (
    fetch_machine, fetch_historical_for_field,
    get_machine_topics, get_numeric_fields
)
from src.services.time_series import get_historical_points
from src.services.storage import get_prediction

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/predict/{machine_id}", response_model=PredictionResponse)
async def get_prediction_endpoint(
    machine_id: str,
    field: str = Query(..., description="Field name to predict"),
    topic: Optional[str] = Query(None, description="Topic path (required for multi-topic machines)"),
    horizon: str = Query("week", description="Prediction horizon: 'day', 'week', or 'month'"),
    force_refresh: bool = Query(False, description="Ignored — kept for backward compatibility")
):
    """
    Get cached time series prediction for a machine field.

    Returns the cached prediction if available, or 404 if not yet trained.
    Training happens automatically in the background.
    """
    if horizon not in ("day", "week", "month"):
        raise HTTPException(status_code=400, detail="Horizon must be 'day', 'week', or 'month'")

    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # Fetch machine definition
    machine = await fetch_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    # Determine topic path
    topics = get_machine_topics(machine)
    if not topics:
        raise HTTPException(status_code=400, detail="Machine has no topics configured")

    if topic:
        if topic not in topics:
            raise HTTPException(status_code=400, detail=f"Topic {topic} not found on machine")
        topic_path = topic
    else:
        if len(topics) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multi-topic machine requires 'topic' parameter"
            )
        topic_path = topics[0]

    # Validate field exists
    numeric_fields = get_numeric_fields(machine, topic_path)
    if field not in numeric_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{field}' not found or not numeric. Available: {numeric_fields}"
        )

    # Return cached prediction
    cached = await get_prediction(driver, machine_id, field, topic_path, horizon)
    if cached:
        logger.info(f"Returning cached prediction for {machine_id}:{field}")
        return cached

    # No cached prediction — return empty response indicating pending
    raise HTTPException(
        status_code=404,
        detail="Prediction not yet available. Models are trained automatically in the background."
    )


@router.get("/predict/{machine_id}/stream")
async def stream_prediction(
    machine_id: str,
    field: str = Query(..., description="Field name to predict"),
    topic: Optional[str] = Query(None, description="Topic path"),
    horizon: str = Query("week", description="Prediction horizon"),
    force_refresh: bool = Query(False, description="Ignored — kept for backward compatibility")
):
    """
    Get cached prediction (kept for backward compatibility with frontend).

    Previously used SSE streaming for live training progress.
    Now simply returns the cached result or a pending status.
    """
    from fastapi.responses import StreamingResponse

    def sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def generate():
        driver = get_neo4j_driver()
        if not driver:
            yield sse_event("error", {"message": "Database connection unavailable"})
            return

        if horizon not in ("day", "week", "month"):
            yield sse_event("error", {"message": "Horizon must be 'day', 'week', or 'month'"})
            return

        machine = await fetch_machine(machine_id)
        if not machine:
            yield sse_event("error", {"message": f"Machine {machine_id} not found"})
            return

        # Determine topic path
        topics = get_machine_topics(machine)
        if not topics:
            yield sse_event("error", {"message": "Machine has no topics configured"})
            return

        if topic:
            if topic not in topics:
                yield sse_event("error", {"message": f"Topic {topic} not found on machine"})
                return
            topic_path = topic
        else:
            if len(topics) > 1:
                yield sse_event("error", {"message": "Multi-topic machine requires 'topic' parameter"})
                return
            topic_path = topics[0]

        # Check cache
        cached = await get_prediction(driver, machine_id, field, topic_path, horizon)
        if cached:
            yield sse_event("progress", {"stage": "complete", "message": "Found cached prediction!", "percent": 100})
            yield sse_event("result", {"prediction": cached.model_dump(by_alias=True)})
        else:
            yield sse_event("progress", {
                "stage": "pending",
                "message": "Prediction not yet available. Models are trained automatically in the background.",
                "percent": 0
            })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/predict/{machine_id}/fields")
async def list_predictable_fields(machine_id: str):
    """
    List all predictable (numeric) fields for a machine.
    """
    machine = await fetch_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    topics = get_machine_topics(machine)
    result = {}

    for topic in topics:
        fields = get_numeric_fields(machine, topic)
        if fields:
            result[topic] = fields

    return {"machineId": machine_id, "fieldsByTopic": result}


@router.get("/predict-topic/stream")
async def stream_topic_prediction(
    topic: str = Query(..., description="Topic path to predict"),
    field: str = Query(..., description="Field name to predict"),
    horizon: str = Query("day", description="Prediction horizon: 'day', 'week', or 'month'"),
    force_refresh: bool = Query(False, description="Ignored — kept for backward compatibility")
):
    """
    Stream prediction for an arbitrary topic (Topic Analyzer feature).

    Returns cached result if available, otherwise returns pending status.
    """
    from fastapi.responses import StreamingResponse

    def sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def generate():
        driver = get_neo4j_driver()
        if not driver:
            yield sse_event("error", {"message": "Database connection unavailable"})
            return

        if horizon not in ("day", "week", "month"):
            yield sse_event("error", {"message": "Horizon must be 'day', 'week', or 'month'"})
            return

        # For topic-based predictions, check if any machine has a cached prediction for this topic
        # Since topic predictions aren't tied to machines, return pending status
        yield sse_event("progress", {
            "stage": "pending",
            "message": "Topic predictions are trained automatically in the background.",
            "percent": 0
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/predict/{machine_id}/history")
async def get_historical_data(
    machine_id: str,
    field: str = Query(..., description="Field name"),
    topic: Optional[str] = Query(None, description="Topic path"),
    days: int = Query(30, description="Number of days of history")
):
    """
    Get historical data for a field (for charting without prediction).
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    machine = await fetch_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    # Determine topic
    topics = get_machine_topics(machine)
    if topic:
        topic_path = topic
    elif len(topics) == 1:
        topic_path = topics[0]
    else:
        raise HTTPException(status_code=400, detail="Topic parameter required for multi-topic machine")

    # Fetch data
    df = await fetch_historical_for_field(driver, topic_path, field, days_back=days)

    if df.empty:
        return {"machineId": machine_id, "field": field, "topic": topic_path, "data": []}

    historical = get_historical_points(df, num_points=len(df))

    return {
        "machineId": machine_id,
        "field": field,
        "topic": topic_path,
        "data": [h.model_dump() for h in historical]
    }
