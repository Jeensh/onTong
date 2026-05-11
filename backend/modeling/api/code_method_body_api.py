"""FastAPI router — `GET /api/ontology/code-methods/{method_fqn:path}/body`.

Wave C-A peek-modal optimization (2026-05-10). Returns only `body_text`
+ line range for a single CodeMethod, avoiding the full CodeType payload
that `getCodeType(parent)` requires for peek scenarios.

At 5K classes × 100 methods/class scale, fetching a parent CodeType to
read one method body wastes ~99% of the bandwidth. This endpoint stays
under 1KB per response for typical method bodies.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from backend.modeling.code_layer.orm import CodeMethodRow
from backend.modeling.persistence.database import session_scope


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/ontology", tags=["ontology-code-method-body"])


class CodeMethodBodyDTO(BaseModel):
    """Minimal payload for code peek — body + locator."""
    fqn: str
    parent_type_fqn: str
    name: str
    return_type: str
    body_text: str | None
    line_start: int | None
    line_end: int | None


@router.get(
    "/code-methods/{method_fqn:path}/body",
    response_model=CodeMethodBodyDTO,
)
def get_code_method_body(
    method_fqn: str,
    repo_id: str = Query(..., description="repo this method belongs to"),
) -> CodeMethodBodyDTO:
    """Return a single method's body + line range. 404 if not found."""
    with session_scope() as session:
        row = session.execute(
            select(CodeMethodRow).where(
                CodeMethodRow.repo_id == repo_id,
                CodeMethodRow.fqn == method_fqn,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"code method not found: repo_id={repo_id!r} fqn={method_fqn!r}",
            )
        return CodeMethodBodyDTO(
            fqn=row.fqn,
            parent_type_fqn=row.parent_type_fqn,
            name=row.name,
            return_type=row.return_type or "",
            body_text=row.body_text,
            line_start=row.line_start,
            line_end=row.line_end,
        )


__all__ = ("router", "CodeMethodBodyDTO")
