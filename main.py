#!/usr/bin/env python3

import asyncio
import multiprocessing
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from src.config import SETTINGS
from src.market_scan import async_market_scan_handler
from src.solve_instances import solve_instances_handler
from src.utils.git import accept_repo_invitations


def market_scan_process():
    """Market scan process."""
    while True:
        try:
            asyncio.run(async_market_scan_handler())
            time.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in market scan process: {e}")
            time.sleep(60)


def git_process():
    """Git process for accepting repo invitations."""
    while True:
        try:
            asyncio.run(accept_repo_invitations(SETTINGS.github_pat))
            time.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Error in git process: {e}")
            time.sleep(60)


def solve_instances_process():
    """Solve instances process."""
    while True:
        try:
            solve_instances_handler()
            time.sleep(60)  # Run every minute
        except Exception as e:
            print(f"Error in solve instances process: {e}")
            time.sleep(60)


def main():
    print("Starting all services in parallel...")

    # Create processes
    processes = [
        multiprocessing.Process(target=market_scan_process, daemon=True),
        multiprocessing.Process(target=git_process, daemon=True),
        multiprocessing.Process(target=solve_instances_process, daemon=True),
    ]

    # Start all processes
    for p in processes:
        p.start()

    # Wait for all processes
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\nShutting down processes...")
        for p in processes:
            p.terminate()
            p.join()


if __name__ == "__main__":
    main()
