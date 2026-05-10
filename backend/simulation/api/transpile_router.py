"""Phase 7-D — Java→Python transpile API.

Endpoints:
  GET  /api/simulation/transpile/methods  — 자바 파일 메서드 목록
  POST /api/simulation/transpile/preview  — LLM 변환 + 동치성 검증 (저장 안 함)
  POST /api/simulation/transpile/save     — sandbox/steps/<name>.py 저장
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..transpile import (
    extract_method,
    list_methods,
    transpile_method,
    shadow_compare,
)
from ..transpile.equivalence import structural_check
from ..transpile.llm_transpile import TranspileRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/simulation/transpile", tags=["simulation-transpile"])


# 안전 가드 — 절대 경로 traversal 차단. 자바 파일은 sample-repos/ 또는 사용자 지정 화이트리스트에서만.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED_ROOTS = [
    _PROJECT_ROOT / "sample-repos",
    _PROJECT_ROOT / "backend",  # 테스트용 fixture 자바 파일 허용
]


def _resolve_safe_path(rel: str) -> Path:
    p = (_PROJECT_ROOT / rel).resolve()
    if not any(_within(p, root.resolve()) for root in _ALLOWED_ROOTS):
        raise HTTPException(400, f"path outside allowed roots: {rel}")
    if not p.exists():
        raise HTTPException(404, f"file not found: {rel}")
    if p.suffix != ".java":
        raise HTTPException(400, f"not a .java file: {rel}")
    return p


def _within(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


# ─── schemas ───────────────────────────────────────────────────────


class MethodInfo(BaseModel):
    class_name: str
    method_name: str
    return_type: str
    parameters: list[tuple[str, str]] = Field(default_factory=list)
    modifiers: list[str] = Field(default_factory=list)
    signature_line: int = 0
    end_line: int = 0
    javadoc: str = ""


class PreviewRequest(BaseModel):
    java_path: str = Field(..., description="프로젝트 루트 기준 상대 경로 (예: 'sample-repos/.../X.java').")
    method_name: str
    class_name: Optional[str] = None
    target_step_id: Optional[str] = Field(None, description="권장 step_id. 미지정 시 LLM 추천.")
    reference_step_id: Optional[str] = Field(
        None,
        description="기존 미러 step ID — shadow 비교 활성. 없으면 structural check 만.",
    )
    sample_inputs: list[dict] = Field(
        default_factory=list,
        description="shadow 비교용 inputs 샘플. 비면 reference 가 있어도 structural 만 수행.",
    )
    prefer_llm: bool = True


class PreviewResponse(BaseModel):
    draft: dict
    equivalence: dict
    java_summary: dict


class SaveRequest(BaseModel):
    step_id: str
    function_name: str
    python_source: str
    overwrite: bool = False


class SaveResponse(BaseModel):
    saved_path: str
    step_id: str
    function_name: str


# ─── endpoints ─────────────────────────────────────────────────────


@router.get("/methods")
async def get_methods(java_path: str) -> list[MethodInfo]:
    """파일의 모든 메서드 시그니처 (body 제외 — 가벼움)."""
    p = _resolve_safe_path(java_path)
    try:
        infos = list_methods(p)
    except RuntimeError as e:
        # tree_sitter unavailable
        raise HTTPException(503, str(e))
    out: list[MethodInfo] = []
    for info in infos:
        out.append(
            MethodInfo(
                class_name=info.class_name,
                method_name=info.method_name,
                return_type=info.return_type,
                parameters=info.parameters,
                modifiers=info.modifiers,
                signature_line=info.signature_line,
                end_line=info.end_line,
                javadoc=info.javadoc[:300],
            )
        )
    return out


@router.post("/preview")
async def preview_transpile(req: PreviewRequest) -> PreviewResponse:
    """LLM 변환 + 동치성 검증. 디스크 저장 없음."""
    p = _resolve_safe_path(req.java_path)
    info = extract_method(p, req.method_name, class_name=req.class_name)
    if info is None:
        raise HTTPException(404, f"method '{req.method_name}' not found in {req.java_path}")

    draft = await transpile_method(
        TranspileRequest(
            info=info,
            target_step_id=req.target_step_id,
            prefer_llm=req.prefer_llm,
        )
    )

    # 동치성: reference + samples 모두 있으면 shadow, 아니면 structural
    if req.reference_step_id and req.sample_inputs:
        rep = shadow_compare(
            draft.python_source,
            draft.function_name,
            req.reference_step_id,
            req.sample_inputs,
        )
    else:
        rep = structural_check(draft.python_source, draft.function_name)

    return PreviewResponse(
        draft=draft.model_dump(),
        equivalence=rep.to_json(),
        java_summary={
            "class_name": info.class_name,
            "method_name": info.method_name,
            "signature": info.signature(),
            "lines": f"{info.signature_line}-{info.end_line}",
            "javadoc": info.javadoc[:300],
        },
    )


@router.post("/save")
async def save_transpiled(req: SaveRequest) -> SaveResponse:
    """변환 결과를 sandbox/steps/<step_id>.py 로 저장.

    안전:
      - 파일명 sanitize (snake_case 알파벳+숫자+_ 만)
      - structural check 강제 (외부 import 금지 등)
      - overwrite=False 면 기존 파일 보호
    """
    safe_name = "".join(c for c in req.step_id if c.isalnum() or c == "_")
    if not safe_name or not safe_name[0].isalpha():
        raise HTTPException(400, "step_id must start with alpha and contain only [a-z0-9_]")

    rep = structural_check(req.python_source, req.function_name)
    if not rep.passed:
        raise HTTPException(
            400,
            f"structural check failed — refused to save. errors={rep.structural_errors}",
        )

    out_dir = _PROJECT_ROOT / "backend" / "simulation" / "sandbox" / "steps_transpiled"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe_name}.py"
    if out_path.exists() and not req.overwrite:
        raise HTTPException(409, f"file already exists: {out_path}. use overwrite=true to replace.")

    out_path.write_text(req.python_source, encoding="utf-8")
    logger.info(f"transpile saved: {out_path}")

    return SaveResponse(
        saved_path=str(out_path.relative_to(_PROJECT_ROOT)),
        step_id=safe_name,
        function_name=req.function_name,
    )
