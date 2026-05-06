"""Capability 4 — Answer Absorber (Sonnet, STANDARD tier).

Round 5 Step 13 §1: "도메인 답변 흡수 (자유서술 → 항목별)".

Takes the InterviewBatch the AI just sent + the user's free-form Korean
reply, and shapes it into per-question structured answers so downstream
capabilities (option_proposer / gap_detector) can consume without re-parsing.

Public API:
    absorb_answers(batch, user_reply, *, session_id, turn_no) -> AbsorbedAnswers
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.capabilities.interview import InterviewBatch
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "answer_absorber"
TIER = ModelTier.STANDARD

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "answer_absorption.md"


# ── Output schema ────────────────────────────────────────────────────


class AbsorbedAnswer(BaseModel):
    question_id: str
    raw_text: str = Field(
        "", description="User's exact verbatim span; '' if unanswered"
    )
    normalized: str = Field(
        "", description="One-line Korean summary; '' if unanswered"
    )
    is_unknown: bool = False
    picked_option: str | None = None
    contradicts_my_guess: bool = False
    contradicts_note: str | None = None


class AbsorbedAnswers(BaseModel):
    per_question: dict[str, AbsorbedAnswer] = Field(default_factory=dict)
    unanswered: list[str] = Field(default_factory=list)
    emergent_facts: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _agent() -> Agent[None, AbsorbedAnswers]:
    return Agent(
        get_authoring_model(TIER),
        output_type=AbsorbedAnswers,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_for_prompt(batch: InterviewBatch, user_reply: str) -> str:
    """Render the batch + user reply for the absorber.

    The questions block lists id / prompt / my_guess / options so the LLM has
    every signal needed to map free-form prose back to ids.
    """
    lines: list[str] = ["# Interview batch (most recent)"]
    if batch.intro:
        lines.append(f"intro: {batch.intro}")
    lines.append("\n## Questions")
    for q in batch.questions:
        lines.append(f"- id: {q.id}")
        lines.append(f"  prompt: {q.prompt}")
        if q.my_guess:
            lines.append(f"  my_guess: {q.my_guess}")
        if q.options:
            lines.append(f"  options: {q.options}")

    lines.append("\n# User reply (verbatim — Korean, may be unstructured)")
    lines.append(user_reply.strip() or "(empty)")
    return "\n".join(lines)


def _ensure_every_id_present(
    out: AbsorbedAnswers, batch: InterviewBatch
) -> AbsorbedAnswers:
    """Defensive: guarantee per_question has an entry for every batch id.

    The model is instructed to do this, but if it slips a question we want
    downstream capabilities to see a deterministic 'unanswered' marker rather
    than KeyError.
    """
    expected_ids = [q.id for q in batch.questions]
    pq = dict(out.per_question)
    for qid in expected_ids:
        if qid not in pq:
            pq[qid] = AbsorbedAnswer(question_id=qid, is_unknown=True)
    # Recompute unanswered from scratch for consistency.
    unanswered = [
        qid
        for qid in expected_ids
        if pq[qid].is_unknown or not pq[qid].normalized.strip()
    ]
    return AbsorbedAnswers(
        per_question=pq,
        unanswered=unanswered,
        emergent_facts=out.emergent_facts,
        contradictions=out.contradictions,
    )


# ── Public API ───────────────────────────────────────────────────────


async def absorb_answers(
    batch: InterviewBatch,
    user_reply: str,
    *,
    session_id: str,
    turn_no: int,
) -> AbsorbedAnswers:
    """Reshape a free-form Korean reply into per-question structured answers."""
    user_prompt = _format_for_prompt(batch, user_reply)

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
    return _ensure_every_id_present(result.output, batch)


def reset_caches() -> None:
    _system_prompt.cache_clear()
    _agent.cache_clear()
