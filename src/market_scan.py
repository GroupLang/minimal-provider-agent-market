import asyncio

import httpx
from loguru import logger

from src import utils
from src.config import SETTINGS, Settings
from src.utils.pricing import PricingStrategy

TIMEOUT = httpx.Timeout(10.0)
pricing_strategy = PricingStrategy(SETTINGS.openrouter_api_key)


async def _create_proposal_for_instance(instance: dict, settings: Settings) -> None:
    instance_id = instance["id"]
    if not utils.find_github_repo_url(instance["background"]):
        logger.info("Instance id {} does not have a github repo url", instance_id)
        return

    logger.info("Creating proposal for instance id: {}", instance_id)

    bid = pricing_strategy.calculate_next_bid()
    logger.info(f"Calculated bid for instance {instance_id}: {bid}")

    headers = {
        "x-api-key": settings.market_api_key,
        "Accept": "application/json",
    }
    url = f"{settings.market_url}/v1/proposals/create/for-instance/{instance_id}"
    data = {
        "max_bid": bid,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)

    response.raise_for_status()
    logger.info(f"Proposal for instance id {instance_id} created successfully")


async def async_market_scan_handler() -> None:
    headers = {
        "x-api-key": SETTINGS.market_api_key,
        "Accept": "application/json",
    }
    url = f"{SETTINGS.market_url}/v1/instances/"
    params = {"instance_status": SETTINGS.market_open_instance_code}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, headers=headers, params=params)

    response.raise_for_status()
    open_instances = response.json()

    if not open_instances:
        logger.debug("No open instances found")
        return

    logger.debug(f"Found {len(open_instances)} open instances")
    url = f"{SETTINGS.market_url}/v1/proposals/"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, headers=headers)

    response.raise_for_status()
    proposals = response.json()

    filled_instances = set(proposal["instance_id"] for proposal in proposals)
    tasks = [
        _create_proposal_for_instance(instance, SETTINGS)
        for instance in open_instances
        if instance["id"] not in filled_instances
    ]
    await asyncio.gather(*tasks)


def market_scan_handler() -> None:
    asyncio.run(async_market_scan_handler())
