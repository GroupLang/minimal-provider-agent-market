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


def load_aws_credentials():
    """Load AWS credentials from .env file."""
    if not Path(".env").exists():
        raise FileNotFoundError(".env file not found")

    load_dotenv()
    required_vars = [
        "CUSTOM_AWS_ACCESS_KEY_ID",
        "CUSTOM_AWS_SECRET_ACCESS_KEY",
        "CUSTOM_AWS_REGION_NAME",
    ]

    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Required environment variable {var} not found in .env file")


def market_scan_process():
    """Process for handling market scanning."""
    while True:
        try:
            # Create event loop for this process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(async_market_scan_handler())
        except Exception as e:
            print(f"Error in market scan process: {e}")
        time.sleep(10)


def git_process():
    """Process for handling git operations."""
    while True:
        try:
            # Create event loop for this process
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(accept_repo_invitations(SETTINGS.github_pat))
        except Exception as e:
            print(f"Error in git process: {e}")
        time.sleep(10)


def solve_instances_process():
    """Process for handling instance solving."""
    while True:
        try:
            solve_instances_handler()
        except Exception as e:
            print(f"Error in solve instances process: {e}")
        time.sleep(10)


def main():
    # Load AWS credentials
    load_aws_credentials()
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
