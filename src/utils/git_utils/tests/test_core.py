import os
import shutil
from unittest import TestCase
from unittest.mock import Mock, patch, call

import git
from git.exc import GitCommandError

from ..core import (
    clone_repository,
    add_and_commit,
    push_commits,
    set_git_config,
    create_and_push_branch,
    GitError,
    GitConfigError,
    GitPushError,
    GitBranchError,
)

class TestCore(TestCase):
    def setUp(self):
        self.test_dir = "/tmp/test_repo"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch('git.Repo.clone_from')
    def test_clone_repository(self, mock_clone):
        repo_url = "https://github.com/test/repo.git"
        clone_repository(repo_url, self.test_dir)
        mock_clone.assert_called_once_with(repo_url, self.test_dir)

    @patch('git.Repo.clone_from')
    def test_clone_repository_failure(self, mock_clone):
        mock_clone.side_effect = git.GitCommandError("clone", "Failed to clone")
        with self.assertRaises(GitError) as ctx:
            clone_repository("https://github.com/test/repo.git", self.test_dir)
        self.assertIn("Failed to clone repository", str(ctx.exception))

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.generate_commit_message')
    def test_add_and_commit(self, mock_generate_msg, mock_repo):
        # Setup mock repository
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.is_dirty.return_value = True
        mock_generate_msg.return_value = "Test commit message"

        result = add_and_commit(self.test_dir)

        self.assertTrue(result)
        mock_instance.git.add.assert_called_once_with(A=True)
        mock_instance.index.commit.assert_called_once_with("Test commit message")

    @patch('git.Repo')
    def test_add_and_commit_failure(self, mock_repo):
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.is_dirty.return_value = True
        mock_instance.git.add.side_effect = git.GitCommandError("add", "Failed to add")

        with self.assertRaises(GitError) as ctx:
            add_and_commit(self.test_dir)
        self.assertIn("Failed to add/commit changes", str(ctx.exception))

    @patch('git.Repo')
    def test_push_commits(self, mock_repo):
        # Setup mock repository
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.head.is_detached = False
        mock_instance.active_branch.name = "main"
        mock_instance.remotes.origin.url = "https://github.com/test/repo.git"
        mock_instance.head.commit = "commit1"
        mock_instance.refs = {"origin/main": Mock(commit="commit2")}

        result = push_commits(self.test_dir, "test_token")

        self.assertTrue(result)
        mock_instance.remotes.origin.push.assert_called_once()

    @patch('git.Repo')
    def test_set_git_config(self, mock_repo):
        # Setup mock repository
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_config = Mock()
        mock_instance.config_writer.return_value.__enter__.return_value = mock_config

        set_git_config("test_user", "test@email.com", self.test_dir)

        mock_config.set_value.assert_any_call("user", "name", "test_user")
        mock_config.set_value.assert_any_call("user", "email", "test@email.com")

    @patch('git.Repo')
    def test_set_git_config_failure(self, mock_repo):
        # Test git config failure
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.config_writer.side_effect = Exception("Config failed")

        with self.assertRaises(GitConfigError) as ctx:
            set_git_config("test_user", "test@email.com", self.test_dir)
        self.assertIn("Failed to set git config", str(ctx.exception))

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.sync_fork_with_upstream')
    def test_create_and_push_branch(self, mock_sync, mock_repo):
        # Setup mock repository
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.bare = False
        mock_instance.heads = []
        mock_instance.remotes.origin.refs = []
        mock_instance.remotes.origin.url = "https://github.com/test/repo.git"

        create_and_push_branch(self.test_dir, "feature-branch", "test_token")

        mock_sync.assert_called_once_with(self.test_dir, "test_token")
        mock_instance.create_head.assert_called_once_with("feature-branch")

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.sync_fork_with_upstream')
    def test_create_and_push_branch_bare_repo(self, mock_sync, mock_repo):
        # Test bare repository error
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.bare = True

        with self.assertRaises(GitError) as ctx:
            create_and_push_branch(self.test_dir, "feature-branch", "test_token")
        self.assertIn("repository is bare", str(ctx.exception))

    @patch('git.Repo')
    def test_push_commits_no_changes(self, mock_repo):
        # Setup mock repository with no changes
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.head.is_detached = False
        mock_instance.active_branch.name = "main"
        mock_instance.remotes.origin.url = "https://github.com/test/repo.git"
        mock_instance.head.commit = "commit1"
        mock_instance.refs = {"origin/main": Mock(commit="commit1")}  # Same commit

        result = push_commits(self.test_dir, "test_token")

        self.assertFalse(result)
        mock_instance.remotes.origin.push.assert_not_called()

    @patch('git.Repo')
    def test_push_commits_detached_head(self, mock_repo):
        # Setup mock repository with detached HEAD
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.head.is_detached = True

        with self.assertRaises(GitPushError) as ctx:
            push_commits(self.test_dir, "test_token")
        self.assertIn("HEAD is detached", str(ctx.exception))

    @patch('git.Repo')
    def test_push_commits_command_error(self, mock_repo):
        # Test git command error during push
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.head.is_detached = False
        mock_instance.active_branch.name = "main"
        mock_instance.remotes.origin.url = "https://github.com/test/repo.git"
        mock_instance.head.commit = "commit1"
        mock_instance.refs = {"origin/main": Mock(commit="commit2")}
        mock_instance.remotes.origin.push.side_effect = git.GitCommandError("push", "Failed to push")

        with self.assertRaises(GitPushError) as ctx:
            push_commits(self.test_dir, "test_token")
        self.assertIn("Git command failed while pushing", str(ctx.exception))

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.generate_commit_message')
    def test_add_and_commit_fallback_message(self, mock_generate_msg, mock_repo):
        # Setup mock repository
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.is_dirty.return_value = True
        mock_generate_msg.return_value = None  # Simulate message generation failure

        result = add_and_commit(self.test_dir)

        self.assertTrue(result)
        mock_instance.git.add.assert_called_once_with(A=True)
        mock_instance.index.commit.assert_called_once_with("agent bot commit")

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.sync_fork_with_upstream')
    def test_create_and_push_branch_command_error(self, mock_sync, mock_repo):
        # Test git command error during branch creation
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.bare = False
        mock_instance.create_head.side_effect = GitCommandError("create_head", "Failed to create branch")

        with self.assertRaises(GitBranchError) as ctx:
            create_and_push_branch(self.test_dir, "feature-branch", "test_token")
        self.assertIn("Git command failed while managing branch", str(ctx.exception))

    @patch('git.Repo')
    @patch('src.utils.git_utils.core.sync_fork_with_upstream')
    def test_create_and_push_branch_invalid_url(self, mock_sync, mock_repo):
        # Test invalid remote URL format
        mock_instance = Mock()
        mock_repo.return_value = mock_instance
        mock_instance.bare = False
        mock_instance.heads = []
        mock_instance.remotes.origin.refs = []
        mock_instance.remotes.origin.url = "invalid://url"

        with self.assertRaises(GitError) as ctx:
            create_and_push_branch(self.test_dir, "feature-branch", "test_token")
        self.assertIn("Unrecognized remote URL format", str(ctx.exception))