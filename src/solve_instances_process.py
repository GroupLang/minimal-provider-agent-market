"""Process that continuously solves awarded instances independently."""

import asyncio
import sys
import time

from loguru import logger

from src.config import SETTINGS
from src.solve_instances import solve_instances_handler
from src.utils.git import accept_repo_invitations


INVITATION_CHECK_INTERVAL = 10  # Check for repo invitations every 10 iterations
SLEEP_INTERVAL = 30  # Sleep for 30 seconds between iterations

async def _process_iteration(iteration_count: int) -> None:
    """Process a single iteration of the solve instances loop."""
    try:
        logger.info("Starting solve instances")
        solve_instances_handler()
        logger.info("Solve instances completed successfully")

        # Check for repo invitations every INVITATION_CHECK_INTERVAL iterations
        if iteration_count % INVITATION_CHECK_INTERVAL == 1:
            logger.info("Accepting invitations to private repos")
            await accept_repo_invitations(SETTINGS.github_pat)
            logger.info("Finished accepting invitations to private repos")
    except Exception as e:
        logger.exception("Error during solve instances: %s", str(e))

async def main():
    """
    Continuously run solve instances as a standalone process.

    The process runs every SLEEP_INTERVAL seconds to process awarded proposals.
    Checks for repository invitations every INVITATION_CHECK_INTERVAL iterations.
    Handles graceful shutdown on keyboard interrupt.

    Fixes #26: Decoupled from market_scan to allow independent operation.
    """
    logger.info("Starting solve instances process...")
    iteration_count = 0

    try:
        while True:
            await _process_iteration(iteration_count)
            await asyncio.sleep(SLEEP_INTERVAL)
            iteration_count = (iteration_count + 1) % INVITATION_CHECK_INTERVAL
    except KeyboardInterrupt:
        logger.info("Solve instances process stopped by user")
    except Exception as e:
        logger.exception("Fatal error in solve instances process: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
