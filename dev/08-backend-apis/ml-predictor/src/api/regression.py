"""Regression API endpoints.

Regressions are trained automatically in the background and cached permanently.
These endpoints only return cached results — they never trigger training.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.database import get_neo4j_driver
from src.models.schemas import RegressionResponse, RegressionRequest, CorrelationsResponse, CorrelationEntry
from src.services.data_fetcher import (
    fetch_machine, fetch_all_machines, fetch_multi_machine_data,
    get_machine_topics, get_numeric_fields, get_similar_machine_topics,
    fetch_all_topics_with_fields
)
from src.services.regression import simple_correlation_analysis
from src.services.storage import get_regression, compute_features_hash

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/regression/available-fields")
async def get_all_available_fields():
    """
    Get all topics and their numeric fields from Neo4j.
    Scans actual message payloads to discover available fields.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    topics = await fetch_all_topics_with_fields(driver)
    return {"topics": topics}


@router.get("/regression/{machine_id}", response_model=RegressionResponse)
async def get_regression_endpoint(
    machine_id: str,
    target_field: str = Query(..., alias="targetField", description="Target field for regression"),
    target_topic: str = Query(..., alias="targetTopic", description="Topic of the target field"),
    include_similar: bool = Query(True, alias="includeSimilar", description="Ignored — kept for backward compatibility"),
    additional_machine_ids: Optional[str] = Query(None, alias="additionalMachineIds", description="Ignored — kept for backward compatibility"),
    force_refresh: bool = Query(False, description="Ignored — kept for backward compatibility")
):
    """
    Get cached regression analysis for a machine field.

    Returns the cached result if available, or 404 if not yet trained.
    Training happens automatically in the background.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # Return cached regression
    cached = await get_regression(driver, machine_id, target_field, target_topic)
    if cached:
        logger.info(f"Returning cached regression for {machine_id}:{target_field}")
        return cached

    raise HTTPException(
        status_code=404,
        detail="Regression not yet available. Models are trained automatically in the background."
    )


@router.get("/correlations/{machine_id}", response_model=CorrelationsResponse)
async def get_correlations_endpoint(
    machine_id: str,
    field: str = Query(..., description="Field to analyze correlations for"),
    topic: Optional[str] = Query(None, description="Topic path"),
    source: str = Query("all", description="Source: 'similar', 'manual', or 'all'"),
    machine_ids: Optional[str] = Query(None, description="Comma-separated machine IDs for manual mode")
):
    """
    Get correlation analysis for a field against other machines.
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

    # Build feature list
    feature_sources = []
    feature_metadata = {}

    # Include similar machines
    if source in ("similar", "all") and machine.similarity_results:
        similar_topics = await get_similar_machine_topics(machine)
        for similar in similar_topics:
            sim_topic = similar["topic_path"]
            for field_name in similar.get("field_names", []):
                col_name = f"similar:{sim_topic}:{field_name}"
                feature_sources.append(("similar", sim_topic, field_name))
                feature_metadata[col_name] = {
                    "machine_id": "similar",
                    "machine_name": f"Similar: {sim_topic.split('/')[-1]}",
                    "topic": sim_topic,
                    "field": field_name
                }

    # Include manual machines
    if source in ("manual", "all") and machine_ids:
        manual_ids = [mid.strip() for mid in machine_ids.split(",")]
        for mid in manual_ids:
            if mid == machine_id:
                continue
            m = await fetch_machine(mid)
            if m:
                for t in get_machine_topics(m):
                    for f in get_numeric_fields(m, t):
                        col_name = f"{mid}:{t}:{f}"
                        feature_sources.append((mid, t, f))
                        feature_metadata[col_name] = {
                            "machine_id": mid,
                            "machine_name": m.name,
                            "topic": t,
                            "field": f
                        }

    if not feature_sources:
        return CorrelationsResponse(
            machineId=machine_id,
            field=field,
            correlations=[]
        )

    # Fetch data
    all_sources = [(machine_id, topic_path, field)] + feature_sources
    df = await fetch_multi_machine_data(driver, all_sources, days_back=90)

    if df.empty:
        return CorrelationsResponse(
            machineId=machine_id,
            field=field,
            correlations=[]
        )

    # Calculate correlations
    target_col = f"{machine_id}:{topic_path}:{field}"
    features, corr_matrix = simple_correlation_analysis(df, target_col, feature_metadata)

    correlations = []
    for feat in features:
        correlations.append(CorrelationEntry(
            sourceMachineId=feat.machine_id,
            sourceMachineName=feat.machine_name,
            sourceTopic=feat.topic,
            sourceField=feat.field,
            targetField=field,
            correlation=feat.coefficient,
            pValue=feat.p_value
        ))

    return CorrelationsResponse(
        machineId=machine_id,
        field=field,
        correlations=correlations
    )


