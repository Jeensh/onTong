"""Wiki CRUD service with async background indexing on write."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from backend.core.schemas import WikiFile, WikiTreeNode
from backend.infrastructure.storage.base import StorageProvider
from backend.infrastructure.events.event_bus import event_bus
from .wiki_indexer import WikiIndexer
from .wiki_search import WikiSearchService

logger = logging.getLogger(__name__)

# ── Indexing status tracking ──────────────────────────────────────────

class IndexStatus:
    """Track indexing status for files (in-memory, non-blocking)."""

    def __init__(self) -> None:
        self._pending: dict[str, float] = {}  # path → queued_at timestamp

    def mark_pending(self, path: str) -> None:
        self._pending[path] = time.time()

    def mark_done(self, path: str) -> None:
        self._pending.pop(path, None)

    def is_pending(self, path: str) -> bool:
        return path in self._pending

    def get_pending(self) -> dict[str, float]:
        return dict(self._pending)

    def pending_count(self) -> int:
        return len(self._pending)


index_status = IndexStatus()

# Regex patterns for error code extraction
ERROR_CODE_PATTERNS = [
    re.compile(r"\b[A-Z]{2,5}[-_]?\d{3,5}\b"),           # DG320, ERR-001, SAP_1234
    re.compile(r"\bERR(?:OR)?[-_]\d{3,5}\b", re.IGNORECASE),  # ERROR-123, err_456
    re.compile(r"\b\d{3,4}(?:E|W|I)\b"),                  # 320E, 1234W (SAP-style)
]


def _extract_error_codes(content: str) -> list[str]:
    """Extract error codes from document content using regex patterns."""
    codes: set[str] = set()
    for pattern in ERROR_CODE_PATTERNS:
        for match in pattern.finditer(content):
            codes.add(match.group())
    return sorted(codes)


class WikiService:
    def __init__(
        self,
        storage: StorageProvider,
        indexer: WikiIndexer,
        search: WikiSearchService,
    ) -> None:
        self.storage = storage
        self.indexer = indexer
        self.search = search
        self._conflict_svc = None  # Lazy init to avoid circular imports

    def set_conflict_service(self, svc) -> None:
        """Set conflict detection service (called from main.py after init)."""
        self._conflict_svc = svc

    async def get_tree(self) -> list[WikiTreeNode]:
        return await self.storage.list_tree()

    async def get_subtree(self, prefix: str) -> list[WikiTreeNode]:
        return await self.storage.list_subtree(prefix)

    async def get_file(self, path: str) -> WikiFile | None:
        return await self.storage.read(path)

    async def save_file(self, path: str, content: str, user_name: str = "") -> WikiFile:
        # Auto-extract error codes if not already present in frontmatter
        content = self._auto_inject_error_codes(content)

        wiki_file = await self.storage.write(path, content, user_name=user_name)

        # Lineage sync: if this file cleared its lineage, clear the counterpart too
        await self._sync_lineage_counterpart(wiki_file)

        # Background indexing — save returns immediately
        index_status.mark_pending(path)
        asyncio.create_task(self._bg_index(wiki_file))
        event_bus.publish("tree_change", {"action": "update", "path": path})
        logger.info(f"Saved: {path} (indexing queued)")
        return wiki_file

    async def _sync_lineage_counterpart(self, wiki_file: WikiFile) -> None:
        """If this file's lineage was cleared, also clear the counterpart document's reference."""
        meta = wiki_file.metadata
        # If this file still has lineage, no cleanup needed
        if meta.supersedes or meta.superseded_by:
            return

        # Check if any other document still references this file in lineage
        try:
            all_entries = await self.storage.list_all_metadata()
        except Exception:
            return

        for entry in all_entries:
            if entry.path == wiki_file.path:
                continue
            refs_this = (
                entry.metadata.supersedes == wiki_file.path
                or entry.metadata.superseded_by == wiki_file.path
            )
            if not refs_this:
                continue

            other = await self.storage.read(entry.path)
            if not other:
                continue
            raw = other.raw_content
            cleaned_lines = []
            for line in raw.split("\n"):
                stripped = line.strip()
                if stripped == f"supersedes: {wiki_file.path}":
                    continue
                if stripped == f"superseded_by: {wiki_file.path}":
                    continue
                cleaned_lines.append(line)
            cleaned = "\n".join(cleaned_lines)
            if cleaned != raw:
                await self.storage.write(entry.path, cleaned, user_name="")
                updated = await self.storage.read(entry.path)
                if updated:
                    index_status.mark_pending(entry.path)
                    asyncio.create_task(self._bg_index(updated))
                logger.info(f"Lineage sync: cleared reference to {wiki_file.path} in {entry.path}")

    async def _bg_index(self, wiki_file: WikiFile) -> None:
        """Background indexing task."""
        try:
            await self.indexer.index_file(wiki_file)
            event_bus.publish("index_status", {"action": "done", "path": wiki_file.path})
            # Incremental conflict check after indexing
            if self._conflict_svc:
                try:
                    await asyncio.to_thread(self._conflict_svc.check_file, wiki_file.path)
                except Exception as e:
                    logger.warning(f"Conflict check failed for {wiki_file.path}: {e}")
        except Exception as e:
            logger.error(f"Background indexing failed for {wiki_file.path}: {e}")
            event_bus.publish("index_status", {"action": "error", "path": wiki_file.path})
        finally:
            index_status.mark_done(wiki_file.path)

    def _auto_inject_error_codes(self, content: str) -> str:
        """If error_codes field is empty/missing in frontmatter, auto-extract from body."""
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return content

        fm_end = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break

        if fm_end < 0:
            return content

        fm_text = "\n".join(lines[1:fm_end])
        body = "\n".join(lines[fm_end + 1:])

        # Check if error_codes already has values
        if re.search(r"error_codes:\s*\[.+\]", fm_text):
            return content

        codes = _extract_error_codes(body)
        if not codes:
            return content

        # Inject error_codes into frontmatter
        codes_str = f"error_codes: [{', '.join(repr(c) for c in codes)}]"
        if "error_codes:" in fm_text:
            # Replace empty error_codes
            lines_new = lines[:fm_end]
            lines_new = [
                re.sub(r"error_codes:\s*\[\s*\]", codes_str, line)
                for line in lines_new
            ]
            return "\n".join(lines_new + lines[fm_end:])
        else:
            # Add error_codes before closing ---
            lines.insert(fm_end, codes_str)
            return "\n".join(lines)

    async def delete_file(self, path: str) -> bool:
        deleted = await self.storage.delete(path)
        if deleted:
            await self.indexer.remove_file(path)
            if self._conflict_svc:
                self._conflict_svc.remove_file(path)
            event_bus.publish("tree_change", {"action": "remove", "path": path})
            logger.info(f"Deleted and removed from index: {path}")
        return deleted

    async def move_file(self, old_path: str, new_path: str) -> bool:
        moved = await self.storage.move(old_path, new_path)
        if moved:
            await self.indexer.remove_file(old_path)
            if self._conflict_svc:
                self._conflict_svc.remove_file(old_path)
            new_file = await self.storage.read(new_path)
            if new_file:
                index_status.mark_pending(new_path)
                asyncio.create_task(self._bg_index(new_file))
            event_bus.publish("tree_change", {"action": "move", "old_path": old_path, "new_path": new_path})
            logger.info(f"Moved file: {old_path} → {new_path}")
        return moved

    async def move_folder(self, old_path: str, new_path: str) -> bool:
        # Collect old file paths before move for conflict cleanup
        old_files: list[str] = []
        if self._conflict_svc:
            try:
                tree = await self.storage.list_subtree(old_path)
                for node in tree:
                    if not node.is_dir:
                        old_files.append(node.path)
            except Exception:
                pass

        moved = await self.storage.move(old_path, new_path)
        if moved:
            # Remove conflicts for all old paths
            if self._conflict_svc:
                for fp in old_files:
                    self._conflict_svc.remove_file(fp)
            asyncio.create_task(self._bg_reindex_all())
            event_bus.publish("tree_change", {"action": "move", "old_path": old_path, "new_path": new_path})
            logger.info(f"Moved folder: {old_path} → {new_path}")
        return moved

    async def _bg_reindex_all(self) -> None:
        """Background full reindex."""
        try:
            await self.reindex_all()
        except Exception as e:
            logger.error(f"Background reindex failed: {e}")

    async def create_folder(self, path: str) -> bool:
        return await self.storage.create_folder(path)

    async def delete_folder(self, path: str) -> bool:
        return await self.storage.delete_folder(path)

    async def get_all_files(self) -> list[WikiFile]:
        return await self.storage.list_all_files()

    async def get_all_metadata(self):
        """Get path + frontmatter for all files (no body content, fast)."""
        return await self.storage.list_all_metadata()

    async def reindex_all(self, force: bool = False) -> int:
        """Reindex wiki files. force=True clears hashes and reindexes everything."""
        files = await self.get_all_files()
        return await self.indexer.reindex_all(files, force=force)
