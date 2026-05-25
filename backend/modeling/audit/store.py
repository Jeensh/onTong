"""Entity change log store — 단순 insert + 최근 변경 조회."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import desc, select

from backend.modeling.persistence.database import session_scope
from backend.modeling.audit.orm import EntityChangeLogRow

logger = logging.getLogger(__name__)


def log_change(
    repo_id: str,
    entity_kind: str,
    entity_id: str,
    change_kind: str,
    *,
    changed_by: str | None = None,
    details: Any = None,
) -> None:
    """단일 변경 기록. 실패해도 caller 흐름 안 깨도록 swallow."""
    try:
        with session_scope() as s:
            s.add(EntityChangeLogRow(
                repo_id=repo_id,
                entity_kind=entity_kind,
                entity_id=entity_id,
                change_kind=change_kind,
                changed_at=datetime.utcnow(),
                changed_by=changed_by,
                details=json.dumps(details, ensure_ascii=False) if details is not None else None,
            ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_change failed: %s", exc)


def log_changes_bulk(rows: Iterable[dict]) -> None:
    """bulk insert — recommend persist 같은 대량 호출용."""
    try:
        now = datetime.utcnow()
        with session_scope() as s:
            for r in rows:
                s.add(EntityChangeLogRow(
                    repo_id=r["repo_id"],
                    entity_kind=r["entity_kind"],
                    entity_id=r["entity_id"],
                    change_kind=r["change_kind"],
                    changed_at=r.get("changed_at", now),
                    changed_by=r.get("changed_by"),
                    details=json.dumps(r["details"], ensure_ascii=False) if r.get("details") is not None else None,
                ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("log_changes_bulk failed: %s", exc)


def count_recent_changes(repo_id: str, *, since_days: int = 7) -> dict[tuple[str, str], int]:
    """recent changes 집계 — (entity_kind, entity_id) → count.

    Coverage view 의 'recent' lens 가 사용. 사용자 변경만 (changed_by IS NOT NULL).
    """
    threshold = datetime.utcnow() - timedelta(days=since_days)
    with session_scope() as s:
        rows = s.execute(
            select(EntityChangeLogRow).where(
                EntityChangeLogRow.repo_id == repo_id,
                EntityChangeLogRow.changed_at >= threshold,
                EntityChangeLogRow.changed_by.isnot(None),
            )
        ).scalars().all()
    out: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.entity_kind, r.entity_id)
        out[key] = out.get(key, 0) + 1
    return out


def recently_changed_ids(
    repo_id: str,
    entity_kind: str,
    *,
    since_days: int = 7,
    user_only: bool = True,
) -> set[str]:
    """특정 entity_kind 안에서 최근 변경된 entity_id set."""
    threshold = datetime.utcnow() - timedelta(days=since_days)
    with session_scope() as s:
        stmt = select(EntityChangeLogRow.entity_id).where(
            EntityChangeLogRow.repo_id == repo_id,
            EntityChangeLogRow.entity_kind == entity_kind,
            EntityChangeLogRow.changed_at >= threshold,
        )
        if user_only:
            stmt = stmt.where(EntityChangeLogRow.changed_by.isnot(None))
        return set(s.execute(stmt).scalars().all())


def list_changes_for_entity(
    repo_id: str, entity_kind: str, entity_id: str, *, limit: int = 50,
) -> list[dict]:
    """단일 entity 의 변경 내역 — Detail panel 의 history 탭에 노출 가능."""
    with session_scope() as s:
        rows = s.execute(
            select(EntityChangeLogRow).where(
                EntityChangeLogRow.repo_id == repo_id,
                EntityChangeLogRow.entity_kind == entity_kind,
                EntityChangeLogRow.entity_id == entity_id,
            ).order_by(desc(EntityChangeLogRow.changed_at)).limit(limit)
        ).scalars().all()
    return [
        {
            "id": r.id,
            "change_kind": r.change_kind,
            "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            "changed_by": r.changed_by,
            "details": json.loads(r.details) if r.details else None,
        }
        for r in rows
    ]


__all__ = ["log_change", "log_changes_bulk", "count_recent_changes", "recently_changed_ids", "list_changes_for_entity"]
