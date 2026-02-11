"""Training API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from src.database import get_neo4j_driver
from src.models.schemas import TrainingRequest, TrainingResponse
from src.services.data_fetcher import (
    fetch_machine, fetch_historical_for_field,
    get_machine_topics, get_numeric_fields
)
from src.services.time_series import run_time_series_prediction
from src.services.storage import save_prediction

logger = logging.getLogger(__name__)
router = APIRouter()


async def run_training_task(
    machine_id: str,
    fields: Optional[list[str]],
    train_prediction: bool,
    train_regression: bool
):
    """Background task to run training."""
    driver = get_neo4j_driver()
    if not driver:
        logger.error("No database connection for training")
        return

    machine = await fetch_machine(machine_id)
    if not machine:
        logger.error(f"Machine {machine_id} not found for training")
        return

    topics = get_machine_topics(machine)

    for topic_path in topics:
        numeric_fields = get_numeric_fields(machine, topic_path)

        # Filter to requested fields if specified
        target_fields = fields if fields else numeric_fields
        target_fields = [f for f in target_fields if f in numeric_fields]

        for field in target_fields:
            if train_prediction:
                logger.info(f"Training prediction for {machine_id}:{topic_path}:{field}")
                try:
                    df = await fetch_historical_for_field(driver, topic_path, field, days_back=90)
                    if not df.empty:
                        # Train for both horizons
                        for horizon in ["week", "month"]:
                            predictions, historical, metrics, data_points = await run_time_series_prediction(
                                df, field, horizon
                            )
                            if predictions:
                                await save_prediction(
                                    driver, machine_id, field, topic_path, horizon,
                                    predictions, historical, metrics, data_points
                                )
                except Exception as e:
                    logger.error(f"Prediction training failed for {field}: {e}")

    logger.info(f"Training completed for machine {machine_id}")


@router.post("/train/{machine_id}", response_model=TrainingResponse)
async def trigger_training(
    machine_id: str,
    request: TrainingRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger model training for a machine.

    Training runs in the background. Use the prediction/regression endpoints
    to check when new models are available.
    """
    machine = await fetch_machine(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    # Queue background training
    background_tasks.add_task(
        run_training_task,
        machine_id,
        request.fields,
        request.prediction,
        request.regression
    )

    return TrainingResponse(
        machineId=machine_id,
        status="started",
        message="Training started in background",
        predictionTrained=False,
        regressionTrained=False
    )


@router.post("/train/batch")
async def trigger_batch_training(background_tasks: BackgroundTasks):
    """
    Trigger training for all machines that need updates.

    This is called by the daily cron job.
    """
    from src.services.storage import get_machines_needing_update

    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    machine_ids = await get_machines_needing_update(driver)

    for machine_id in machine_ids:
        background_tasks.add_task(
            run_training_task,
            machine_id,
            None,  # All fields
            True,  # Train predictions
            False  # Skip regression in batch (too expensive)
        )

    return {
        "status": "started",
        "machineCount": len(machine_ids),
        "machineIds": machine_ids
    }


@router.delete("/train/{machine_id}/cache")
async def clear_cache(machine_id: str):
    """
    Clear cached predictions and regressions for a machine.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    query = """
    MATCH (m:SimulatedMachine {id: $machineId})-[:HAS_PREDICTION|HAS_REGRESSION]->(n)
    DETACH DELETE n
    RETURN count(n) AS deleted
    """

    async with driver.session() as session:
        result = await session.run(query, {"machineId": machine_id})
        record = await result.single()
        deleted = record["deleted"] if record else 0

    return {
        "machineId": machine_id,
        "deletedCount": deleted,
        "message": f"Cleared {deleted} cached predictions/regressions"
    }
