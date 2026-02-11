"""Service to fetch historical data from Neo4j for ML training."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pandas as pd
from neo4j import AsyncDriver

from src.config import get_settings
from src.models.schemas import MachineDefinition

logger = logging.getLogger(__name__)
settings = get_settings()


async def fetch_machine(machine_id: str) -> Optional[MachineDefinition]:
    """Fetch machine definition from machine-simulator service."""
    url = f"{settings.machine_simulator_url}/api/machines/{machine_id}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                return MachineDefinition(**data)
            else:
                logger.error(f"Failed to fetch machine {machine_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching machine {machine_id}: {e}")
            return None


async def fetch_all_machines() -> list[MachineDefinition]:
    """Fetch all machines from machine-simulator service."""
    url = f"{settings.machine_simulator_url}/api/machines"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                return [MachineDefinition(**m) for m in data]
            else:
                logger.error(f"Failed to fetch machines: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching machines: {e}")
            return []


def get_machine_topics(machine: MachineDefinition) -> list[str]:
    """Extract topic paths from a machine definition."""
    if machine.topics:
        return [t.topic_path for t in machine.topics]
    elif machine.topic_path:
        return [machine.topic_path]
    return []


def get_numeric_fields(machine: MachineDefinition, topic_path: Optional[str] = None) -> list[str]:
    """Get numeric field names from a machine definition."""
    # Fields to exclude (metadata, not actual values to predict)
    excluded_fields = {"timestamp", "time", "ts", "created_at", "updated_at", "asset_id", "id"}
    fields = []

    if machine.topics:
        for topic in machine.topics:
            if topic_path is None or topic.topic_path == topic_path:
                for field in topic.fields:
                    if field.type in ("number", "integer") and field.name.lower() not in excluded_fields:
                        fields.append(field.name)
    elif machine.fields:
        for field in machine.fields:
            if field.type in ("number", "integer") and field.name.lower() not in excluded_fields:
                fields.append(field.name)

    return fields


async def fetch_historical_messages(
    driver: AsyncDriver,
    topic_path: str,
    days_back: int = 90,
    broker: Optional[str] = None
) -> pd.DataFrame:
    """
    Fetch historical messages for a topic from Neo4j.

    Args:
        driver: Neo4j async driver
        topic_path: The MQTT topic path
        days_back: Number of days of history to fetch
        broker: Optional broker filter ("uncurated", "curated", or None for both)

    Returns:
        DataFrame with columns: timestamp, field_name, value
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    query = """
    MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
    WHERE t.path = $topicPath
      AND m.timestamp >= datetime($cutoffDate)
    """

    if broker:
        query += """
      AND EXISTS { (m)-[:FROM_BROKER]->(b:Broker {name: $broker}) }
    """

    query += """
    RETURN m.rawPayload AS payload,
           m.timestamp AS timestamp
    ORDER BY m.timestamp ASC
    """

    params = {
        "topicPath": topic_path,
        "cutoffDate": cutoff_date.isoformat(),
    }
    if broker:
        params["broker"] = broker

    records = []
    async with driver.session() as session:
        result = await session.run(query, params)
        async for record in result:
            try:
                payload_str = record["payload"]
                timestamp = record["timestamp"]

                # Parse payload JSON
                payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

                # Convert Neo4j DateTime to Python datetime if needed
                if hasattr(timestamp, 'to_native'):
                    timestamp = timestamp.to_native()

                # Handle non-dict payloads (simple numeric values like "1" or 1.5)
                if not isinstance(payload, dict):
                    if isinstance(payload, (int, float)):
                        records.append({
                            "timestamp": timestamp,
                            "field_name": "value",
                            "value": float(payload)
                        })
                    continue

                # Extract numeric values from dict payload
                for field_name, value in payload.items():
                    if isinstance(value, (int, float)) and field_name.lower() not in (
                        "timestamp", "time", "ts", "created_at", "updated_at"
                    ):
                        records.append({
                            "timestamp": timestamp,
                            "field_name": field_name,
                            "value": float(value)
                        })
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"Failed to parse payload: {e}")
                continue

    df = pd.DataFrame(records)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    logger.info(f"Fetched {len(df)} records for topic {topic_path}")
    return df


