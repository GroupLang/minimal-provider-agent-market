import os
from typing import Any, Dict

from src.enums import ModelName, ProviderType
from src.utils.cost_tracker import CostTracker


def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
    model_provider: str = "openai",
    expert_provider: str = "openai",
) -> Dict[str, Any]:
    escaped_solver_command = solver_command.replace('"', '\\"')
    entrypoint = [
        "/bin/bash",
        "-c",
        (
            f'source /venv/bin/activate && ra-aid -m "{escaped_solver_command}" '
            f"--provider openrouter --model google/gemini-2.0-flash-001 "
            f"--expert-provider openrouter --expert-model openai/o3-mini-high "
            f"--cowboy-mode"
        ).strip(),
    ]

    volumes = {
        f"{repo_directory}/.": {"bind": "/app", "mode": "rw"},
        "/tmp/aider_cache": {"bind": "/home/ubuntu", "mode": "rw"},
    }
    env_vars = {key: os.getenv(key) for key in os.environ.keys()}
    # Add cost tracking configuration
    env_vars.update({
        "TRACK_API_COSTS": "true",
        "COST_TRACKER_MODEL": model_name.value,
        "COST_TRACKER_PROVIDER": model_provider,
        "COST_TRACKER_EXPERT_MODEL": "o3-mini",
        "COST_TRACKER_EXPERT_PROVIDER": expert_provider,
    })
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
