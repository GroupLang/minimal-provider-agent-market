import os
import re
import shutil
import time
from typing import Optional

import git
import github
import httpx
import tenacity
from loguru import logger

from .commit_message import generate_commit_message


def find_github_repo_url(text: str) -> Optional[str]:
    pattern = r"https://github.com/[^\s]+"
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    return None


def clone_repository(repo_url: str, target_dir: str, github_token: str = None) -> None:
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)

    os.makedirs(target_dir)

    if github_token and repo_url.startswith("https://"):
        auth_url = f"https://{github_token}@github.com/{repo_url.split('github.com/')[-1]}"
    else:
        auth_url = repo_url

    git.Repo.clone_from(auth_url, target_dir)
    logger.info(f"Cloned repository from {repo_url} to {target_dir}")


def fork_repo(github_url: str, github_token: str) -> str:
    g = github.Github(github_token)
    repo_path = github_url.replace("https://github.com/", "").removesuffix(".git")
    repo = g.get_repo(repo_path)
    user = g.get_user()
    forked_repo = user.create_fork(repo)
    logger.info("Forked repo: {}", forked_repo.clone_url)
    return forked_repo.clone_url


def add_and_commit(repo_path: str) -> None:
    try:
        repo = git.Repo(repo_path)
        logger.info(f"Repository initialized at {repo_path}")

        if repo.is_dirty(untracked_files=True):
            logger.info("Repository is dirty. Staging changes except aider files.")

            # Get tracked files that have been modified
            changed_files = []
            for item in repo.index.diff(None):
                if item.deleted_file:
                    # Handle deleted files explicitly
                    changed_files.append(item.a_path)
                    repo.index.remove([item.a_path])
                else:
                    # Only add existing files
                    if os.path.exists(os.path.join(repo_path, item.a_path)):
                        changed_files.append(item.a_path)
                    else:
                        logger.warning(f"Skipping non-existent tracked file: {item.a_path}")

            # Get untracked files that exist
            untracked_files = []
            for f in repo.untracked_files:
                if os.path.exists(os.path.join(repo_path, f)):
                    untracked_files.append(f)
                else:
                    logger.warning(f"Skipping non-existent untracked file: {f}")

            all_files = changed_files + untracked_files

            files_to_stage = [
                f
                for f in all_files
                if not f.startswith(".aider") and not f.endswith("aider_modify_repo.py")
            ]

            if files_to_stage:
                # Stage files that definitely exist
                files_to_add = []
                for f in files_to_stage:
                    file_path = os.path.join(repo_path, f)
                    if os.path.exists(file_path):
                        files_to_add.append(f)
                    else:
                        logger.warning(f"Skipping non-existent file during staging: {f}")

                if files_to_add:
                    repo.index.add(files_to_add)
                logger.info("Changes staged successfully (excluding aider files).")

                commit_message = generate_commit_message(repo_path)
                if commit_message is None:
                    commit_message = "agent bot commit"

                repo.index.commit(commit_message)
                logger.info(f"Changes committed with message: '{commit_message}'")
            else:
                logger.info("No non-aider files to stage. Skipping commit.")
        else:
            logger.info("No unstaged changes detected. Nothing to commit.")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise



def push_commits(repo_path: str, github_token: str) -> bool:
    try:
        repo = git.Repo(repo_path)

        if repo.head.is_detached:
            logger.error("The HEAD is detached. Cannot push commits.")
            return False

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
    except Exception as e:
        logger.error(f"Error pushing changes: {e}")
        raise


