"""`audit_patch` context manager — Wave 2 hook surface for PATCH handlers.

사용 패턴 (Wave 2 가 queue_actions_api.py 에 끼워 넣을 형태):

    >>> from backend.modeling.audit import audit_patch
    >>> from backend.modeling.persistence.database import session_scope
    >>>
    >>> with session_scope() as s, audit_patch(
    ...     session=s, repo_id=repo_id, entity_kind="term",
    ...     entity_id=fqn, user_id="alice",
    ... ) as ctx:
    ...     row = s.execute(...).scalar_one_or_none()
    ...     ctx.set_before(_orm_to_dict(row))
    ...     # ... mutate row ...
    ...     ctx.set_after(_orm_to_dict(row))

`__exit__` 시점에 before/after 가 모두 set 되어 있으면 `record_patch` 호출.
하나라도 비어 있으면 audit 안 씀 (no-op). 예외 발생 시도 silent — main flow
는 `session_scope` 의 rollback 에 맡김.

다른 액션 (confirm / unconfirm 등) 은 직접 `record_audit` 호출 권장.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from sqlalchemy.orm import Session

from backend.modeling.audit.recorder import record_patch

logger = logging.getLogger(__name__)


@dataclass
class AuditPatchContext:
    repo_id: str
    entity_kind: str
    entity_id: str
    user_id: str | None
    _before: dict[str, Any] | None = field(default=None, init=False)
    _after: dict[str, Any] | None = field(default=None, init=False)

    def set_before(self, snapshot: dict[str, Any] | None) -> None:
        """변경 직전 entity 상태 (dict). None 이면 audit 안 씀."""
        self._before = dict(snapshot) if snapshot else None

    def set_after(self, snapshot: dict[str, Any] | None) -> None:
        """변경 직후 entity 상태 (dict). None 이면 audit 안 씀."""
        self._after = dict(snapshot) if snapshot else None

    @property
    def has_both(self) -> bool:
        return self._before is not None and self._after is not None


@contextmanager
def audit_patch(
    *,
    session: Session,
    repo_id: str,
    entity_kind: str,
    entity_id: str,
    user_id: str | None,
) -> Iterator[AuditPatchContext]:
    """PATCH handler 용 context manager — before/after 를 ctx 에 채우면 자동 audit 기록.

    사용 예는 모듈 docstring 참고.
    """
    ctx = AuditPatchContext(
        repo_id=repo_id,
        entity_kind=entity_kind,
        entity_id=entity_id,
        user_id=user_id,
    )
    try:
        yield ctx
    finally:
        try:
            if ctx.has_both:
                assert ctx._before is not None and ctx._after is not None  # narrow
                record_patch(
                    session,
                    repo_id=repo_id,
                    entity_kind=entity_kind,
                    entity_id=entity_id,
                    before_dict=ctx._before,
                    after_dict=ctx._after,
                    user_id=user_id,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "audit_patch: finalize failed (%s/%s/%s): %s",
                repo_id, entity_kind, entity_id, e,
            )


__all__ = ("audit_patch", "AuditPatchContext")
