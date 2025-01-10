from unittest import TestCase

from ..command_builder import (
    build_solver_command,
    _build_solver_command_from_instance_background,
    _build_solver_command_from_pr_and_chat,
    _build_solver_command_from_pr,
    _build_solver_command_from_chat,
)

class TestCommandBuilder(TestCase):
    def setUp(self):
        self.background = "Test background"
        self.pr_comments = "Test PR comments"
        self.user_messages = "Test user messages"

    def test_build_solver_command_all_inputs(self):
        result = build_solver_command(
            self.background,
            self.pr_comments,
            self.user_messages
        )
        
        # Check that all inputs are included in the result
        self.assertIn(self.background, result)
        self.assertIn(self.pr_comments, result)
        self.assertIn(self.user_messages, result)
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)

    def test_build_solver_command_pr_only(self):
        result = build_solver_command(
            self.background,
            self.pr_comments,
            None
        )
        
        # Check that PR comments are included but user messages are not
        self.assertIn(self.background, result)
        self.assertIn(self.pr_comments, result)
        self.assertNotIn(self.user_messages, result)
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)

    def test_build_solver_command_chat_only(self):
        result = build_solver_command(
            self.background,
            None,
            self.user_messages
        )
        
        # Check that user messages are included but PR comments are not
        self.assertIn(self.background, result)
        self.assertNotIn(self.pr_comments, result)
        self.assertIn(self.user_messages, result)
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)

    def test_build_solver_command_background_only(self):
        result = build_solver_command(
            self.background,
            None,
            None
        )
        
        # Check that only background is included
        self.assertIn(self.background, result)
        self.assertNotIn(self.pr_comments, result)
        self.assertNotIn(self.user_messages, result)
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)

    def test_build_solver_command_from_instance_background(self):
        result = _build_solver_command_from_instance_background(self.background)
        
        # Check structure and content
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)
        self.assertIn("=== CONTEXT ===", result)
        self.assertIn(self.background, result)
        self.assertIn("=== REQUIRED ACTIONS ===", result)

    def test_build_solver_command_from_pr_and_chat(self):
        result = _build_solver_command_from_pr_and_chat(
            self.background,
            self.pr_comments,
            self.user_messages
        )
        
        # Check structure and content
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)
        self.assertIn("=== CONTEXT ===", result)
        self.assertIn("=== PULL REQUEST COMMENTS ===", result)
        self.assertIn("=== USER MESSAGES ===", result)
        self.assertIn(self.background, result)
        self.assertIn(self.pr_comments, result)
        self.assertIn(self.user_messages, result)

    def test_build_solver_command_from_pr(self):
        result = _build_solver_command_from_pr(
            self.background,
            self.pr_comments
        )
        
        # Check structure and content
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)
        self.assertIn("=== CONTEXT ===", result)
        self.assertIn("=== PULL REQUEST COMMENTS ===", result)
        self.assertIn(self.background, result)
        self.assertIn(self.pr_comments, result)
        self.assertNotIn("=== USER MESSAGES ===", result)

    def test_build_solver_command_from_chat(self):
        result = _build_solver_command_from_chat(
            self.background,
            self.user_messages
        )
        
        # Check structure and content
        self.assertIn("=== SYSTEM INSTRUCTIONS ===", result)
        self.assertIn("=== CONTEXT ===", result)
        self.assertIn("=== USER MESSAGES ===", result)
        self.assertIn(self.background, result)
        self.assertIn(self.user_messages, result)
        self.assertNotIn("=== PULL REQUEST COMMENTS ===", result)

    def test_system_requirements_present(self):
        # Test that system requirements are present in all command types
        commands = [
            build_solver_command(self.background, None, None),
            build_solver_command(self.background, self.pr_comments, None),
            build_solver_command(self.background, None, self.user_messages),
            build_solver_command(self.background, self.pr_comments, self.user_messages),
        ]
        
        for command in commands:
            self.assertIn("=== SYSTEM REQUIREMENTS ===", command)
            self.assertIn("NEVER COMMIT THE CHANGES PROPOSED", command)
            self.assertIn("NEVER PUSH THE CHANGES", command)
            self.assertIn("ALWAYS STAY IN THE SAME REPOSITORY BRANCH", command)