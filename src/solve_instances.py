"""Instance solving functionality to handle awarded proposals."""

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict

import httpx
from loguru import logger

from src import agents, utils
from src.config import SETTINGS, Settings
from src.containers import launch_container_with_repo_mounted
from src.enums import AgentType

# Constants
TIMEOUT = httpx.Timeout(10.0)
DEFAULT_HEADERS = {"Accept": "application/json"}


@dataclass
class InstanceToSolve:
    """Represents an instance that needs to be solved."""
    
    instance: dict
    repo_url: Optional[str] = None
    pr_url: Optional[str] = None
    pr_comments: Optional[str] = None
    messages_with_requester: Optional[str] = None
    started_solving: bool = False

    @property
    def instance_id(self) -> str:
        """Get the instance ID."""
        return self.instance["id"]

    @property
    def has_github_interaction(self) -> bool:
        """Check if instance has GitHub PR interaction."""
        return bool(self.pr_url and self.pr_comments)

    @property
    def needs_attention(self) -> bool:
        """Check if instance needs attention based on interactions."""
        return (
            self.started_solving 
            and not self.has_github_interaction 
            and not self.messages_with_requester
        )


class InstanceSolver:
    """Handles fetching and solving instances."""

    def __init__(self, settings: Settings):
        """Initialize solver with settings."""
        self.settings = settings
        self.headers = {
            **DEFAULT_HEADERS,
            "x-api-key": settings.market_api_key,
        }
        self.base_url = settings.market_url

    async def get_instance_details(self, instance_id: str) -> Optional[InstanceToSolve]:
        """Fetch and construct instance details."""
        try:
            # Fetch instance data
            instance_url = f"{self.base_url}/v1/instances/{instance_id}"
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(instance_url, headers=self.headers)
                instance = response.json()

            if instance["status"] != self.settings.market_resolved_instance_code:
                return None

            # Check for GitHub repo
            repo_url = utils.find_github_repo_url(instance["background"])
            if not repo_url:
                logger.info(f"Instance {instance_id} has no GitHub repo URL")
                return InstanceToSolve(instance=instance)

            # Fetch chat history
            chat_url = f"{self.base_url}/v1/chat/{instance_id}"
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(chat_url, headers=self.headers)
                chat = response.json()

            if not chat:
                return InstanceToSolve(instance=instance, repo_url=repo_url)

            # Process chat messages
            messages_from_provider = any(msg["sender"] == "provider" for msg in chat)
            sorted_messages = sorted(chat, key=lambda m: m["timestamp"])
            messages_with_requester = (
                utils.format_messages(chat)
                if sorted_messages[-1]["sender"] == "requester"
                else None
            )

            # Get PR information
            formatted_chat = utils.format_messages(chat)
            pr_url = utils.get_pr_url(formatted_chat)
            pr_comments = None
            
            if pr_url:
                pr_comments = utils.get_last_pr_comments(pr_url, self.settings.github_pat)

            return InstanceToSolve(
                instance=instance,
                repo_url=repo_url,
                pr_url=pr_url,
                pr_comments=pr_comments,
                messages_with_requester=messages_with_requester,
                started_solving=messages_from_provider,
            )

        except Exception as e:
            logger.error(f"Error fetching instance {instance_id} details: {e}")
            return None

    def solve_instance(self, instance: InstanceToSolve) -> Optional[str]:
        """Solve an instance by running appropriate agent in container."""
        try:
            logger.info(f"Solving instance: {instance.instance_id}")
            
            # Prepare solver command
            solver_command = utils.build_solver_command(
                instance.instance["background"],
                instance.pr_comments,
                instance.messages_with_requester,
            )
            solver_command = utils.remove_all_urls(solver_command)

            # Fork and clone repository
            forked_repo_url = utils.fork_repo(instance.repo_url, self.settings.github_pat)
            forked_repo_name = utils.extract_repo_name_from_url(forked_repo_url)

            with tempfile.TemporaryDirectory() as temp_dir:
                repo_path = Path(temp_dir)
                
                # Setup repository
                utils.clone_repository(forked_repo_url, str(repo_path), self.settings.github_pat)
                utils.create_and_push_branch(repo_path, instance.instance_id, self.settings.github_pat)
                utils.set_git_config(self.settings.github_username, self.settings.github_email, repo_path)

                # Configure agent-specific container
                container_kwargs = self._get_agent_container_kwargs(repo_path, solver_command)
                
                # Run container and get logs
                logs = launch_container_with_repo_mounted(**container_kwargs)
                
                # Handle PR comments if needed
                if instance.pr_url:
                    utils.add_logs_as_pr_comments(instance.pr_url, self.settings.github_pat, logs)

                # Commit and push changes
                utils.add_and_commit(str(repo_path))
                if not utils.push_commits(str(repo_path), self.settings.github_pat):
                    logger.info(f"No new commits for instance {instance.instance_id}")
                    return logs

                # Create PR if needed
                if instance.pr_url:
                    return "Added comments to PR"

                target_repo_name = utils.extract_repo_name_from_url(instance.repo_url)
                pr_title = utils.get_pr_title(instance.instance["background"])
                pr_body = utils.get_pr_body(instance.instance["background"], logs)

                pr_url = utils.create_pull_request(
                    source_repo_name=forked_repo_name,
                    target_repo_name=target_repo_name,
                    source_repo_path=str(repo_path),
                    github_token=self.settings.github_pat,
                    pr_title=pr_title,
                    pr_body=pr_body,
                )

                return f"Solved instance {instance.instance_id} with PR {pr_url}"

        except Exception as e:
            logger.error(f"Error solving instance {instance.instance_id}: {e}")
            return None

    def _get_agent_container_kwargs(self, repo_path: Path, solver_command: str) -> Dict:
        """Get container configuration based on agent type."""
        if self.settings.agent_type == AgentType.open_hands:
            return agents.open_hands_get_container_kwargs(
                str(repo_path),
                solver_command,
                self.settings.foundation_model_name,
            )
            
        elif self.settings.agent_type == AgentType.aider:
            # Setup Aider-specific files
            modify_repo_path = (
                Path(os.path.dirname(os.path.abspath(__file__)))
                / "agents"
                / "aider_modify_repo.py"
            )
            utils.copy_file_to_directory(modify_repo_path, repo_path)
            utils.change_directory_ownership_recursive(repo_path, os.getuid(), os.getgid())

            test_command = agents.aider_suggest_test_command(str(repo_path))
            return agents.aider_get_container_kwargs(
                str(repo_path),
                self.settings.foundation_model_name.value,
                solver_command,
                test_command,
                self.settings.architect_model_name.value,
            )
            
        elif self.settings.agent_type == AgentType.raaid:
            utils.change_directory_ownership_recursive(repo_path, os.getuid(), os.getgid())
            return agents.raaid_get_container_kwargs(
                str(repo_path),
                solver_command,
                self.settings.foundation_model_name,
            )
            
        raise ValueError(f"Unsupported agent type: {self.settings.agent_type}")

    async def get_awarded_proposals(self) -> List[dict]:
        """Get list of awarded proposals from the last 24 hours."""
        try:
            url = f"{self.base_url}/v1/proposals/"
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                all_proposals = response.json()

            # Filter proposals by time and status
            current_time = datetime.utcnow()
            one_day_ago = current_time - timedelta(days=1)

            awarded_proposals = [
                p for p in all_proposals
                if (p["status"] == self.settings.market_awarded_proposal_code and
                    datetime.fromisoformat(p["creation_date"]) > one_day_ago)
            ]
            
            logger.info(f"Found {len(awarded_proposals)} awarded proposals in last 24h")
            return awarded_proposals

        except Exception as e:
            logger.error(f"Error fetching awarded proposals: {e}")
            return []

    async def send_message(self, instance_id: str, message: str) -> bool:
        """Send a message to an instance chat."""
        try:
            url = f"{self.base_url}/v1/chat/send-message/{instance_id}"
            data = {"message": message}

            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
            return True

        except Exception as e:
            logger.error(f"Error sending message to instance {instance_id}: {e}")
            return False


async def solve_instances_handler() -> None:
    """Main handler for solving awarded instances."""
    try:
        solver = InstanceSolver(SETTINGS)
        awarded_proposals = await solver.get_awarded_proposals()

        for proposal in awarded_proposals:
            instance_id = proposal["instance_id"]
            try:
                # Get instance details
                instance = await solver.get_instance_details(instance_id)
                if not instance or not instance.repo_url:
                    logger.debug(f"Skipping instance {instance_id} - no repo URL")
                    continue

                # Skip if no new interaction needed
                if instance.needs_attention:
                    logger.debug(f"Skipping instance {instance_id} - no new interaction needed")
                    continue

                # Solve instance
                message = solver.solve_instance(instance)
                if not message:
                    logger.warning(f"No solution message for instance {instance_id}")
                    continue

                # Send solution message
                if await solver.send_message(instance_id, message):
                    logger.info(f"Successfully processed instance {instance_id}")
                else:
                    logger.error(f"Failed to send message for instance {instance_id}")

            except Exception as e:
                logger.error(f"Error processing instance {instance_id}: {e}")
                continue

    except Exception as e:
        logger.exception(f"Fatal error in solve instances handler: {e}")