def create_pull_request(
    source_repo_name: str,
    target_repo_name: str,
    source_repo_path: str,
    github_token: str,
    pr_title: str = None,
    pr_body: str = None,
    base_branch: str = "main",
) -> str:
    try:
        repo = git.Repo(source_repo_path)
        g = github.Github(github_token)

        source_repo_name = source_repo_name.removesuffix(".git")
        target_repo_name = target_repo_name.removesuffix(".git")

        logger.info(f"Attempting to create PR from {source_repo_name} to {target_repo_name}")

        try:
            target_repo = g.get_repo(target_repo_name)
        except github.UnknownObjectException:
            logger.error(f"Target repository not found: {target_repo_name}")
            raise ValueError(f"Target repository not found: {target_repo_name}")

        try:
            source_repo = g.get_repo(source_repo_name)
        except github.UnknownObjectException:
            logger.error(f"Source repository not found: {source_repo_name}")
            raise ValueError(f"Source repository not found: {source_repo_name}")

        try:
            target_repo.get_branch(base_branch)
        except github.GithubException:
            logger.warning(f"Base branch '{base_branch}' not found, trying 'master'")
            try:
                target_repo.get_branch("master")
                base_branch = "master"
            except github.GithubException:
                logger.error("Neither 'main' nor 'master' branch found in target repo")
                raise ValueError("Could not find a valid base branch")

        current_branch = repo.active_branch.name
        repo.remotes.origin.fetch()

        try:
            comparison = target_repo.compare(
                base=f"{target_repo.owner.login}:{base_branch}",
                head=f"{source_repo.owner.login}:{current_branch}",
            )

            if comparison.total_commits == 0:
                logger.warning("No changes detected between source and target branches")
                return "No changes needed"
        except github.GithubException as e:
            logger.error(f"Error comparing branches: {e.data}")
            raise

        if not pr_title:
            pr_title = (
                "Automated changes from fork at "
                f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())}"
            )

        if not pr_body:
            pr_body = (
                "This pull request contains automated changes pushed to the forked repository."
            )

        head = f"{source_repo.owner.login}:{current_branch}"
        logger.info(f"Creating PR with head={head} and base={base_branch}")

        try:
            pr = target_repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=head,
                base=base_branch,
            )
            logger.info(f"Pull request created: {pr.html_url}")
            return pr.html_url
        except github.GithubException as e:
            logger.error(f"Error creating pull request: {e.data}")
            logger.error(f"PR creation failed with head={head}, base={base_branch}")
            raise

    except Exception as e:
        logger.error(f"Error creating pull request: {e}")
        raise


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


def set_git_config(username: str, email: str, repo_dir: str):
    try:
        repo = git.Repo(repo_dir)
        with repo.config_writer() as git_config:
            git_config.set_value("user", "name", username)
            git_config.set_value("user", "email", email)
        logger.info(
            f"Git repo config set for user: {username}, email: {email} in directory: {repo_dir}"
        )
    except Exception as e:
        logger.info(f"Error setting git config: {e}")
        raise


def sync_fork_with_upstream(repo_path: str, github_token: str) -> None:
    try:
        logger.info(f"Starting fork sync for repository at {repo_path}")
        repo = git.Repo(repo_path)

        # Get the remote URL and extract owner/repo
        origin_url = repo.remotes.origin.url.rstrip("/")
        logger.debug(f"Original origin URL: {origin_url}")

        if origin_url.startswith("https://"):
            repo_path_str = origin_url.split("github.com/")[-1].removesuffix(".git")
            logger.debug("Using HTTPS URL format")
        elif origin_url.startswith("git@"):
            repo_path_str = origin_url.split(":")[-1].removesuffix(".git")
            logger.debug("Using SSH URL format")
        else:
            logger.error(f"Unrecognized URL format: {origin_url}")
            raise ValueError("Unrecognized remote URL format")

        logger.info(f"Extracted repository path: {repo_path_str}")

        # Connect to GitHub API
        g = github.Github(github_token)
        logger.debug("Connected to GitHub API")
        fork_repo = g.get_repo(repo_path_str)
        logger.info(f"Found fork repository: {fork_repo.full_name}")

        # Get the parent (upstream) repository
        parent_repo = fork_repo.parent
        if not parent_repo:
            logger.info("This repository is not a fork")
            return

        logger.info(f"Found parent repository: {parent_repo.full_name}")
        upstream_url = parent_repo.clone_url.rstrip("/")
        logger.debug(f"Original upstream URL: {upstream_url}")

        # Format upstream URL with token
        if upstream_url.startswith("https://"):
            upstream_url = f"https://{github_token}@github.com/{parent_repo.full_name}.git"
            logger.debug("Formatted upstream URL with token")

        try:
            upstream = repo.remote("upstream")
            if upstream.url != upstream_url:
                logger.info("Updating existing upstream remote URL")
                upstream.set_url(upstream_url)
        except ValueError:
            logger.info("Creating new upstream remote")
            upstream = repo.create_remote("upstream", upstream_url)

        # Fetch from upstream
        logger.info("Fetching from upstream...")
        upstream.fetch()
        logger.info("Successfully fetched latest changes from upstream repository")

        # Get default branch
        default_branch = parent_repo.default_branch
        logger.info(f"Using default branch: {default_branch}")

        # Sync fork with upstream
        logger.info(f"Checking out {default_branch} branch")
        repo.git.checkout(default_branch)

        logger.info(f"Merging upstream/{default_branch}")
        repo.git.merge(f"upstream/{default_branch}")
        logger.info(f"Successfully merged upstream/{default_branch} into local {default_branch}")

        # Format origin URL with token
        if origin_url.startswith("https://"):
            new_origin_url = f"https://{github_token}@github.com/{repo_path_str}.git"
            logger.debug("Updating origin URL with token")
            repo.remotes.origin.set_url(new_origin_url)

        logger.info(f"Pushing to origin/{default_branch}")
        repo.remotes.origin.push(default_branch)
        logger.info(f"Successfully pushed synced {default_branch} to origin")

    except github.GithubException as e:
        logger.error(f"GitHub API error: {e.status} - {e.data.get('message', '')}")
        raise
    except git.GitCommandError as e:
        logger.error(f"Git command error: {e.command} - {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Error syncing fork with upstream: {str(e)}")
        raise


