import os
from typing import Any, Dict

from src.enums import ModelName
from src.utils.cost_tracker import MODEL_COSTS


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
        "MODEL_COSTS_GEMINI": str(MODEL_COSTS.get("openrouter/deepseek/deepseek-r1", {"input": 0.001, "output": 0.002})),
        "MODEL_COSTS_EXPERT": str(MODEL_COSTS.get("o3-mini", {"input": 0.0002, "output": 0.0004})),
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
