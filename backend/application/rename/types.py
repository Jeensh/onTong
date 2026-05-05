"""Dataclasses for rename plans, results, audit records."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImpactItem:
    """One inbound document that will be patched during rename."""
    source_path: str
    ref_count: int           # how many refs from this source point to old_path


@dataclass(frozen=True)
class RenamePlan:
    """Result of plan stage. Returned by /rename-preview."""
    audit_id: str
    old_path: str
    new_path: str
    actor: str
    inbound_count: int                 # total refs across all sources (NOT unique sources)
    unique_inbound_sources: int        # distinct source documents
    confirm_required: bool             # True if inbound_count > confirm_threshold
    estimated_seconds: float
    impact_items: list[ImpactItem]     # truncated to first N (e.g. 100) for UI


@dataclass
class RenameAuditRow:
    """A single row in wiki_audit."""
    id: int
    op: str                             # "rename" | "move" | "folder_move" | "bulk" | "undo_rename"
    actor: str
    payload: dict                       # JSON: {old_path, new_path, inbound_count, ...}
    started_at: float                   # epoch
    finished_at: float | None
    status: str                         # "running" | "success" | "partial" | "failed"
    error: str | None


@dataclass
class RenameJobRow:
    """A single row in wiki_jobs (one per inbound to patch / chunk to update)."""
    id: int
    audit_id: int
    kind: str                           # "patch_inbound" | "update_chunk_meta" | ...
    target_path: str
    status: str                         # "pending" | "running" | "done" | "failed"
    attempts: int
    last_error: str | None
    updated_at: float


@dataclass(frozen=True)
class RenameResult:
    """Final outcome of execute()."""
    audit_id: str
    status: str                         # "queued" | "success" | "partial" | "failed"
    inbound_done: int
    inbound_failed: int
    inbound_total: int
    error: str | None = None
