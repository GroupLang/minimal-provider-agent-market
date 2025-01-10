from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx
import openai
from loguru import logger

from src.agents.aider_modify_repo import modify_repo_with_aider
from src.config import SETTINGS, Settings
from src.enums import ModelName

TIMEOUT = httpx.Timeout(10.0)

openai.api_key = SETTINGS.openai_api_key
WEAK_MODEL = "gpt-4o-mini"


@dataclass
class InstanceToSolve:
    instance: dict
    messages_history: Optional[str] = None
    provider_needs_response: bool = False


def _get_instance_to_solve(instance_id: str, settings: Settings) -> Optional[InstanceToSolve]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        instance_endpoint = f"{settings.market_url}/v1/instances/{instance_id}"
        response = client.get(instance_endpoint, headers=headers)
        instance = response.json()

        if instance["status"] != settings.market_resolved_instance_code:
            return None

    with httpx.Client(timeout=TIMEOUT) as client:
        chat_endpoint = f"{settings.market_url}/v1/chat/{instance_id}"
        response = client.get(chat_endpoint, headers=headers)

        chat = response.json()
        if not chat:
            return InstanceToSolve(instance=instance)

        sorted_messages = sorted(chat, key=lambda m: m["timestamp"])
        last_message = sorted_messages[-1]
        provider_needs_response = last_message["sender"] == "provider" and len(sorted_messages) < 5

        messages_history = "\n\n".join(
            [f"{message['sender']}: {message['message']}" for message in sorted_messages]
        )

        return InstanceToSolve(
            instance=instance,
            messages_history=messages_history,
            provider_needs_response=provider_needs_response,
        )


def _clean_response(response: str) -> str:
    prompt = """
    Below is a code review response. Clean up any formatting issues, remove redundant text, 
    and ensure consistent spacing. Do not change the content or meaning of the feedback.

    Response:
    {feedback}
    """

    try:
        cleaned = openai.chat.completions.create(
            model=WEAK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that cleans up text formatting.",
                },
                {"role": "user", "content": prompt.format(feedback=response)},
            ],
        )
        return cleaned.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to clean response with GPT-4: {e}")
        return response


def _solve_instance(
    instance_to_solve: InstanceToSolve,
) -> str:
    logger.info("Solving instance id: {}", instance_to_solve.instance["id"])

    system_prompt = (
        "You are a code reviewer examining this PR and conversation history. "
        "If there are questions to answer or PR changes to request, provide a response. "
        "Otherwise, reply with 'NO_RESPONSE_NEEDED'. Be thorough but constructive in your review."
    )

    solver_command_parts = [
        system_prompt,
    ]

    if instance_to_solve.messages_history:
        messages = instance_to_solve.messages_history
        if "github.com" in messages and "/pull/" in messages:
            import re

            pr_link = re.search(r"https://github\.com/[^/]+/[^/]+/pull/\d+", messages)
            if pr_link:
                pr_url = pr_link.group(0)
                files_url = f"{pr_url}/files"
                repo_url = pr_url.split("/pull/")[0]

                try:
                    pr_response = httpx.get(pr_url, timeout=TIMEOUT)
                    if pr_response.status_code == 200:
                        pr_content = pr_response.text
                        issue_link = re.search(
                            r"https://github\.com/[^/]+/[^/]+/issues/\d+", pr_content
                        )
                        if issue_link:
                            messages += f"\n\nRelated issue: {issue_link.group(0)}"
                except Exception as e:
                    logger.warning(f"Failed to fetch PR content: {e}")

                messages += (
                    f"\n\nAdditional links:\nFiles view: {files_url}\nRepository: {repo_url}"
                )

        solver_command_parts.append(f"This is the conversation history:\n{messages}")

    solver_command = "\n\n\n".join(solver_command_parts)

    try:
        response = modify_repo_with_aider(ModelName.gpt_4o, solver_command)
        if not response:
            logger.warning("Received empty response from Aider")
            return None

        if "NO_RESPONSE_NEEDED" in response:
            logger.info("No response needed for this instance")
            return None

        cleaned_response = _clean_response(response.strip())
        return cleaned_response

    except Exception as e:
        logger.error(
            "Error using Aider for instance {}: {}",
            instance_to_solve.instance["id"],
            str(e),
            exc_info=True,
        )
        return None


def get_awarded_proposals(settings: Settings) -> list[dict]:
    headers = {
        "x-api-key": settings.market_api_key,
    }
    url = f"{settings.market_url}/v1/proposals/"

    response = httpx.get(url, headers=headers)
    response.raise_for_status()
    all_proposals = response.json()

    current_time = datetime.utcnow()
    one_day_ago = current_time - timedelta(days=1)

    awarded_proposals = [
        p
        for p in all_proposals
        if p["status"] == settings.market_awarded_proposal_code
        and datetime.fromisoformat(p["creation_date"]) > one_day_ago
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


def solve_instances_handler() -> None:
    logger.info("Solve instances handler")
    awarded_proposals = get_awarded_proposals(SETTINGS)

    logger.info(f"Found {len(awarded_proposals)} awarded proposals")

    for p in awarded_proposals:
        instance_to_solve = _get_instance_to_solve(p["instance_id"], SETTINGS)
        try:
            if not instance_to_solve:
                continue

            if not instance_to_solve.provider_needs_response:
                continue

            message = _solve_instance(instance_to_solve)
            if not message:
                continue

            _send_message(
                instance_to_solve.instance["id"],
                message,
                SETTINGS,
            )
        except Exception as e:
            logger.error(f"Error solving instance id {instance_to_solve.instance['id']}: {e}")
