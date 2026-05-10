"""Auto-PR — 자바 방어 코드 자동 생성.

LLM 우선 + fallback graceful (LLM 미가용 시 결정론적 stub 패치).
unified_diff 는 stdlib difflib 으로 생성.
"""

from __future__ import annotations

import difflib
import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..transpile.parser import JavaMethodInfo

logger = logging.getLogger(__name__)


class PatchSuggestion(BaseModel):
    """LLM 이 생성한 패치 제안."""

    rationale: str = Field(..., description="왜 이 가드를 추가하는지 1~3문장 (한국어).")
    patched_method: str = Field(
        ...,
        description=(
            "패치된 메서드 전체 (자바 원본 메서드 본문을 대체할 코드)."
            " import 가 필요하면 주석으로 명시."
        ),
    )
    additional_imports: list[str] = Field(
        default_factory=list,
        description="패치에 필요한 추가 import 목록 (예: 'java.util.Optional').",
    )
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="패치 신뢰도 (0~1).")
    method: str = Field("fallback", description="'llm' 또는 'fallback'.")
    risk_notes: list[str] = Field(
        default_factory=list,
        description="이 패치 적용 시 주의할 점 (성능, side effect, 다른 케이스 깨짐 가능성 등).",
    )


@dataclass
class FailedCase:
    """LLM 에 전달할 실패 케이스 요약."""

    case_id: str
    description: str
    case_type: str  # normal / boundary / error / performance
    expected: dict
    actual_output: dict


@dataclass
class AutoPRRequest:
    info: JavaMethodInfo
    failures: list[FailedCase]
    prefer_llm: bool = True
    max_failures_in_prompt: int = 5  # 너무 많은 케이스는 LLM 부담


# ─── unified diff ──────────────────────────────────────────────────


def make_unified_diff(
    original: str,
    patched: str,
    *,
    fromfile: str = "original.java",
    tofile: str = "patched.java",
) -> str:
    """두 자바 본문 사이의 unified diff 텍스트."""
    orig_lines = original.splitlines(keepends=True)
    new_lines = patched.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
        n=3,
    )
    return "".join(diff)


# ─── LLM 경로 ──────────────────────────────────────────────────────


_SYSTEM_PROMPT = """당신은 Slab 설계 (slab-design Java) 같은 제조업 비즈니스 룰 시스템의 시니어 자바 개발자입니다.

샌드박스 시뮬에서 특정 입력으로 자바 메서드가 깨졌습니다 (실패 케이스).
**이 입력에서도 안 깨지도록 자바 방어 코드를 보강** 하세요.

규칙
----
1. 출력은 **메서드 전체** (시그니처부터 닫는 `}` 까지). 클래스 단위 X.
2. 자바 원본 코드 스타일/포매팅 유지. 변수명도 그대로.
3. 가드 추가는 다음 우선순위:
   - early-return (입력이 부적절하면 throw 대신 안전한 기본값)
   - 명시적 null check + 의미 있는 예외 메시지
   - try-catch 로 감싸 fallback 값 반환
4. 자바 21 / Spring Boot 3 문법 OK. 외부 라이브러리 추가 금지.
5. rationale: 1~3문장 한국어로 어떤 가드를 왜 추가했는지.
6. risk_notes: 이 패치가 다른 케이스를 깨뜨릴 가능성 / 성능 영향 등 1~3개.
7. confidence: 단순 null check (0.85+), 복잡한 분기 추가 (0.5~0.7), 룰 자체 변경 필요해 보이면 (0.3~).
"""


def _format_failures(failures: list[FailedCase], limit: int) -> str:
    """LLM prompt 에 들어갈 실패 케이스 요약."""
    out: list[str] = []
    for f in failures[:limit]:
        out.append(
            f"케이스 {f.case_id} ({f.case_type})\n"
            f"  설명: {f.description}\n"
            f"  expected: {f.expected}\n"
            f"  actual:   {f.actual_output}"
        )
    if len(failures) > limit:
        out.append(f"... (+{len(failures) - limit} 건 더 있음, 위 {limit}건만 LLM 에 전달)")
    return "\n\n".join(out)


