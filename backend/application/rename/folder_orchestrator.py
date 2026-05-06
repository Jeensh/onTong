"""Folder rename orchestrator — batched single-file rename for subtree.

Wraps RenameOrchestrator: for each markdown child of the source folder,
runs plan + execute. Processes in chunks of CHUNK_SIZE with asyncio yield
between chunks. Per-user bulk lock prevents concurrent folder ops by the
same actor.
"""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from .types import RenamePlan, RenameResult, ImpactItem
from .audit_protocol import AuditStore
from .lock_helper import lock_set_in_order, lock_set_release_all
from .orchestrator import RenameOrchestrator

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50
CHUNK_YIELD_SECONDS = 0.01
BULK_LOCK_TTL = 1800  # 30 min


@dataclass(frozen=True)
class FolderRenamePlan:
    audit_id: str
    old_folder: str
    new_folder: str
    actor: str
    file_count: int                    # number of markdown children
    inbound_count: int                 # sum of inbound across all children
    unique_inbound_sources: int        # union across all children (deduplicated)
    estimated_seconds: float
    impact_items: list[ImpactItem]     # top-N aggregated
    file_pairs: list[tuple[str, str]]  # [(old, new), ...] all children


@dataclass
class FolderRenameResult:
    audit_id: str
    status: str                # "success" | "partial" | "failed"
    total_files: int
    files_done: int
    files_failed: int
    inbound_done: int
    inbound_failed: int
    error: str | None = None