async def fetch_historical_for_field(
    driver: AsyncDriver,
    topic_path: str,
    field_name: str,
    days_back: int = 90
) -> pd.DataFrame:
    """
    Fetch historical data for a specific field, aggregated to hourly values.

    Uses hourly aggregation instead of daily to provide more data points
    when there's limited historical data (e.g., all data from same day).

    Args:
        driver: Neo4j async driver
        topic_path: The MQTT topic path
        field_name: The specific field to fetch
        days_back: Number of days of history

    Returns:
        DataFrame with columns: date, value (hourly averages)
    """
    df = await fetch_historical_messages(driver, topic_path, days_back)

    if df.empty:
        return pd.DataFrame(columns=["date", "value"])

    # Filter to specific field
    field_df = df[df["field_name"] == field_name].copy()

    if field_df.empty:
        return pd.DataFrame(columns=["date", "value"])

    # Make timestamps timezone-naive for consistency
    if field_df["timestamp"].dt.tz is not None:
        field_df["timestamp"] = field_df["timestamp"].dt.tz_localize(None)

    # Aggregate to hourly values (instead of daily) to get more data points
    field_df = field_df.set_index("timestamp")
    hourly_df = field_df["value"].resample("1h").mean()
    result = hourly_df.reset_index()
    result.columns = ["date", "value"]

    # Drop NaN values
    result = result.dropna()
    result = result.sort_values("date")

    logger.info(f"Aggregated to {len(result)} hourly records for {topic_path}:{field_name}")
    return result


async def fetch_historical_for_field_30min(
    driver: AsyncDriver,
    topic_path: str,
    field_name: str,
    hours_back: int = 48
) -> pd.DataFrame:
    """
    Fetch historical data for a specific field, aggregated to 30-minute intervals.

    Args:
        driver: Neo4j async driver
        topic_path: The MQTT topic path
        field_name: The specific field to fetch
        hours_back: Number of hours of history (default 48 = 2 days)

    Returns:
        DataFrame with columns: timestamp, value (30-minute averages)
    """
    # Convert hours to days for the fetch function
    days_back = max(1, hours_back / 24)
    df = await fetch_historical_messages(driver, topic_path, int(days_back) + 1)

    if df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Filter to specific field
    field_df = df[df["field_name"] == field_name].copy()

    if field_df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Filter to the requested time window
    # Make cutoff_time timezone-aware to match DataFrame timestamps
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    # Convert timestamps to naive UTC for comparison if they have timezone
    if field_df["timestamp"].dt.tz is not None:
        field_df["timestamp"] = field_df["timestamp"].dt.tz_localize(None)
    field_df = field_df[field_df["timestamp"] >= cutoff_time]

    if field_df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Resample to 30-minute intervals
    field_df = field_df.set_index("timestamp")
    resampled = field_df["value"].resample("30T").mean()
    result = resampled.reset_index()
    result.columns = ["timestamp", "value"]

    # Drop NaN values (intervals with no data)
    result = result.dropna()
    result = result.sort_values("timestamp")

    logger.info(f"Aggregated to {len(result)} 30-min records for {topic_path}:{field_name}")
    return result


async def fetch_historical_raw(
    driver: AsyncDriver,
    topic_path: str,
    field_name: str,
    hours_back: int = 48
) -> pd.DataFrame:
    """
    Fetch historical data for a specific field, resampled to 1-minute intervals.
    Uses fine granularity to retain maximum data points for AutoGluon training.

    Args:
        driver: Neo4j async driver
        topic_path: The MQTT topic path
        field_name: The specific field to fetch
        hours_back: Number of hours of history (default 48 = 2 days)

    Returns:
        DataFrame with columns: timestamp, value (1-minute averages)
    """
    days_back = max(1, hours_back / 24)
    df = await fetch_historical_messages(driver, topic_path, int(days_back) + 1)

    if df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Filter to specific field
    field_df = df[df["field_name"] == field_name].copy()

    if field_df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Filter to the requested time window
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
    if field_df["timestamp"].dt.tz is not None:
        field_df["timestamp"] = field_df["timestamp"].dt.tz_localize(None)
    field_df = field_df[field_df["timestamp"] >= cutoff_time]

    if field_df.empty:
        return pd.DataFrame(columns=["timestamp", "value"])

    # Resample to 1-minute intervals for maximum data retention
    # This provides a regular frequency that AutoGluon needs
    field_df = field_df.set_index("timestamp")
    resampled = field_df["value"].resample("1min").mean()
    result = resampled.reset_index()
    result.columns = ["timestamp", "value"]

    # Drop NaN values (intervals with no data)
    result = result.dropna()
    result = result.sort_values("timestamp")

    logger.info(f"Resampled to {len(result)} 1-min records for {topic_path}:{field_name}")
    return result


