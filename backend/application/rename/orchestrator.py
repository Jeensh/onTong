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
UNDO_WINDOW_SECONDS = 5 * 60  # 5 minutes


def _build_hunk(
    raw: str,
    off: int,
    length: int,
    expected_raw: str,
    new_target: str,
    context_chars: int,
) -> dict:
    """Extract a context window around a single ref change.

    Snaps to line boundaries on each side so the UI can render the hunk as
    a clean code block instead of mid-line fragments.
    """
    ctx_start = max(0, off - context_chars)
    ctx_end = min(len(raw), off + length + context_chars)

    nl_before = raw.rfind("\n", ctx_start, off)
    if nl_before > -1:
        ctx_start = nl_before + 1
    nl_after = raw.find("\n", off + length, ctx_end)
    if nl_after > -1:
        ctx_end = nl_after

    before = raw[ctx_start:ctx_end]
    rel_off = off - ctx_start
    after = before[:rel_off] + new_target + before[rel_off + length:]
    line_no = raw.count("\n", 0, off) + 1

    return {
        "line_no": line_no,
        "before": before,
        "after": after,
        "old_target": expected_raw,
        "new_target": new_target,
    }


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

    def _check_edit_lock(self, path: str, actor: str) -> str | None:
        """Check if there's an active edit lock held by SOMEONE OTHER than the rename actor.

        Returns the holder's name if blocked, None if clear.
        Uses backend.application.lock_service.get_lock_service() — the same lock
        service used by the editor's edit-session locks.
        """
        try:
            from backend.application.lock_service import get_lock_service
            svc = get_lock_service()
            info = svc.status(path)
            if info is None:
                return None
            if info.user == actor:
                # Same user is renaming what they're editing — allow
                return None
            # Different user holds the edit lock
            return info.user
        except Exception as e:
            # Non-fatal — log and let the rename proceed
            import logging
            logging.getLogger(__name__).warning(f"edit lock check failed for {path}: {e}")
            return None

    async def plan(self, old_path: str, new_path: str, actor: str) -> RenamePlan:
        """Compute impact of rename without making any changes."""
        # Phase 5-C: check edit-session lock before computing impact
        holder = self._check_edit_lock(old_path, actor)
        if holder:
            raise RuntimeError(
                f"이 문서는 현재 {holder}가 편집 중입니다. 편집이 끝난 후 다시 시도하세요."
            )

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

    def _publish_progress(self, audit_id: str, event_type: str, data: dict) -> None:
        """Publish to event_bus. Non-fatal if event_bus unavailable."""
        try:
            from backend.infrastructure.events.event_bus import event_bus
            event_bus.publish(event_type, {"audit_id": audit_id, **data})
        except Exception as e:
            logger.warning("event_bus publish failed for %s: %s", event_type, e)

    async def compute_preview_hunks(
        self,
        old_path: str,
        new_path: str,
        *,
        max_sources: int = 20,
        context_chars: int = 200,
    ) -> list[dict]:
        """Dry-run the rename and return per-source body hunks for the UI preview.

        Returns: [
            {
              "source_path": "...",
              "hunks": [{"line_no": int, "before": str, "after": str,
                         "old_target": str, "new_target": str}, ...]
            },
            ...
        ]

        Capped at max_sources to keep the preview cheap. Hunks include
        context_chars on each side, clipped to the nearest line boundary
        for readability. The hunk's `before` / `after` differ only at the
        rewritten ref so the UI can display them inline.
        """
        from pathlib import Path as _P
        from backend.application.refindex.extractor import RefKind

        target_remap: dict[str, str] = {old_path: new_path}
        old_stem = _P(old_path).stem
        new_stem = _P(new_path).stem
        if old_stem and old_stem != new_stem:
            target_remap[old_stem] = new_stem

        all_inbound = list(self._ref_index.inbound(old_path))
        if old_stem and old_stem != old_path:
            all_inbound += list(self._ref_index.inbound(old_stem, kind=RefKind.BODY_WIKILINK))

        unique_sources = sorted({r.source_path for r in all_inbound})[:max_sources]
        if not unique_sources or self._content is None:
            return []

        previews: list[dict] = []
        for src_path in unique_sources:
            try:
                src_file = await self._content.storage.read(src_path)
            except Exception as e:
                logger.warning("preview read failed for %s: %s", src_path, e)
                continue
            if src_file is None:
                continue
            raw = src_file.raw_content

            src_refs = self._ref_index.outbound(src_path)
            relevant = [r for r in src_refs if r.target_path in target_remap]
            # Same descending-offset order as the real patcher uses, so
            # offsets in `before` line up with what execute() will see.
            relevant.sort(key=lambda r: -r.location["offset"])

            hunks: list[dict] = []
            for r in relevant:
                off = r.location["offset"]
                length = r.location["length"]
                expected_raw = r.location["raw"]
                if raw[off:off + length] != expected_raw:
                    # Stale offset — would skip in execute() too. Don't display.
                    continue
                new_target = target_remap[r.target_path]
                hunks.append(_build_hunk(raw, off, length, expected_raw, new_target, context_chars))

            if hunks:
                # Display in document order (top-to-bottom)
                hunks.reverse()
                previews.append({"source_path": src_path, "hunks": hunks})

        return previews

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

            # Phase 5-C: check edit-session lock before acquiring rename locks
            holder = self._check_edit_lock(old_path, actor)
            if holder:
                self._audit.update_audit_status(
                    int(audit_id), "failed",
                    error=f"edit lock held by {holder}",
                )
                return RenameResult(
                    audit_id=audit_id,
                    status="failed",
                    inbound_done=0,
                    inbound_failed=0,
                    inbound_total=0,
                    error=f"이 문서는 현재 {holder}가 편집 중입니다.",
                )

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

            # Collect inbound refs early to include in rename_started event
            # (we rebuild below — this is just for the count)
            _early_inbound = list(self._ref_index.inbound(old_path))
            from pathlib import Path as _P_early
            _old_stem_early = _P_early(old_path).stem
            if _old_stem_early and _old_stem_early != old_path:
                from backend.application.refindex.extractor import RefKind as _RK_early
                _early_inbound += list(self._ref_index.inbound(_old_stem_early, kind=_RK_early.BODY_WIKILINK))
            _early_unique_sources = sorted({r.source_path for r in _early_inbound})[:50]

            self._publish_progress(audit_id, "rename_started", {
                "old_path": old_path,
                "new_path": new_path,
                "inbound_total": len(_early_unique_sources),
            })

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

            # E4: ACL leak window guard — sync chunk metadata BEFORE inbound
            # patches. If we leave this until the end, every inbound patch
            # widens the window during which ChromaDB chunks still carry the
            # old path (and old ACL). Doing it here closes the window to the
            # update_for_path_rename call itself (~10-50ms typical).
            jobs = self._audit.list_jobs(int(audit_id))
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
                    self._publish_progress(audit_id, "rename_progress", {
                        "step": "chunk_meta_done",
                        "access_scope_synced": cm_result.get("access_scope_synced", False),
                    })
                except Exception as e:
                    logger.error("chunk meta update failed: %s", e)
                    if chunk_job:
                        self._audit.update_job(chunk_job.id, status="failed", last_error=str(e))

            # Patch each inbound source — runs after the ACL window is closed.
            from backend.application.rename.patcher import patch_references
            inbound_done = 0
            inbound_failed = 0
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
                        # Re-read from storage so RefIndex offsets reflect the
                        # post-write content. The storage adapter may inject
                        # frontmatter timestamps (created/updated), shifting
                        # body offsets. Without this, undo's patcher would
                        # see stale offsets and skip the reverse patch.
                        written = await self._content.storage.read(src_path)
                        ext = ReferenceExtractor()
                        new_refs = ext.extract(
                            src_path,
                            written.raw_content if written else result.new_content,
                        )
                        self._ref_index.upsert_for_source(src_path, new_refs)
                    inbound_done += 1
                    if job:
                        self._audit.update_job(job.id, status="done")
                    self._publish_progress(audit_id, "rename_progress", {
                        "done": inbound_done,
                        "failed": inbound_failed,
                        "total": len(unique_sources_capped),
                        "current": src_path,
                    })
                except Exception as e:
                    inbound_failed += 1
                    logger.error("patch_inbound failed for %s: %s", src_path, e)
                    if job:
                        self._audit.update_job(job.id, status="failed", last_error=str(e))
                    self._publish_progress(audit_id, "rename_progress", {
                        "done": inbound_done,
                        "failed": inbound_failed,
                        "total": len(unique_sources_capped),
                        "current": src_path,
                    })

            # E4: chunk_meta now runs *before* the inbound loop above so the
            # ACL leak window stays minimal. Just refresh job status here so
            # the success/partial decision below sees the latest state.
            jobs = self._audit.list_jobs(int(audit_id))
            chunk_job = next((j for j in jobs if j.kind == "update_chunk_meta"), None)
            chunk_failed = chunk_job is not None and chunk_job.status == "failed"

            if inbound_failed == 0 and not chunk_failed:
                self._audit.update_audit_status(int(audit_id), "success")
                final_status = "success"
            else:
                self._audit.update_audit_status(int(audit_id), "partial")
                final_status = "partial"

            self._publish_progress(audit_id, "rename_finished", {
                "status": final_status,
                "done": inbound_done,
                "failed": inbound_failed,
            })

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

    async def undo(self, audit_id: str, actor: str) -> RenameResult:
        """Undo a rename within the 5-minute window.

        Steps:
        1. Load audit row. Reject if op != 'rename_plan' or outside undo window.
        2. Reverse the rename: new_path → old_path via the same orchestrator pipeline.
        3. The reverse rename's body patcher restores inbound refs automatically.
        4. Mark a new audit row (reverse plan's audit_id is returned via the result).
        """
        import time

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
        if audit_row.op != "rename_plan" or audit_row.status not in ("success", "partial"):
            return RenameResult(
                audit_id=audit_id,
                status="failed",
                inbound_done=0,
                inbound_failed=0,
                inbound_total=0,
                error=(
                    f"audit op={audit_row.op}, status={audit_row.status} "
                    "— undoable only for completed renames"
                ),
            )
        if audit_row.finished_at and (time.time() - audit_row.finished_at > UNDO_WINDOW_SECONDS):
            return RenameResult(
                audit_id=audit_id,
                status="failed",
                inbound_done=0,
                inbound_failed=0,
                inbound_total=0,
                error="undo window expired (5 min)",
            )

        old_path = audit_row.payload.get("old_path")
        new_path = audit_row.payload.get("new_path")

        # Plan + execute the reverse rename (new_path → old_path)
        reverse_plan = await self.plan(new_path, old_path, f"system:undo({actor})")
        result = await self.execute(reverse_plan.audit_id)
        return result
