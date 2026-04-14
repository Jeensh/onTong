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
from backend.application.trust.scoring_config import SCORING as _SCORING

_RELATED_CFG = _SCORING.related

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
        self._meta_index = None    # MetadataIndex, set from main.py
        self._chroma = None        # ChromaWrapper, set from main.py
        self._confidence_svc = None  # ConfidenceService, set from main.py

    def set_metadata_index(self, idx) -> None:
        """Set metadata index service (called from main.py after init)."""
        self._meta_index = idx

    def set_conflict_service(self, svc) -> None:
        """Set conflict detection service (called from main.py after init)."""
        self._conflict_svc = svc

    def set_chroma(self, chroma) -> None:
        """Set ChromaDB wrapper (called from main.py after init)."""
        self._chroma = chroma

    def set_confidence_service(self, svc) -> None:
        """Set confidence scoring service (called from main.py after init)."""
        self._confidence_svc = svc

    async def get_tree(self) -> list[WikiTreeNode]:
        return await self.storage.list_tree()

    async def get_subtree(self, prefix: str) -> list[WikiTreeNode]:
        return await self.storage.list_subtree(prefix)

    async def get_file(self, path: str) -> WikiFile | None:
        return await self.storage.read(path)

    async def save_file(self, path: str, content: str, user_name: str = "") -> WikiFile:
        # Auto-downgrade: if existing doc is approved and body changed → set to draft
        content = await self._auto_downgrade_approved(path, content)

        # Auto-extract error codes if not already present in frontmatter
        content = self._auto_inject_error_codes(content)

        # Lineage validation (before write)
        lineage_warnings = self._validate_lineage(path, content)
        errors = [w for w in lineage_warnings if w.level == "error"]
        if errors:
            raise ValueError("; ".join(w.message for w in errors))
        if lineage_warnings:
            for w in lineage_warnings:
                logger.warning(f"Lineage warning for {path}: [{w.code}] {w.message}")

        wiki_file = await self.storage.write(path, content, user_name=user_name)

        # Soft validation: warn if domain/process not in templates
        self._validate_metadata_soft(wiki_file)

        # Lineage sync: if this file cleared its lineage, clear the counterpart too
        await self._sync_lineage_counterpart(wiki_file)

        # Update materialized metadata index (sync, fast)
        if self._meta_index:
            m = wiki_file.metadata
            self._meta_index.on_file_saved(
                path, m.domain, m.process, m.tags,
                updated=m.updated,
                updated_by=m.updated_by,
                created_by=m.created_by,
                related=m.related,
                status=m.status,
                supersedes=m.supersedes,
                superseded_by=m.superseded_by,
            )

        # Deprecation side effects: auto-resolve conflicts involving this file
        if wiki_file.metadata.status == "deprecated" and self._conflict_svc:
            self._auto_resolve_conflicts_for_deprecated(path)

        # Background indexing — save returns immediately
        index_status.mark_pending(path)
        asyncio.create_task(self._bg_index(wiki_file))
        event_bus.publish("tree_change", {"action": "update", "path": path})
        logger.info(f"Saved: {path} (indexing queued)")
        return wiki_file

    async def _auto_downgrade_approved(self, path: str, content: str) -> str:
        """If existing doc is approved and body content changed, downgrade status to draft."""
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter
        try:
            old_file = await self.storage.read(path)
            if not old_file or old_file.metadata.status != "approved":
                return content
            # Compare body only (exclude frontmatter)
            new_meta, new_body = _parse_frontmatter(content)
            if new_body.strip() != old_file.content.strip():
                new_meta.status = "draft"
                logger.info(f"Auto-downgrade: {path} approved → draft (content changed)")
                return _serialize_frontmatter(new_meta, new_body)
        except Exception:
            pass
        return content

    def _validate_lineage(self, path: str, content: str) -> list:
        """Run lineage validation on content before saving. Returns list of LineageWarning."""
        from backend.infrastructure.storage.local_fs import _parse_frontmatter
        from backend.application.wiki.lineage_validator import validate_lineage, LineageWarning
        try:
            meta, _ = _parse_frontmatter(content)
            return validate_lineage(
                path=path,
                supersedes=meta.supersedes,
                superseded_by=meta.superseded_by,
                status=meta.status,
                meta_index=self._meta_index,
            )
        except Exception:
            return []

    async def update_status(self, path: str, new_status: str, user_name: str = "", prev_status: str = "") -> WikiFile:
        """Update only the status field in a document's frontmatter."""
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter
        old_file = await self.storage.read(path)
        if not old_file:
            raise ValueError(f"File not found: {path}")
        meta, body = _parse_frontmatter(old_file.raw_content)
        if prev_status:
            meta.prev_status = prev_status
        meta.status = new_status
        content = _serialize_frontmatter(meta, body)
        return await self.save_file(path, content, user_name=user_name)

    def _auto_resolve_conflicts_for_deprecated(self, path: str) -> None:
        """When a document is deprecated, auto-resolve all conflict pairs involving it."""
        try:
            pairs = self._conflict_svc.get_pairs(filter_mode="unresolved")
            resolved_count = 0
            for pair in pairs:
                if pair.file_a == path or pair.file_b == path:
                    self._conflict_svc.resolve_pair(
                        pair.file_a, pair.file_b,
                        resolved_by="system:deprecation",
                        action="auto_deprecated",
                    )
                    resolved_count += 1
            if resolved_count:
                logger.info(f"Auto-resolved {resolved_count} conflict(s) for deprecated {path}")
        except Exception as e:
            logger.warning(f"Auto-resolve conflicts failed for {path}: {e}")

    def _validate_metadata_soft(self, wiki_file: WikiFile) -> None:
        """Log warning if domain/process not in metadata templates (soft validation)."""
        meta = wiki_file.metadata
        if not meta.domain and not meta.process:
            return
        try:
            import json
            from pathlib import Path
            from backend.core.config import settings
            tpl_path = Path(settings.wiki_dir) / ".ontong" / "metadata_templates.json"
            if not tpl_path.exists():
                return
            tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
            dp = tpl.get("domain_processes", {})
            if meta.domain and meta.domain not in dp:
                logger.warning(f"Non-template domain '{meta.domain}' in {wiki_file.path}")
            if meta.domain and meta.process and meta.domain in dp:
                if meta.process not in dp[meta.domain]:
                    logger.warning(f"Non-template process '{meta.process}' for domain '{meta.domain}' in {wiki_file.path}")
        except Exception:
            pass

    async def _sync_lineage_counterpart(self, wiki_file: WikiFile) -> None:
        """Bi-directional lineage sync.

        When supersedes is set on B → auto-set superseded_by on target A (and vice versa).
        When lineage is cleared → also clear the counterpart's reference.
        """
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter

        meta = wiki_file.metadata
        my_path = wiki_file.path

        # Forward sync: set counterpart references
        if meta.supersedes:
            await self._set_counterpart_field(meta.supersedes, "superseded_by", my_path)
        if meta.superseded_by:
            await self._set_counterpart_field(meta.superseded_by, "supersedes", my_path)

        # Reverse cleanup: if lineage was cleared, remove stale references from other docs
        if not meta.supersedes and not meta.superseded_by:
            await self._clear_stale_lineage_refs(my_path)

    async def _set_counterpart_field(self, target_path: str, field: str, value: str) -> None:
        """Set a lineage field on the target document if not already correct."""
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter

        other = await self.storage.read(target_path)
        if not other:
            return
        current_val = getattr(other.metadata, field, "")
        if current_val == value:
            return  # already correct

        parsed_meta, body = _parse_frontmatter(other.raw_content)
        setattr(parsed_meta, field, value)
        new_content = _serialize_frontmatter(parsed_meta, body)
        await self.storage.write(target_path, new_content, user_name="")
        updated = await self.storage.read(target_path)
        if updated:
            if self._meta_index:
                m = updated.metadata
                self._meta_index.on_file_saved(
                    target_path, m.domain, m.process, m.tags,
                    updated=m.updated, updated_by=m.updated_by, created_by=m.created_by,
                    related=m.related, status=m.status,
                    supersedes=m.supersedes, superseded_by=m.superseded_by,
                )
            index_status.mark_pending(target_path)
            asyncio.create_task(self._bg_index(updated))
        logger.info(f"Lineage sync: set {field}={value} on {target_path}")

    async def _clear_stale_lineage_refs(self, my_path: str) -> None:
        """When this file has no lineage, clear any other doc that still references it."""
        try:
            all_entries = await self.storage.list_all_metadata()
        except Exception:
            return

        for entry in all_entries:
            if entry.path == my_path:
                continue
            refs_this = (
                entry.metadata.supersedes == my_path
                or entry.metadata.superseded_by == my_path
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
                if stripped == f"supersedes: {my_path}":
                    continue
                if stripped == f"superseded_by: {my_path}":
                    continue
                cleaned_lines.append(line)
            cleaned = "\n".join(cleaned_lines)
            if cleaned != raw:
                await self.storage.write(entry.path, cleaned, user_name="")
                updated = await self.storage.read(entry.path)
                if updated:
                    if self._meta_index:
                        m = updated.metadata
                        self._meta_index.on_file_saved(
                            entry.path, m.domain, m.process, m.tags,
                            updated=m.updated, updated_by=m.updated_by, created_by=m.created_by,
                            related=m.related, status=m.status,
                            supersedes=m.supersedes, superseded_by=m.superseded_by,
                        )
                    index_status.mark_pending(entry.path)
                    asyncio.create_task(self._bg_index(updated))
                logger.info(f"Lineage sync: cleared reference to {my_path} in {entry.path}")

    async def _bg_index(self, wiki_file: WikiFile) -> None:
        """Background indexing task."""
        try:
            await self.indexer.index_file(wiki_file)
            event_bus.publish("index_status", {"action": "done", "path": wiki_file.path})
            # Incremental conflict check after indexing
            if self._conflict_svc:
                try:
                    await asyncio.to_thread(self._conflict_svc.check_file, wiki_file.path)
                    # Trigger async deep analysis for high-similarity pairs
                    await self._conflict_svc.trigger_deep_analysis(wiki_file.path, max_pairs=3)
                except Exception as e:
                    logger.warning(f"Conflict check failed for {wiki_file.path}: {e}")
            # Related document suggestions are shown in the graph tab only (not auto-injected into metadata)
        except Exception as e:
            logger.error(f"Background indexing failed for {wiki_file.path}: {e}")
            event_bus.publish("index_status", {"action": "error", "path": wiki_file.path})
        finally:
            index_status.mark_done(wiki_file.path)

    async def _auto_suggest_related(self, wiki_file: WikiFile) -> None:
        """After indexing, find top related files and add to metadata.related (if empty).

        Only runs when:
        - File has no existing related entries
        - ChromaDB has embeddings for this file
        - At least 1 candidate with similarity > 0.7
        Max 3 related entries added.
        """
        import numpy as np

        path = wiki_file.path
        if path.startswith("_skills/") or path.startswith("_personas/"):
            return

        data = await asyncio.to_thread(self._chroma.get_file_embeddings, path)
        embeddings = data.get("embeddings", [])
        if embeddings is None or len(embeddings) == 0:
            return

        avg_embedding = np.mean(embeddings, axis=0)
        avg_norm = np.linalg.norm(avg_embedding)
        if avg_norm == 0:
            return

        results = await asyncio.to_thread(
            self._chroma.query_by_embedding, avg_embedding.tolist(), 15
        )
        result_metadatas = results.get("metadatas", [[]])[0]
        if not result_metadatas:
            return

        candidates: dict[str, float] = {}
        for meta in result_metadatas:
            fp = meta.get("file_path", "")
            if not fp or fp == path or fp.startswith("_skills/") or fp.startswith("_personas/"):
                continue
            # Skip deprecated documents from related suggestions
            if meta.get("status") == "deprecated":
                continue
            if fp not in candidates:
                # Compute accurate similarity
                other_data = await asyncio.to_thread(self._chroma.get_file_embeddings, fp)
                other_embs = other_data.get("embeddings", [])
                if other_embs is None or len(other_embs) == 0:
                    continue
                other_avg = np.mean(other_embs, axis=0)
                other_norm = np.linalg.norm(other_avg)
                if other_norm == 0:
                    continue
                sim = float(np.dot(avg_embedding, other_avg) / (avg_norm * other_norm))
                if sim >= _RELATED_CFG.auto_suggest_similarity:
                    candidates[fp] = sim

        if not candidates:
            return

        # Take top N
        top_related = sorted(candidates.items(), key=lambda x: -x[1])[:_RELATED_CFG.auto_suggest_max]
        related_paths = [p for p, _ in top_related]

        # Re-read the file to inject related into frontmatter
        current = await self.storage.read(path)
        if not current or current.metadata.related:
            return  # already has related, or file disappeared

        raw = current.raw_content
        if not raw.startswith("---"):
            return

        # Inject related field into frontmatter
        lines = raw.split("\n")
        fm_end = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
        if fm_end < 0:
            return

        related_yaml = "related:\n" + "\n".join(f"  - {p}" for p in related_paths)
        lines.insert(fm_end, related_yaml)
        new_content = "\n".join(lines)
        await self.storage.write(path, new_content, user_name="")
        logger.info(f"Auto-related: {path} → {related_paths}")

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
        # Clean up lineage links in counterpart documents before deletion
        await self._cleanup_lineage_on_delete(path)
        deleted = await self.storage.delete(path)
        if deleted:
            await self.indexer.remove_file(path)
            if self._conflict_svc:
                self._conflict_svc.remove_file(path)
            if self._meta_index:
                self._meta_index.on_file_deleted(path)
            event_bus.publish("tree_change", {"action": "remove", "path": path})
            logger.info(f"Deleted and removed from index: {path}")
        return deleted

    async def _cleanup_lineage_on_delete(self, path: str) -> None:
        """Clear supersedes/superseded_by references in other docs that point to this path."""
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter
        try:
            file = await self.storage.read(path)
            if not file:
                return
            meta = file.metadata
            # If this doc supersedes A → clear A's superseded_by
            if meta.supersedes:
                await self._clear_counterpart_field(meta.supersedes, "superseded_by", path)
            # If this doc is superseded_by B → clear B's supersedes
            if meta.superseded_by:
                await self._clear_counterpart_field(meta.superseded_by, "supersedes", path)
        except Exception as e:
            logger.warning(f"Lineage cleanup on delete failed for {path}: {e}")

    async def _clear_counterpart_field(self, target_path: str, field: str, expected_value: str) -> None:
        """Clear a lineage field on target if it points to expected_value.

        If clearing superseded_by on a deprecated doc, restore status to draft
        (the successor is being deleted, so deprecation no longer applies).
        """
        from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter
        other = await self.storage.read(target_path)
        if not other:
            return
        parsed_meta, body = _parse_frontmatter(other.raw_content)
        current = getattr(parsed_meta, field, "")
        if current != expected_value:
            return
        setattr(parsed_meta, field, "")
        # Restore status if successor is removed
        if field == "superseded_by" and parsed_meta.status == "deprecated":
            restored = parsed_meta.prev_status if parsed_meta.prev_status else "draft"
            parsed_meta.status = restored
            parsed_meta.prev_status = ""
            logger.info(f"Restored {target_path} from deprecated → {restored} (successor deleted)")
        new_content = _serialize_frontmatter(parsed_meta, body)
        await self.storage.write(target_path, new_content)
        if self._meta_index:
            m2 = parsed_meta
            self._meta_index.on_file_saved(
                target_path, m2.domain, m2.process, m2.tags,
                updated=m2.updated, updated_by=m2.updated_by,
                created_by=m2.created_by, related=m2.related,
                status=m2.status, supersedes=m2.supersedes,
                superseded_by=m2.superseded_by,
            )
        logger.info(f"Cleared {field} on {target_path} (was: {expected_value})")

    async def move_file(self, old_path: str, new_path: str) -> bool:
        moved = await self.storage.move(old_path, new_path)
        if moved:
            await self.indexer.remove_file(old_path)
            if self._conflict_svc:
                self._conflict_svc.remove_file(old_path)
            if self._meta_index:
                self._meta_index.on_file_deleted(old_path)
            new_file = await self.storage.read(new_path)
            if new_file:
                index_status.mark_pending(new_path)
                asyncio.create_task(self._bg_index(new_file))
                # Update metadata index for new path
                if self._meta_index:
                    m = new_file.metadata
                    self._meta_index.on_file_saved(
                        new_path, m.domain, m.process, m.tags,
                        updated=m.updated, updated_by=m.updated_by,
                        created_by=m.created_by, related=m.related,
                        status=m.status, supersedes=m.supersedes,
                        superseded_by=m.superseded_by,
                    )
            # Update references in other documents that point to old_path
            await self._update_references(old_path, new_path)
            event_bus.publish("tree_change", {"action": "move", "old_path": old_path, "new_path": new_path})
            logger.info(f"Moved file: {old_path} → {new_path}")
        return moved

    async def _update_references(self, old_path: str, new_path: str) -> None:
        """Update supersedes/superseded_by/related references in other files after a move."""
        if not self._meta_index:
            return
        try:
            from backend.infrastructure.storage.local_fs import _parse_frontmatter, _serialize_frontmatter
            # Find files that reference old_path
            referencing: set[str] = set()
            # Check supersedes reverse: who supersedes old_path
            referencing.update(self._meta_index.get_supersedes_reverse(old_path))
            # Check related reverse: who has old_path in their related
            referencing.update(self._meta_index.get_related_reverse(old_path))
            # Check files whose superseded_by points to old_path
            for p, entry in self._meta_index._load().get("files", {}).items():
                if entry.get("superseded_by") == old_path:
                    referencing.add(p)

            for ref_path in referencing:
                try:
                    ref_file = await self.storage.read(ref_path)
                    if not ref_file:
                        continue
                    raw = ref_file.raw_content
                    updated = raw.replace(old_path, new_path)
                    if updated != raw:
                        await self.storage.write(ref_path, updated)
                        logger.info(f"Updated reference in {ref_path}: {old_path} → {new_path}")
                except Exception as e:
                    logger.warning(f"Failed to update reference in {ref_path}: {e}")
        except Exception as e:
            logger.warning(f"Reference update failed for {old_path} → {new_path}: {e}")

    def get_referencing_files(self, path: str) -> list[str]:
        """Return list of files that reference the given path via `related` only.

        Lineage references (supersedes/superseded_by) are excluded because
        deleting a version should clean up lineage links, not block deletion.
        """
        if not self._meta_index:
            return []
        return sorted(self._meta_index.get_related_reverse(path))

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
        count = await self.indexer.reindex_all(files, force=force)

        # Rebuild materialized metadata index
        if self._meta_index:
            file_meta = [
                {
                    "path": f.path,
                    "domain": f.metadata.domain,
                    "process": f.metadata.process,
                    "tags": f.metadata.tags,
                    "updated": f.metadata.updated,
                    "updated_by": f.metadata.updated_by,
                    "created_by": f.metadata.created_by,
                    "related": f.metadata.related,
                    "status": f.metadata.status,
                    "supersedes": f.metadata.supersedes,
                    "superseded_by": f.metadata.superseded_by,
                }
                for f in files
            ]
            self._meta_index.rebuild(extended=file_meta)

        return count
