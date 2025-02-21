"""Market scan process that runs independently to check for new instances."""

import asyncio
import sys
from datetime import datetime

from loguru import logger

from src.market_scan import market_scan_handler


async def process_cycle() -> None:
    """Run one cycle of market scanning."""
    try:
        logger.info(f"Starting market scan cycle at {datetime.utcnow()}")
        await market_scan_handler()
        logger.info("Market scan completed successfully")
    except Exception as e:
        logger.exception(f"Error during market scan cycle: {e}")


async def main() -> None:
    """
    Continuously run market scan as a standalone process.
    
    The process runs every 10 seconds to check for new instances.
    Handles graceful shutdown on keyboard interrupt.
    
    Fixes #26: Decoupled from solve_instances to allow independent operation.
    Fixes #82: Refactored for better async handling and error management.
    """
    logger.info("Starting market scan process...")

    try:
        while True:
            await process_cycle()
            await asyncio.sleep(10)  # Non-blocking sleep
            
    except KeyboardInterrupt:
        logger.info("Market scan process stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error in market scan process: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
