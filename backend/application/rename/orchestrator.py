"""RenameOrchestrator — Plan / Execute / Reconcile."""
from __future__ import annotations

import logging

from .types import RenamePlan, RenameResult, ImpactItem
from .audit_protocol import AuditStore
from .lock_helper import lock_set_in_order, lock_set_release_all

logger = logging.getLogger(__name__)

CONFIRM_THRESHOLD = 10        # inbound_count above which UI must confirm
ESTIMATE_PER_INBOUND = 0.05   # seconds — rough placeholder; tuned in Phase 6 load test
LOCK_TTL = 5
MAX_IMPACT_PREVIEW = 100


class RenameOrchestrator:
    """Coordinates the end-to-end rename.

    Plan: computes impact, creates audit row.
    Execute: acquires locks, snapshots, moves file, patches inbound refs,
             updates ChromaDB chunk metadata, releases locks.
    """

    def __init__(self, ref_index, audit_store: AuditStore, content_store=None,
                 occ_manager=None, snapshot_store=None, chunk_updater=None) -> None:
        self._ref_index = ref_index
        self._audit = audit_store
        self._content = content_store
        self._occ = occ_manager
        self._snapshots = snapshot_store
        self._chunk_updater = chunk_updater

    async def plan(self, old_path: str, new_path: str, actor: str) -> RenamePlan:
        """Compute impact of rename without making any changes."""
        # 1. Aggregate inbound refs from RefIndex (full path)
        inbound = self._ref_index.inbound(old_path)

        # Also stem-match for BODY_WIKILINK (Phase 1 over-collect strategy)
        from pathlib import Path as _P
        from backend.application.refindex.extractor import RefKind
        stem = _P(old_path).stem
        if stem and stem != old_path:
            stem_refs = self._ref_index.inbound(stem, kind=RefKind.BODY_WIKILINK)
            inbound = list(inbound) + list(stem_refs)

        # 2. Group by source_path → ref_count
        from collections import Counter
        src_counter: Counter[str] = Counter()
        for r in inbound:
            src_counter[r.source_path] += 1

        # Sort by descending ref_count, then alphabetical for stable output
        impact_items = sorted(
            (ImpactItem(source_path=src, ref_count=cnt) for src, cnt in src_counter.items()),
            key=lambda it: (-it.ref_count, it.source_path),
        )[:MAX_IMPACT_PREVIEW]

        inbound_count = len(inbound)
        unique_inbound_sources = len(src_counter)

        # 3. Create audit row (status=running). Caller can later resolve via audit_id.
        audit_id_int = self._audit.create_audit(
            op="rename_plan",
            actor=actor,
            payload={
                "old_path": old_path,
                "new_path": new_path,
                "inbound_count": inbound_count,
                "unique_inbound_sources": unique_inbound_sources,
            },
        )

        # 4. Mark plan as success (execute() not yet fully implemented)
        self._audit.update_audit_status(audit_id_int, "success")

        return RenamePlan(
            audit_id=str(audit_id_int),
            old_path=old_path,
            new_path=new_path,
            actor=actor,
            inbound_count=inbound_count,
            unique_inbound_sources=unique_inbound_sources,
            confirm_required=(inbound_count > CONFIRM_THRESHOLD),
            estimated_seconds=inbound_count * ESTIMATE_PER_INBOUND,
            impact_items=impact_items,
        )

    async def execute(self, audit_id: str, *, force: bool = False) -> RenameResult:
        """Full rename pipeline.

        1. Load audit row (from plan stage). Extract old_path, new_path, actor.
        2. Acquire source path lock.
        3. Build target_remap (path + stem for BODY_WIKILINK).
        4. Acquire inbound batch locks (sorted alphabetical, deadlock-safe).
        5. Snapshot source pre-rename if SnapshotStore configured.
        6. Storage rename (filesystem move).
        7. OCC store key rename + RefIndex.rename_source.
        8. For each unique inbound source:
            - Read content via storage
            - Get fresh refs from RefIndex.outbound
            - Apply Patcher
            - If applied > 0: write back directly (skip save_file to avoid recursion)
            - Re-extract and upsert RefIndex for updated source
        9. ChunkMetaUpdater.update_for_path_rename (OQ-4=A: includes re-embedding).
        10. Mark audit status: success if all jobs done, partial if some failed.
        11. Release all locks.
        """
        inbound_paths_acquired: list[str] = []
        source_acquired: bool = False
        old_path: str = ""
        lock_user: str = f"rename:unknown"

        try:
            audit_row = self._audit.get_audit(int(audit_id))
            if audit_row is None:
                return RenameResult(
                    audit_id=audit_id,
                    status="failed",
                    inbound_done=0,
                    inbound_failed=0,
                    inbound_total=0,
                    error="audit row not found",
                )
            old_path = audit_row.payload.get("old_path")
            new_path = audit_row.payload.get("new_path")
            actor = audit_row.actor
            lock_user = f"rename:{actor}"

            # Source lock
            src_acq, src_missed = lock_set_in_order([old_path], lock_user, ttl=LOCK_TTL)
            if not src_acq:
                self._audit.update_audit_status(
                    int(audit_id), "failed",
                    error=f"source lock missed: {src_missed}",
                )
                return RenameResult(
                    audit_id=audit_id,
                    status="failed",
                    inbound_done=0,
                    inbound_failed=0,
                    inbound_total=0,
                    error="source lock missed",
                )
            source_acquired = True

            # Build target_remap: full path + stem (for BODY_WIKILINK kind=4)
            target_remap: dict[str, str] = {old_path: new_path}
            from pathlib import Path as _P
            from backend.application.refindex.extractor import RefKind, ReferenceExtractor
            old_stem = _P(old_path).stem
            new_stem = _P(new_path).stem
            if old_stem and old_stem != new_stem:
                target_remap[old_stem] = new_stem

            # Collect inbound refs (path + stem-matched)
            all_inbound = list(self._ref_index.inbound(old_path))
            if old_stem and old_stem != old_path:
                all_inbound += list(self._ref_index.inbound(old_stem, kind=RefKind.BODY_WIKILINK))

            unique_sources = sorted({r.source_path for r in all_inbound})
            unique_sources_capped = unique_sources[:50]  # batch cap

            if unique_sources_capped:
                inb_acq, inb_missed = lock_set_in_order(
                    unique_sources_capped, lock_user, ttl=LOCK_TTL,
                )
                if inb_missed:
                    self._audit.update_audit_status(
                        int(audit_id), "failed",
                        error=f"inbound lock missed: {inb_missed}",
                    )
                    return RenameResult(
                        audit_id=audit_id,
                        status="failed",
                        inbound_done=0,
                        inbound_failed=0,
                        inbound_total=len(unique_sources_capped),
                        error="inbound lock conflict",
                    )
                inbound_paths_acquired = inb_acq

            # Snapshot source pre-rename
            if self._snapshots is not None and self._content is not None:
                try:
                    old_file = await self._content.storage.read(old_path)
                    if old_file is not None:
                        cur_v = self._occ.current(old_path) if self._occ else ""
                        self._snapshots.append(
                            path=old_path,
                            content=old_file.raw_content,
                            version=cur_v or "",
                            user_name=actor,
                            reason="pre_rename",
                        )
                except Exception as e:
                    logger.warning("pre_rename snapshot failed: %s", e)

            # Register jobs (one per inbound + one chunk_meta)
            if unique_sources_capped:
                self._audit.add_jobs(
                    int(audit_id),
                    [("patch_inbound", src) for src in unique_sources_capped],
                )
            self._audit.add_jobs(int(audit_id), [("update_chunk_meta", new_path)])

            # Storage rename (filesystem move)
            moved = await self._content.storage.move(old_path, new_path)
            if not moved:
                self._audit.update_audit_status(
                    int(audit_id), "failed", error="storage move failed (file missing?)"
                )
                return RenameResult(
                    audit_id=audit_id,
                    status="failed",
                    inbound_done=0,
                    inbound_failed=0,
                    inbound_total=len(unique_sources_capped),
                    error="storage move failed",
                )

            # OCC store key rename
            if self._occ is not None:
                try:
                    self._occ._store.rename(old_path, new_path)
                except Exception as e:
                    logger.warning("OCC rename failed (non-fatal): %s", e)

            # RefIndex source key rename
            try:
                self._ref_index.rename_source(old_path, new_path)
            except Exception as e:
                logger.warning("RefIndex.rename_source failed: %s", e)

            # Patch each inbound source
            from backend.application.rename.patcher import patch_references
            inbound_done = 0
            inbound_failed = 0
            jobs = self._audit.list_jobs(int(audit_id))
            job_by_target = {j.target_path: j for j in jobs if j.kind == "patch_inbound"}

            for src_path in unique_sources_capped:
                job = job_by_target.get(src_path)
                try:
                    if job:
                        self._audit.update_job(job.id, status="running")
                    src_file = await self._content.storage.read(src_path)
                    if src_file is None:
                        inbound_failed += 1
                        if job:
                            self._audit.update_job(job.id, status="failed", last_error="not found")
                        continue
                    src_refs = self._ref_index.outbound(src_path)
                    result = patch_references(src_file.raw_content, src_refs, target_remap)
                    if result.applied > 0:
                        # Write directly — skip save_file to avoid recursive hooks
                        await self._content.storage.write(
                            src_path, result.new_content, user_name="system:rename"
                        )
                        # Re-extract and refresh RefIndex for this source
                        ext = ReferenceExtractor()
                        new_refs = ext.extract(src_path, result.new_content)
                        self._ref_index.upsert_for_source(src_path, new_refs)
                    inbound_done += 1
                    if job:
                        self._audit.update_job(job.id, status="done")
                except Exception as e:
                    inbound_failed += 1
                    logger.error("patch_inbound failed for %s: %s", src_path, e)
                    if job:
                        self._audit.update_job(job.id, status="failed", last_error=str(e))

            # Chunk metadata update (OQ-4=A: includes re-embedding)
            chunk_job = next((j for j in jobs if j.kind == "update_chunk_meta"), None)
            if self._chunk_updater is not None:
                try:
                    if chunk_job:
                        self._audit.update_job(chunk_job.id, status="running")
                    wiki_file_at_new = await self._content.storage.read(new_path)
                    cm_result = await self._chunk_updater.update_for_path_rename(
                        old_path, new_path, wiki_file_at_new_path=wiki_file_at_new,
                    )
                    if chunk_job:
                        if cm_result.get("error"):
                            self._audit.update_job(
                                chunk_job.id, status="failed", last_error=cm_result["error"]
                            )
                        else:
                            self._audit.update_job(chunk_job.id, status="done")
                except Exception as e:
                    logger.error("chunk meta update failed: %s", e)
                    if chunk_job:
                        self._audit.update_job(chunk_job.id, status="failed", last_error=str(e))

            # Refresh jobs list to check final statuses
            jobs = self._audit.list_jobs(int(audit_id))
            chunk_job = next((j for j in jobs if j.kind == "update_chunk_meta"), None)
            chunk_failed = chunk_job is not None and chunk_job.status == "failed"

            if inbound_failed == 0 and not chunk_failed:
                self._audit.update_audit_status(int(audit_id), "success")
                final_status = "success"
            else:
                self._audit.update_audit_status(int(audit_id), "partial")
                final_status = "partial"

            return RenameResult(
                audit_id=audit_id,
                status=final_status,
                inbound_done=inbound_done,
                inbound_failed=inbound_failed,
                inbound_total=len(unique_sources_capped),
            )

        except Exception as e:
            logger.error("RenameOrchestrator.execute fatal: %s", e, exc_info=True)
            try:
                self._audit.update_audit_status(int(audit_id), "failed", error=str(e))
            except Exception:
                pass
            return RenameResult(
                audit_id=audit_id,
                status="failed",
                inbound_done=0,
                inbound_failed=0,
                inbound_total=0,
                error=str(e),
            )
        finally:
            # Always release locks — even on exception path
            if inbound_paths_acquired:
                lock_set_release_all(inbound_paths_acquired, lock_user)
            if source_acquired:
                lock_set_release_all([old_path], lock_user)