async def _llm_suggest(req: AutoPRRequest) -> Optional[PatchSuggestion]:
    """LLM 호출. 실패 시 None."""
    try:
        from pydantic_ai import Agent
        from backend.application.agent.llm_factory import get_model
    except Exception as e:
        logger.warning(f"pydantic_ai unavailable: {e}")
        return None

    try:
        model = get_model()
    except Exception as e:
        logger.warning(f"LLM model not configured: {e}")
        return None

    info = req.info
    fails_block = _format_failures(req.failures, req.max_failures_in_prompt)

    user_prompt = (
        f"**자바 메서드 원본** ({info.class_name}.{info.method_name}, {info.file_path}):\n"
        f"```java\n"
        f"{info.signature()} {{\n"
        f"{info.body_source}\n"
        f"}}\n"
        f"```\n\n"
        f"**실패 케이스 ({len(req.failures)}건)**:\n"
        f"{fails_block}\n\n"
        f"위 입력에서도 깨지지 않도록 메서드를 보강해 주세요."
    )

    try:
        agent = Agent(
            model,
            output_type=PatchSuggestion,
            system_prompt=_SYSTEM_PROMPT,
        )
        result = await agent.run(user_prompt)
        suggestion = result.output
        suggestion.method = "llm"
        if suggestion.confidence is None or suggestion.confidence == 0:
            suggestion.confidence = 0.7
        return suggestion
    except Exception as e:
        logger.warning(f"LLM auto-pr suggest failed: {e}")
        return None


# ─── Fallback ──────────────────────────────────────────────────────


def _fallback_suggestion(req: AutoPRRequest) -> PatchSuggestion:
    """LLM 미가용 — 실패 케이스를 자바 주석으로 보존하는 stub 패치."""
    info = req.info
    fails = req.failures[: req.max_failures_in_prompt]
    case_comments = "\n".join(
        f"        // - {f.case_id} ({f.case_type}): {f.description}"
        for f in fails
    )
    if len(req.failures) > req.max_failures_in_prompt:
        case_comments += f"\n        // - +{len(req.failures) - req.max_failures_in_prompt}건 더 있음"

    # 원본 메서드 위에 주석 + body 그대로 보존하는 stub
    patched = (
        f"    {info.signature()} {{\n"
        f"        // [Auto-PR fallback] LLM 미가용 — 수작업 패치 필요.\n"
        f"        // 아래 입력에서 깨졌습니다 (운영자 검토 후 가드 추가 요망):\n"
        f"{case_comments}\n"
        f"\n"
        f"{info.body_source.removeprefix('{').removesuffix('}').rstrip()}\n"
        f"    }}"
    )
    return PatchSuggestion(
        rationale=(
            "LLM 미가용 환경 — 실패 케이스를 자바 주석으로 보존한 stub 패치를 생성했습니다. "
            "운영자가 위 입력 조건에 맞춰 직접 가드 (null check / early-return / try-catch) 를 추가해 주세요."
        ),
        patched_method=patched,
        additional_imports=[],
        confidence=0.15,
        method="fallback",
        risk_notes=[
            "이 stub 은 실제 가드를 추가하지 않습니다 — 자바 동작은 변하지 않음.",
            "실패 케이스 컨텍스트만 주석으로 첨부 — 이후 수동 패치 시 참조용.",
        ],
    )


# ─── 진입점 ────────────────────────────────────────────────────────


async def suggest_patch(req: AutoPRRequest) -> tuple[PatchSuggestion, str]:
    """실패 케이스 → LLM 자바 패치 제안 + unified_diff.

    Returns:
        (PatchSuggestion, unified_diff_text)
    """
    suggestion: Optional[PatchSuggestion] = None
    if req.prefer_llm and os.getenv("SIMULATION_DISABLE_LLM_AUTO_PR", "0") != "1":
        suggestion = await _llm_suggest(req)
    if suggestion is None:
        suggestion = _fallback_suggestion(req)

    # original 메서드 본문 — signature + body
    info = req.info
    original = f"    {info.signature()} {{\n{info.body_source.lstrip('{').rstrip('}')}\n    }}"
    diff = make_unified_diff(
        original.strip() + "\n",
        suggestion.patched_method.strip() + "\n",
        fromfile=f"{info.class_name}.{info.method_name} (original)",
        tofile=f"{info.class_name}.{info.method_name} (patched)",
    )
    return suggestion, diff
