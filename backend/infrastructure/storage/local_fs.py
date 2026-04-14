"""Local filesystem storage adapter for wiki files."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
import yaml

from backend.core.schemas import DocumentMetadata, WikiFile, WikiTreeNode
from .base import FileMetadataEntry, StorageProvider

logger = logging.getLogger(__name__)

# Regex patterns for extracting wiki metadata
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([\w\-]+)", re.MULTILINE)
TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

ALLOWED_EXTENSIONS = {".md", ".xlsx", ".pptx", ".pdf", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


_VALID_STATUSES = {"draft", "approved", "deprecated"}


def _normalize_status(raw_status: str) -> str:
    """Normalize status to one of draft|approved|deprecated. Maps review/empty to draft."""
    s = (raw_status or "").strip().lower()
    if s in _VALID_STATUSES:
        return s
    return "draft"


def _parse_frontmatter(raw: str) -> tuple[DocumentMetadata, str]:
    """Parse YAML frontmatter from raw content.

    Returns (metadata, body_without_frontmatter).
    Falls back to empty metadata + original content on parse errors.
    """
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return DocumentMetadata(), raw

    yaml_str = match.group(1)
    body = raw[match.end():]

    try:
        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return DocumentMetadata(), raw
    except yaml.YAMLError:
        logger.warning("Invalid YAML frontmatter, treating as plain content")
        return DocumentMetadata(), raw

    # Backward compat: 'author' → 'created_by'
    created_by = data.get("created_by", "") or data.get("author", "")

    meta = DocumentMetadata(
        domain=data.get("domain", ""),
        process=data.get("process", ""),
        error_codes=data.get("error_codes", []) or [],
        tags=data.get("tags", []) or [],
        status=_normalize_status(data.get("status", "")),
        prev_status=data.get("prev_status", ""),
        supersedes=data.get("supersedes", ""),
        superseded_by=data.get("superseded_by", ""),
        related=data.get("related", []) or [],
        created=str(data.get("created", "")),
        updated=str(data.get("updated", "")),
        created_by=str(created_by),
        updated_by=str(data.get("updated_by", "")),
    )
    return meta, body


def _serialize_frontmatter(meta: DocumentMetadata, body: str) -> str:
    """Serialize DocumentMetadata back into YAML frontmatter + body."""
    lines: list[str] = []

    if meta.domain:
        lines.append(f"domain: {meta.domain}")
    if meta.process:
        lines.append(f"process: {meta.process}")
    if meta.status:
        lines.append(f"status: {meta.status}")
    if meta.prev_status:
        lines.append(f"prev_status: {meta.prev_status}")
    if meta.supersedes:
        lines.append(f"supersedes: {meta.supersedes}")
    if meta.superseded_by:
        lines.append(f"superseded_by: {meta.superseded_by}")
    if meta.created_by:
        lines.append(f"created_by: {meta.created_by}")
    if meta.updated_by:
        lines.append(f"updated_by: {meta.updated_by}")
    if meta.created:
        lines.append(f"created: '{meta.created}'")
    if meta.updated:
        lines.append(f"updated: '{meta.updated}'")

    if meta.error_codes:
        lines.append("error_codes:")
        for ec in meta.error_codes:
            lines.append(f"  - {ec}")

    if meta.tags:
        lines.append("tags:")
        for t in meta.tags:
            lines.append(f"  - {t}")

    if meta.related:
        lines.append("related:")
        for r in meta.related:
            lines.append(f"  - {r}")

    if not lines:
        return body

    return f"---\n{chr(10).join(lines)}\n---\n{body}"


def _inject_metadata(
    raw_content: str,
    user_name: str,
    now: str,
) -> str:
    """Parse frontmatter, inject timestamps + author info, re-serialize."""
    meta, body = _parse_frontmatter(raw_content)

    # created / created_by: set only if empty (first save)
    if not meta.created:
        meta.created = now
    if not meta.created_by and user_name:
        meta.created_by = user_name

    # updated / updated_by: always refresh
    meta.updated = now
    if user_name:
        meta.updated_by = user_name

    return _serialize_frontmatter(meta, body)


class LocalFSAdapter(StorageProvider):
    def __init__(self, wiki_dir: Path) -> None:
        self.wiki_dir = wiki_dir
        self.wiki_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        resolved = (self.wiki_dir / path).resolve()
        if not str(resolved).startswith(str(self.wiki_dir.resolve())):
            raise ValueError(f"Path traversal detected: {path}")
        return resolved

    def _extract_title(self, content: str, path: str) -> str:
        match = TITLE_RE.search(content)
        return match.group(1).strip() if match else Path(path).stem

    def _extract_tags(self, content: str) -> list[str]:
        return TAG_RE.findall(content)

    def _extract_links(self, content: str) -> list[str]:
        return WIKILINK_RE.findall(content)

    def _to_wiki_file(self, path: str, raw_content: str) -> WikiFile:
        metadata, body = _parse_frontmatter(raw_content)

        # Fallback: if no frontmatter tags, extract #hashtag style tags from body
        if not metadata.tags:
            metadata.tags = self._extract_tags(body)

        return WikiFile(
            path=path,
            title=self._extract_title(body, path),
            content=body,
            raw_content=raw_content,
            metadata=metadata,
            links=self._extract_links(body),
        )

    async def read(self, path: str) -> WikiFile | None:
        full = self._resolve(path)
        if not full.exists():
            return None
        if full.suffix != ".md" and full.suffix != ".txt":
            return WikiFile(
                path=path,
                title=full.stem,
                content=f"[Binary file: {full.suffix}]",
                links=[],
            )
        async with aiofiles.open(full, "r", encoding="utf-8") as f:
            content = await f.read()
        return self._to_wiki_file(path, content)

    async def write(self, path: str, content: str, user_name: str = "") -> WikiFile:
        full = self._resolve(path)
        full.parent.mkdir(parents=True, exist_ok=True)

        # Auto-inject timestamps + author for markdown files
        if full.suffix in (".md", ".txt"):
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            content = _inject_metadata(content, user_name, now)

        async with aiofiles.open(full, "w", encoding="utf-8") as f:
            await f.write(content)
        return self._to_wiki_file(path, content)

    async def delete(self, path: str) -> bool:
        full = self._resolve(path)
        if full.exists():
            full.unlink()
            return True
        return False

    async def list_tree(self) -> list[WikiTreeNode]:
        import asyncio
        return await asyncio.to_thread(self._build_tree, self.wiki_dir, "")

    def _build_tree(self, directory: Path, prefix: str) -> list[WikiTreeNode]:
        nodes: list[WikiTreeNode] = []
        for item in sorted(directory.iterdir()):
            if item.name.startswith("."):
                continue
            rel = f"{prefix}/{item.name}" if prefix else item.name
            if item.is_dir():
                children = self._build_tree(item, rel)
                nodes.append(WikiTreeNode(name=item.name, path=rel, is_dir=True, children=children))
            elif item.suffix in ALLOWED_EXTENSIONS:
                nodes.append(WikiTreeNode(name=item.name, path=rel, is_dir=False))
        return nodes

    async def list_subtree(self, prefix: str) -> list[WikiTreeNode]:
        """List immediate children of a directory (one level, no recursion).
        Runs in thread to avoid blocking event loop on large directories."""
        import asyncio
        return await asyncio.to_thread(self._list_subtree_sync, prefix)

    def _list_subtree_sync(self, prefix: str) -> list[WikiTreeNode]:
        target_dir = self.wiki_dir / prefix if prefix else self.wiki_dir
        if not target_dir.is_dir():
            return []
        nodes: list[WikiTreeNode] = []
        for item in sorted(target_dir.iterdir()):
            if item.name.startswith("."):
                continue
            rel = f"{prefix}/{item.name}" if prefix else item.name
            if item.is_dir():
                has_children = any(
                    not c.name.startswith(".")
                    and (c.is_dir() or c.suffix in ALLOWED_EXTENSIONS)
                    for c in item.iterdir()
                )
                nodes.append(WikiTreeNode(
                    name=item.name, path=rel, is_dir=True,
                    children=[], has_children=has_children,
                ))
            elif item.suffix in ALLOWED_EXTENSIONS:
                nodes.append(WikiTreeNode(name=item.name, path=rel, is_dir=False))
        return nodes

    async def list_all_files(self) -> list[WikiFile]:
        import asyncio
        paths = await asyncio.to_thread(self._scan_file_paths)
        files: list[WikiFile] = []
        for rel in paths:
            wiki_file = await self.read(rel)
            if wiki_file:
                files.append(wiki_file)
        return files

    def _scan_file_paths(self) -> list[str]:
        """Scan all file paths (synchronous, for use in thread)."""
        paths: list[str] = []
        for item in self.wiki_dir.rglob("*"):
            if item.is_file() and not item.name.startswith(".") and item.suffix in ALLOWED_EXTENSIONS:
                # Skip hidden parent directories
                rel = item.relative_to(self.wiki_dir)
                if any(part.startswith(".") for part in rel.parts):
                    continue
                paths.append(str(rel))
        return paths

    async def list_file_paths(self) -> list[str]:
        """List all file paths without reading content (lightweight)."""
        import asyncio
        return await asyncio.to_thread(self._scan_file_paths)

    async def list_all_metadata(self) -> list[FileMetadataEntry]:
        """Read only frontmatter from each .md file (skips body content)."""
        import asyncio
        return await asyncio.to_thread(self._scan_all_metadata)

    def _scan_all_metadata(self) -> list[FileMetadataEntry]:
        """Sync: scan files and parse only frontmatter (no full content read)."""
        entries: list[FileMetadataEntry] = []
        for item in self.wiki_dir.rglob("*"):
            if not item.is_file() or item.name.startswith(".") or item.suffix not in ALLOWED_EXTENSIONS:
                continue
            rel = item.relative_to(self.wiki_dir)
            if any(part.startswith(".") for part in rel.parts):
                continue
            rel_str = str(rel)
            if item.suffix != ".md":
                entries.append(FileMetadataEntry(path=rel_str, metadata=DocumentMetadata()))
                continue
            try:
                # Read only first 4KB — enough for any frontmatter
                with open(item, "r", encoding="utf-8") as f:
                    head = f.read(4096)
                meta, _ = _parse_frontmatter(head)
                entries.append(FileMetadataEntry(path=rel_str, metadata=meta))
            except Exception:
                entries.append(FileMetadataEntry(path=rel_str, metadata=DocumentMetadata()))
        return entries

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    async def move(self, old_path: str, new_path: str) -> bool:
        src = self._resolve(old_path)
        dst = self._resolve(new_path)
        if not src.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return True

    async def create_folder(self, path: str) -> bool:
        full = self._resolve(path)
        if full.exists():
            return False
        full.mkdir(parents=True, exist_ok=True)
        return True

    async def delete_folder(self, path: str) -> bool:
        full = self._resolve(path)
        if not full.is_dir():
            return False
        # Only delete if empty (safe)
        try:
            full.rmdir()
            return True
        except OSError:
            return False