@router.get("/regression/{machine_id}/available-machines")
async def list_available_machines(machine_id: str):
    """
    List all machines available for correlation analysis.
    """
    machines = await fetch_all_machines()

    result = []
    for m in machines:
        if m.id == machine_id:
            continue
        topics = get_machine_topics(m)
        fields_by_topic = {}
        for topic in topics:
            fields = get_numeric_fields(m, topic)
            if fields:
                fields_by_topic[topic] = fields

        if fields_by_topic:
            result.append({
                "machineId": m.id,
                "name": m.name,
                "status": m.status,
                "fieldsByTopic": fields_by_topic
            })

    return {"machines": result}


@router.get("/regression/{machine_id}/cached")
async def get_cached_regression_endpoint(
    machine_id: str,
    target_topic: str = Query(..., alias="targetTopic", description="Topic of the target field"),
    target_field: str = Query(..., alias="targetField", description="Target field for regression"),
    features: str = Query(..., description="JSON array of {topic, field} objects")
):
    """
    Check for cached regression result without training.

    Returns the cached result if found, or null if no cache exists.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # Parse features JSON
    try:
        feature_list = json.loads(features)
        if not isinstance(feature_list, list):
            raise ValueError("Features must be an array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid features JSON: {e}")

    # Compute features hash
    feature_tuples = [(f.get("topic", ""), f.get("field", "")) for f in feature_list]
    features_hash = compute_features_hash(feature_tuples)

    # Check cache
    cached = await get_regression(driver, machine_id, target_field, target_topic, features_hash)
    if cached:
        logger.info(f"Found cached regression for {machine_id}:{target_field} (hash={features_hash})")
        return cached

    # Return null if not cached
    return None


@router.post("/regression/{machine_id}/custom")
async def run_custom_regression(
    machine_id: str,
    target_topic: str = Query(..., alias="targetTopic", description="Topic of the target field"),
    target_field: str = Query(..., alias="targetField", description="Target field for regression"),
    features: str = Query(..., description="JSON array of {topic, field} objects"),
    force_refresh: bool = Query(False, description="Ignored — kept for backward compatibility")
):
    """
    Get cached regression with explicit feature selection.

    Returns cached result if available, or 404 if not yet trained.
    """
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    # Parse features JSON
    try:
        feature_list = json.loads(features)
        if not isinstance(feature_list, list):
            raise ValueError("Features must be an array")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid features JSON: {e}")

    if not feature_list:
        raise HTTPException(status_code=400, detail="At least one feature is required")

    # Compute features hash for cache lookup
    feature_tuples = [(f.get("topic", ""), f.get("field", "")) for f in feature_list]
    features_hash = compute_features_hash(feature_tuples)

    # Return cached result
    cached = await get_regression(driver, machine_id, target_field, target_topic, features_hash)
    if cached:
        logger.info(f"Returning cached regression for {machine_id}:{target_field} (hash={features_hash})")
        return cached

    raise HTTPException(
        status_code=404,
        detail="Regression not yet available. Models are trained automatically in the background."
    )