class FolderRenameOrchestrator:
    BULK_LOCK_KEY_PREFIX = "ontong:lock:bulk:"

    def __init__(self, rename_orch: RenameOrchestrator, audit_store: AuditStore, content_store=None) -> None:
        self._rename = rename_orch
        self._audit = audit_store
        self._content = content_store

    async def plan(self, old_folder: str, new_folder: str, actor: str) -> FolderRenamePlan:
        """Aggregate impact across all markdown children under old_folder."""
        # Phase 5-C: skip edit lock check at folder level — each per-file plan does it during execute

        # Enumerate subtree
        if self._content is None or not hasattr(self._content, "storage"):
            raise RuntimeError("content_store with storage required")
        children = await self._enumerate_md_files(old_folder)
        if not children:
            raise RuntimeError(f"폴더에 마크다운 파일이 없거나 폴더가 존재하지 않습니다: {old_folder}")

        file_pairs = [
            (child, _swap_prefix(child, old_folder, new_folder))
            for child in children
        ]

        # Per-child plan; aggregate
        all_impact: list[ImpactItem] = []
        unique_sources: set[str] = set()
        total_inbound = 0
        for old_p, new_p in file_pairs:
            try:
                p = await self._rename.plan(old_p, new_p, actor)
                total_inbound += p.inbound_count
                for it in p.impact_items:
                    unique_sources.add(it.source_path)
                    all_impact.append(it)
            except RuntimeError as e:
                # If plan fails (e.g. edit lock), surface to caller
                raise RuntimeError(f"폴더 내 {old_p} 미리보기 실패: {e}")

        # Group impact_items by source_path, sum ref_count
        from collections import Counter
        agg: Counter[str] = Counter()
        for it in all_impact:
            agg[it.source_path] += it.ref_count
        impact_items = sorted(
            (ImpactItem(source_path=src, ref_count=cnt) for src, cnt in agg.items()),
            key=lambda it: (-it.ref_count, it.source_path),
        )[:100]

        # Create folder audit row
        audit_id = self._audit.create_audit(
            op="folder_rename_plan",
            actor=actor,
            payload={
                "old_folder": old_folder,
                "new_folder": new_folder,
                "file_count": len(file_pairs),
                "total_inbound": total_inbound,
                "unique_inbound_sources": len(unique_sources),
            },
        )
        self._audit.update_audit_status(audit_id, "success")

        return FolderRenamePlan(
            audit_id=str(audit_id),
            old_folder=old_folder,
            new_folder=new_folder,
            actor=actor,
            file_count=len(file_pairs),
            inbound_count=total_inbound,
            unique_inbound_sources=len(unique_sources),
            estimated_seconds=0.05 * total_inbound + 0.1 * len(file_pairs),
            impact_items=impact_items,
            file_pairs=file_pairs,
        )

    async def execute(self, audit_id: str, *, force: bool = False) -> FolderRenameResult:
        """Execute folder rename in chunks of CHUNK_SIZE.

        Uses per-user bulk lock to prevent concurrent folder ops by same actor.
        """
        audit_row = self._audit.get_audit(int(audit_id))
        if audit_row is None or audit_row.op != "folder_rename_plan":
            return FolderRenameResult(
                audit_id=audit_id, status="failed",
                total_files=0, files_done=0, files_failed=0,
                inbound_done=0, inbound_failed=0,
                error="audit row not found or not a folder_rename_plan"
            )
        old_folder = audit_row.payload["old_folder"]
        new_folder = audit_row.payload["new_folder"]
        actor = audit_row.actor

        # Acquire per-user bulk lock.
        # Lock user is fixed ("bulk_active") — the key already encodes the actor.
        # Check status BEFORE acquiring: InMemoryLockBackend.acquire() refreshes for
        # the same user (does not block). Checking first gives a true "already locked"
        # guard regardless of who holds it.
        bulk_lock_key = f"{self.BULK_LOCK_KEY_PREFIX}{actor}"
        _BULK_LOCK_USER = "bulk_active"
        from backend.application.lock_service import get_lock_service
        lock_svc = get_lock_service()
        existing = lock_svc.status(bulk_lock_key)
        if existing is not None:
            bulk_lock = None
        else:
            bulk_lock = lock_svc.acquire(bulk_lock_key, _BULK_LOCK_USER, ttl=BULK_LOCK_TTL)
        if bulk_lock is None:
            self._audit.update_audit_status(int(audit_id), "failed",
                                            error="이미 진행 중인 bulk 작업이 있습니다")
            return FolderRenameResult(
                audit_id=audit_id, status="failed",
                total_files=0, files_done=0, files_failed=0,
                inbound_done=0, inbound_failed=0,
                error="bulk lock conflict (이미 다른 폴더 작업 진행 중)",
            )

        try:
            # Re-enumerate (subtree may have changed since plan; tolerate).
            children = await self._enumerate_md_files(old_folder)
            file_pairs = [
                (child, _swap_prefix(child, old_folder, new_folder))
                for child in children
            ]

            # Audit jobs: one per child file
            self._audit.add_jobs(int(audit_id),
                                  [("folder_child_rename", old_p) for old_p, _ in file_pairs])

            self._publish_progress(audit_id, "folder_rename_started", {
                "old_folder": old_folder,
                "new_folder": new_folder,
                "total_files": len(file_pairs),
            })

            jobs = self._audit.list_jobs(int(audit_id))
            job_by_target = {j.target_path: j for j in jobs if j.kind == "folder_child_rename"}

            files_done = 0
            files_failed = 0
            inbound_done = 0
            inbound_failed = 0

            # Process in chunks
            for chunk_start in range(0, len(file_pairs), CHUNK_SIZE):
                chunk = file_pairs[chunk_start:chunk_start + CHUNK_SIZE]
                for old_p, new_p in chunk:
                    job = job_by_target.get(old_p)
                    try:
                        if job:
                            self._audit.update_job(job.id, status="running")
                        # Per-child plan + execute. The child plan creates its
                        # own audit row (op=rename_plan), then execute runs the
                        # full single-file pipeline (storage.move + body
                        # patching + chunk meta).
                        child_plan = await self._rename.plan(old_p, new_p, actor)
                        child_result = await self._rename.execute(child_plan.audit_id)
                        if child_result.status in ("success", "partial"):
                            files_done += 1
                            inbound_done += child_result.inbound_done
                            inbound_failed += child_result.inbound_failed
                            if job:
                                self._audit.update_job(job.id,
                                    status="done" if child_result.status == "success" else "failed",
                                    last_error=None if child_result.status == "success" else f"partial: {child_result.error or 'some inbound failed'}",
                                )
                        else:
                            files_failed += 1
                            if job:
                                self._audit.update_job(job.id, status="failed",
                                    last_error=child_result.error or "child execute failed")
                    except Exception as e:
                        files_failed += 1
                        logger.error(f"folder child rename failed for {old_p}: {e}")
                        if job:
                            self._audit.update_job(job.id, status="failed", last_error=str(e))

                # Progress per chunk
                self._publish_progress(audit_id, "folder_rename_progress", {
                    "files_done": files_done,
                    "files_failed": files_failed,
                    "total_files": len(file_pairs),
                    "current_chunk_end": min(chunk_start + CHUNK_SIZE, len(file_pairs)),
                })
                # Yield to event loop between chunks
                await asyncio.sleep(CHUNK_YIELD_SECONDS)

            final_status = "success" if files_failed == 0 else ("partial" if files_done > 0 else "failed")
            self._audit.update_audit_status(int(audit_id), final_status)

            self._publish_progress(audit_id, "folder_rename_finished", {
                "status": final_status,
                "files_done": files_done,
                "files_failed": files_failed,
                "inbound_done": inbound_done,
                "inbound_failed": inbound_failed,
            })

            return FolderRenameResult(
                audit_id=audit_id, status=final_status,
                total_files=len(file_pairs),
                files_done=files_done, files_failed=files_failed,
                inbound_done=inbound_done, inbound_failed=inbound_failed,
            )

        except Exception as e:
            logger.error(f"FolderRenameOrchestrator.execute fatal: {e}", exc_info=True)
            self._audit.update_audit_status(int(audit_id), "failed", error=str(e))
            return FolderRenameResult(
                audit_id=audit_id, status="failed",
                total_files=0, files_done=0, files_failed=0,
                inbound_done=0, inbound_failed=0, error=str(e),
            )
        finally:
            # Always release bulk lock
            try:
                lock_svc.release(bulk_lock_key, _BULK_LOCK_USER)
            except Exception:
                pass

    def _publish_progress(self, audit_id: str, event_type: str, data: dict) -> None:
        try:
            from backend.infrastructure.events.event_bus import event_bus
            event_bus.publish(event_type, {"audit_id": audit_id, **data})
        except Exception as e:
            logger.warning("event_bus publish failed for %s: %s", event_type, e)

    async def _enumerate_md_files(self, folder: str) -> list[str]:
        """List all .md files under folder (recursive). Returns relative paths from wiki_dir."""
        from backend.core.config import settings
        wiki_dir = Path(settings.wiki_dir)
        target_dir = wiki_dir / folder
        if not target_dir.is_dir():
            return []
        result: list[str] = []
        for p in target_dir.rglob("*.md"):
            rel = p.relative_to(wiki_dir).as_posix()
            # Skip system/dotted dirs
            if rel.startswith(("_skills/", "_personas/", ".ontong/", "assets/")):
                continue
            if any(part.startswith(".") for part in p.relative_to(wiki_dir).parts):
                continue
            result.append(rel)
        return sorted(result)


def _swap_prefix(child_path: str, old_folder: str, new_folder: str) -> str:
    """Replace the old folder prefix in child_path with new_folder.

    e.g. _swap_prefix('데모/sub/c.md', '데모', '데모2') == '데모2/sub/c.md'
    Uses pure path-prefix comparison (Path-aware), not naive str.replace.
    """
    old_norm = old_folder.rstrip("/") + "/"
    if child_path == old_folder.rstrip("/"):
        return new_folder.rstrip("/")
    if child_path.startswith(old_norm):
        return new_folder.rstrip("/") + "/" + child_path[len(old_norm):]
    return child_path  # unchanged if not under old_folder
