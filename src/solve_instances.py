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


def _get_instance_to_solve(instance_id: str, settings: Settings) -> Optional[InstanceToSolve]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            instance_endpoint = f"{settings.market_url}/v1/instances/{instance_id}"
            response = client.get(instance_endpoint, headers=headers)
            response.raise_for_status()
            instance = response.json()
            
            if not isinstance(instance, dict):
                logger.error(f"Unexpected response format for instance {instance_id}: {instance}")
                return None
                
            if "status" not in instance:
                logger.error(f"Missing status field in instance {instance_id}: {instance}")
                return None
                
            if instance["status"] != settings.market_resolved_instance_code:
                return None
    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching instance {instance_id}: {e}")
        return None
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error parsing response for instance {instance_id}: {e}")
        return None

    repo_url = utils.find_github_repo_url(instance["background"])
    if not repo_url:
        logger.info(f"Instance id {instance_id} does not have a github repo url")
        return InstanceToSolve(instance=instance)

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            chat_endpoint = f"{settings.market_url}/v1/chat/{instance_id}"
            response = client.get(chat_endpoint, headers=headers)
            response.raise_for_status()
            
            chat = response.json()
            if not chat:
                return InstanceToSolve(instance=instance, repo_url=repo_url)
            
            if not isinstance(chat, list):
                logger.error(f"Unexpected chat format for instance {instance_id}: {chat}")
                return InstanceToSolve(instance=instance, repo_url=repo_url)

            try:
                messages_from_provider_present = any(
                    isinstance(message, dict) and message.get("sender") == "provider" 
                    for message in chat
                )
                logger.info(
                    f"Instance id {instance_id} messages from provider: {messages_from_provider_present}"
                )

                valid_messages = [m for m in chat if isinstance(m, dict) and "timestamp" in m and "sender" in m]
                messages_with_requester = None
                if valid_messages:
                    latest_message = sorted(valid_messages, key=lambda m: m["timestamp"])[-1]
                    if latest_message["sender"] == "requester":
                        messages_with_requester = utils.format_messages(chat)
                logger.info(f"Messages with requester: {messages_with_requester}")

                formatted_messages = utils.format_messages(chat)
                pr_url = utils.get_pr_url(formatted_messages)
                logger.info(
                    "PR URL {} found {} for instance id {}. Looking for PR comments".format(
                        "NOT" if not pr_url else "", pr_url if pr_url else "", instance_id
                    )
                )
            except Exception as e:
                logger.error(f"Error processing chat messages for instance {instance_id}: {e}")
                return InstanceToSolve(instance=instance, repo_url=repo_url)

    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching chat for instance {instance_id}: {e}")
        return InstanceToSolve(instance=instance, repo_url=repo_url)
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing chat response for instance {instance_id}: {e}")
        return InstanceToSolve(instance=instance, repo_url=repo_url)

    if not pr_url:
        return InstanceToSolve(
            instance=instance,
            repo_url=repo_url,
            messages_with_requester=messages_with_requester,
            started_solving=messages_from_provider_present,
        )

    try:
        logger.info(f"Looking for PR comments in chat with instance id {instance_id}")
        pr_comments = utils.get_last_pr_comments(pr_url, settings.github_pat)
        pr_comments = pr_comments if pr_comments else None
        logger.info(
            "PR comments {} found {} for instance id {}".format(
                "NOT" if not pr_comments else "", pr_comments if pr_comments else "", instance_id
            )
        )
        return InstanceToSolve(
            instance=instance,
            repo_url=repo_url,
            pr_url=pr_url,
            pr_comments=pr_comments,
            messages_with_requester=messages_with_requester,
            started_solving=messages_from_provider_present,
        )
    except Exception as e:
        logger.error(f"Error getting PR comments for instance {instance_id}: {e}")
        return InstanceToSolve(
            instance=instance,
            repo_url=repo_url,
            pr_url=pr_url,
            messages_with_requester=messages_with_requester,
            started_solving=messages_from_provider_present,
        )


