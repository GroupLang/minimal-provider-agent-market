import os

from src.config import SETTINGS
from src.enums import ModelName


def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
) -> str:
    escaped_solver_command = solver_command.replace("'", "'\"'\"'")
    entrypoint = [
        "/bin/bash",
        "-c",
        (
            "source /venv/bin/activate && "
            f"ra-aid -m '{escaped_solver_command}' --architect --model openrouter/deepseek/deepseek-r1 --editor-model bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0 --cowboy-mode"  # noqa: E501
        ).strip(),
    ]

    env_vars = {
        "OPENAI_API_BASE": SETTINGS.litellm_docker_internal_api_base,
        "OPENAI_API_KEY": SETTINGS.litellm_api_key,
        "OPENROUTER_API_KEY": SETTINGS.openrouter_api_key,
        "AWS_ACCESS_KEY_ID": SETTINGS.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": SETTINGS.aws_secret_access_key,
        "AWS_REGION_NAME": SETTINGS.aws_region_name,
    }

    volumes = {
        f"{repo_directory}/.": {"bind": "/app", "mode": "rw"},
        "/tmp/aider_cache": {"bind": "/home/ubuntu", "mode": "rw"},
    }
    user = f"{os.getuid()}:{os.getgid()}"
    kwargs = {
        "image": "aider-raaid",
        "entrypoint": entrypoint,
        "environment": env_vars,
        "volumes": volumes,
        "user": user,
        "extra_hosts": {"host.docker.internal": "host-gateway"},
    }
    return kwargs
