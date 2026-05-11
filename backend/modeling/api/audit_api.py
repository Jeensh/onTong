"""FastAPI router — audit log read endpoints for modeling section.

Endpoints:
- GET /api/ontology/audit/{entity_kind}/{entity_id}?repo_id=X&limit=50
    이 entity 의 최근 audit row N건 (ts DESC).
- GET /api/ontology/audit/recent?repo_id=X&limit=50
    repo 전체 (또는 모든 repo) 최근 audit row N건.

DTO 직렬화:
- before_json / after_json 은 string 으로 그대로 노출 (FE 가 JSON.parse)
- ts 는 ISO 8601 string
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Path, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.modeling.audit.orm import AuditLogRow
from backend.modeling.persistence.database import session_scope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/audit", tags=["ontology-audit"])

# 허용된 entity_kind — 임의 입력 막아 인덱스 효율 + 오기 방지
_VALID_KINDS = {"term", "action", "rule", "anchor", "code_type"}


class AuditLogDTO(BaseModel):
    id: int
    repo_id: str
    entity_kind: str
    entity_id: str
    field: str | None
    before_json: str
    after_json: str
    action: str
    user_id: str | None
    ts: str            # ISO 8601


def _row_to_dto(row: AuditLogRow) -> AuditLogDTO:
    return AuditLogDTO(
        id=row.id,
        repo_id=row.repo_id,
        entity_kind=row.entity_kind,
        entity_id=row.entity_id,
        field=row.field,
        before_json=row.before_json,
        after_json=row.after_json,
        action=row.action,
        user_id=row.user_id,
        ts=row.ts.isoformat() if row.ts is not None else "",
    )


# NOTE: /recent must be declared before /{entity_kind}/{entity_id} — 그렇지 않으면
# `/recent?repo_id=X` 가 entity_kind="recent" 로 매치 시도. (현재 /recent 는 segment
# 1개라 안 걸리지만, 향후 path 변경 사고 방지 차원에서 명시 순서.)
@router.get("/recent", response_model=list[AuditLogDTO])
def get_recent(
    repo_id: str | None = Query(None, description="optional repo filter"),
    limit: int = Query(50, ge=1, le=500),
) -> list[AuditLogDTO]:
    """repo 전체 (또는 글로벌) 최근 audit row (ts DESC). 짧은 dashboard 용."""
    with session_scope() as s:
        stmt = (
            select(AuditLogRow)
            .order_by(AuditLogRow.ts.desc())
            .limit(limit)
        )
        if repo_id:
            stmt = stmt.where(AuditLogRow.repo_id == repo_id)
        rows = s.execute(stmt).scalars().all()
        return [_row_to_dto(r) for r in rows]


@router.get(
    "/{entity_kind}/{entity_id:path}",
    response_model=list[AuditLogDTO],
)
def get_entity_history(
    entity_kind: str = Path(..., description="term / action / rule / anchor / code_type"),
    entity_id: str = Path(..., description="fqn 또는 anchor id"),
    repo_id: str | None = Query(None, description="optional repo filter"),
    limit: int = Query(50, ge=1, le=500),
) -> list[AuditLogDTO]:
    """entity 단위 최근 audit row (ts DESC).

    `entity_kind` 는 _VALID_KINDS 에 없으면 빈 list 반환 — 404 대신 noisy fallback 방지.
    """
    if entity_kind not in _VALID_KINDS:
        logger.warning("audit: unknown entity_kind queried: %s", entity_kind)
        return []
    with session_scope() as s:
        stmt = (
            select(AuditLogRow)
            .where(
                AuditLogRow.entity_kind == entity_kind,
                AuditLogRow.entity_id == entity_id,
            )
            .order_by(AuditLogRow.ts.desc())
            .limit(limit)
        )
        if repo_id:
            stmt = stmt.where(AuditLogRow.repo_id == repo_id)
        rows = s.execute(stmt).scalars().all()
        return [_row_to_dto(r) for r in rows]


__all__ = ("router",)
