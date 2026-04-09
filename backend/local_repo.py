import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import config

logger = logging.getLogger(__name__)

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".scala", ".r", ".sh", ".bash", ".yaml", ".yml", ".toml",
    ".html", ".css", ".sql", ".vue", ".svelte", ".md",
}

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", "vendor",
    "venv", ".venv", "coverage", "__pycache__", ".cache",
}


def _safe_repo_dir(owner: str, repo: str) -> Path:
    repo_key = f"{owner}_{repo}".replace("/", "_").replace("..", "_")
    base = Path(config.ANALYSIS_WORKDIR).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base / repo_key


def _run(cmd: List[str], cwd: Optional[Path] = None) -> None:
    subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def clone_or_refresh_repo(owner: str, repo: str, token: Optional[str] = None) -> str:
    repo_dir = _safe_repo_dir(owner, repo)
    auth_prefix = f"{token}@" if token else ""
    repo_url = f"https://{auth_prefix}github.com/{owner}/{repo}.git"

    if not repo_dir.exists():
        _run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)])
        return str(repo_dir)

    # Keep cache fresh when possible. If refresh fails (auth/remote corruption),
    # rebuild the local clone so chat/review endpoints can recover automatically.
    try:
        _run(["git", "remote", "set-url", "origin", repo_url], cwd=repo_dir)
        _run(["git", "fetch", "origin", "--prune"], cwd=repo_dir)
        _run(["git", "reset", "--hard", "origin/HEAD"], cwd=repo_dir)
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "Repo refresh failed for %s/%s (%s). Re-cloning local cache.",
            owner,
            repo,
            exc,
        )
        shutil.rmtree(repo_dir, ignore_errors=True)
        _run(["git", "clone", "--depth", "1", repo_url, str(repo_dir)])

    return str(repo_dir)


def checkout_pr(repo_dir: str, pr_number: int) -> None:
    path = Path(repo_dir)
    branch = f"pr-{pr_number}"
    try:
        _run(["git", "checkout", branch], cwd=path)
        _run(["git", "pull", "--ff-only"], cwd=path)
    except subprocess.CalledProcessError:
        _run(["git", "fetch", "origin", f"pull/{pr_number}/head:{branch}"], cwd=path)
        _run(["git", "checkout", branch], cwd=path)


def collect_repo_files(repo_dir: str) -> List[Dict]:
    root = Path(repo_dir)
    files: List[Dict] = []

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        ext = file_path.suffix.lower()
        if ext not in CODE_EXTENSIONS:
            continue
        try:
            size = file_path.stat().st_size
            if size <= 0 or size > config.MAX_INDEX_FILE_BYTES:
                continue
            rel_path = file_path.relative_to(root).as_posix()
            content = file_path.read_text(encoding="utf-8", errors="replace")
            files.append(
                {
                    "path": rel_path,
                    "content": content,
                    "size": size,
                    "extension": ext,
                }
            )
            if len(files) >= config.MAX_INDEX_FILES:
                break
        except OSError:
            continue

    return files


def cleanup_repo(owner: str, repo: str) -> None:
    repo_dir = _safe_repo_dir(owner, repo)
    if repo_dir.exists():
        shutil.rmtree(repo_dir, ignore_errors=True)
