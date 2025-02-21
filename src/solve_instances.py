import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from src import agents, utils
from src.config import SETTINGS, Settings
from src.containers import launch_container_with_repo_mounted
from src.enums import AgentType

TIMEOUT = httpx.Timeout(10.0)


@dataclass
class InstanceToSolve:
    instance: dict
    repo_url: Optional[str] = None
    pr_url: Optional[str] = None
    pr_comments: Optional[str] = None
    messages_with_requester: Optional[str] = None
    started_solving: bool = False


def _get_instance_to_solve(
    instance_id: str, settings: Settings
) -> Optional[InstanceToSolve]:
    headers = _get_market_headers(settings)

    # Get instance details
    with httpx.Client(timeout=TIMEOUT) as client:
        instance_endpoint = f"{settings.market_url}/v1/instances/{instance_id}"
        response = client.get(instance_endpoint, headers=headers)
        response.raise_for_status()
        instance = response.json()

        if instance["status"] != settings.market_resolved_instance_code:
            return None

        # Get chat messages
        chat_endpoint = f"{settings.market_url}/v1/chat/{instance_id}"
        response = client.get(chat_endpoint, headers=headers)
        response.raise_for_status()
        chat = response.json()

    repo_url = utils.find_github_repo_url(instance["background"])
    if not repo_url:
        logger.info(f"Instance id {instance_id} does not have a github repo url")
        return InstanceToSolve(instance=instance)

    if not chat:
        return InstanceToSolve(instance=instance, repo_url=repo_url)

    # Process chat messages
    messages_from_provider_present = any(
        message["sender"] == "provider" for message in chat
    )
    logger.info(
        f"Instance id {instance_id} messages from provider: {messages_from_provider_present}"
    )

    sorted_messages = sorted(chat, key=lambda m: m["timestamp"])
    messages_with_requester = (
        utils.format_messages(chat)
        if sorted_messages[-1]["sender"] == "requester"
        else None
    )
    logger.info(f"Messages with requester: {messages_with_requester}")

    # Process PR information
    formatted_messages = utils.format_messages(chat)
    pr_url = utils.get_pr_url(formatted_messages)
    logger.info(
        f"PR URL {'NOT ' if not pr_url else ''}found {pr_url or ''} for instance id {instance_id}"
    )

    if not pr_url:
        return InstanceToSolve(
            instance=instance,
            repo_url=repo_url,
            messages_with_requester=messages_with_requester,
            started_solving=messages_from_provider_present,
        )

    # Get PR comments
    logger.info(f"Looking for PR comments in chat with instance id {instance_id}")
    pr_comments = utils.get_last_pr_comments(pr_url, settings.github_pat)
    logger.info(
        f"PR comments {'NOT ' if not pr_comments else ''}found {pr_comments or ''} for instance id {instance_id}"
    )

    return InstanceToSolve(
        instance=instance,
        repo_url=repo_url,
        pr_url=pr_url,
        pr_comments=pr_comments,
        messages_with_requester=messages_with_requester,
        started_solving=messages_from_provider_present,
    )


def _setup_repo(instance_to_solve: InstanceToSolve, settings: Settings) -> tuple[Path, str, str]:
    """Set up repository for solving the instance."""
    forked_repo_url = utils.fork_repo(instance_to_solve.repo_url, settings.github_pat)
    logger.info(f"Forked repo url: {forked_repo_url}")
    forked_repo_name = utils.extract_repo_name_from_url(forked_repo_url)
    
    temp_dir = tempfile.mkdtemp()
    repo_absolute_path = Path(temp_dir)
    logger.info(f"Cloning repository {forked_repo_url} to {repo_absolute_path}")

    utils.clone_repository(forked_repo_url, str(repo_absolute_path), settings.github_pat)
    utils.create_and_push_branch(repo_absolute_path, instance_to_solve.instance["id"], settings.github_pat)
    utils.set_git_config(settings.github_username, settings.github_email, repo_absolute_path)
    
    return repo_absolute_path, forked_repo_url, forked_repo_name


def _get_container_kwargs(
    instance_to_solve: InstanceToSolve,
    settings: Settings,
    repo_absolute_path: Path,
    solver_command: str,
) -> dict:
    """Get container configuration based on agent type."""
    if settings.agent_type == AgentType.open_hands:
        return agents.open_hands_get_container_kwargs(
            str(repo_absolute_path),
            solver_command,
            settings.foundation_model_name,
        )
    elif settings.agent_type == AgentType.aider:
        logger.info("Aider agent type")
        modify_repo_absolute_path = (
            Path(os.path.dirname(os.path.abspath(__file__)))
            / "agents"
            / "aider_modify_repo.py"
        )
        utils.copy_file_to_directory(modify_repo_absolute_path, repo_absolute_path)
        utils.change_directory_ownership_recursive(repo_absolute_path, os.getuid(), os.getgid())

        test_command = agents.aider_suggest_test_command(str(repo_absolute_path))
        return agents.aider_get_container_kwargs(
            str(repo_absolute_path),
            settings.foundation_model_name.value,
            solver_command,
            test_command,
            settings.architect_model_name.value,
        )
    elif settings.agent_type == AgentType.raaid:
        utils.change_directory_ownership_recursive(repo_absolute_path, os.getuid(), os.getgid())
        return agents.raaid_get_container_kwargs(
            str(repo_absolute_path),
            solver_command,
            settings.foundation_model_name,
        )
    raise ValueError(f"Unknown agent type: {settings.agent_type}")


