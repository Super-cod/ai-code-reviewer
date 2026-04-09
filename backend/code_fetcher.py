"""
code_fetcher.py
---------------
Fetches all source code files from a public GitHub repository URL.
Returns a list of {path, content, size, extension} dicts.
"""

import base64
import re
import logging
from typing import List, Dict, Tuple, Optional

import httpx

logger = logging.getLogger(__name__)

# File extensions to analyse
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.cpp', '.c', '.h', '.cs', '.rb', '.php', '.swift', '.kt',
    '.scala', '.r', '.sh', '.bash', '.yaml', '.yml', '.toml',
    '.html', '.css', '.sql', '.vue', '.svelte', '.md', '.env.example',
}

# Directories to always skip
SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', 'dist', 'build', '.next',
    'vendor', 'venv', '.venv', 'coverage', 'migrations', '.github',
    'test', 'tests', '__tests__', 'fixtures', 'mocks', '.cache',
}

MAX_FILES = 60
MAX_FILE_BYTES = 80_000      # 80KB per file
MAX_TOTAL_CHARS = 600_000    # ~600KB total across all files


def parse_github_url(url: str) -> Tuple[str, str]:
    """
    Parse a GitHub URL into (owner, repo).
    Accepts:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/main
      - owner/repo  (shorthand)
    """
    url = url.strip().rstrip('/')
    if re.match(r'^[\w.\-]+/[\w.\-]+$', url):
        parts = url.split('/')
        return parts[0], parts[1]
    match = re.search(r'github\.com/([^/]+)/([^/.\s]+)', url)
    if match:
        return match.group(1), match.group(2).rstrip('.git')
    raise ValueError(
        f"Could not parse GitHub URL: '{url}'. "
        "Use format: https://github.com/owner/repo"
    )


async def fetch_repo_files(
    owner: str,
    repo: str,
    github_token: Optional[str] = None,
) -> List[Dict]:
    """
    Fetch all code source files from a GitHub repo via the REST API.

    Returns:
        List of {path, content, size, extension}
    """
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AI-Code-Reviewer/2.0"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    async with httpx.AsyncClient(timeout=30) as client:

        # Resolve default branch
        repo_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        if repo_resp.status_code == 404:
            raise ValueError(f"Repository '{owner}/{repo}' not found or is private.")
        if repo_resp.status_code != 200:
            raise ValueError(f"GitHub API error {repo_resp.status_code}.")
        default_branch = repo_resp.json().get("default_branch", "main")

        # Fetch full recursive file tree
        tree_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
            headers=headers,
        )
        if tree_resp.status_code != 200:
            raise ValueError(f"Could not read file tree from '{owner}/{repo}'.")

        tree = tree_resp.json().get("tree", [])

        # Filter to code files only
        candidates = [
            item for item in tree
            if item["type"] == "blob"
            and any(item["path"].endswith(ext) for ext in CODE_EXTENSIONS)
            and not any(seg in SKIP_DIRS for seg in item["path"].split("/"))
            and item.get("size", 0) < MAX_FILE_BYTES
            and item.get("size", 0) > 0
        ]

        # Prioritise larger, more substantial files (but skip huge generated bundles)
        candidates.sort(key=lambda x: x.get("size", 0), reverse=True)
        candidates = candidates[:MAX_FILES]

        logger.info("Fetching %d code files from %s/%s …", len(candidates), owner, repo)

        files: List[Dict] = []
        total_chars = 0

        for item in candidates:
            if total_chars >= MAX_TOTAL_CHARS:
                logger.info("Total char limit reached, stopping file fetch.")
                break

            content_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}",
                headers=headers,
            )
            if content_resp.status_code != 200:
                continue

            data = content_resp.json()
            if data.get("encoding") == "base64":
                try:
                    raw = base64.b64decode(data["content"].replace("\n", ""))
                    content = raw.decode("utf-8", errors="replace")
                    ext = "." + item["path"].rsplit(".", 1)[-1] if "." in item["path"] else ""
                    files.append({
                        "path": item["path"],
                        "content": content,
                        "size": item.get("size", 0),
                        "extension": ext,
                    })
                    total_chars += len(content)
                except Exception as e:
                    logger.debug("Skipping %s: %s", item["path"], e)

        logger.info("Fetched %d files, %d total chars.", len(files), total_chars)
        return files