async def fetch_multi_machine_data(
    driver: AsyncDriver,
    machine_topics: list[tuple[str, str, str]],  # List of (machine_id, topic_path, field_name)
    days_back: int = 90
) -> pd.DataFrame:
    """
    Fetch data from multiple machines/topics for regression analysis.

    Uses 5-minute aggregation to retain more data points for regression,
    especially important for simulated machines that haven't run long.

    Args:
        driver: Neo4j async driver
        machine_topics: List of (machine_id, topic_path, field_name) tuples
        days_back: Number of days of history

    Returns:
        DataFrame with date index and columns for each machine:field
    """
    all_data = {}

    for machine_id, topic_path, field_name in machine_topics:
        # Fetch raw messages and aggregate to 5-minute intervals (not hourly)
        df = await fetch_historical_messages(driver, topic_path, days_back)
        if df.empty:
            continue

        # Filter to specific field
        field_df = df[df["field_name"] == field_name].copy()
        if field_df.empty:
            continue

        # Make timestamps timezone-naive for consistency
        if field_df["timestamp"].dt.tz is not None:
            field_df["timestamp"] = field_df["timestamp"].dt.tz_localize(None)

        # Aggregate to 1-minute intervals for maximum data retention
        # This is important for machines that haven't run long
        field_df = field_df.set_index("timestamp")
        resampled = field_df["value"].resample("1min").mean()
        resampled = resampled.dropna()

        if not resampled.empty:
            col_name = f"{machine_id}:{topic_path}:{field_name}"
            all_data[col_name] = resampled
            logger.info(f"Aggregated to {len(resampled)} 1-min records for {topic_path}:{field_name}")

    if not all_data:
        return pd.DataFrame()

    # Combine all series - this creates NaN where timestamps don't match
    combined_df = pd.DataFrame(all_data)

    # Sort by index for proper interpolation
    combined_df = combined_df.sort_index()

    # Interpolate to fill gaps (limit to 10 intervals = 10 min max gap for 1-min data)
    combined_df = combined_df.interpolate(method="time", limit=10)

    # Also forward/backward fill for edge cases (limit to 5 intervals = 5 min)
    combined_df = combined_df.ffill(limit=5).bfill(limit=5)

    # Drop rows with any remaining NaN
    combined_df = combined_df.dropna()

    logger.info(f"Combined data: {combined_df.shape[0]} rows, {combined_df.shape[1]} columns")
    return combined_df


async def get_similar_machine_topics(
    machine: MachineDefinition
) -> list[tuple[str, str, str, str]]:
    """
    Get topics from similar machines based on similarity_results.

    Returns:
        List of (machine_id, machine_name, topic_path, field_names) for similar machines
    """
    similar_topics = []

    if not machine.similarity_results:
        return similar_topics

    for result in machine.similarity_results:
        topic_path = result.get("topic_path", "")
        field_names = result.get("field_names", [])
        similarity = result.get("similarity", 0)

        # Only include reasonably similar topics
        if similarity > 0.3 and topic_path and field_names:
            # We don't have machine_id for similar topics, use topic as identifier
            similar_topics.append({
                "topic_path": topic_path,
                "field_names": field_names,
                "similarity": similarity
            })

    return similar_topics


async def fetch_all_topics_with_fields(driver: AsyncDriver) -> list[dict]:
    """
    Fetch all topics and their numeric fields from Neo4j by sampling messages.

    Returns:
        List of dicts: [{path: str, fields: [str]}]
    """
    # Get all topics with sample payloads to discover fields
    # Uses CALL subquery with LIMIT to avoid memory exhaustion
    # (the old collect()[0..10] approach loaded ALL messages first)
    query = """
    MATCH (t:Topic)
    CALL {
        WITH t
        MATCH (t)-[:HAS_MESSAGE]->(m:Message)
        RETURN m.rawPayload AS payload
        LIMIT 10
    }
    WITH t.path AS topicPath, collect(payload) AS samplePayloads
    WHERE size(samplePayloads) > 0
    RETURN topicPath, samplePayloads
    ORDER BY topicPath
    """

    excluded_fields = {"timestamp", "time", "ts", "created_at", "updated_at", "asset_id", "id"}
    topics_with_fields = []

    async with driver.session() as session:
        result = await session.run(query)
        async for record in result:
            topic_path = record["topicPath"]
            sample_payloads = record["samplePayloads"]

            # Extract numeric fields from sample payloads
            numeric_fields = set()
            for payload_str in sample_payloads:
                try:
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    if not isinstance(payload, dict):
                        continue
                    for field_name, value in payload.items():
                        if isinstance(value, (int, float)) and field_name.lower() not in excluded_fields:
                            numeric_fields.add(field_name)
                except (json.JSONDecodeError, TypeError):
                    continue

            if numeric_fields:
                topics_with_fields.append({
                    "path": topic_path,
                    "fields": sorted(list(numeric_fields))
                })

    logger.info(f"Found {len(topics_with_fields)} topics with numeric fields")
    return topics_with_fields
