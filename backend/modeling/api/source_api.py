"""Source file tree API — browse cloned repository file structures."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

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

# Language detection from file extension
LANGUAGE_MAP = {
    ".java": "java", ".py": "python", ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".xml": "xml", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".properties": "properties", ".md": "markdown",
    ".sql": "sql", ".sh": "shell", ".gradle": "groovy",
}


def init(repos_dir: Path, neo4j_client=None) -> None:
    global _repos_dir, _neo4j_client
    _repos_dir = repos_dir
    _neo4j_client = neo4j_client


def _resolve_repo_path(repo_id: str) -> Path:
    """Resolve repo path: check repos_dir first, then sample-repos fallback.

    Includes path traversal protection via resolve() + is_relative_to().
    """
    # Primary: repos_dir / repo_id
    if _repos_dir is not None:
        base = _repos_dir.resolve()
        candidate = (base / repo_id).resolve()
        if candidate.is_relative_to(base) and candidate.is_dir():
            return candidate

    # Fallback: walk up from __file__ to find sample-repos / repo_id
    current = Path(__file__).resolve()
    for parent in current.parents:
        sample_base = (parent / "sample-repos").resolve()
        candidate = (sample_base / repo_id).resolve()
        if candidate.is_relative_to(sample_base) and candidate.is_dir():
            return candidate

    raise FileNotFoundError(f"Repository '{repo_id}' not found")


MAX_TREE_DEPTH = 30


def _build_tree(dir_path: Path, base_path: Path, depth: int = 0) -> dict[str, Any]:
    """Recursively build a file tree node for a directory."""
    rel = dir_path.relative_to(base_path)
    rel_str = rel.as_posix() if str(rel) != "." else ""

    children: list[dict[str, Any]] = []

    if depth >= MAX_TREE_DEPTH:
        return {"name": dir_path.name, "type": "directory", "path": rel_str, "children": []}

    try:
        entries = list(dir_path.iterdir())
    except PermissionError:
        entries = []

    for entry in entries:
        if entry.name in HIDDEN_DIRS or entry.name.startswith("."):
            continue
        if entry.is_symlink():
            continue
        if entry.is_dir():
            child_node = _build_tree(entry, base_path, depth + 1)
            children.append(child_node)
        elif entry.is_file():
            if entry.suffix.lower() in BINARY_EXTENSIONS:
                continue
            child_rel = entry.relative_to(base_path)
            children.append({
                "name": entry.name,
                "type": "file",
                "path": child_rel.as_posix(),
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


def _get_entities_for_file(repo_id: str, file_path: str) -> list[dict[str, Any]]:
    """Query Neo4j for code entities defined in the given file."""
    if _neo4j_client is None:
        return []

    query = """
    MATCH (e:CodeEntity {repo_id: $repo_id, file_path: $file_path})
    OPTIONAL MATCH (e)-[r:MAPPED_TO]->(d:DomainNode)
    RETURN e.qualified_name as qualified_name, e.kind as kind,
           e.line_start as line_start, e.line_end as line_end,
           d.id as domain, r.status as mapping_status, r.granularity as granularity
    ORDER BY e.line_start
    """
    records = _neo4j_client.query(query, {"repo_id": repo_id, "file_path": file_path})

    entities: list[dict[str, Any]] = []
    for rec in records:
        mapping = None
        if rec.get("domain") is not None:
            mapping = {
                "domain_path": rec["domain"],
                "status": rec.get("mapping_status"),
                "granularity": rec.get("granularity"),
            }
        entities.append({
            "fqn": rec["qualified_name"],
            "kind": rec["kind"],
            "start_line": rec["line_start"],
            "end_line": rec["line_end"],
            "mapping": mapping,
        })
    return entities


@router.get("/file/{repo_id}")
async def get_file_content(repo_id: str, path: str = Query(...)):
    """Return file content with entity position data for a source file."""
    try:
        repo_path = _resolve_repo_path(repo_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")

    # Security: prevent path traversal within the repo
    full_path = (repo_path / path).resolve()
    if not str(full_path).startswith(str(repo_path.resolve())):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    # Reject binary files
    suffix = full_path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Binary files are not supported")

    # Read file content
    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

    # Detect language
    language = LANGUAGE_MAP.get(suffix, "text")

    # Get entities from Neo4j
    entities = _get_entities_for_file(repo_id, path)

    return {
        "path": path,
        "language": language,
        "content": content,
        "entities": entities,
    }


@router.get("/entity/{repo_id}/{qualified_name:path}")
async def get_entity_location(repo_id: str, qualified_name: str):
    """Look up the file path and line range for a code entity."""
    if _neo4j_client is None:
        raise HTTPException(status_code=503, detail="Neo4j not available")

    results = _neo4j_client.query(
        """
        MATCH (e:CodeEntity {repo_id: $repo_id, qualified_name: $qn})
        RETURN e.qualified_name as qualified_name,
               e.file_path as file_path,
               e.line_start as line_start,
               e.line_end as line_end
        """,
        {"repo_id": repo_id, "qn": qualified_name},
    )

    if not results:
        raise HTTPException(status_code=404, detail=f"Entity '{qualified_name}' not found")

    row = results[0]
    return {
        "qualified_name": row["qualified_name"],
        "file_path": row["file_path"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
    }
