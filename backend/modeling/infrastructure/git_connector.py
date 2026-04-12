"""Git connector for cloning and monitoring customer repositories."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitDiff:
    """Result of comparing two commits."""
    modified: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


class GitConnector:
    """Manages customer code repositories (clone, pull, diff)."""

    def __init__(self, repos_dir: Path) -> None:
        self.repos_dir = repos_dir
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def clone(self, url: str, repo_id: str) -> Path:
        dest = self.repos_dir / repo_id
        if dest.exists():
            logger.info(f"Repo {repo_id} already exists, pulling instead")
            self.pull(repo_id)
            return dest

        subprocess.run(
            ["git", "clone", "--depth=1", url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Cloned {url} → {dest}")
        return dest

    def pull(self, repo_id: str) -> str:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found at {repo_path}")

        result = subprocess.run(
            ["git", "pull"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Pulled {repo_id}: {result.stdout.strip()}")
        return result.stdout

    def list_files(self, repo_id: str, extension: str = "") -> list[str]:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found")

        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        if extension:
            files = [f for f in files if f.endswith(extension)]
        return files

    def diff(self, repo_id: str, from_commit: str, to_commit: str) -> GitDiff:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found")

        result = subprocess.run(
            ["git", "diff", "--name-status", from_commit, to_commit],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )

        diff = GitDiff()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            status, path = parts[0], parts[1]
            if status == "M":
                diff.modified.append(path)
            elif status == "A":
                diff.added.append(path)
            elif status == "D":
                diff.deleted.append(path)

        return diff

    def get_head_commit(self, repo_id: str) -> str:
        repo_path = self.repos_dir / repo_id
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def read_file(self, repo_id: str, file_path: str) -> str:
        full_path = self.repos_dir / repo_id / file_path
        return full_path.read_text(encoding="utf-8")
