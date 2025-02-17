import argparse

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
import time


def modify_repo_with_aider(
    editor_model_name, solver_command, architect_model_name=None, test_command=None,
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

    coder.run(solver_command)

    if test_command:
        coder.run(f"/test {test_command}")


def main():
    time.sleep(1000)
    parser = argparse.ArgumentParser(description="Modify a repository with Aider.")
    parser.add_argument(
        "--editor-model-name", type=str, required=True, help="The name of the model to use."
    )
    parser.add_argument(
        "--solver-command",
        type=str,
        required=True,
        help="The command to run the solver.",
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
    print(args)
    time.sleep(1000)
    # modify_repo_with_aider(
    #     args.editor_model_name, args.solver_command, args.architect_model_name args.test_command,
    # )


if __name__ == "__main__":
    main()
