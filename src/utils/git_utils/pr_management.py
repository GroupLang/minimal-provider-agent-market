import re
import time
from typing import Optional
import git
import github
from loguru import logger

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

def add_logs_as_pr_comments(pr_url: str, github_token: str, logs: str) -> None:
    g = github.Github(github_token)
    pr_path = pr_url.split("github.com/")[-1]
    owner_repo, pr_number = pr_path.split("/pull/")
    pr_number = int(pr_number)

    repo = g.get_repo(owner_repo)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(logs)

def get_pr_url(chat_text: str) -> Optional[str]:
    pattern = r"https://github\.com/[^/]+/[^/]+/pull/\d+"
    match = re.search(pattern, chat_text)
    return match.group(0) if match else None