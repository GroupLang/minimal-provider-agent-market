import os
import shlex
from datetime import datetime

from dotenv import load_dotenv

from src.config import SETTINGS
from src.enums import ModelName, ProviderType

load_dotenv()


_MODEL_ALIAS_TO_MODEL: dict[ModelName, dict[ProviderType, str]] = {
    ModelName.claude_sonnet_4_vertex: {
        ProviderType.VERTEX_AI: "claude-sonnet-4@20250514",
    },
    ModelName.claude_opus_4_vertex: {
        ProviderType.VERTEX_AI: "claude-opus-4@20250514",
    },
    ModelName.claude_3_5_sonnet_vertex: {
        ProviderType.VERTEX_AI: "claude-3-5-sonnet-v2@20241022",
    },
    ModelName.claude_3_5_haiku_vertex: {
        ProviderType.VERTEX_AI: "claude-3-5-haiku@20241022",
    },
}

# Claude Code Docker image (this would need to be built or obtained from appropriate source)
_DOCKER_IMAGE = "claude-code:latest"
_DOCKER_NETWORK_HOST = ["host.docker.internal:host-gateway"]


def get_container_kwargs(
    repo_directory: str,
    solver_command: str,
    model_name: ModelName,
) -> str:
    # Claude Code command based on documentation
    # Using the one-time task mode with quotes
    # Properly escape the solver_command for shell execution
    import shlex

    claude_code_cmd = [
        "claude",
        "-p",
        shlex.quote(solver_command),  # Properly escape the command
        "--dangerously-skip-permissions",
        "--output-format",
        "text",
    ]

    # Fix permissions and run Claude Code
    entrypoint = [
        "sh",
        "-c",
        f"chown -R claude:claude /workspace && chmod -R 755 /workspace && {' '.join(claude_code_cmd)}",
    ]

    env_vars = {
        # Vertex AI configuration
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLOUD_ML_REGION": SETTINGS.vertex_ai_region,
        "ANTHROPIC_VERTEX_PROJECT_ID": "grouplang-450317",
        "GOOGLE_APPLICATION_CREDENTIALS": "/home/claude/vertex-key.json",
        # GitHub configuration
        "GITHUB_TOKEN": SETTINGS.github_pat,
        "GITHUB_USERNAME": SETTINGS.github_username,
        "GITHUB_EMAIL": SETTINGS.github_email,
        # Git configuration
        "GIT_ASKPASS": "echo",
        "GIT_TERMINAL_PROMPT": "0",
        # Optional: Disable prompt caching if needed
        # "DISABLE_PROMPT_CACHING": "1",
    }

    volumes = {
        repo_directory: {"bind": "/workspace", "mode": "rw"},
        # Mount Google Cloud credentials if available
        os.path.abspath("vertex-key.json"): {
            "bind": "/home/claude/vertex-key.json",
            "mode": "ro",
        },
        # Mount Docker socket for any containerized operations
        "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
    }

    container_name = f"claude-code-app-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    kwargs = {
        "image": _DOCKER_IMAGE,
        "entrypoint": entrypoint,
        "environment": env_vars,
        "volumes": volumes,
        "name": container_name,
        "extra_hosts": _DOCKER_NETWORK_HOST,
        "working_dir": "/workspace",
    }

    return kwargs
