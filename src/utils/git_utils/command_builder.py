from typing import Optional

def build_solver_command(
    background: str, pr_comments: Optional[str], user_messages: Optional[str]
) -> str:
    if pr_comments and user_messages:
        return _build_solver_command_from_pr_and_chat(background, pr_comments, user_messages)

    if pr_comments:
        return _build_solver_command_from_pr(background, pr_comments)

    if user_messages:
        return _build_solver_command_from_chat(background, user_messages)

    return _build_solver_command_from_instance_background(background)

def _build_solver_command_from_instance_background(background: str) -> str:
    return f"""
=== SYSTEM INSTRUCTIONS ===
You are a helpful AI assistant that interacts with a human and implements code changes. Your task is to analyze the issue description and specifically address the conversation with the user. Focus only on implementing changes requested in the conversation with the user. Ensure your changes maintain code quality and follow the project's standards

=== CONTEXT ===
ISSUE DESCRIPTION
{background}

=== REQUIRED ACTIONS ===
1. Review the issue description to understand the context
2. Implement the necessary code changes to solve the issue
3. Ensure your changes maintain code quality and follow the project's standards

=== SYSTEM REQUIREMENTS ===
NEVER COMMIT THE CHANGES PROPOSED. NEVER PUSH THE CHANGES. ALWAYS STAY IN THE SAME REPOSITORY BRANCH.
"""

def _build_solver_command_from_pr_and_chat(
    background: str, pr_comments: str, user_messages: str
) -> str:
    return f"""
=== SYSTEM INSTRUCTIONS ===
You are a helpful AI assistant that interacts with a human and implements code changes. Your task is to analyze the issue description and specifically address the conversation with the user. Focus only on implementing changes requested in the conversation with the user. Ensure your changes maintain code quality and follow the project's standards

=== CONTEXT ===
ISSUE DESCRIPTION
{background}

=== PULL REQUEST COMMENTS ===
{pr_comments}

=== USER MESSAGES ===
{user_messages}

=== REQUIRED ACTIONS ===
1. Review the issue description to understand the context
2. Review the pull request comments and user messages
3. Implement the necessary code changes to solve the issue
4. Ensure your changes maintain code quality and follow the project's standards

=== SYSTEM REQUIREMENTS ===
NEVER COMMIT THE CHANGES PROPOSED. NEVER PUSH THE CHANGES. ALWAYS STAY IN THE SAME REPOSITORY BRANCH.
"""

def _build_solver_command_from_pr(background: str, pr_comments: str) -> str:
    return f"""
=== SYSTEM INSTRUCTIONS ===
You are a helpful AI assistant that interacts with a human and implements code changes. Your task is to analyze the issue description and specifically address the conversation with the user. Focus only on implementing changes requested in the conversation with the user. Ensure your changes maintain code quality and follow the project's standards

=== CONTEXT ===
ISSUE DESCRIPTION
{background}

=== PULL REQUEST COMMENTS ===
{pr_comments}

=== REQUIRED ACTIONS ===
1. Review the issue description to understand the context
2. Review the pull request comments
3. Implement the necessary code changes to solve the issue
4. Ensure your changes maintain code quality and follow the project's standards

=== SYSTEM REQUIREMENTS ===
NEVER COMMIT THE CHANGES PROPOSED. NEVER PUSH THE CHANGES. ALWAYS STAY IN THE SAME REPOSITORY BRANCH.
"""

def _build_solver_command_from_chat(background: str, user_messages: str) -> str:
    return f"""
=== SYSTEM INSTRUCTIONS ===
You are a helpful AI assistant that interacts with a human and implements code changes. Your task is to analyze the issue description and specifically address the conversation with the user. Focus only on implementing changes requested in the conversation with the user. Ensure your changes maintain code quality and follow the project's standards

=== CONTEXT ===
ISSUE DESCRIPTION
{background}

=== USER MESSAGES ===
{user_messages}

=== REQUIRED ACTIONS ===
1. Review the issue description to understand the context
2. Review the user messages
3. Implement the necessary code changes to solve the issue
4. Ensure your changes maintain code quality and follow the project's standards

=== SYSTEM REQUIREMENTS ===
NEVER COMMIT THE CHANGES PROPOSED. NEVER PUSH THE CHANGES. ALWAYS STAY IN THE SAME REPOSITORY BRANCH.
"""