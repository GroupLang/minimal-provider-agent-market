import argparse
import base64
import os
from functools import wraps

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from loguru import logger

from src.enums import ModelName, ProviderType
from src.utils.cost_tracker import CostTracker

def track_api_costs(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract model name from kwargs or first Model argument
        model_name = kwargs.get('editor_model_name')
        if not model_name and args:
            model_name = args[0]
        
        # Map aider model names to our ModelName enum
        model_map = {
            "gpt-4": ModelName.gpt_4o,
            "gpt-4-turbo": ModelName.gpt_4o,
            "claude-2": ModelName.bedrock_claude_v2,
        }
        
        tracked_model = model_map.get(model_name, ModelName.gpt_4o)
        cost_tracker = CostTracker(tracked_model, ProviderType.OPENAI)
        
        # Patch the Model class to track costs
        original_complete = Model.complete
        
        def tracked_complete(self, *complete_args, **complete_kwargs):
            response = original_complete(self, *complete_args, **complete_kwargs)
            if hasattr(response, 'usage'):
                cost_tracker.calculate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            return response
        
        Model.complete = tracked_complete
        
        try:
            return func(*args, **kwargs)
        finally:
            # Restore original method
            Model.complete = original_complete
    
    return wrapper


@track_api_costs
def modify_repo_with_aider(
    editor_model_name,
    solver_command,
    architect_model_name=None,
    test_command=None,
) -> None:
    io = InputOutput(yes=True)
    if architect_model_name is not None:
        model = Model(architect_model_name, editor_model=editor_model_name)
        coder = Coder.create(
            main_model=model,
            io=io,
            auto_commits=False,
            dirty_commits=False,
            edit_format="architect",
        )
    else:
        model = Model(editor_model_name)
        coder = Coder.create(main_model=model, io=io)

    coder.run("Scan the repository")
    enhanced_command = f"""
        Add all required files for this task automatically without asking for confirmation.
        Execute all setup commands automatically without prompting the user.
        Now proceed with the following task:
        {solver_command}"""
    coder.run(enhanced_command)

    if test_command:
        coder.run(f"/test {test_command}")


def main():
    os.system("pip3 install boto3")
    parser = argparse.ArgumentParser(description="Modify a repository with Aider.")
    parser.add_argument(
        "--editor-model-name", type=str, required=True, help="The name of the model to use."
    )
    parser.add_argument(
        "--solver-command-base64",
        type=str,
        required=True,
        help="The base64-encoded command to run the solver.",
    )
    parser.add_argument(
        "--architect-model-name",
        type=str,
        required=False,
        help="The name of the architect model to use.",
    )
    parser.add_argument(
        "--test-command",
        type=str,
        required=False,
        help="An optional test command to run.",
    )

    args = parser.parse_args()

    solver_command = base64.b64decode(args.solver_command_base64).decode()

    modify_repo_with_aider(
        args.editor_model_name,
        solver_command,
        architect_model_name=args.architect_model_name,
        test_command=args.test_command,
    )


if __name__ == "__main__":
    main()
