"""Daily training job for ML Predictor.

This script is run by the Kubernetes CronJob as a safety net to train
any machines that the background training loop may have missed.
Models are trained once and cached permanently (never retrained).
"""

import asyncio
import logging
import sys

from neo4j import AsyncGraphDatabase

from src.config import get_settings
from src.jobs.background_training import train_machine_all
from src.services.storage import (
    get_machines_needing_update, delete_old_regressions
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for daily training job (safety net)."""
    logger.info("Starting daily training job")

    settings = get_settings()

    # Connect to Neo4j
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    try:
        # Verify connection
        async with driver.session() as session:
            await session.run("RETURN 1")
        logger.info("Connected to Neo4j")

        # Clean up duplicate regressions
        deleted = await delete_old_regressions(driver, keep_count=5)
        logger.info(f"Cleaned up {deleted} old regressions")

        # Find machines that have never been trained
        machine_ids = await get_machines_needing_update(driver)
        logger.info(f"Found {len(machine_ids)} untrained machines")

        if not machine_ids:
            logger.info("All machines are trained. Job complete.")
            return

        # Train each machine (predictions + regression)
        for machine_id in machine_ids:
            logger.info(f"Training machine {machine_id}")
            try:
                await train_machine_all(driver, machine_id)
                logger.info(f"Machine {machine_id}: training complete")
            except Exception as e:
                logger.error(f"Machine {machine_id}: training failed: {e}")

        logger.info("Daily training job complete")

    except Exception as e:
        logger.error(f"Daily training job failed: {e}")
        sys.exit(1)

    finally:
        await driver.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    asyncio.run(main())
