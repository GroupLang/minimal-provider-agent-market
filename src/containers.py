import re
from typing import Optional

import openai
from docker import from_env as docker_from_env
from loguru import logger
from requests.exceptions import ReadTimeout

from src.config import SETTINGS

openai.api_key = SETTINGS.openai_api_key


def _clean_logs(logs: str) -> str:
    """Clean and summarize container execution logs using AI.
    
    Args:
        logs: Raw container execution logs
        
    Returns:
        Cleaned and summarized logs as a user-friendly message
    """
    # Remove ANSI escape codes and token counts
    anti_escape_logs = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")
    logs = anti_escape_logs.sub("", logs).split("Tokens:")[0]

    try:
        response = openai.chat.completions.create(
            model=SETTINGS.log_processing_model,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize technical logs into clear, user-friendly messages.",
                },
                {
                    "role": "user", 
                    "content": f"Summarize these logs focusing on important actions and changes:\n{logs}"
                },
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to process logs: {e}")
        return logs


def launch_container_with_repo_mounted(
    timeout: int = 3600,
    **kwargs,
) -> str:
    """Launch a Docker container with a repository mounted and return execution logs.
    
    Args:
        timeout: Maximum execution time in seconds
        **kwargs: Additional arguments passed to docker.containers.run()
        
    Returns:
        Cleaned and summarized container execution logs
        
    Raises:
        TimeoutError: If container execution exceeds timeout
        Exception: If container exits with non-zero status code
    """
    docker_client = docker_from_env()
    container = None
    
    try:
        # Launch container with standard options
        container = docker_client.containers.run(
            **kwargs,
            tty=True,
            stdin_open=True,
            detach=True,
        )
        logger.info(f"Container {container.short_id} launched")

        # Wait for container completion
        result = container.wait(timeout=timeout)
        status_code = result.get('StatusCode', -1)
        logger.info(f"Container exited with status code: {status_code}")

        # Get container logs
        raw_logs = container.logs(stream=False).decode("utf-8")
        
        # Check for execution success
        if status_code != 0:
            error_msg = f"Container exited with non-zero status code: {status_code}"
            logger.error(f"{error_msg}\nLogs: {raw_logs}")
            raise Exception(error_msg)

        # Process and return logs
        clean_logs = _clean_logs(raw_logs)
        logger.debug(f"Clean logs: {clean_logs}")
        return clean_logs

    except ReadTimeout:
        error_msg = f"Container execution exceeded {timeout} seconds timeout"
        logger.error(error_msg)
        raise TimeoutError(error_msg)

    except Exception as e:
        logger.error(f"Container execution failed: {str(e)}")
        raise

    finally:
        try:
            # Clean up containers
            containers = docker_client.containers.list(all=True)
            for c in containers:
                try:
                    c.stop(timeout=10)
                    c.remove(force=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up container {c.short_id}: {e}")
            
            logger.info(f"Cleaned up {len(containers)} containers")
            
        except Exception as e:
            logger.error(f"Error during container cleanup: {e}")
