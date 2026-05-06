"""Capability 3 — Interview Question Generator (Sonnet, STANDARD tier).

Round 5 Step 13 §1: "인터뷰 설계 (Q 분해, 1~2줄 답변용 placeholder)".

Takes the hypothesis from capability 2 and turns it into a batch of
short, friendly Korean questions in the Step-4 style:
  - "내 추측" hint per question
  - 1-2줄 답변 placeholder
  - skip-OK on most
  - critical/standard/optional importance for ordering

Public API:
    design_interview(hypothesis, *, session_id, turn_no) -> InterviewBatch
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "interview"
TIER = ModelTier.STANDARD

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "interview.md"


# ── Output schema ────────────────────────────────────────────────────


Importance = Literal["critical", "standard", "optional"]


class InterviewQuestion(BaseModel):
    id: str = Field(..., description="snake_case key threaded back into answers")
    prompt: str = Field(..., description="Korean, one short sentence")
    my_guess: str | None = Field(None, description="AI's current best guess, Korean, short")
    placeholder: str = Field(..., description="Korean example answer to nudge the user")
    options: list[str] | None = Field(None, description="Optional ≤4 Korean alternatives")
    importance: Importance = "standard"
    skip_ok: bool = True


class InterviewBatch(BaseModel):
    intro: str = Field(..., description="One or two friendly Korean sentences")
    questions: list[InterviewQuestion] = Field(default_factory=list)


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _agent() -> Agent[None, InterviewBatch]:
    return Agent(
        get_authoring_model(TIER),
        output_type=InterviewBatch,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_hypothesis_for_prompt(h: EntityHypothesis) -> str:
    """Compact, faithful render of the hypothesis for the interview designer."""
    lines: list[str] = [
        f"# Entity hypothesis (confidence={h.confidence:.2f})",
        f"표시명 (Korean): {h.candidate_term_korean}",
        f"식별자 (English): {h.candidate_term_english}",
        f"domain_role: {h.domain_role}",
        "",
        "## PK 의 도메인 의미",
        h.pk_role_summary,
    ]
    if h.column_notes:
        lines.append("\n## 컬럼별 메모")
        for c in h.column_notes:
            lines.append(f"  - {c.db_column}: {c.note}")
    if h.relations_hint:
        lines.append("\n## 관계 단서 (가설)")
        for r in h.relations_hint:
            lines.append(f"  - {r}")
    if h.assumptions:
        lines.append("\n## 가설이 의존하는 추정")
        for a in h.assumptions:
            lines.append(f"  - {a}")
    if h.concerns:
        lines.append("\n## 우려 사항")
        for c in h.concerns:
            lines.append(f"  - {c}")
    if h.domain_questions:
        lines.append("\n## 가설이 이미 적은 follow-up 질문 후보 (참고용 — 더 다듬어주세요)")
        for q in h.domain_questions:
            lines.append(f"  - {q}")
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def design_interview(
    hypothesis: EntityHypothesis,
    *,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
) -> InterviewBatch:
    """Turn an entity hypothesis into a Step-4 style interview batch.

    `user_comment` (F3): correction text from ✏ 수정 on prior interview card.
    """
    user_prompt = _format_hypothesis_for_prompt(hypothesis)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (인터뷰 질문을 다듬어주세요)\n"
            + user_comment.strip()
        )

    with cost_mod.measure() as t:
        result = await _agent().run(user_prompt, model_settings=_settings())

    usage = _usage_from_result(result.usage())
    cost_mod.log_call(
        session_id=session_id,
        turn_no=turn_no,
        capability=CAPABILITY_NAME,
        tier=TIER,
        model_id=get_model_id(TIER),
        usage=usage,
        duration_ms=t["elapsed_ms"],
    )
    return result.output


def reset_caches() -> None:
    _system_prompt.cache_clear()
    _agent.cache_clear()
