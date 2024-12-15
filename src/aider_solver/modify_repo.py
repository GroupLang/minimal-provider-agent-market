import argparse

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


def verify_tests(coder, test_command) -> bool:
    """Verify that tests have been written and run successfully."""
    if not test_command:
        return False

    # Run the test command and capture the output
    test_output = coder.run(f"/test {test_command}")

    # Check if the output indicates successful test execution
    if "FAIL" in test_output or "ERROR" in test_output:
        return False

    return True


def modify_repo_with_aider(model_name, solver_command, test_command=None) -> None:
    io = InputOutput(yes=True)
    model = Model(model_name)
    coder = Coder.create(main_model=model, io=io)
    coder.run(solver_command)

    if test_command:
        if not verify_tests(coder, test_command):
            raise Exception("Tests did not pass or were not found.")


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
