import os

from src.config import SETTINGS
from src.enums import ModelName


def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
    expert_provider: str = "openrouter",
    expert_model: str = "openrouter/deepseek/deepseek-r1",
) -> str:
    escaped_solver_command = solver_command.replace("'", "'\"'\"'")
    entrypoint = [
        "/bin/bash",
        "-c",
        (
            "source /venv/bin/activate && "
            f"ra-aid -m '{escaped_solver_command}' --provider openai-compatible --model {model_name.value} --expert-provider {expert_provider} --expert-model {expert_model} --cowboy-mode"  # noqa: E501
        ).strip(),
    ]

    env_vars = {
        "OPENAI_API_BASE": SETTINGS.litellm_docker_internal_api_base,
        "OPENAI_API_KEY": SETTINGS.litellm_api_key,
        "EXPERT_OPENROUTER_API_KEY": SETTINGS.openrouter_api_key,
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
