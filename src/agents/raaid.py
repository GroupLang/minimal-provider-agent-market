import os

from src.config import SETTINGS
from src.enums import ModelName


def parse_aider_flags() -> str:
    """Parse aider flags from environment variable.
    
    Reads flags from AIDER_FLAGS environment variable. If not set, defaults to architect-mode.
    Each flag in the comma-separated list is converted to a command line argument.
    
    Returns:
        Formatted string of aider command line flags.
    """
    flags = os.getenv("AIDER_FLAGS", "architect-mode").split(",")
    return " ".join(f"--{flag.strip()}" for flag in flags if flag.strip())

def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
    expert_provider: str = "openrouter",
    expert_model: str = "openrouter/deepseek/deepseek-r1",
) -> str:
    escaped_solver_command = solver_command.replace('"', '\\"')
    aider_flags = parse_aider_flags()
    
    entrypoint = [
        "/bin/bash",
        "-c",
        (
            "source /venv/bin/activate && "
            f'ra-aid -m "{escaped_solver_command}" --provider openai-compatible --model {model_name.value} --expert-provider {expert_provider} --expert-model {expert_model} --cowboy-mode {aider_flags}'  # noqa: E501
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
