import re
from typing import Optional

import openai
import tiktoken

from src.config import SETTINGS
from src.utils.cost_tracking import log_api_cost

openai.api_key = SETTINGS.openai_api_key
WEAK_MODEL = "gpt-4o-mini"

def count_tokens(text: str, model: str = WEAK_MODEL) -> int:
    """Count the number of tokens in a text string."""
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to approximate token count if model not found
        return len(text.split()) * 1.3


def get_pr_title(background: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that helps generate concise, "
                "professional pull request titles."
            ),
        },
        {
            "role": "user",
            "content": (
                "Based on the following background, "
                f"generate a pull request title: {background}"
            ),
        },
    ]
    
    # Calculate input tokens
    input_tokens = sum(count_tokens(msg["content"], WEAK_MODEL) for msg in messages)
    
    response = openai.chat.completions.create(
        model=WEAK_MODEL,
        messages=messages,
    )
    
    output_text = response.choices[0].message.content.strip()
    output_tokens = count_tokens(output_text, WEAK_MODEL)
    
    # Log API cost
    log_api_cost(
        model=WEAK_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        agent_type="OpenHands"
    )
    
    return output_text


def get_pr_body(background: str, logs: str) -> str:
    match = re.search(r"Issue Number: (\d+)", background)
    issue_number = match.group(1) if match else None

    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that helps generate detailed, "
                "clear, and professional pull request descriptions."
            ),
        },
        {
            "role": "user",
            "content": (
                "Based on the following background and git logs, "
                f"generate a pull request description.\n\n"
                f"Background:\n{background}\n\n"
                f"Git Logs:\n{logs}"
            ),
        },
    ]

    # Calculate input tokens
    input_tokens = sum(count_tokens(msg["content"], WEAK_MODEL) for msg in messages)

    response = openai.chat.completions.create(
        model=WEAK_MODEL,
        messages=messages,
    )
    
    body = response.choices[0].message.content.strip()
    
    if issue_number is not None and f"fixes #{issue_number}" not in body.lower():
        body = f"{body}\n\nFixes #{issue_number}"

    output_tokens = count_tokens(body, WEAK_MODEL)
    
    # Log API cost
    log_api_cost(
        model=WEAK_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        agent_type="OpenHands"
    )

    return body


def remove_all_urls(text: str) -> str:
    text = text.replace("Repository URL:", "")
    text = text.replace("Issue URL:", "")
    return re.sub(r"https?:\/\/[^\s]+", "", text)


def format_messages(messages: list[dict]) -> str:
    return "\n".join([m["message"] for m in messages])
