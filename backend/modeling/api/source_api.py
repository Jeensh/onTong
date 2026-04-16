"""Source file tree API — browse cloned repository file structures."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/modeling/source", tags=["modeling-source"])
logger = logging.getLogger(__name__)

_repos_dir: Path | None = None
_neo4j_client = None

# Directories to skip when building the tree
HIDDEN_DIRS = {".git", ".svn", ".hg", "__pycache__", ".idea", ".vscode", "node_modules"}

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    ".class", ".jar", ".war", ".pyc", ".so", ".dll", ".exe",
    ".png", ".jpg", ".gif", ".zip", ".tar", ".gz",
}


def init(repos_dir: Path, neo4j_client=None) -> None:
    global _repos_dir, _neo4j_client
    _repos_dir = repos_dir
    _neo4j_client = neo4j_client


def _resolve_repo_path(repo_id: str) -> Path:
    """Resolve repo path: check repos_dir first, then sample-repos fallback."""
    # Primary: repos_dir / repo_id
    if _repos_dir is not None:
        candidate = _repos_dir / repo_id
        if candidate.exists() and candidate.is_dir():
            return candidate

    # Fallback: walk up from __file__ to find sample-repos / repo_id
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "sample-repos" / repo_id
        if candidate.exists() and candidate.is_dir():
            return candidate

    raise FileNotFoundError(f"Repository '{repo_id}' not found")


def _build_tree(dir_path: Path, base_path: Path) -> dict[str, Any]:
    """Recursively build a file tree node for a directory."""
    rel = dir_path.relative_to(base_path)
    rel_str = str(rel) if str(rel) != "." else ""

    children: list[dict[str, Any]] = []
    try:
        entries = sorted(dir_path.iterdir(), key=lambda p: p.name.lower())
    except PermissionError:
        entries = []

    for entry in entries:
        if entry.name in HIDDEN_DIRS:
            continue
        if entry.is_dir():
            child_node = _build_tree(entry, base_path)
            children.append(child_node)
        elif entry.is_file():
            if entry.suffix.lower() in BINARY_EXTENSIONS:
                continue
            child_rel = entry.relative_to(base_path)
            children.append({
                "name": entry.name,
                "type": "file",
                "path": str(child_rel),
                "children": [],
            })

    # Sort: directories first, then files, each group alphabetical case-insensitive
    children.sort(key=lambda c: (0 if c["type"] == "directory" else 1, c["name"].lower()))

    return {
        "name": dir_path.name,
        "type": "directory",
        "path": rel_str,
        "children": children,
    }


@router.get("/tree/{repo_id}")
async def get_source_tree(repo_id: str):
    """Return the file tree structure for a cloned repository."""
    try:
        repo_path = _resolve_repo_path(repo_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")

    tree = _build_tree(repo_path, repo_path)
    return tree
