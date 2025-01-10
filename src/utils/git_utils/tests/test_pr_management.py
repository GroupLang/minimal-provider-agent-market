from unittest import TestCase
from unittest.mock import Mock, patch

import github
from github import GithubException, UnknownObjectException

from ..pr_management import (
    create_pull_request,
    get_last_pr_comments,
    add_logs_as_pr_comments,
    get_pr_url,
)

class TestPRManagement(TestCase):
    @patch('git.Repo')
    @patch('github.Github')
    def test_create_pull_request(self, mock_github, mock_repo):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo_instance = Mock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.active_branch.name = "feature-branch"

        # Mock GitHub repositories
        mock_target_repo = Mock()
        mock_source_repo = Mock()
        mock_gh.get_repo.side_effect = [mock_target_repo, mock_source_repo]

        # Mock repository owners
        mock_target_repo.owner.login = "target-owner"
        mock_source_repo.owner.login = "source-owner"

        # Mock branch comparison
        mock_comparison = Mock()
        mock_comparison.total_commits = 1
        mock_target_repo.compare.return_value = mock_comparison

        # Mock pull request creation
        mock_pr = Mock()
        mock_pr.html_url = "https://github.com/test/repo/pull/1"
        mock_target_repo.create_pull.return_value = mock_pr

        result = create_pull_request(
            "source/repo",
            "target/repo",
            "/path/to/repo",
            "test_token",
            "Test PR",
            "Test description",
            "main"
        )

        self.assertEqual(result, "https://github.com/test/repo/pull/1")
        mock_target_repo.create_pull.assert_called_once()

    @patch('github.Github')
    def test_get_last_pr_comments(self, mock_github):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_pr = Mock()
        mock_repo.get_pull.return_value = mock_pr

        # Mock comments
        mock_comment = Mock()
        mock_comment.user.login = "reviewer"
        mock_comment.created_at = "2024-01-01"
        mock_comment.body = "Test comment"
        mock_pr.get_issue_comments.return_value = [mock_comment]
        mock_pr.get_review_comments.return_value = []

        # Mock files
        mock_file = Mock()
        mock_file.filename = "test.py"
        mock_file.status = "modified"
        mock_file.additions = 10
        mock_file.deletions = 5
        mock_file.patch = "test patch"
        mock_pr.get_files.return_value = [mock_file]

        result = get_last_pr_comments(
            "https://github.com/test/repo/pull/1",
            "test_token"
        )

        self.assertIsInstance(result, str)
        self.assertIn("DIFF", result)
        self.assertIn("COMMENTS", result)

    @patch('github.Github')
    def test_add_logs_as_pr_comments(self, mock_github):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_pr = Mock()
        mock_repo.get_pull.return_value = mock_pr

        add_logs_as_pr_comments(
            "https://github.com/test/repo/pull/1",
            "test_token",
            "Test logs"
        )

        mock_pr.create_issue_comment.assert_called_once_with("Test logs")

    def test_get_pr_url(self):
        # Test valid PR URL
        text = "Check PR at https://github.com/user/repo/pull/123 for details"
        self.assertEqual(
            get_pr_url(text),
            "https://github.com/user/repo/pull/123"
        )

        # Test no PR URL
        text = "This text has no PR URL"
        self.assertIsNone(get_pr_url(text))

        # Test multiple PR URLs
        text = "PRs: https://github.com/user1/repo1/pull/1 and https://github.com/user2/repo2/pull/2"
        self.assertEqual(
            get_pr_url(text),
            "https://github.com/user1/repo1/pull/1"
        )

    @patch('git.Repo')
    @patch('github.Github')
    def test_create_pull_request_no_changes(self, mock_github, mock_repo):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo_instance = Mock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.active_branch.name = "feature-branch"

        # Mock GitHub repositories
        mock_target_repo = Mock()
        mock_source_repo = Mock()
        mock_gh.get_repo.side_effect = [mock_target_repo, mock_source_repo]

        # Mock comparison with no changes
        mock_comparison = Mock()
        mock_comparison.total_commits = 0
        mock_target_repo.compare.return_value = mock_comparison

        result = create_pull_request(
            "source/repo",
            "target/repo",
            "/path/to/repo",
            "test_token"
        )

        self.assertEqual(result, "No changes needed")
        mock_target_repo.create_pull.assert_not_called()

    @patch('git.Repo')
    @patch('github.Github')
    def test_create_pull_request_repo_not_found(self, mock_github, mock_repo):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo_instance = Mock()
        mock_repo.return_value = mock_repo_instance

        # Mock GitHub repository not found
        mock_gh.get_repo.side_effect = UnknownObjectException(404, "Not Found")

        with self.assertRaises(ValueError):
            create_pull_request(
                "source/repo",
                "target/repo",
                "/path/to/repo",
                "test_token"
            )

    @patch('github.Github')
    def test_get_last_pr_comments_no_comments(self, mock_github):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_pr = Mock()
        mock_repo.get_pull.return_value = mock_pr

        # Mock no comments
        mock_pr.get_issue_comments.return_value = []
        mock_pr.get_review_comments.return_value = []

        result = get_last_pr_comments(
            "https://github.com/test/repo/pull/1",
            "test_token"
        )

        self.assertFalse(result)