def _solve_instance(
    instance_to_solve: InstanceToSolve,
    settings: Settings,
) -> None:
    logger.info("Solving instance id: {}", instance_to_solve.instance["id"])
    solver_command = utils.build_solver_command(
        instance_to_solve.instance["background"],
        instance_to_solve.pr_comments,
        instance_to_solve.messages_with_requester,
    )
    solver_command = utils.remove_all_urls(solver_command)

    forked_repo_url = utils.fork_repo(instance_to_solve.repo_url, settings.github_pat)
    logger.info(f"Forked repo url: {forked_repo_url}")
    forked_repo_name = utils.extract_repo_name_from_url(forked_repo_url)
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_absolute_path = Path(temp_dir)
        logger.info(f"Cloning repository {forked_repo_url} to {repo_absolute_path}")

        utils.clone_repository(forked_repo_url, str(repo_absolute_path))
        utils.create_and_push_branch(
            repo_absolute_path, instance_to_solve.instance["id"], settings.github_pat
        )
        utils.set_git_config(settings.github_username, settings.github_email, repo_absolute_path)

        if settings.agent_type == AgentType.open_hands:
            container_kwargs = agents.open_hands_get_container_kwargs(
                str(repo_absolute_path),
                solver_command,
                settings.foundation_model_name,
            )
        elif settings.agent_type == AgentType.aider:
            modify_repo_absolute_path = (
                Path(os.path.dirname(os.path.abspath(__file__))) / "agents" / "aider_modify_repo.py"
            )
            utils.copy_file_to_directory(modify_repo_absolute_path, repo_absolute_path)
            utils.change_directory_ownership_recursive(repo_absolute_path, os.getuid(), os.getgid())

            test_command = agents.aider_suggest_test_command(str(repo_absolute_path))
            solver_command = utils.aider_get_solver_command(
                solver_command, instance_to_solve.pr_comments
            )
            container_kwargs = agents.aider_get_container_kwargs(
                str(repo_absolute_path),
                settings.foundation_model_name.value,
                solver_command,
                test_command,
            )
        elif settings.agent_type == AgentType.raaid:
            utils.change_directory_ownership_recursive(repo_absolute_path, os.getuid(), os.getgid())
            container_kwargs = agents.raaid_get_container_kwargs(
                str(repo_absolute_path),
                solver_command,
                settings.foundation_model_name,
            )

        logs = launch_container_with_repo_mounted(**container_kwargs)
        if instance_to_solve.pr_url:
            utils.add_logs_as_pr_comments(instance_to_solve.pr_url, settings.github_pat, logs)

        utils.add_and_commit(str(repo_absolute_path))
        pushed = utils.push_commits(str(repo_absolute_path), settings.github_pat)
        if pushed:
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
        else:
            logger.info(
                f"No new commits to push for instance id {instance_to_solve.instance['id']}"
            )
            return logs


def get_awarded_proposals(settings: Settings) -> list[dict]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    url = f"{settings.market_url}/v1/proposals/"

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            all_proposals = response.json()

            if not isinstance(all_proposals, list):
                logger.error(f"Unexpected proposals format: {all_proposals}")
                return []

            current_time = datetime.utcnow()
            one_day_ago = current_time - timedelta(days=1)

            awarded_proposals = []
            for p in all_proposals:
                try:
                    if not isinstance(p, dict):
                        continue
                    if "status" not in p or "creation_date" not in p:
                        continue
                    if p["status"] == settings.market_awarded_proposal_code:
                        creation_date = datetime.fromisoformat(p["creation_date"])
                        if creation_date > one_day_ago:
                            awarded_proposals.append(p)
                except (ValueError, TypeError, KeyError) as e:
                    logger.error(f"Error processing proposal: {e}")
                    continue

            return awarded_proposals

    except httpx.HTTPError as e:
        logger.error(f"HTTP error while fetching proposals: {e}")
        return []
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing proposals response: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_awarded_proposals: {e}")
        return []


def _send_message(instance_id: str, message: str, settings: Settings) -> bool:
    """Send a message to the instance chat.
    
    Returns:
        bool: True if message was sent successfully, False otherwise.
    """
    headers = {
        "x-api-key": settings.market_api_key,
    }
    url = f"{settings.market_url}/v1/chat/send-message/{instance_id}"
    data = {"message": message}

    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
    except httpx.HTTPError as e:
        logger.error(f"HTTP error while sending message to instance {instance_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while sending message to instance {instance_id}: {e}")
        return False


def solve_instances_handler() -> None:
    logger.info("Solve instances handler")
    awarded_proposals = get_awarded_proposals(SETTINGS)

    logger.info(f"Found {len(awarded_proposals)} awarded proposals")

    for p in awarded_proposals:
        instance_to_solve = _get_instance_to_solve(p["instance_id"], SETTINGS)
        try:
            if not instance_to_solve or not instance_to_solve.repo_url:
                continue

            pr_interaction = bool(instance_to_solve.pr_url) and bool(instance_to_solve.pr_comments)
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
        else:
            if not _send_message(
                instance_to_solve.instance["id"],
                message,
                SETTINGS,
            ):
                logger.error(
                    f"Failed to send message for instance id {instance_to_solve.instance['id']}"
                )
