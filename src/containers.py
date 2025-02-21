import re

import openai
from docker import from_env as docker_from_env
from loguru import logger
from requests.exceptions import ReadTimeout

from src.config import SETTINGS

openai.api_key = SETTINGS.openai_api_key
WEAK_MODEL = SETTINGS.architect_model_name


def _clean_logs(logs: str, max_retries: int = 3) -> str:
    """
    Clean and summarize container execution logs.
    
    Args:
        logs: Raw logs from container execution
        max_retries: Maximum number of retries for OpenAI API calls
        
    Returns:
        str: Cleaned and summarized logs
    """
    # Remove ANSI escape sequences and token information
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    logs = ansi_escape.sub('', logs)
    
    # Remove token counts and other technical artifacts
    logs = re.sub(r'Tokens:.*?\n', '\n', logs, flags=re.MULTILINE)
    logs = re.sub(r'\s+', ' ', logs).strip()
    
    if not logs:
        return "No logs available"

    prompt = """
    Summarize the following AI coding assistant logs into a clear, concise message.
    Focus on important actions and changes made. Remove technical artifacts and redundant information.
    Format the response in a user-friendly way, using bullet points for multiple changes.

    Raw logs:
    {logs}
    """

    for attempt in range(max_retries):
        try:
            response = openai.chat.completions.create(
                model=WEAK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a technical log processor that creates clear, concise summaries.",
                    },
                    {"role": "user", "content": prompt.format(logs=logs)},
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=500,   # Limit response length
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}/{max_retries} failed to process logs: {e}")
            if attempt == max_retries - 1:
                logger.error("All attempts to process logs failed, returning cleaned raw logs")
                # If all retries fail, return the cleaned logs without summarization
                return logs[:2000] + "..." if len(logs) > 2000 else logs


def _cleanup_containers(docker_client) -> None:
    """Stop and remove all containers."""
    try:
        logger.info("Removing all containers")
        for container in docker_client.containers.list(all=True):
            try:
                container.stop(timeout=10)  # Give containers 10 seconds to stop gracefully
                container.remove(force=True)  # Force remove if necessary
            except Exception as e:
                logger.warning(f"Error cleaning up container {container.id}: {e}")
        logger.info("Containers removed")
    except Exception as e:
        logger.error(f"Error during container cleanup: {e}")


def launch_container_with_repo_mounted(
    timeout: int = 3600,
    **kwargs,
) -> str:
    """
    Launch a container with a repository mounted and execute the specified command.
    
    Args:
        timeout: Maximum time in seconds to wait for container execution
        **kwargs: Additional arguments to pass to docker.containers.run
        
    Returns:
        str: Cleaned logs from container execution
        
    Raises:
        TimeoutError: If container execution exceeds timeout
        Exception: If container exits with non-zero status code or other errors occur
    """
    docker_client = docker_from_env()
    container = None
    
    try:
        logger.info("Launching container with kwargs: %s", kwargs)
        container = docker_client.containers.run(
            **kwargs,
            tty=True,
            stdin_open=True,
            detach=True,
        )
        logger.info(f"Container {container.id} launched")

        logger.info(f"Waiting for container to finish (timeout: {timeout}s)")
        result = container.wait(timeout=timeout)
        status_code = result.get("StatusCode")
        logger.info(f"Container exited with status code: {status_code}")

        raw_logs = container.logs(stream=False).decode("utf-8")
        logger.debug(f"Raw logs: {raw_logs}")

        if status_code != 0:
            error_msg = result.get("Error", {}).get("Message", "Unknown error")
            raise Exception(
                f"Container exited with non-zero status code {status_code}: {error_msg}"
            )

        logs = _clean_logs(raw_logs)
        logger.info(f"Clean logs: {logs}")
        return logs

    except ReadTimeout:
        error_msg = f"Container execution exceeded {timeout} seconds timeout"
        logger.error(error_msg)
        if container:
            logger.error(f"Last logs before timeout: {container.logs(tail=100).decode('utf-8')}")
        raise TimeoutError(error_msg)

    except Exception as e:
        logger.error(f"Failed to run container: {str(e)}")
        if container:
            logger.error(f"Container logs: {container.logs().decode('utf-8')}")
        raise

    finally:
        _cleanup_containers(docker_client)
