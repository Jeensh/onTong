"""Phase 7-E — Auto-PR API.

POST /api/simulation/auto_pr/suggest — 실패 케이스 + 자바 메서드 → 패치 제안 + unified diff.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..auto_pr.suggester import AutoPRRequest, FailedCase, suggest_patch
from ..transpile.parser import extract_method

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulation/auto_pr", tags=["simulation-auto-pr"])

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED_ROOTS = [
    _PROJECT_ROOT / "sample-repos",
    _PROJECT_ROOT / "backend",
]


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_safe_path(rel: str) -> Path:
    p = (_PROJECT_ROOT / rel).resolve()
    if not any(_within(p, root.resolve()) for root in _ALLOWED_ROOTS):
        raise HTTPException(400, f"path outside allowed roots: {rel}")
    if not p.exists():
        raise HTTPException(404, f"file not found: {rel}")
    if p.suffix != ".java":
        raise HTTPException(400, f"not a .java file: {rel}")
    return p


# ─── schemas ───────────────────────────────────────────────────────


class FailedCaseDto(BaseModel):
    case_id: str
    description: str = ""
    case_type: str = "normal"
    expected: dict = Field(default_factory=dict)
    actual_output: dict = Field(default_factory=dict)


class SuggestRequest(BaseModel):
    java_path: str = Field(..., description="프로젝트 루트 기준 자바 파일 상대 경로.")
    method_name: str
    class_name: Optional[str] = None
    failures: list[FailedCaseDto] = Field(..., description="실패 케이스 목록.")
    prefer_llm: bool = True


class SuggestResponse(BaseModel):
    suggestion: dict
    unified_diff: str
    java_summary: dict


# ─── endpoints ─────────────────────────────────────────────────────


@router.post("/suggest")
async def suggest(req: SuggestRequest) -> SuggestResponse:
    if not req.failures:
        raise HTTPException(400, "failures must not be empty")
    p = _resolve_safe_path(req.java_path)
    info = extract_method(p, req.method_name, class_name=req.class_name)
    if info is None:
        raise HTTPException(404, f"method '{req.method_name}' not found in {req.java_path}")

    failures = [
        FailedCase(
            case_id=f.case_id,
            description=f.description,
            case_type=f.case_type,
            expected=f.expected,
            actual_output=f.actual_output,
        )
        for f in req.failures
    ]

    auto_req = AutoPRRequest(info=info, failures=failures, prefer_llm=req.prefer_llm)
    suggestion, diff = await suggest_patch(auto_req)

    return SuggestResponse(
        suggestion=suggestion.model_dump(),
        unified_diff=diff,
        java_summary={
            "class_name": info.class_name,
            "method_name": info.method_name,
            "signature": info.signature(),
            "lines": f"{info.signature_line}-{info.end_line}",
            "javadoc": info.javadoc[:300],
        },
    )
