import os
import shlex
from docker import from_env as docker_from_env
from dotenv import load_dotenv
from loguru import logger
import re
import openai
from src.config import SETTINGS
import time

DOCKER_IMAGE = "paulgauthier/aider"
load_dotenv()
ENV_VARS = {key: os.getenv(key) for key in os.environ.keys()}
WEAK_MODEL = "gpt-4o-mini"
openai.api_key = SETTINGS.openai_api_key

def _clean_logs(logs: str) -> str:
    anti_escape_logs = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    logs = anti_escape_logs.sub('', logs).split("Tokens:")[0]

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
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that processes technical logs."},
                {"role": "user", "content": prompt.format(logs=logs)}
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Failed to process logs with GPT-4: {e}")
        # Placeholder for user feedback
        user_feedback = input("Provide feedback to the agent (or press Enter to skip): ")
        if user_feedback:
            logger.info(f"User feedback: {user_feedback}")

        return logs

def launch_container_with_repo_mounted(
    repo_directory: str, model_name: str, instance_background: str, test_command: str, timeout: int = 60
) -> None:
    docker_client = docker_from_env()
    
    escaped_background = instance_background.replace("'", "'\"'\"'")
    escaped_test_command = shlex.quote(test_command) if test_command else ""
    
    test_args_and_command = f' --test-command {escaped_test_command}' if test_command else ""
    
    entrypoint = [
        "/bin/bash",
        "-c",
        (f"source /venv/bin/activate && python modify_repo.py --model-name {shlex.quote(model_name)} "
        f"--instance-background '{escaped_background}'{test_args_and_command}")
    ]
    
    logger.info(f"Launching container with entrypoint: {entrypoint}")
    logger.info(f"Test command: {test_command}")
    logger.info(f"Instance background: {instance_background}")
    try:
        container = docker_client.containers.run(
            DOCKER_IMAGE,
            entrypoint=entrypoint,
            user=f"{os.getuid()}:{os.getgid()}",
            volumes={
                f"{repo_directory}/.": {"bind": "/app", "mode": "rw"},
                "/tmp/aider_cache": {"bind": "/home/ubuntu", "mode": "rw"},
            },
            environment=ENV_VARS,
            detach=True,
            tty=True,
            stdin_open=True,
        )
        logger.info("Container launched. Streaming logs...")

        start_time = time.time()
        for log in container.logs(stream=True, follow=True):
            if time.time() - start_time > timeout:
                logger.warning(f"Container execution timed out after {timeout} seconds")
                container.stop()
                break
            try:    
                print(log.decode('utf-8'), end='', flush=True)
            except UnicodeDecodeError:
                pass

        logs = container.logs().decode("utf-8")
        logs = _clean_logs(logs)

        result = container.wait()

        exit_status = result.get("StatusCode", -1)
        logger.info(f"Container finished with exit code: {exit_status}")

        container.remove()
        logger.info("Container removed")

        return logs

    except Exception as e:
        logger.error(f"Container execution failed: {e}")
        try:
            container.stop()
            container.remove()
        except:
            pass
        raise
