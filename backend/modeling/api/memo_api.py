"""FastAPI router — entity memo (자유 형식 참고 메모).

REST:
- GET  /api/ontology/repos/{repo_id}/memos/{kind}/{entity_id:path}
- PUT  /api/ontology/repos/{repo_id}/memos/{kind}/{entity_id:path}

memo 는 ontology data (term/action/realization) 에 영향 없음 — 별도 테이블.
empty body 도 valid (= 메모 비우기).
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.modeling.memos.store import get_memo, upsert_memo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-memo"])


_VALID_KINDS = {"action", "term", "codeType", "rule", "anchor"}


class MemoDTO(BaseModel):
    repo_id: str
    entity_kind: str
    entity_id: str
    body: str
    updated_at: datetime
    updated_by: str | None = None


class MemoUpdate(BaseModel):
    body: str = Field(default="", description="자유 형식 텍스트. 빈 문자열도 허용.")
    updated_by: str | None = None


def _ensure_kind(kind: str) -> None:
    if kind not in _VALID_KINDS:
        raise HTTPException(status_code=400, detail=f"invalid kind={kind!r}; allowed={sorted(_VALID_KINDS)}")


@router.get("/{repo_id}/memos/{kind}/{entity_id:path}", response_model=MemoDTO | None)
def read_memo(repo_id: str, kind: str, entity_id: str) -> MemoDTO | None:
    _ensure_kind(kind)
    m = get_memo(repo_id, kind, entity_id)
    if m is None:
        return None
    return MemoDTO(
        repo_id=m.repo_id,
        entity_kind=m.entity_kind,
        entity_id=m.entity_id,
        body=m.body,
        updated_at=m.updated_at,
        updated_by=m.updated_by,
    )


@router.put("/{repo_id}/memos/{kind}/{entity_id:path}", response_model=MemoDTO)
def write_memo(repo_id: str, kind: str, entity_id: str, body: MemoUpdate) -> MemoDTO:
    _ensure_kind(kind)
    m = upsert_memo(repo_id, kind, entity_id, body.body, updated_by=body.updated_by)
    logger.info(
        "memo upsert: repo=%s kind=%s id=%s len=%d",
        repo_id, kind, entity_id, len(body.body),
    )
    return MemoDTO(
        repo_id=m.repo_id,
        entity_kind=m.entity_kind,
        entity_id=m.entity_id,
        body=m.body,
        updated_at=m.updated_at,
        updated_by=m.updated_by,
    )


__all__ = ["router"]
