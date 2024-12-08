import tempfile
from pathlib import Path
from typing import Optional

import httpx
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from loguru import logger

from src import utils
from src.config import SETTINGS, Settings

TIMEOUT = httpx.Timeout(10.0)


def _get_instance_to_solve(instance_id: str, settings: Settings) -> Optional[dict]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        instance_url = f"{settings.market_url}/v1/instances/{instance_id}"
        response = client.get(instance_url, headers=headers)
        instance = response.json()

        if instance["status"] != settings.market_resolved_instance_code:
            logger.info(
                f"Instance id {instance_id} has status {instance['status']}. "
                f"Skipping since it is not resolved ({settings.market_resolved_instance_code})"
            )
            return None

    with httpx.Client(timeout=TIMEOUT) as client:
        chat_url = f"{settings.market_url}/v1/chat/{instance_id}"
        response = client.get(chat_url, headers=headers)

        chat = response.json()
        if chat:
            logger.info(f"Instance id {instance_id} has chat messages. Skipping solving.")
            return None

        return instance


def _solve_instance(instance_id: str, instance_background: str, settings: Settings) -> None:
    logger.info("Solving instance id: {}", instance_id)
    target_repo_url = utils.find_github_repo_url(instance_background)
    instance_background = utils.remove_all_urls(instance_background)
    if not target_repo_url:
        logger.info(f"Instance id {instance_id} does not have a github repo url")
        return

    forked_repo_url = utils.fork_repo(target_repo_url, settings.github_pat)
    logger.info(f"Forked repo url: {forked_repo_url}")
    forked_repo_name = utils.extract_repo_name_from_url(forked_repo_url)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_absolute_path = Path(temp_dir)
        logger.info(f"Cloning repository {forked_repo_url} to {repo_absolute_path}")
        try:
            utils.clone_repository(forked_repo_url, str(repo_absolute_path))
            utils.create_and_push_branch(repo_absolute_path, instance_id, settings.github_pat)
            utils.set_git_config(
                settings.github_username, settings.github_email, repo_absolute_path
            )
            tracked_files = utils.list_tracked_files(str(repo_absolute_path))

            model = Model(settings.foundation_model_name.value)
            io = InputOutput(yes=True)
            coder = Coder.create(
                main_model=model,
                fnames=tracked_files,
                io=io,
            )
            output = coder.run(instance_background)
            logger.info("Output: {}", output)

            utils.push_commits(str(repo_absolute_path), settings.github_pat)
            logger.info(f"Pushed commits to {forked_repo_url}")

            target_repo_name = utils.extract_repo_name_from_url(target_repo_url)
            logger.info(
                f"Creating pull request from source repo {forked_repo_name} "
                f"to target repo {target_repo_name}"
            )

            pr_title = utils.get_pr_title(instance_background)
            pr_body = utils.get_pr_body(instance_background)

            pr_url = utils.create_pull_request(
                source_repo_name=forked_repo_name,
                target_repo_name=target_repo_name,
                source_repo_path=str(repo_absolute_path),
                github_token=settings.github_pat,
                pr_title=pr_title,
                pr_body=pr_body,
            )

            return pr_url

        except Exception as e:
            logger.error(f"Error while processing repository: {e}")
            raise


def get_awarded_proposals(settings: Settings) -> list[dict]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    url = f"{settings.market_url}/v1/proposals/"

    response = httpx.get(url, headers=headers)
    response.raise_for_status()
    all_proposals = response.json()

    awarded_proposals = [
        p for p in all_proposals if p["status"] == settings.market_awarded_proposal_code
    ]
    return awarded_proposals


def _send_message(instance_id: str, message: str, settings: Settings) -> None:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    url = f"{settings.market_url}/v1/chat/send-message/{instance_id}"
    data = {"message": message}

    response = httpx.post(url, headers=headers, json=data)
    response.raise_for_status()


def handler(event, context) -> None:
    logger.info("Lambda handler to solve instances")
    awarded_proposals = get_awarded_proposals(SETTINGS)

    logger.info(f"Found {len(awarded_proposals)} awarded proposals")
    logger.info(f"Awarded proposals: {awarded_proposals}")

    for p in awarded_proposals:
        instance = _get_instance_to_solve(p["instance_id"], SETTINGS)
        if not instance:
            continue

        logger.info("Solving instance id: {}", instance["id"])
        try:
            pr_url = _solve_instance(
                instance["id"],
                instance["background"],
                SETTINGS,
            )
        except Exception as e:
            logger.error(f"Error solving instance id {instance['id']}: {e}")
        else:
            try:
                _send_message(
                    instance["id"],
                    f"Solved instance {instance['id']} with PR {pr_url}",
                    SETTINGS,
                )
            except Exception as e:
                logger.error(f"Error sending message for instance id {instance['id']}: {e}")

    return {"statusCode": 200, "body": "Instances solved successfully"}