def _handle_solution_result(
    instance_to_solve: InstanceToSolve,
    settings: Settings,
    repo_absolute_path: Path,
    forked_repo_name: str,
    logs: str,
) -> str:
    """Handle the result of solving an instance."""
    if instance_to_solve.pr_url:
        utils.add_logs_as_pr_comments(instance_to_solve.pr_url, settings.github_pat, logs)

    utils.add_and_commit(str(repo_absolute_path))
    pushed = utils.push_commits(str(repo_absolute_path), settings.github_pat)
    
    if not pushed:
        logger.info(f"No new commits to push for instance id {instance_to_solve.instance['id']}")
        return logs

    if instance_to_solve.pr_url:
        return "Added comments to PR"

    target_repo_name = utils.extract_repo_name_from_url(instance_to_solve.repo_url)
    logger.info(
        f"Creating pull request from source repo {forked_repo_name} "
        f"to target repo {target_repo_name}"
    )

    pr_title = utils.get_pr_title(instance_to_solve.instance["background"])
    pr_body = utils.get_pr_body(instance_to_solve.instance["background"], logs)

    pr_url = utils.create_pull_request(
        source_repo_name=forked_repo_name,
        target_repo_name=target_repo_name,
        source_repo_path=str(repo_absolute_path),
        github_token=settings.github_pat,
        pr_title=pr_title,
        pr_body=pr_body,
    )

    return f"Solved instance {instance_to_solve.instance['id']} with PR {pr_url}"


def _solve_instance(
    instance_to_solve: InstanceToSolve,
    settings: Settings,
) -> str:
    """Solve an instance by running the appropriate agent in a container."""
    logger.info("Solving instance id: {}", instance_to_solve.instance["id"])
    
    solver_command = utils.build_solver_command(
        instance_to_solve.instance["background"],
        instance_to_solve.pr_comments,
        instance_to_solve.messages_with_requester,
    )
    solver_command = utils.remove_all_urls(solver_command)

    try:
        repo_absolute_path, forked_repo_url, forked_repo_name = _setup_repo(instance_to_solve, settings)
        container_kwargs = _get_container_kwargs(instance_to_solve, settings, repo_absolute_path, solver_command)
        logs = launch_container_with_repo_mounted(**container_kwargs)
        
        return _handle_solution_result(
            instance_to_solve,
            settings,
            repo_absolute_path,
            forked_repo_name,
            logs,
        )
    finally:
        if 'repo_absolute_path' in locals():
            import shutil
            shutil.rmtree(repo_absolute_path, ignore_errors=True)


def _get_market_headers(settings: Settings) -> dict:
    return {
        "x-api-key": settings.market_api_key,
        "Accept": "application/json",
    }


def get_awarded_proposals(settings: Settings) -> list[dict]:
    url = f"{settings.market_url}/v1/proposals/"
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.get(url, headers=_get_market_headers(settings))
        response.raise_for_status()
        all_proposals = response.json()

    current_time = datetime.utcnow()
    one_day_ago = current_time - timedelta(days=1)

    return [
        p
        for p in all_proposals
        if p["status"] == settings.market_awarded_proposal_code
        and datetime.fromisoformat(p["creation_date"]) > one_day_ago
    ]


def _send_message(instance_id: str, message: str, settings: Settings) -> None:
    url = f"{settings.market_url}/v1/chat/send-message/{instance_id}"
    data = {"message": message}

    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(
            url, 
            headers=_get_market_headers(settings), 
            json=data
        )
        response.raise_for_status()


def solve_instances_handler() -> None:
    logger.info("Solve instances handler")
    awarded_proposals = get_awarded_proposals(SETTINGS)

    logger.info(f"Found {len(awarded_proposals)} awarded proposals")

    for p in awarded_proposals:
        try:
            instance_to_solve = _get_instance_to_solve(p["instance_id"], SETTINGS)
            if not instance_to_solve or not instance_to_solve.repo_url:
                continue

            pr_interaction = bool(instance_to_solve.pr_url) and bool(
                instance_to_solve.pr_comments
            )
            user_interaction = bool(instance_to_solve.messages_with_requester)
            if (
                instance_to_solve.started_solving
                and (not pr_interaction)
                and (not user_interaction)
            ):
                continue

            message = _solve_instance(
                instance_to_solve,
                SETTINGS,
            )
            if not message:
                continue
        except Exception as e:
            logger.error(f"Error solving instance id {instance_to_solve.instance['id']}: {e}")
            continue

        try:
            _send_message(instance_to_solve.instance["id"], message, SETTINGS)
        except Exception as e:
            logger.error(f"Error sending message for instance id {instance_to_solve.instance['id']}: {e}")