def create_and_push_branch(repo_path: str, branch_name: str, github_token: str) -> None:
    """Create and push a new branch, ensuring the fork is synced with upstream first.

    Args:
        repo_path: Path to the local repository
        branch_name: Name of the branch to create
        github_token: GitHub personal access token
    """
    try:
        # First sync the fork with upstream
        sync_fork_with_upstream(repo_path, github_token)

        repo = git.Repo(repo_path)
        repo.remotes.origin.fetch()
        logger.info(f"Repository initialized and fetched at {repo_path}")

        if repo.bare:
            logger.error("The repository is bare. Cannot perform operations.")
            raise Exception("The repository is bare. Cannot perform operations.")

        local_branches = [head.name for head in repo.heads]
        logger.info(f"Local heads are: {local_branches}")
        remote_branches = [ref.name.split("/")[-1] for ref in repo.remotes.origin.refs if "heads"]
        logger.info(f"Remote branches are: {remote_branches}")

        branch_in_remote = branch_name in remote_branches

        if branch_name in local_branches:
            logger.info(f"Branch '{branch_name}' already exists locally.")
        elif branch_in_remote:
            logger.info(f"Branch '{branch_name}' exists remotely. Checking it out locally.")
            repo.git.checkout(f"origin/{branch_name}", b=branch_name)
        else:
            logger.info(f"Branch '{branch_name}' does not exist. Creating locally.")
            repo.create_head(branch_name)

        repo.heads[branch_name].checkout()
        logger.info(f"Checked out to branch '{branch_name}'.")

        if branch_in_remote:
            logger.info(f"Pulling latest changes from origin/{branch_name}")
            repo.remotes.origin.pull(branch_name)
        else:
            logger.info(f"No remote branch '{branch_name}' to pull from.")

        g = github.Github(github_token)
        logger.info("Authenticated with GitHub using the provided token.")

        origin = repo.remote(name="origin")
        remote_url = origin.url
        logger.info(f"Remote URL: {remote_url}")

        if remote_url.startswith("https://"):
            repo_path = remote_url.split("github.com/")[-1].removesuffix(".git")
        elif remote_url.startswith("git@"):
            repo_path = remote_url.split(":")[-1].removesuffix(".git")
        else:
            logger.error("Unrecognized remote URL format.")
            raise Exception("Invalid remote URL format.")

        github_repo = g.get_repo(repo_path)
        logger.info(f"Connected to GitHub repository: {github_repo.full_name}")

        remote_branches = [ref.ref.replace("refs/heads/", "") for ref in github_repo.get_git_refs()]
        logger.info(f"Remote branches fetched: {remote_branches}")

        if branch_name in remote_branches:
            logger.warning(f"Branch '{branch_name}' already exists on the remote.")
        else:
            origin.push(refspec=f"{branch_name}:{branch_name}", set_upstream=True)
            logger.info(f"Branch '{branch_name}' pushed to remote and set upstream.")

    except Exception as e:
        logger.error(f"Error: {e}")


