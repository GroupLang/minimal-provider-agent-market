import os
import shutil
from typing import Optional, NoReturn
import git
from loguru import logger
from src.utils.commit_message import generate_commit_message

class GitError(Exception):
    """Base exception for git operations."""
    pass

class GitConfigError(GitError):
    """Raised when git configuration fails."""
    pass

class GitPushError(GitError):
    """Raised when push operation fails."""
    pass

class GitBranchError(GitError):
    """Raised when branch operations fail."""
    pass

def clone_repository(repo_url: str, target_dir: str) -> None:
    """Clone a git repository to the specified directory.
    
    Args:
        repo_url: URL of the repository to clone
        target_dir: Target directory for the clone
        
    Raises:
        GitError: If cloning fails
    """
    try:
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)

        os.makedirs(target_dir)
        git.Repo.clone_from(repo_url, target_dir)
        logger.info(f"Cloned repository from {repo_url} to {target_dir}")
    except Exception as e:
        raise GitError(f"Failed to clone repository: {e}") from e

def add_and_commit(repo_path: str) -> bool:
    """Add all changes and create a commit.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        bool: True if changes were committed, False if no changes to commit
        
    Raises:
        GitError: If add/commit operations fail
    """
    try:
        repo = git.Repo(repo_path)
        logger.info(f"Repository initialized at {repo_path}")

        if not repo.is_dirty(untracked_files=True):
            logger.info("No unstaged changes detected. Nothing to commit.")
            return False

        logger.info("Repository is dirty. Staging all changes.")
        repo.git.add(A=True)
        logger.info("All changes staged successfully.")

        commit_message = generate_commit_message(repo_path)
        if commit_message is None:
            commit_message = "agent bot commit"  # Fallback if generation fails

        repo.index.commit(commit_message)
        logger.info(f"Changes committed with message: '{commit_message}'")
        return True

    except Exception as e:
        raise GitError(f"Failed to add/commit changes: {e}") from e

def push_commits(repo_path: str, github_token: str) -> bool:
    """Push commits to remote repository.
    
    Args:
        repo_path: Path to the git repository
        github_token: GitHub authentication token
        
    Returns:
        bool: True if changes were pushed, False if no changes to push
        
    Raises:
        GitPushError: If push operation fails
    """
    try:
        repo = git.Repo(repo_path)

        if repo.head.is_detached:
            raise GitPushError("The HEAD is detached. Cannot push commits.")

        current_branch = repo.active_branch.name

        remote_url = repo.remotes.origin.url.rstrip("/")
        if "github.com/" in remote_url:
            repo_part = remote_url.split("github.com/")[-1]
            remote_url = f"https://{github_token}@github.com/{repo_part}"
            repo.remotes.origin.set_url(remote_url)

        logger.info("Fetching remote changes")
        repo.remotes.origin.fetch()

        remote_branch = f"origin/{current_branch}"
        if remote_branch in repo.refs and repo.head.commit != repo.refs[remote_branch].commit:
            logger.info("There are commits ahead of the remote branch.")
        else:
            logger.info("No new commits to push.")
            return False

        repo.remotes.origin.push()
        logger.info("Changes pushed to remote.")
        return True
    except git.GitCommandError as e:
        raise GitPushError(f"Git command failed while pushing: {e}") from e
    except Exception as e:
        raise GitPushError(f"Error pushing changes: {e}") from e

def set_git_config(username: str, email: str, repo_dir: str) -> None:
    """Configure git user name and email for a repository.
    
    Args:
        username: Git user name
        email: Git user email
        repo_dir: Path to the git repository
        
    Raises:
        GitConfigError: If configuration fails
    """
    try:
        repo = git.Repo(repo_dir)
        with repo.config_writer() as git_config:
            git_config.set_value("user", "name", username)
            git_config.set_value("user", "email", email)
        logger.info(
            f"Git repo config set for user: {username}, email: {email} in directory: {repo_dir}"
        )
    except Exception as e:
        raise GitConfigError(f"Failed to set git config: {e}") from e

def create_and_push_branch(repo_path: str, branch_name: str, github_token: str) -> None:
    """Create and push a new branch, ensuring the fork is synced with upstream first.

    Args:
        repo_path: Path to the local repository
        branch_name: Name of the branch to create
        github_token: GitHub personal access token
        
    Raises:
        GitBranchError: If branch creation or push fails
        GitError: If repository operations fail
    """
    try:
        # First sync the fork with upstream
        from .github_api import sync_fork_with_upstream
        sync_fork_with_upstream(repo_path, github_token)

        repo = git.Repo(repo_path)
        if repo.bare:
            raise GitError("The repository is bare. Cannot perform operations.")

        # Fetch and log branch information
        repo.remotes.origin.fetch()
        logger.info(f"Repository initialized and fetched at {repo_path}")
        
        local_branches = [head.name for head in repo.heads]
        remote_branches = [ref.name.split("/")[-1] for ref in repo.remotes.origin.refs if "heads" in ref.name]
        logger.info(f"Local branches: {local_branches}")
        logger.info(f"Remote branches: {remote_branches}")

        # Handle branch creation/checkout
        try:
            if branch_name in local_branches:
                logger.info(f"Branch '{branch_name}' exists locally")
                branch = repo.heads[branch_name]
            elif branch_name in remote_branches:
                logger.info(f"Branch '{branch_name}' exists remotely")
                branch = repo.create_head(branch_name, f"origin/{branch_name}")
                branch.set_tracking_branch(repo.remotes.origin.refs[branch_name])
            else:
                logger.info(f"Creating new branch '{branch_name}'")
                branch = repo.create_head(branch_name)
            
            branch.checkout()
            logger.info(f"Checked out branch '{branch_name}'")

            # Pull if remote branch exists
            if branch_name in remote_branches:
                logger.info(f"Pulling latest changes from origin/{branch_name}")
                repo.remotes.origin.pull(branch_name)

            # Update remote URL with token
            origin = repo.remote(name="origin")
            remote_url = origin.url
            if "github.com" in remote_url:
                if remote_url.startswith("https://"):
                    repo_path = remote_url.split("github.com/")[-1].removesuffix(".git")
                elif remote_url.startswith("git@"):
                    repo_path = remote_url.split(":")[-1].removesuffix(".git")
                else:
                    raise GitError("Unrecognized remote URL format")
                
                new_url = f"https://{github_token}@github.com/{repo_path}"
                if not new_url.endswith(".git"):
                    new_url += ".git"
                origin.set_url(new_url)

            # Push branch if it doesn't exist remotely
            if branch_name not in remote_branches:
                logger.info(f"Pushing branch '{branch_name}' to remote")
                origin.push(refspec=f"{branch_name}:{branch_name}", set_upstream=True)
                logger.info(f"Branch '{branch_name}' pushed and tracking set")
            else:
                logger.info(f"Branch '{branch_name}' already exists on remote")

        except git.GitCommandError as e:
            raise GitBranchError(f"Git command failed while managing branch: {e}") from e

    except Exception as e:
        if isinstance(e, (GitError, GitBranchError)):
            raise
        raise GitError(f"Failed to create/push branch: {e}") from e