"""Audit recorder helpers — write `AuditLogRow` rows from inside `session_scope()`.

Two entry points:
- `record_audit` : single entity-level event (confirm / unconfirm / created / deleted),
  or a single field-level event when caller already knows what changed.
- `record_patch` : diff a before-dict vs after-dict and emit one row per changed field.
  PATCH handlers are the primary user (Wave 2 hook).

설계 원칙:
- `session.add()` 만 호출. commit 은 호출자의 `session_scope` 가 책임.
- 절대 raise 하지 않음 — audit 실패가 main flow 를 막으면 안 됨. 실패는 logger.warning.
- before/after 가 둘 다 None 이면 row 없이 return (no-op).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.modeling.audit.orm import AuditLogRow

logger = logging.getLogger(__name__)


def _safe_json(obj: Any) -> str:
    """SQLAlchemy ORM 객체 / datetime 등 비-JSON 값을 안전하게 직렬화."""
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        logger.warning("audit: json serialize failed (%s) — falling back to repr", e)
        return json.dumps({"__repr__": repr(obj)}, ensure_ascii=False)


def record_audit(
    session: Session,
    *,
    repo_id: str,
    entity_kind: str,
    entity_id: str,
    field: str | None,
    before: Any,
    after: Any,
    action: str,
    user_id: str | None,
) -> None:
    """단일 audit row 작성. session.add() 만 — commit 은 호출자."""
    try:
        row = AuditLogRow(
            repo_id=repo_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=field,
            before_json=_safe_json(before),
            after_json=_safe_json(after),
            action=action,
            user_id=user_id,
        )
        session.add(row)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "audit: record_audit failed (%s/%s/%s field=%s): %s",
            repo_id, entity_kind, entity_id, field, e,
        )


def record_patch(
    session: Session,
    *,
    repo_id: str,
    entity_kind: str,
    entity_id: str,
    before_dict: dict[str, Any],
    after_dict: dict[str, Any],
    user_id: str | None,
) -> int:
    """before/after dict 를 비교해 변경된 field 마다 row 1개씩 작성.

    Returns 작성된 row 개수 (테스트/디버그 용).
    """
    if not before_dict and not after_dict:
        return 0

    keys = set(before_dict.keys()) | set(after_dict.keys())
    changed = 0
    for k in sorted(keys):
        b = before_dict.get(k)
        a = after_dict.get(k)
        if b == a:
            continue
        record_audit(
            session,
            repo_id=repo_id,
            entity_kind=entity_kind,
            entity_id=entity_id,
            field=k,
            before={k: b},
            after={k: a},
            action="patched",
            user_id=user_id,
        )
        changed += 1
    return changed


__all__ = ("record_audit", "record_patch")
