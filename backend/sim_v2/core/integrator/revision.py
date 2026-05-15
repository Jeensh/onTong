"""Revision pointer + lineage chain — ADR-003 §5.

Revision = merged proposal 의 fixed point. R5 (수정 전후 비교) 의 기준.

Public API:
    - Revision — pydantic model with parent_revision chain
    - RevisionStore — in-memory store + lineage traversal
    - FixtureBaseline — per-fixture output + measured tolerance (Lesson 5 §4.4)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FixtureBaseline(BaseModel):
    """Per-fixture revision baseline — Lesson 5 §4.4.

    Revision N 의 fixture_baseline 이 revision N+1 의 oracle 비교 기준.
    """
    model_config = ConfigDict(frozen=True)

    fixture_id:           str
    output:               Any
    trace:                list[dict[str, Any]] = Field(default_factory=list)
    measured_tolerance:   dict[str, float] = Field(default_factory=dict)
    # measured_tolerance: per-action 의 실측 drift (Lesson 5 §3.1 의 hardcode 회피)


class Revision(BaseModel):
    """Merged proposal 의 revision pointer.

    Lineage: parent_revision → new revision (Phase α tag 와 동일 pattern, but DB-level).
    R5 mechanism = lineage 의 baseline diff (ADR-003 §5).
    """
    id:                str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id:       str

    # 변경 실 적용 위치 (3-tier git/migration reference)
    ontology_revision: str       # ontology git tag / migration version
    code_revision:     str       # source code git commit
    schema_revision:   str       # DDL migration version (ADR-004)

    # Lineage
    parent_revision:   str | None = None
    fixture_baselines: dict[str, FixtureBaseline] = Field(default_factory=dict)
    # post-change baseline (next proposal 의 oracle 비교 기준)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str


class RevisionStore:
    """In-memory revision store + lineage chain.

    Production 시 persistent (SQLite / git tags) — 현재는 sprint W2-W3 인-메모리.
    """

    def __init__(self) -> None:
        self._revisions: dict[str, Revision] = {}

    def add(self, revision: Revision) -> None:
        if revision.id in self._revisions:
            raise ValueError(f"Revision {revision.id!r} already exists")
        if revision.parent_revision and revision.parent_revision not in self._revisions:
            raise ValueError(
                f"Parent revision {revision.parent_revision!r} not found"
            )
        self._revisions[revision.id] = revision

    def get(self, revision_id: str) -> Revision | None:
        return self._revisions.get(revision_id)

    def lineage(self, revision_id: str) -> list[Revision]:
        """Walk parent chain from leaf → root. First element = revision_id itself."""
        chain: list[Revision] = []
        current_id: str | None = revision_id
        while current_id is not None:
            rev = self._revisions.get(current_id)
            if rev is None:
                raise ValueError(f"Broken lineage at {current_id!r}")
            chain.append(rev)
            current_id = rev.parent_revision
        return chain

    def latest_for_plugin(self, plugin: str) -> Revision | None:
        """Most recent revision whose ontology/code/schema refers to plugin (heuristic)."""
        # Simple impl — plugin tag often embedded in revision string. Production 시 별도 metadata.
        candidates = [
            r for r in self._revisions.values()
            if plugin in r.ontology_revision or plugin in r.code_revision
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: r.created_at)

    def count(self) -> int:
        return len(self._revisions)


__all__ = ["FixtureBaseline", "Revision", "RevisionStore"]
