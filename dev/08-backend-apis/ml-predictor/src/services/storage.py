"""Neo4j storage service for predictions and regressions."""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from neo4j import AsyncDriver

from src.config import get_settings
from src.models.schemas import (
    PredictionResponse, PredictionPoint, PredictionMetrics,
    RegressionResponse, FeatureInfo
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ============== Prediction Storage ==============

async def save_prediction(
    driver: AsyncDriver,
    machine_id: str,
    field_name: str,
    topic_path: str,
    horizon: str,
    predictions: list[PredictionPoint],
    historical: list[PredictionPoint],
    metrics: PredictionMetrics,
    data_points_used: int
) -> str:
    """
    Save a prediction to Neo4j.

    Returns:
        The prediction ID
    """
    prediction_id = str(uuid.uuid4())
    now = datetime.utcnow()

    query = """
    MERGE (m:SimulatedMachine {id: $machineId})
    CREATE (p:Prediction {
        id: $predictionId,
        machineId: $machineId,
        fieldName: $fieldName,
        topicPath: $topicPath,
        predictionType: 'time_series',
        horizon: $horizon,
        predictions: $predictions,
        historical: $historical,
        modelMetrics: $modelMetrics,
        trainedAt: datetime($trainedAt),
        dataPointsUsed: $dataPointsUsed
    })
    MERGE (m)-[:HAS_PREDICTION]->(p)
    RETURN p.id AS id
    """

    params = {
        "machineId": machine_id,
        "predictionId": prediction_id,
        "fieldName": field_name,
        "topicPath": topic_path,
        "horizon": horizon,
        "predictions": json.dumps([p.model_dump() for p in predictions]),
        "historical": json.dumps([h.model_dump() for h in historical]),
        "modelMetrics": json.dumps(metrics.model_dump()),
        "trainedAt": now.isoformat(),
        "dataPointsUsed": data_points_used
    }

    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()
        logger.info(f"Saved prediction {prediction_id} for {machine_id}:{field_name}")
        return record["id"] if record else prediction_id


async def get_prediction(
    driver: AsyncDriver,
    machine_id: str,
    field_name: str,
    topic_path: str,
    horizon: str
) -> Optional[PredictionResponse]:
    """
    Get a cached prediction from Neo4j.

    Returns:
        PredictionResponse if found and not expired, None otherwise
    """
    query = """
    MATCH (m:SimulatedMachine {id: $machineId})-[:HAS_PREDICTION]->(p:Prediction)
    WHERE p.fieldName = $fieldName
      AND p.topicPath = $topicPath
      AND p.horizon = $horizon
    RETURN p
    ORDER BY p.trainedAt DESC
    LIMIT 1
    """

    params = {
        "machineId": machine_id,
        "fieldName": field_name,
        "topicPath": topic_path,
        "horizon": horizon
    }

    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()

        if not record:
            return None

        p = record["p"]

        # Parse JSON fields
        predictions = [PredictionPoint(**pt) for pt in json.loads(p["predictions"])]
        historical = [PredictionPoint(**pt) for pt in json.loads(p["historical"])]
        metrics = PredictionMetrics(**json.loads(p["modelMetrics"]))

        # Convert Neo4j DateTime to Python datetime
        trained_at = p["trainedAt"]
        if hasattr(trained_at, 'to_native'):
            trained_at = trained_at.to_native()

        return PredictionResponse(
            machineId=p["machineId"],
            field=p["fieldName"],
            topic=p["topicPath"],
            horizon=p["horizon"],
            predictions=predictions,
            historical=historical,
            metrics=metrics,
            trainedAt=trained_at,
            dataPointsUsed=p["dataPointsUsed"]
        )


async def delete_expired_predictions(driver: AsyncDriver) -> int:
    """No-op: predictions no longer expire. Kept for backward compatibility."""
    return 0


# ============== Regression Storage ==============

def compute_features_hash(features: list[tuple[str, str]]) -> str:
    """
    Compute hash of feature list for cache key.

    Args:
        features: List of (topic, field) tuples

    Returns:
        16-character hash string
    """
    sorted_features = sorted(f"{t}:{f}" for t, f in features)
    return hashlib.md5("|".join(sorted_features).encode()).hexdigest()[:16]


async def save_regression(
    driver: AsyncDriver,
    machine_id: str,
    target_field: str,
    target_topic: str,
    features: list[FeatureInfo],
    intercept: float,
    r_squared: float,
    correlation_matrix: dict,
    data_points_used: int,
    features_hash: Optional[str] = None
) -> str:
    """
    Save a regression analysis to Neo4j.

    Args:
        features_hash: Hash of feature selection for cache key (optional for backward compat)

    Returns:
        The regression ID
    """
    regression_id = str(uuid.uuid4())
    now = datetime.utcnow()

    query = """
    MERGE (m:SimulatedMachine {id: $machineId})
    CREATE (r:Regression {
        id: $regressionId,
        machineId: $machineId,
        targetField: $targetField,
        targetTopic: $targetTopic,
        featuresHash: $featuresHash,
        features: $features,
        intercept: $intercept,
        rSquared: $rSquared,
        correlationMatrix: $correlationMatrix,
        trainedAt: datetime($trainedAt),
        dataPointsUsed: $dataPointsUsed
    })
    MERGE (m)-[:HAS_REGRESSION]->(r)
    RETURN r.id AS id
    """

    params = {
        "machineId": machine_id,
        "regressionId": regression_id,
        "targetField": target_field,
        "targetTopic": target_topic,
        "featuresHash": features_hash or "",
        "features": json.dumps([f.model_dump(by_alias=True) for f in features]),
        "intercept": intercept,
        "rSquared": r_squared,
        "correlationMatrix": json.dumps(correlation_matrix),
        "trainedAt": now.isoformat(),
        "dataPointsUsed": data_points_used
    }

    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()
        logger.info(f"Saved regression {regression_id} for {machine_id}:{target_field} (hash={features_hash})")
        return record["id"] if record else regression_id


async def get_regression(
    driver: AsyncDriver,
    machine_id: str,
    target_field: str,
    target_topic: str,
    features_hash: Optional[str] = None
) -> Optional[RegressionResponse]:
    """
    Get a cached regression from Neo4j.

    Args:
        features_hash: If provided, only return regression with matching feature set

    Returns:
        RegressionResponse if found, None otherwise
    """
    if features_hash:
        # Query with features hash for exact cache match
        query = """
        MATCH (m:SimulatedMachine {id: $machineId})-[:HAS_REGRESSION]->(r:Regression)
        WHERE r.targetField = $targetField
          AND r.targetTopic = $targetTopic
          AND r.featuresHash = $featuresHash
        RETURN r
        ORDER BY r.trainedAt DESC
        LIMIT 1
        """
        params = {
            "machineId": machine_id,
            "targetField": target_field,
            "targetTopic": target_topic,
            "featuresHash": features_hash
        }
    else:
        # Query without features hash (backward compat)
        query = """
        MATCH (m:SimulatedMachine {id: $machineId})-[:HAS_REGRESSION]->(r:Regression)
        WHERE r.targetField = $targetField
          AND r.targetTopic = $targetTopic
        RETURN r
        ORDER BY r.trainedAt DESC
        LIMIT 1
        """
        params = {
            "machineId": machine_id,
            "targetField": target_field,
            "targetTopic": target_topic
        }

    async with driver.session() as session:
        result = await session.run(query, params)
        record = await result.single()

        if not record:
            return None

        r = record["r"]

        # Parse JSON fields
        features = [FeatureInfo(**f) for f in json.loads(r["features"])]

        # Handle correlation_matrix - might be None or missing in older records
        corr_matrix_raw = r.get("correlationMatrix")
        if corr_matrix_raw:
            correlation_matrix = json.loads(corr_matrix_raw)
        else:
            correlation_matrix = {}

        # Convert Neo4j DateTime to Python datetime
        trained_at = r["trainedAt"]
        if hasattr(trained_at, 'to_native'):
            trained_at = trained_at.to_native()

        return RegressionResponse(
            machine_id=r["machineId"],
            target_field=r["targetField"],
            target_topic=r["targetTopic"],
            features=features,
            intercept=r["intercept"],
            r_squared=r["rSquared"],
            correlation_matrix=correlation_matrix,
            trained_at=trained_at,
            data_points_used=r["dataPointsUsed"]
        )


async def get_machines_needing_update(driver: AsyncDriver, hours_threshold: int = 24) -> list[str]:
    """
    Get machine IDs that have never been trained (no predictions at all).

    Models are trained once and cached permanently, so only machines
    with zero predictions need training.

    Args:
        hours_threshold: Ignored (kept for backward compatibility)

    Returns:
        List of machine IDs
    """
    query = """
    MATCH (m:SimulatedMachine)
    WHERE m.status = 'running'
      AND NOT (m)-[:HAS_PREDICTION]->(:Prediction)
    RETURN m.id AS machineId
    """

    machine_ids = []
    async with driver.session() as session:
        result = await session.run(query)
        async for record in result:
            machine_ids.append(record["machineId"])

    logger.info(f"Found {len(machine_ids)} untrained machines needing predictions")
    return machine_ids


async def delete_old_regressions(driver: AsyncDriver, keep_count: int = 5) -> int:
    """
    Delete old regression results, keeping only the most recent ones per machine/field.

    Args:
        keep_count: Number of most recent regressions to keep per machine/field

    Returns:
        Number of deleted regressions
    """
    query = """
    MATCH (m:SimulatedMachine)-[:HAS_REGRESSION]->(r:Regression)
    WITH m.id AS machineId, r.targetField AS field, r
    ORDER BY r.trainedAt DESC
    WITH machineId, field, collect(r) AS regressions
    WHERE size(regressions) > $keepCount
    UNWIND regressions[$keepCount..] AS oldRegression
    DETACH DELETE oldRegression
    RETURN count(oldRegression) AS deleted
    """

    async with driver.session() as session:
        result = await session.run(query, {"keepCount": keep_count})
        record = await result.single()
        deleted = record["deleted"] if record else 0
        logger.info(f"Deleted {deleted} old regressions")
        return deleted
