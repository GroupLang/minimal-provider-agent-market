import os
from datetime import datetime

from dotenv import load_dotenv

from src.config import SETTINGS
from src.enums import ModelName, ProviderType

load_dotenv()


_MODEL_ALIAS_TO_MODEL: dict[ModelName, dict[ProviderType, str]] = {
    ModelName.gpt_4o: {
        ProviderType.OPENAI: "openai/gpt-4o",
    },
    ModelName.bedrock_claude_v2: {
        ProviderType.LITELLM: f"litellm_proxy/{ModelName.bedrock_claude_v2.value}",
    },
}

_DOCKER_IMAGE = "docker.all-hands.dev/all-hands-ai/openhands:0.28"
_RUNTIME_IMAGE = "docker.all-hands.dev/all-hands-ai/runtime:0.28-nikolaik"
_DOCKER_NETWORK_HOST = ["host.docker.internal:host-gateway"]
_PROVIDER_CONFIGS: dict[ProviderType, dict[str, str]] = {
    ProviderType.LITELLM: {
        "LLM_BASE_URL": SETTINGS.litellm_docker_internal_api_base,
        "LLM_API_KEY": SETTINGS.litellm_api_key,
    },
    ProviderType.OPENAI: {
        "OPENAI_API_KEY": SETTINGS.openai_api_key,
    },
}


def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
) -> str:
    solver_command += (
        "\n\n=== SYSTEM REQUIREMENTS ===\n"
        "NEVER COMMIT THE CHANGES PROPOSED. "
        "NEVER PUSH THE CHANGES. "
        "ALWAYS STAY IN THE SAME REPOSITORY BRANCH."
    )
    entrypoint = ["python", "-m", "openhands.core.main", "-t", solver_command]
    env_vars = {
        "SANDBOX_RUNTIME_CONTAINER_IMAGE": _RUNTIME_IMAGE,
        "SANDBOX_USER_ID": str(os.getuid()),
        "GITHUB_TOKEN": SETTINGS.github_pat,
        "GITHUB_USERNAME": SETTINGS.github_username,
        "GITHUB_EMAIL": SETTINGS.github_email,
        "AWS_REGION": SETTINGS.aws_region_name,
        "AWS_ACCESS_KEY_ID": SETTINGS.aws_access_key_id,
        "AWS_SECRET_ACCESS_KEY": SETTINGS.aws_secret_access_key,
        "WORKSPACE_MOUNT_PATH": repo_directory,
        "LLM_MODEL": _MODEL_ALIAS_TO_MODEL[model_name][SETTINGS.provider],
        "LOG_ALL_EVENTS": "true",
        "GIT_ASKPASS": "echo",
        "GIT_TERMINAL_PROMPT": "0",
    }
    for key, value in _PROVIDER_CONFIGS[SETTINGS.provider].items():
        env_vars[key] = value
    volumes = {
        repo_directory: {"bind": "/opt/workspace_base", "mode": "rw"},
        "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
        os.path.expanduser("~/.openhands-state"): {"bind": "/.openhands-state", "mode": "rw"},
    }
    container_name = f"openhands-app-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    kwargs = {
        "image": _DOCKER_IMAGE,
        "entrypoint": entrypoint,
        "environment": env_vars,
        "volumes": volumes,
        "name": container_name,
        "extra_hosts": _DOCKER_NETWORK_HOST,
        "user": f"{os.getuid()}:{os.getgid()}",  # Set user:group permissions
    }
    return kwargs
