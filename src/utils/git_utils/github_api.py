import re
from typing import Optional
import git
import github
from loguru import logger

def find_github_repo_url(text: str) -> Optional[str]:
    pattern = r"https://github.com/[^\s]+"
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None

def fork_repo(github_url: str, github_token: str) -> str:
    g = github.Github(github_token)
    repo_path = github_url.replace("https://github.com/", "").removesuffix(".git")
    repo = g.get_repo(repo_path)
    user = g.get_user()
    forked_repo = user.create_fork(repo)
    logger.info("Forked repo: {}", forked_repo.clone_url)
    return forked_repo.clone_url

def extract_repo_name_from_url(repo_url: str) -> str:
    """Extract the repository name from a GitHub URL.

    Args:
        repo_url: The GitHub repository URL

    Returns:
        The repository name in the format "owner/repo"
    """
    # Remove trailing slashes and .git suffix
    repo_url = repo_url.rstrip("/")
    repo_url = repo_url.removesuffix(".git")

    # Handle both HTTPS and SSH URLs
    if repo_url.startswith("git@github.com:"):
        repo_name = repo_url.split("git@github.com:")[-1]
    else:
        repo_name = repo_url.split("github.com/")[-1]

    # Validate the repository name format
    if not repo_name or "/" not in repo_name:
        raise ValueError(f"Invalid repository URL format: {repo_url}")

    owner, repo = repo_name.split("/", 1)
    if not owner or not repo:
        raise ValueError(f"Invalid repository name format: {repo_name}")

    logger.info(f"Extracted repository name: {owner}/{repo}")
    return f"{owner}/{repo}"

def sync_fork_with_upstream(repo_path: str, github_token: str) -> None:
    """Sync a forked repository with its upstream (original) repository.

    Args:
        repo_path: Path to the local repository
        github_token: GitHub personal access token
    """
    try:
        repo = git.Repo(repo_path)

        # Get the remote URL and extract owner/repo
        origin_url = repo.remotes.origin.url
        if origin_url.startswith("https://"):
            repo_path_str = origin_url.split("github.com/")[-1].removesuffix(".git")
        elif origin_url.startswith("git@"):
            repo_path_str = origin_url.split(":")[-1].removesuffix(".git")
        else:
            raise ValueError("Unrecognized remote URL format")

        # Connect to GitHub API
        g = github.Github(github_token)
        fork_repo = g.get_repo(repo_path_str)

        # Get the parent (upstream) repository
        parent_repo = fork_repo.parent
        if not parent_repo:
            logger.info("This repository is not a fork")
            return

        # Add upstream remote if it doesn't exist
        upstream_url = parent_repo.clone_url
        try:
            upstream = repo.remote("upstream")
            if upstream.url != upstream_url:
                upstream.set_url(upstream_url)
        except ValueError:
            upstream = repo.create_remote("upstream", upstream_url)

        # Fetch from upstream
        upstream.fetch()
        logger.info("Fetched latest changes from upstream repository")

        # Get default branch (usually main or master)
        default_branch = parent_repo.default_branch

        # Sync fork with upstream
        repo.git.checkout(default_branch)
        repo.git.merge(f"upstream/{default_branch}")
        logger.info(f"Merged upstream/{default_branch} into local {default_branch}")

        # Push to origin
        if origin_url.startswith("https://"):
            new_origin_url = f"https://{github_token}@{origin_url.split('://')[-1]}"
            repo.remotes.origin.set_url(new_origin_url)

        repo.remotes.origin.push(default_branch)
        logger.info(f"Pushed synced {default_branch} to origin")

    except Exception as e:
        logger.error(f"Error syncing fork with upstream: {e}")
        raise