def get_last_pr_comments(pr_url: str, github_token: str) -> str | bool:
    g = github.Github(github_token)

    pr_path = pr_url.split("github.com/")[-1]
    owner_repo, pr_number = pr_path.split("/pull/")
    pr_number = int(pr_number)

    repo = g.get_repo(owner_repo)
    pr = repo.get_pull(pr_number)

    issue_comments = list(pr.get_issue_comments())
    review_comments = list(pr.get_review_comments())

    last_issue_comment = issue_comments[-1] if issue_comments else None
    last_review_comment = review_comments[-1] if review_comments else None

    last_comment = None
    if last_issue_comment and last_review_comment:
        last_comment = (
            last_issue_comment
            if last_issue_comment.created_at > last_review_comment.created_at
            else last_review_comment
        )
    elif last_issue_comment:
        last_comment = last_issue_comment
    elif last_review_comment:
        last_comment = last_review_comment
    else:
        return False  # No comments found

    if last_comment.user.login == g.get_user().login:
        return False

    diff_content = pr.get_files()
    diff_text = []
    for file in diff_content:
        diff_text.append(f"File: {file.filename}")
        diff_text.append(f"Status: {file.status}")
        diff_text.append(f"Changes: +{file.additions} -{file.deletions}")
        diff_text.append(f"Patch:\n{file.patch if file.patch else 'No patch available'}\n")

    comments = []

    issue_comments = pr.get_issue_comments()
    for comment in issue_comments:
        comments.append(f"Comment by {comment.user.login} at {comment.created_at}:")
        comments.append(comment.body)
        comments.append("---")

    review_comments = pr.get_review_comments()
    for comment in review_comments:
        comments.append(f"Review comment by {comment.user.login} at {comment.created_at}:")
        comments.append(f"File: {comment.path}, Line: {comment.line}")
        comments.append(comment.body)
        comments.append("---")

    result = "\n".join(
        [
            "DIFF",
            "\n".join(diff_text),
            "COMMENTS",
            "\n".join(comments),
        ]
    )

    return result


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
    result = "\n".join(
        [
            "=== SYSTEM INSTRUCTIONS ===",
            "You are a helpful AI assistant that interacts with a human and implements code "
            "changes. Your task is to analyze the issue description and specifically address "
            "the conversation with the user. Focus only on implementing changes requested in "
            "the conversation with the user. Ensure your changes maintain code quality and "
            "follow the project's standards. If the project is a frontend app or FastAPI backend, "
            "you must create a deploy.sh file that handles deployment using AWS credentials "
            "(AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME) stored as environment "
            "variables. For frontend apps, configure AWS S3 website hosting. For FastAPI, "
            "set up AWS ECS deployment. After creating the deploy script, ensure it prints the "
            "resource address (the CloudFront URL for frontend or API endpoint URL for FastAPI) "
            "as its last line. You MUST test the deploy.sh script thoroughly and ensure it works "
            "correctly. If any issues arise during deployment, you MUST debug and fix them until "
            "the deployment process works flawlessly. Do not consider the task complete until "
            "deploy.sh has been successfully executed and the deployment is verified working. "
            "Execute the script to perform the initial deployment if AWS credentials are available.",
            "=== CONTEXT ===",
            "ISSUE DESCRIPTION",
            background,
            "=== REQUIRED ACTIONS ===",
            "1. Review the issue description to understand the context",
            "2. Implement the necessary code changes to solve the issue",
            "3. Ensure your changes maintain code quality and follow the project's standards",
            "4. If the project is a frontend app or FastAPI backend:",
            "   a. Create deploy.sh with AWS S3 configuration for frontend or AWS ECS for FastAPI",
            "   b. Verify AWS credentials (AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME)",
            "   c. Execute deploy.sh for initial deployment if credentials are available",
        ]
    )
    return result


