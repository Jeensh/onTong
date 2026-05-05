"""RenameOrchestrator — Plan / Execute / Reconcile (Plan + lock scaffold this dispatch)."""
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
    """Coordinates the end-to-end rename. Plan stage live this dispatch.

    Future dispatches add: full execute() body patching, ChromaDB updates,
    SSE progress events, retry queue, undo.
    """

    def __init__(self, ref_index, audit_store: AuditStore, content_store=None,
                 occ_manager=None, snapshot_store=None) -> None:
        self._ref_index = ref_index
        self._audit = audit_store
        self._content = content_store         # WikiContentService — unused this dispatch
        self._occ = occ_manager
        self._snapshots = snapshot_store

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
        """[scaffolded] — body patching completes in Dispatch B.

        For this dispatch:
        - Acquires source path lock
        - Acquires inbound batch locks (sorted order, deadlock-safe)
        - Records lock acquisition in audit
        - Releases immediately (no actual rename yet)
        - Returns RenameResult(status='queued')
        """
        inbound_paths: list[str] = []
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
            actor = audit_row.actor

            # Source lock (single path)
            src_acquired, src_missed = lock_set_in_order(
                [old_path], f"rename:{actor}", ttl=LOCK_TTL
            )
            if not src_acquired:
                self._audit.update_audit_status(
                    int(audit_id), "failed",
                    error=f"could not acquire source lock: {src_missed}",
                )
                return RenameResult(
                    audit_id=audit_id,
                    status="failed",
                    inbound_done=0,
                    inbound_failed=0,
                    inbound_total=0,
                    error="source locked by another rename",
                )

            # Inbound batch lock (sorted order — deadlock-avoidance)
            try:
                for r in self._ref_index.inbound(old_path):
                    inbound_paths.append(r.source_path)
                inbound_paths = sorted(set(inbound_paths))[:50]  # batch cap

                if inbound_paths:
                    inb_acquired, inb_missed = lock_set_in_order(
                        inbound_paths, f"rename:{actor}", ttl=LOCK_TTL,
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
                            inbound_total=len(inbound_paths),
                            error="inbound lock conflict",
                        )

                # PLACEHOLDER for actual rename: Dispatch B implements 3-3 + 3-4
                logger.info(
                    "Phase 3 Dispatch A: locks acquired for %s + %d inbound. "
                    "(Body patch deferred to Dispatch B.)",
                    old_path, len(inbound_paths),
                )
            finally:
                # Always release inbound locks first, then source
                if inbound_paths:
                    lock_set_release_all(inbound_paths, f"rename:{actor}")
                lock_set_release_all([old_path], f"rename:{actor}")

            # Mark as queued — body patcher pending in Dispatch B
            self._audit.update_audit_status(int(audit_id), "queued")

            return RenameResult(
                audit_id=audit_id,
                status="queued",
                inbound_done=0,
                inbound_failed=0,
                inbound_total=len(inbound_paths),
            )

        except Exception as e:
            logger.error("RenameOrchestrator.execute failed: %s", e, exc_info=True)
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
