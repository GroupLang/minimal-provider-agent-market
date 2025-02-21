import base64
import os
import shlex

import openai
from dotenv import load_dotenv
from loguru import logger

from src.config import SETTINGS

load_dotenv()
openai.api_key = SETTINGS.openai_api_key
WEAK_MODEL = "gpt-4o-mini"


def _get_readme_content(repo_path: str) -> str:
    logger.info(f"Searching for README files in the repository: {repo_path}")
    readme_files = ["README.md", "README.txt", "README.rst", "README"]

    for root, _, files in os.walk(repo_path):
        for file in files:
            if file in readme_files:
                readme_path = os.path.join(root, file)
                logger.info(f"README file found: {readme_path}")
                try:
                    with open(readme_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        logger.debug(
                            f"README content loaded successfully from {readme_path}"
                        )
                        return content
                except Exception as e:
                    logger.error(f"Error reading README file {readme_path}: {e}")
                    return ""
    logger.warning("No README file found in the repository.")
    return ""


def suggest_test_command(repo_path: str) -> str:
    logger.info(f"Starting test command suggestion process for repo: {repo_path}")
    readme_content = _get_readme_content(repo_path)

    if not readme_content:
        logger.warning("No README content available to analyze for test commands.")
        return ""

    logger.info("Requesting OpenAI to generate a test command based on README content.")
    try:
        response = openai.chat.completions.create(
            model=WEAK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that provides Shell commands to run tests "
                        "based on project documentation. You don't format your answer and "
                        "provide raw text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Based on the following README content, "
                        "provide a single shell command necessary to run the project tests. "
                        "Make sure to output a single command. Example: `make tests`."
                        "If the content doesn't specify how to run tests, do not output anything:"
                        "\n\n"
                        f"{readme_content}"
                    ),
                },
            ],
        )
        command = response.choices[0].message.content.strip()
        if command:
            logger.info(f"Test command successfully generated: {command}")
            return command
        else:
            logger.warning("No suitable test command found in the OpenAI response.")
            return ""
    except Exception as e:
        logger.error(f"Error during OpenAI API call: {e}")
        return ""


def get_container_kwargs(
    repo_directory: str,
    model_name: str,
    solver_command: str,
    test_command: str,
    architect_model_name: str | None = None,
) -> str:
    encoded_solver_command = base64.b64encode(solver_command.encode()).decode()

    test_args_and_command = (
        f" --test-command {shlex.quote(test_command)}" if test_command else ""
    )
    entrypoint = [
        "/bin/bash",
        "-c",
        (
            "source /venv/bin/activate && "
            f"python aider_modify_repo.py --editor-model-name {shlex.quote(model_name)} "
            f"--solver-command-base64 {encoded_solver_command} "
            f"--architect-model-name {shlex.quote(architect_model_name or '')} "
            f"{test_args_and_command}"
        ).strip(),
    ]
    logger.info(f"Entrypoint: {entrypoint}")
    env_vars = {key: os.getenv(key) for key in os.environ.keys()}
    volumes = {
        repo_directory: {"bind": "/app", "mode": "rw"},
        "/tmp/aider_cache": {"bind": "/home/ubuntu", "mode": "rw"},
    }
    user = f"{os.getuid()}:{os.getgid()}"
    kwargs = {
        "image": "paulgauthier/aider",
        "entrypoint": entrypoint,
        "environment": env_vars,
        "user": user,
        "volumes": volumes,
    }
    return kwargs
