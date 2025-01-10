import argparse
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from aider.repo import GitRepo
from loguru import logger

from src.utils.git import clone_repository, find_github_repo_url

from .prompt_cache import PromptCache


def modify_repo_with_aider(model_name, solver_command, test_command=None) -> str:
    io_instance = InputOutput(yes=True)
    model = Model("sonnet")
    prompt_cache = PromptCache()

    prompt_cache.cleanup_expired()

    cached_response = prompt_cache.get(solver_command, model_name)
    if cached_response:
        logger.info("Using cached response")
        return cached_response

    output_buffer = io.StringIO()

    temp_dir = tempfile.mkdtemp(prefix="aider_")
    logger.info(f"Created temporary directory: {temp_dir}")

    original_cwd = os.getcwd()

    try:
        with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
            repo_url = find_github_repo_url(solver_command)
            if repo_url:
                logger.info(f"Found GitHub repository URL: {repo_url}")
                clone_repository(repo_url, temp_dir)
                logger.info(f"Cloned repository to {temp_dir}")

            os.chdir(temp_dir)
            logger.info(f"Changed working directory to: {temp_dir}")

            coder = Coder.create(
                main_model=model,
                io=io_instance,
                suggest_shell_commands=True,
                auto_commits=False,
                dirty_commits=False,
                auto_lint=False,
            )

            coder.run(solver_command)

        full_output = output_buffer.getvalue()
        logger.info(f"Full output: {full_output}")

        if full_output:
            prompt_cache.store(solver_command, model_name, full_output)

        return full_output

    except Exception as e:
        logger.exception(f"Error during execution: {str(e)}")
        return None

    finally:
        os.chdir(original_cwd)
        logger.info(f"Changed back to original directory: {original_cwd}")

        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory {temp_dir}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Modify a repository with Aider.")
    parser.add_argument(
        "--model-name", type=str, required=True, help="The name of the model to use."
    )
    parser.add_argument(
        "--solver-command",
        type=str,
        required=True,
        help="The command to run the solver.",
    )
    parser.add_argument(
        "--test-command",
        type=str,
        required=False,
        help="An optional test command to run.",
    )

    args = parser.parse_args()

    modify_repo_with_aider(args.model_name, args.solver_command, args.test_command)


if __name__ == "__main__":
    main()
