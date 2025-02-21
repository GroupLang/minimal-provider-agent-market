"""Market scan process that runs independently to check for new instances."""

import asyncio
import sys

from loguru import logger

from src.market_scan import market_scan_handler


SCAN_INTERVAL = 10  # Scan for new instances every 10 seconds


async def _process_scan() -> None:
    """Process a single market scan iteration."""
    try:
        logger.info("Starting market scan")
        market_scan_handler()
        logger.info("Market scan completed successfully")
    except Exception as e:
        logger.exception("Error during market scan: %s", str(e))


async def main() -> None:
    """
    Continuously run market scan as a standalone process.

    The process runs every SCAN_INTERVAL seconds to check for new instances.
    Handles graceful shutdown on keyboard interrupt.

    Fixes #26: Decoupled from solve_instances to allow independent operation.
    """
    logger.info("Starting market scan process...")

    try:
        while True:
            await _process_scan()
            await asyncio.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Market scan process stopped by user")
    except Exception as e:
        logger.exception("Fatal error in market scan process: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
