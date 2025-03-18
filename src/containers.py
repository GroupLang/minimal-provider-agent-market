import re

import openai
from docker import from_env as docker_from_env
from loguru import logger
from requests.exceptions import ReadTimeout

from src.config import SETTINGS

openai.api_key = SETTINGS.openai_api_key
WEAK_MODEL = "gpt-4o-mini"


def _clean_logs(logs: str) -> str:
    anti_escape_logs = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    logs = anti_escape_logs.sub("", logs).split("Tokens:")[0]

    prompt = """
    Below are the raw logs from an AI coding assistant. Please rewrite these logs as a clear, 
    concise message to a user, focusing on the important actions and changes made. Remove any 
    technical artifacts, ANSI escape codes, and redundant information. Format the response 
    in a user-friendly way.

    Raw logs:
    {logs}
    """

    try:
        response = openai.chat.completions.create(
            model=WEAK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that processes technical logs.",
                },
                {"role": "user", "content": prompt.format(logs=logs)},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to process logs with GPT-4: {e}")
        return logs


def launch_container_with_repo_mounted(
    timeout: int = 3600,
    **kwargs,
) -> str:
    docker_client = docker_from_env()
    logger.info("Launching container")
    container = docker_client.containers.run(
        **kwargs,
        tty=True,
        stdin_open=True,
        detach=True,
    )
    logger.info("Container launched")

    try:
        logger.info(f"Waiting for container to finish (timeout: {timeout}s)")
        result = container.wait(timeout=timeout)
        logger.info(f"Container exited with status code: {result['StatusCode']}")

        raw_logs = container.logs(stream=False).decode("utf-8")
        logger.info(f"Raw logs: {raw_logs}")

        if result["StatusCode"] != 0:
            raise Exception(f"Container exited with non-zero status code: {result['StatusCode']}")

        logs = _clean_logs(raw_logs)
        logger.info(f"Clean logs: {logs}")

    except ReadTimeout:
        logger.error(f"Container timed out after {timeout} seconds")
        raise TimeoutError(f"Container execution exceeded {timeout} seconds timeout")

    except Exception as e:
        logger.error(f"Failed to wait for container: {e}")
        raise

    finally:
        logger.info("Removing all containers")
        for container in docker_client.containers.list(all=True):
            container.stop()
            container.remove()
        logger.info("Containers removed")

    return logs, raw_logs
