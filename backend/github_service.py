"""
github_service.py
-----------------
Wraps the PyGithub library to interact with the GitHub API.
Provides methods to fetch repositories, pull requests, diffs, and post comments.
"""

import logging
from typing import List, Dict, Any, Optional
from github import Github, Auth, GithubException

from config import config

logger = logging.getLogger(__name__)


class GitHubService:
    """Encapsulates all GitHub API interactions."""

    def __init__(self, token: str = None):
        self.token = token or config.GITHUB_TOKEN
        self.gh: Optional[Github] = None
        if self.token:
            try:
                self.gh = Github(auth=Auth.Token(self.token))
                logger.info("✅ GitHub service authenticated.")
            except Exception as e:
                logger.error("GitHub authentication failed: %s", e)
        else:
            logger.warning("⚠️  No GitHub token provided. Service disabled.")

    # -----------------------------------------------------------------------
    # Repositories
    # -----------------------------------------------------------------------

    def get_user_repos(self) -> List[Dict[str, Any]]:
        """
        Fetch all repositories belonging to the authenticated user.

        Returns:
            List of repo dicts with id, name, owner, description, url, stars.
        """
        if not self.gh:
            return []
        try:
            user = self.gh.get_user()
            repos = []
            for repo in user.get_repos(sort="updated"):
                repos.append({
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "owner": repo.owner.login,
                    "description": repo.description or "",
                    "url": repo.html_url,
                    "stars": repo.stargazers_count,
                    "language": repo.language or "Unknown",
                    "private": repo.private,
                })
            return repos
        except GithubException as e:
            logger.error("Failed to fetch repos: %s", e)
            raise

    # -----------------------------------------------------------------------
    # Pull Requests
    # -----------------------------------------------------------------------

    def get_pull_requests(self, owner: str, repo_name: str) -> List[Dict[str, Any]]:
        """
        Fetch open pull requests for a given repository.

        Returns:
            List of PR dicts with full metadata.
        """
        if not self.gh:
            return []
        try:
            repo = self.gh.get_repo(f"{owner}/{repo_name}")
            prs = []
            for pr in repo.get_pulls(state="open", sort="updated", direction="desc"):
                prs.append({
                    "id": pr.id,
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "author_avatar": pr.user.avatar_url,
                    "state": pr.state,
                    "created_at": pr.created_at.isoformat(),
                    "updated_at": pr.updated_at.isoformat(),
                    "url": pr.html_url,
                    "additions": pr.additions,
                    "deletions": pr.deletions,
                    "changed_files": pr.changed_files,
                    "base_branch": pr.base.ref,
                    "head_branch": pr.head.ref,
                    "body": pr.body or "",
                })
            return prs
        except GithubException as e:
            logger.error("Failed to fetch PRs for %s/%s: %s", owner, repo_name, e)
            raise

    def get_pr_details(self, owner: str, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """Fetch metadata for a single PR."""
        if not self.gh:
            return {}
        try:
            repo = self.gh.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            return {
                "id": pr.id,
                "number": pr.number,
                "title": pr.title,
                "author": pr.user.login,
                "state": pr.state,
                "created_at": pr.created_at.isoformat(),
                "url": pr.html_url,
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
            }
        except GithubException as e:
            logger.error("Failed to fetch PR details: %s", e)
            raise

    def get_pr_diff(self, owner: str, repo_name: str, pr_number: int) -> str:
        """
        Build a unified-diff-like string from all changed files in a PR.

        Returns:
            A multi-file diff string suitable for AI analysis.
        """
        if not self.gh:
            return ""
        try:
            repo = self.gh.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            files = pr.get_files()

            diff_parts = []
            for f in files:
                header = (
                    f"--- a/{f.filename}\n"
                    f"+++ b/{f.filename}\n"
                    f"Status: {f.status} | +{f.additions} additions / -{f.deletions} deletions\n"
                )
                patch = f.patch if f.patch else "(binary or non-text file)"
                diff_parts.append(header + patch)

            return "\n\n".join(diff_parts)
        except GithubException as e:
            logger.error("Failed to get PR diff: %s", e)
            raise

    # -----------------------------------------------------------------------
    # Comments
    # -----------------------------------------------------------------------

    def post_comment(
        self, owner: str, repo_name: str, pr_number: int, body: str
    ) -> bool:
        """
        Post a comment on a GitHub PR.

        Returns:
            True on success, False on failure.
        """
        if not self.gh:
            return False
        try:
            repo = self.gh.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            comment_body = (
                "## 🤖 AI Code Review\n\n"
                f"{body}\n\n"
                "---\n*Review generated by [AI Code Reviewer](https://github.com)*"
            )
            pr.create_issue_comment(comment_body)
            logger.info("Comment posted to PR #%d in %s/%s", pr_number, owner, repo_name)
            return True
        except GithubException as e:
            logger.error("Failed to post comment: %s", e)
            return False