def _build_solver_command_from_pr_and_chat(
    background: str, pr_comments: str, user_messages: str
) -> str:
    result = "\n".join(
        [
            "=== SYSTEM INSTRUCTIONS ===",
            "You are a helpful AI assistant that interacts with a human and implements code "
            "changes based on feedback provided via a pull request or a chat. Your task is to "
            "analyze the issue description and specifically address the LAST comment in the "
            "pull request. Focus only on implementing changes requested in the most recent "
            "comment. If the project is a frontend app or FastAPI backend, you must create a "
            "deploy.sh file that handles deployment using AWS credentials (AWS_SECRET_ACCESS_KEY, "
            "AWS_ACCESS_KEY_ID, AWS_REGION_NAME) stored as environment variables. For frontend "
            "apps, configure AWS S3 website hosting. For FastAPI, set up AWS ECS deployment. "
            "After creating the deploy script, ensure it prints the resource address (the CloudFront URL "
            "for frontend or API endpoint URL for FastAPI) as its last line. You MUST test the "
            "deploy.sh script thoroughly and ensure it works correctly. If any issues arise during "
            "deployment, you MUST debug and fix them until the deployment process works flawlessly. "
            "Do not consider the task complete until deploy.sh has been successfully executed and "
            "the deployment is verified working. Execute the script to perform the initial deployment "
            "if AWS credentials are available.",
            "=== CONTEXT ===",
            "ISSUE DESCRIPTION",
            background,
            "PULL REQUEST DETAILS",
            pr_comments,
            "CONVERSATION WITH THE USER",
            user_messages,
            "=== REQUIRED ACTIONS ===",
            "1. Review the issue description to understand the context",
            "2. Analyze the pull request diff and comments",
            "3. Analyze the conversation with the user",
            "4. Implement the necessary code changes addressing the feedback in the last comment "
            "of the PR and the conversation with the user",
            "5. Ensure your changes maintain code quality and follow the project's standards",
            "6. If the project is a frontend app or FastAPI backend:",
            "   a. Create deploy.sh with AWS S3 configuration for frontend or AWS ECS for FastAPI",
            "   b. Verify AWS credentials (AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME)",
            "   c. Execute deploy.sh for initial deployment if credentials are available",
        ]
    )
    return result


def _build_solver_command_from_pr(background: str, pr_comments: str) -> str:
    result = "\n".join(
        [
            "=== SYSTEM INSTRUCTIONS ===",
            "You are a helpful AI assistant that interacts with a human and implements code "
            "changes. Your task is to analyze the issue description and specifically address "
            "the last comment in the pull request. Focus only on implementing changes requested "
            "in the most recent comment. Ensure your changes maintain code quality and follow "
            "the project's standards. If the project is a frontend app or FastAPI backend, you "
            "must create a deploy.sh file that handles deployment using AWS credentials "
            "(AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME) stored as environment "
            "variables. For frontend apps, configure AWS S3 website hosting. For FastAPI, "
            "set up AWS ECS deployment. After creating the deploy script, ensure it prints the "
            "resource address (the CloudFront URL for frontend or API endpoint URL for FastAPI) "
            "as its last line. You MUST test the deploy.sh script thoroughly and ensure it works "
            "correctly. If any issues arise during deployment, you MUST debug and fix them until "
            "the deployment process works flawlessly. Do not consider the task complete until "
            "deploy.sh has been successfully executed and the deployment is verified working. "
            "Execute the script to perform the initial deployment if AWS credentials are available.",
            "=== CONTEXT ===",
            "ISSUE DESCRIPTION",
            background,
            "PULL REQUEST DETAILS",
            pr_comments,
            "=== REQUIRED ACTIONS ===",
            "1. Review the issue description to understand the context",
            "2. Analyze the pull request diff and comments",
            "3. Implement the necessary code changes addressing the feedback in the last comment "
            "of the PR",
            "4. Ensure your changes maintain code quality and follow the project's standards",
            "5. If the project is a frontend app or FastAPI backend:",
            "   a. Create deploy.sh with AWS S3 configuration for frontend or AWS ECS for FastAPI",
            "   b. Verify AWS credentials (AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME)",
            "   c. Execute deploy.sh for initial deployment if credentials are available",
        ]
    )
    return result


