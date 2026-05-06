"""Capability 9 — Archiver (Sonnet for narrative + Python for markdown render).

Round 5 Step 13 §1: "archive 자동 생성 (표·다이어그램)".

Hybrid design:
  - Sonnet generates `summary_korean`, `decisions`, `structure_diagram`
    (the narrative parts that need domain wording).
  - Python deterministically renders the surrounding markdown (title block,
    table headers, code-fence wrapping). This keeps output token count low
    and the markdown structure invariant across runs.

Public API:
    archive_entity_cycle(
        *, hypothesis, answers, accepted_option, names, gaps=None,
        step_number=None, session_id, turn_no
    ) -> ArchiveDocument
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
from backend.application.authoring.capabilities.answer_absorber import AbsorbedAnswers
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.capabilities.gap_detector import GapAnalysis
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.capabilities.naming import NamingDecision
from backend.application.authoring.capabilities.option_proposer import OntologyOption
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "archiver"
TIER = ModelTier.STANDARD

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "archiver.md"


# ── Output schemas ───────────────────────────────────────────────────


ArchiveStatus = Literal["completed", "partial"]


class ArchiveDecision(BaseModel):
    topic_korean: str = Field(..., description='e.g. "모델링 옵션", "명명"')
    decision_korean: str
    rationale_korean: str


class ArchiveBody(BaseModel):
    """LLM-generated narrative parts of the archive."""

    summary_korean: str
    decisions: list[ArchiveDecision] = Field(default_factory=list)
    structure_diagram: str = Field(..., description="6-line ASCII tree of entity shape")


class ArchiveDocument(BaseModel):
    """Final archive — body + deterministic title + rendered markdown."""

    title: str
    status: ArchiveStatus
    body: ArchiveBody
    markdown: str = Field(..., description="Python-rendered markdown ready to save")


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _agent() -> Agent[None, ArchiveBody]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ArchiveBody,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_for_prompt(
    hypothesis: EntityHypothesis,
    answers: AbsorbedAnswers,
    accepted_option: OntologyOption,
    names: NamingDecision,
    gaps: GapAnalysis | None,
) -> str:
    lines: list[str] = ["# Final names (cap 8)"]
    for e in names.entities:
        parent = f", parent={e.parent_english_id}" if e.parent_english_id else ""
        lines.append(
            f"  - {e.english_id} / {e.korean_label} (role={e.role}{parent}) — {e.description_short}"
        )

    lines.append("\n# Accepted option (cap 6)")
    lines.append(f"id: {accepted_option.id} — {accepted_option.name}")
    lines.append(f"description: {accepted_option.description}")
    lines.append(f"trade_offs: {accepted_option.trade_offs_one_line}")
    lines.append("structure_sketch:")
    for ln in accepted_option.structure_sketch.splitlines():
        lines.append(f"  {ln}")

    lines.append("\n# Hypothesis seed (cap 2)")
    lines.append(
        f"표시명 후보: {hypothesis.candidate_term_korean} / 식별자 후보: {hypothesis.candidate_term_english}"
    )
    lines.append(f"domain_role: {hypothesis.domain_role}")

    lines.append("\n# User answers (cap 4) — answered ones only")
    for qid, ans in answers.per_question.items():
        if ans.is_unknown or not ans.normalized.strip():
            continue
        bits = [f"  - {qid}: {ans.normalized}"]
        if ans.raw_text and ans.raw_text != ans.normalized:
            bits.append(f"raw='{ans.raw_text}'")
        if ans.contradicts_my_guess:
            bits.append(f"[CONTRADICTS my_guess: {ans.contradicts_note}]")
        lines.append(" ".join(bits))
    if answers.emergent_facts:
        lines.append("Emergent facts:")
        for f in answers.emergent_facts:
            lines.append(f"  - {f}")

    if gaps and gaps.gaps:
        lines.append("\n# Detected gaps (cap 5)")
        for g in gaps.gaps:
            lines.append(
                f"  - {g.id} [{g.kind}/{g.severity}] {g.title} "
                f"→ resolution={g.recommended_resolution}"
            )
            lines.append(f"      rationale: {g.resolution_rationale}")

    return "\n".join(lines)


def _render_markdown(
    *,
    title: str,
    status: ArchiveStatus,
    body: ArchiveBody,
    accepted_option: OntologyOption,
) -> str:
    """Render the final markdown deterministically — no LLM in this step."""
    status_badge = "✓ 완료" if status == "completed" else "⚠️ 부분 완료"
    out: list[str] = []
    out.append(f"# {title}")
    out.append("")
    out.append(f"**상태**: {status_badge}")
    out.append("")
    out.append("## 요약")
    out.append("")
    out.append(body.summary_korean.strip())
    out.append("")
    out.append("## 채택 옵션")
    out.append("")
    out.append(f"- **{accepted_option.name}** (id: `{accepted_option.id}`)")
    out.append(f"- trade-off: {accepted_option.trade_offs_one_line}")
    out.append("")
    out.append("## 구조")
    out.append("")
    out.append("```")
    out.append(body.structure_diagram.strip())
    out.append("```")
    out.append("")
    out.append("## 결정 사항")
    out.append("")
    out.append("| 항목 | 결정 | 근거 |")
    out.append("|------|------|------|")
    for d in body.decisions:
        # Escape pipes in cell content so the table stays valid.
        topic = d.topic_korean.replace("|", "\\|")
        decision = d.decision_korean.replace("|", "\\|")
        rationale = d.rationale_korean.replace("|", "\\|")
        out.append(f"| {topic} | {decision} | {rationale} |")
    out.append("")
    return "\n".join(out)


def _build_title(
    names: NamingDecision,
    step_number: int | None,
) -> str:
    """Default title: 'Step N — <root korean label> entity 결정 ✓'."""
    root = next((e for e in names.entities if e.role == "root"), None)
    standalone = next((e for e in names.entities if e.role == "standalone"), None)
    label = (root or standalone or names.entities[0]).korean_label
    prefix = f"Step {step_number} — " if step_number is not None else ""
    return f"{prefix}{label} entity 결정 ✓"


# ── Public API ───────────────────────────────────────────────────────


async def archive_entity_cycle(
    *,
    hypothesis: EntityHypothesis,
    answers: AbsorbedAnswers,
    accepted_option: OntologyOption,
    names: NamingDecision,
    gaps: GapAnalysis | None = None,
    step_number: int | None = None,
    session_id: str,
    turn_no: int,
) -> ArchiveDocument:
    """Archive one entity authoring cycle into a saveable markdown document."""
    user_prompt = _format_for_prompt(hypothesis, answers, accepted_option, names, gaps)

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

    body = result.output
    status: ArchiveStatus = (
        "partial" if (gaps and any(g.severity == "high" for g in gaps.gaps)) else "completed"
    )
    title = _build_title(names, step_number)
    markdown = _render_markdown(
        title=title, status=status, body=body, accepted_option=accepted_option
    )
    return ArchiveDocument(title=title, status=status, body=body, markdown=markdown)


def reset_caches() -> None:
    _system_prompt.cache_clear()
    _agent.cache_clear()
