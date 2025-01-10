from unittest import TestCase
from unittest.mock import Mock, patch

import github

from ..github_api import (
    find_github_repo_url,
    fork_repo,
    extract_repo_name_from_url,
    sync_fork_with_upstream,
)

class TestGithubApi(TestCase):
    def test_find_github_repo_url(self):
        # Test with valid URL
        text = "Check out this repo: https://github.com/user/repo and more text"
        self.assertEqual(find_github_repo_url(text), "https://github.com/user/repo")

        # Test with no URL
        text = "This text has no GitHub URL"
        self.assertIsNone(find_github_repo_url(text))

        # Test with multiple URLs
        text = "URLs: https://github.com/user1/repo1 and https://github.com/user2/repo2"
        self.assertEqual(find_github_repo_url(text), "https://github.com/user1/repo1")

    @patch('github.Github')
    def test_fork_repo(self, mock_github):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo = Mock()
        mock_gh.get_repo.return_value = mock_repo
        mock_user = Mock()
        mock_gh.get_user.return_value = mock_user
        mock_forked = Mock()
        mock_user.create_fork.return_value = mock_forked
        mock_forked.clone_url = "https://github.com/forked/repo.git"

        result = fork_repo("https://github.com/original/repo", "test_token")

        self.assertEqual(result, "https://github.com/forked/repo.git")
        mock_gh.get_repo.assert_called_once_with("original/repo")
        mock_user.create_fork.assert_called_once_with(mock_repo)

    def test_extract_repo_name_from_url(self):
        # Test HTTPS URL
        url = "https://github.com/user/repo.git"
        self.assertEqual(extract_repo_name_from_url(url), "user/repo")

        # Test SSH URL
        url = "git@github.com:user/repo.git"
        self.assertEqual(extract_repo_name_from_url(url), "user/repo")

        # Test URL with trailing slash
        url = "https://github.com/user/repo/"
        self.assertEqual(extract_repo_name_from_url(url), "user/repo")

        # Test invalid URLs
        with self.assertRaises(ValueError):
            extract_repo_name_from_url("https://github.com/invalid")
        with self.assertRaises(ValueError):
            extract_repo_name_from_url("not_a_url")

    @patch('git.Repo')
    @patch('github.Github')
    def test_sync_fork_with_upstream(self, mock_github, mock_repo):
        # Setup mocks
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo_instance = Mock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.remotes.origin.url = "https://github.com/fork/repo.git"

        # Mock GitHub repository
        mock_fork_repo = Mock()
        mock_gh.get_repo.return_value = mock_fork_repo
        mock_parent_repo = Mock()
        mock_fork_repo.parent = mock_parent_repo
        mock_parent_repo.clone_url = "https://github.com/upstream/repo.git"
        mock_parent_repo.default_branch = "main"

        # Mock git operations
        mock_upstream = Mock()
        mock_repo_instance.remote.return_value = mock_upstream
        mock_repo_instance.create_remote.return_value = mock_upstream

        sync_fork_with_upstream("/path/to/repo", "test_token")

        # Verify the sync operations
        mock_gh.get_repo.assert_called_once_with("fork/repo")
        mock_upstream.fetch.assert_called_once()
        mock_repo_instance.git.checkout.assert_called_once_with("main")
        mock_repo_instance.git.merge.assert_called_once_with("upstream/main")
        mock_repo_instance.remotes.origin.push.assert_called_once_with("main")

    @patch('git.Repo')
    @patch('github.Github')
    def test_sync_fork_with_upstream_not_fork(self, mock_github, mock_repo):
        # Setup mocks for a repository that is not a fork
        mock_gh = Mock()
        mock_github.return_value = mock_gh
        mock_repo_instance = Mock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.remotes.origin.url = "https://github.com/original/repo.git"

        # Mock GitHub repository without parent
        mock_repo_obj = Mock()
        mock_gh.get_repo.return_value = mock_repo_obj
        mock_repo_obj.parent = None

        sync_fork_with_upstream("/path/to/repo", "test_token")

        # Verify that no sync operations were performed
        mock_repo_instance.git.checkout.assert_not_called()
        mock_repo_instance.git.merge.assert_not_called()
        mock_repo_instance.remotes.origin.push.assert_not_called()