def _build_solver_command_from_chat(background: str, user_messages: str) -> str:
    result = "\n".join(
        [
            "=== SYSTEM INSTRUCTIONS ===",
            "You are a helpful AI assistant that interacts with a human and implements code "
            "changes. Your task is to analyze the issue description and specifically address the "
            "conversation with the user. Focus only on implementing changes requested in the "
            "conversation with the user. Ensure your changes maintain code quality and follow the "
            "project's standards. If the project is a frontend app or FastAPI backend, you must "
            "create a deploy.sh file that handles deployment using AWS credentials "
            "(AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME) stored as environment "
            "variables. For frontend apps, configure AWS S3 website hosting. For FastAPI, "
            "set up AWS ECS deployment. After creating the deploy script, ensure it prints the "
            "resource address (the CloudFront URL for frontend or API endpoint URL for FastAPI) "
            "as its last line. You MUST test the deploy.sh script thoroughly and ensure it works "
            "correctly. If any issues arise during deployment, you MUST debug and fix them until "
            "the deployment process works flawlessly. Do not consider the task complete until "
            "deploy.sh has been successfully executed and the deployment is verified working. "
            "Execute the script to perform the initial deployment if AWS credentials are available.",
            "=== CONTEXT ===",
            "ISSUE DESCRIPTION",
            background,
            "CONVERSATION WITH THE USER",
            user_messages,
            "=== REQUIRED ACTIONS ===",
            "1. Review the issue description to understand the context",
            "2. Analyze the conversation with the user",
            "3. Implement the necessary code changes addressing the feedback in the conversation "
            "with the user",
            "4. Ensure your changes maintain code quality and follow the project's standards",
            "5. If the project is a frontend app or FastAPI backend:",
            "   a. Create deploy.sh with AWS S3 configuration for frontend or AWS ECS for FastAPI",
            "   b. Verify AWS credentials (AWS_SECRET_ACCESS_KEY, AWS_ACCESS_KEY_ID, AWS_REGION_NAME)",
            "   c. Execute deploy.sh for initial deployment if credentials are available",
        ]
    )
    return result


def add_logs_as_pr_comments(pr_url: str, github_token: str, logs: str) -> None:
    g = github.Github(github_token)

    pr_path = pr_url.split("github.com/")[-1]
    owner_repo, pr_number = pr_path.split("/pull/")
    pr_number = int(pr_number)

    repo = g.get_repo(owner_repo)
    pr = repo.get_pull(pr_number)

    comment = f"## Aider:\n{logs}\n"

    pr.create_issue_comment(comment)
    logger.info("Successfully added logs as PR comment")


def get_pr_url(chat_text: str) -> Optional[str]:
    pr_url_pattern = r"https://github\.com/[^/]+/[^/]+/pull/\d+"
    match = re.search(pr_url_pattern, chat_text)
    if match:
        return match.group(0)
    return None


def retry_if_transient_error(exception):
    return isinstance(
        exception, (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    ) and (
        getattr(exception, "response", None) is None
        or exception.response.status_code
        in {
            httpx.codes.TOO_MANY_REQUESTS,  # 429
            httpx.codes.INTERNAL_SERVER_ERROR,  # 500
            httpx.codes.BAD_GATEWAY,  # 502
            httpx.codes.SERVICE_UNAVAILABLE,  # 503
            httpx.codes.GATEWAY_TIMEOUT,  # 504
        }
    )


@tenacity.retry(
    retry=tenacity.retry_if_exception(retry_if_transient_error),
    wait=tenacity.wait_exponential(multiplier=1, min=4, max=10),
    stop=tenacity.stop_after_attempt(3),
    before_sleep=lambda retry_state: logger.warning(
        f"Attempt {retry_state.attempt_number} failed. "
        f"Retrying in {retry_state.next_action.sleep} seconds..."
    ),
)
async def make_github_request(client, method, url, headers):
    request_method = getattr(client, method)
    response = await request_method(url, headers=headers)
    response.raise_for_status()
    return response


async def accept_repo_invitations(pat_token):
    api_url = "https://api.github.com"
    headers = {"Authorization": f"token {pat_token}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            invitations_url = f"{api_url}/user/repository_invitations"
            response = await make_github_request(client, "get", invitations_url, headers)
            invitations = response.json()

            if not invitations:
                logger.info("No pending repository invitations found.")
                return

            for invitation in invitations:
                invitation_id = invitation["id"]
                repo_name = invitation["repository"]["full_name"]

                accept_url = f"{api_url}/user/repository_invitations/{invitation_id}"
                await make_github_request(client, "patch", accept_url, headers)
                logger.info(f"Successfully accepted invitation for repository: {repo_name}")

        except tenacity.RetryError as e:
            logger.error(f"Failed after multiple retries: {str(e.last_attempt.exception())}")
        except httpx.RequestError as e:
            logger.error(f"Unrecoverable error occurred: {str(e)}")
