"""Process that continuously solves awarded instances independently."""

import asyncio
import sys
from datetime import datetime

from loguru import logger

from src.config import SETTINGS
from src.solve_instances import solve_instances_handler
from src.utils.git import accept_repo_invitations


async def process_cycle() -> None:
    """Run one cycle of instance solving and repo invitation acceptance."""
    try:
        logger.info(f"Starting solve instances cycle at {datetime.utcnow()}")
        await solve_instances_handler()
        logger.info("Solve instances completed successfully")
        
        logger.info("Accepting invitations to private repos")
        await accept_repo_invitations(SETTINGS.github_pat)
        logger.info("Finished accepting invitations to private repos")
        
    except Exception as e:
        logger.exception(f"Error during solve instances cycle: {e}")


async def main() -> None:
    """
    Continuously run solve instances as a standalone process.
    
    The process runs every 30 seconds to process awarded proposals.
    Handles graceful shutdown on keyboard interrupt.
    
    Fixes #26: Decoupled from market_scan to allow independent operation.
    Fixes #82: Refactored for better async handling and error management.
    """
    logger.info("Starting solve instances process...")

    try:
        while True:
            await process_cycle()
            await asyncio.sleep(30)  # Non-blocking sleep
            
    except KeyboardInterrupt:
        logger.info("Solve instances process stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error in solve instances process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
