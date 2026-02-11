"""Background training loop for ML Predictor.

Periodically checks for machines that have never been trained and
trains both prediction and regression models when enough data exists.
Models are trained once and cached permanently.
"""

import asyncio
import logging

from src.config import get_settings
from src.database import get_neo4j_driver
from src.services.data_fetcher import (
    fetch_machine, fetch_historical_for_field, fetch_historical_raw,
    fetch_multi_machine_data,
    get_machine_topics, get_numeric_fields
)
from src.services.time_series import run_time_series_prediction
from src.services.regression import run_regression_analysis
from src.services.storage import (
    save_prediction, save_regression, get_machines_needing_update
)

logger = logging.getLogger(__name__)
settings = get_settings()

CHECK_INTERVAL_SECONDS = 300  # Check every 5 minutes


async def background_training_loop():
    """Main background loop that checks for untrained machines."""
    logger.info("Background training loop started (interval: %ds)", CHECK_INTERVAL_SECONDS)

    # Wait a bit on startup to let other services initialize
    await asyncio.sleep(30)

    while True:
        try:
            driver = get_neo4j_driver()
            if not driver:
                logger.warning("No Neo4j driver available, skipping training check")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue

            machine_ids = await get_machines_needing_update(driver)

            if machine_ids:
                logger.info("Found %d untrained machines: %s", len(machine_ids), machine_ids)

            for machine_id in machine_ids:
                try:
                    await train_machine_all(driver, machine_id)
                except Exception as e:
                    logger.error("Failed to train machine %s: %s", machine_id, e)

        except asyncio.CancelledError:
            logger.info("Background training loop cancelled")
            return
        except Exception as e:
            logger.error("Background training loop error: %s", e)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def train_machine_all(driver, machine_id: str):
    """Train all prediction and regression models for a machine."""
    machine = await fetch_machine(machine_id)
    if not machine:
        logger.warning("Machine %s not found, skipping", machine_id)
        return

    topics = get_machine_topics(machine)
    if not topics:
        logger.warning("Machine %s has no topics, skipping", machine_id)
        return

    pred_success = 0
    pred_failure = 0

    # --- Train predictions for every topic × field × horizon ---
    for topic_path in topics:
        numeric_fields = get_numeric_fields(machine, topic_path)

        for field in numeric_fields:
            logger.info("Training predictions for %s:%s:%s", machine_id, topic_path, field)

            try:
                # Hourly data for week/month horizons
                df_hourly = await fetch_historical_for_field(driver, topic_path, field, days_back=90)
                if not df_hourly.empty:
                    for horizon in ("week", "month"):
                        predictions, historical, metrics, data_points = await run_time_series_prediction(
                            df_hourly, field, horizon
                        )
                        if predictions:
                            await save_prediction(
                                driver, machine_id, field, topic_path, horizon,
                                predictions, historical, metrics, data_points
                            )
                            pred_success += 1
                        else:
                            pred_failure += 1

                # Raw 1-minute data for day horizon
                df_raw = await fetch_historical_raw(driver, topic_path, field, hours_back=96)
                if not df_raw.empty:
                    predictions, historical, metrics, data_points = await run_time_series_prediction(
                        df_raw, field, "day"
                    )
                    if predictions:
                        await save_prediction(
                            driver, machine_id, field, topic_path, "day",
                            predictions, historical, metrics, data_points
                        )
                        pred_success += 1
                    else:
                        pred_failure += 1

            except Exception as e:
                logger.error("Error training prediction %s:%s:%s: %s", machine_id, topic_path, field, e)
                pred_failure += 1

    logger.info("Machine %s predictions: %d success, %d failure", machine_id, pred_success, pred_failure)

    # --- Train auto regression for each topic's first numeric field ---
    await _train_auto_regression(driver, machine_id, machine, topics)


async def _train_auto_regression(driver, machine_id: str, machine, topics: list[str]):
    """Train auto regression using each topic's fields as features."""
    for topic_path in topics:
        numeric_fields = get_numeric_fields(machine, topic_path)
        if len(numeric_fields) < 2:
            # Need at least a target + one feature
            continue

        target_field = numeric_fields[0]

        # Build feature sources: other fields from same topic
        feature_sources = []
        feature_metadata = {}

        for field in numeric_fields[1:]:
            col_name = f"{machine_id}:{topic_path}:{field}"
            feature_sources.append((machine_id, topic_path, field))
            feature_metadata[col_name] = {
                "machine_id": machine_id,
                "machine_name": machine.name,
                "topic": topic_path,
                "field": field
            }

        if not feature_sources:
            continue

        try:
            all_sources = [(machine_id, topic_path, target_field)] + feature_sources
            df = await fetch_multi_machine_data(driver, all_sources, days_back=90)

            if df.empty or len(df) < 10:
                logger.info("Insufficient regression data for %s:%s:%s (%d rows)",
                            machine_id, topic_path, target_field, len(df) if not df.empty else 0)
                continue

            target_col = f"{machine_id}:{topic_path}:{target_field}"
            features, intercept, r_squared, corr_matrix, data_points = await run_regression_analysis(
                df, target_col, feature_metadata
            )

            if features:
                await save_regression(
                    driver, machine_id, target_field, topic_path,
                    features, intercept, r_squared, corr_matrix, data_points
                )
                logger.info("Saved regression for %s:%s:%s (R²=%.3f)",
                            machine_id, topic_path, target_field, r_squared)
            else:
                logger.warning("Regression failed for %s:%s:%s", machine_id, topic_path, target_field)

        except Exception as e:
            logger.error("Error training regression %s:%s:%s: %s", machine_id, topic_path, target_field, e)
