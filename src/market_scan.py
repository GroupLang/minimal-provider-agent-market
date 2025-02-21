"""Market scanning functionality to find and create proposals for open instances."""

import asyncio
from typing import List, Optional, Set

import httpx
from loguru import logger

from src import utils
from src.config import SETTINGS, Settings

# Constants
TIMEOUT = httpx.Timeout(10.0)
DEFAULT_HEADERS = {"Accept": "application/json"}


class MarketScanner:
    """Handles scanning the market for open instances and creating proposals."""

    def __init__(self, settings: Settings):
        """Initialize scanner with settings."""
        self.settings = settings
        self.headers = {
            **DEFAULT_HEADERS,
            "x-api-key": settings.market_api_key,
        }
        self.base_url = settings.market_url

    async def _fetch_open_instances(self) -> List[dict]:
        """Fetch all open instances from the market."""
        url = f"{self.base_url}/v1/instances/"
        params = {"instance_status": self.settings.market_open_instance_code}

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            instances = response.json()

        logger.debug(f"Found {len(instances)} open instances")
        return instances

    async def _fetch_existing_proposals(self) -> Set[str]:
        """Fetch existing proposals and return set of instance IDs."""
        url = f"{self.base_url}/v1/proposals/"
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            proposals = response.json()

        return {proposal["instance_id"] for proposal in proposals}

    async def _create_proposal(self, instance: dict) -> Optional[str]:
        """Create a proposal for an instance if it has a GitHub repo.
        
        Returns:
            str: Instance ID if proposal was created successfully
            None: If proposal creation was skipped or failed
        """
        instance_id = instance["id"]
        
        # Skip instances without GitHub repos
        if not utils.find_github_repo_url(instance["background"]):
            logger.info(f"Instance {instance_id} skipped - no GitHub repo URL")
            return None

        try:
            url = f"{self.base_url}/v1/proposals/create/for-instance/{instance_id}"
            data = {"max_bid": self.settings.max_bid}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()

            logger.info(f"Created proposal for instance {instance_id}")
            return instance_id

        except Exception as e:
            logger.error(f"Failed to create proposal for instance {instance_id}: {e}")
            return None

    async def scan_and_create_proposals(self) -> None:
        """Main method to scan market and create proposals for new instances."""
        try:
            # Fetch open instances and existing proposals
            open_instances = await self._fetch_open_instances()
            if not open_instances:
                logger.debug("No open instances found")
                return

            filled_instances = await self._fetch_existing_proposals()
            
            # Create proposals for new instances
            new_instances = [
                instance for instance in open_instances 
                if instance["id"] not in filled_instances
            ]
            
            if new_instances:
                tasks = [self._create_proposal(instance) for instance in new_instances]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Count successful proposals
                successful = sum(1 for r in results if r is not None)
                logger.info(f"Created {successful} new proposals out of {len(new_instances)} attempts")
            else:
                logger.debug("No new instances to create proposals for")

        except Exception as e:
            logger.exception(f"Error during market scan: {e}")
            raise


def market_scan_handler() -> None:
    """Entry point for market scanning functionality."""
    scanner = MarketScanner(SETTINGS)
    asyncio.run(scanner.scan_and_create_proposals())
