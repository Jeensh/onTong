"""Capability 12 — Comprehensive Archive (Sonnet, STANDARD tier).

Session-level synthesis: takes the snapshots of every entity authored in
this session and produces a domain-level report a stakeholder can read.

Distinct from cap 9 (`archiver`) which is single-entity.

Public API:
    write_comprehensive_archive(req, *, session_id, turn_no) -> ComprehensiveArchive
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "comprehensive_archive"
TIER = ModelTier.STANDARD

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "comprehensive_archive.md"
)


# ── Input snapshot per entity ────────────────────────────────────────


class EntitySnapshot(BaseModel):
    """Compact per-entity snapshot the frontend builds from CompletedEntityCycle.

    Only the fields needed for synthesis — full hypothesis / option / gaps
    payloads stay in the frontend store.
    """

    class_name: str
    package: str = ""
    candidate_term_korean: str
    candidate_term_english: str
    domain_role: str
    accepted_option_name: str | None = None
    accepted_option_alignment: str | None = None
    accepted_option_structure: str | None = None
    persisted_fqns: list[str] = Field(default_factory=list)
    gap_titles: list[str] = Field(default_factory=list)  # short titles only
    pattern_findings_summary: str | None = None
    archive_excerpt: str | None = None  # first ~300 chars of single-entity archive markdown
    in_progress: bool = False  # True for the user's CURRENT entity (not yet "다음 Entity"-clicked)


class ComprehensiveArchiveRequest(BaseModel):
    repo_id: str
    session_id_for_log: str = ""  # echo to LLM context, not used by router
    entities: list[EntitySnapshot] = Field(..., min_length=1)


# ── LLM output (structured; markdown rendered in Python) ─────────────


class EntitySectionSummary(BaseModel):
    class_name: str
    candidate_term_korean: str
    candidate_term_english: str
    domain_role: str
    accepted_option_name: str | None = None
    persisted_fqns: list[str] = Field(default_factory=list)
    summary_korean: str
    notable_gaps_or_concerns: list[str] = Field(default_factory=list, max_length=8)


class CrossCuttingObservation(BaseModel):
    title: str
    description_korean: str
    affected_entities: list[str] = Field(default_factory=list)


class ComprehensiveArchiveBody(BaseModel):
    title: str
    executive_summary: str
    entity_sections: list[EntitySectionSummary]
    cross_cutting_observations: list[CrossCuttingObservation] = Field(default_factory=list)
    decisions_made: list[str] = Field(default_factory=list)
    next_steps_korean: list[str] = Field(default_factory=list, max_length=5)


class ComprehensiveArchive(BaseModel):
    body: ComprehensiveArchiveBody
    markdown: str
    rendered_at: str  # ISO 8601


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_agent() -> Agent[None, ComprehensiveArchiveBody]:
    return Agent(
        get_authoring_model(TIER),
        output_type=ComprehensiveArchiveBody,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_for_prompt(req: ComprehensiveArchiveRequest) -> str:
    lines = [f"# Repository: {req.repo_id}"]
    lines.append(f"# Total entities this session: {len(req.entities)}")
    in_progress = [e for e in req.entities if e.in_progress]
    completed = [e for e in req.entities if not e.in_progress]
    lines.append(
        f"# Completed: {len(completed)}, In-progress: {len(in_progress)}"
    )
    for i, e in enumerate(req.entities, start=1):
        lines.append(f"\n## Entity #{i} — {e.class_name}{' (in-progress)' if e.in_progress else ''}")
        if e.package:
            lines.append(f"  package: {e.package}")
        lines.append(f"  candidate_term_korean: {e.candidate_term_korean}")
        lines.append(f"  candidate_term_english: {e.candidate_term_english}")
        lines.append(f"  domain_role: {e.domain_role}")
        if e.accepted_option_name:
            lines.append(f"  accepted_option_name: {e.accepted_option_name}")
        if e.accepted_option_alignment:
            lines.append(f"  accepted_option_alignment: {e.accepted_option_alignment}")
        if e.accepted_option_structure:
            lines.append(f"  accepted_option_structure: {e.accepted_option_structure[:200]}")
        if e.persisted_fqns:
            lines.append(f"  persisted_fqns: {', '.join(e.persisted_fqns[:8])}"
                         + (f" (+{len(e.persisted_fqns)-8})" if len(e.persisted_fqns) > 8 else ""))
        if e.gap_titles:
            lines.append("  gap_titles:")
            for g in e.gap_titles[:6]:
                lines.append(f"    - {g}")
        if e.pattern_findings_summary:
            lines.append(f"  pattern_findings: {e.pattern_findings_summary}")
        if e.archive_excerpt:
            lines.append(f"  archive_excerpt: {e.archive_excerpt[:300]}")
    lines.append(
        "\n# Task\nSynthesize a session-level comprehensive archive per the schema. "
        "Don't write markdown — only the structured fields."
    )
    return "\n".join(lines)


def _render_markdown(body: ComprehensiveArchiveBody, repo_id: str) -> str:
    """Deterministic markdown rendering from the structured body."""
    out: list[str] = [f"# {body.title}", ""]
    if repo_id:
        out.append(f"_Repository: `{repo_id}`_  ·  _Generated: "
                   f"{datetime.now(timezone.utc).isoformat()}_")
        out.append("")
    out.append("## 요약")
    out.append("")
    out.append(body.executive_summary)
    out.append("")

    out.append(f"## Entity 섹션 ({len(body.entity_sections)})")
    out.append("")
    for i, e in enumerate(body.entity_sections, start=1):
        out.append(f"### {i}. {e.class_name} → {e.candidate_term_english} ({e.candidate_term_korean})")
        out.append("")
        meta_bits = [f"**역할**: {e.domain_role}"]
        if e.accepted_option_name:
            meta_bits.append(f"**채택 옵션**: {e.accepted_option_name}")
        out.append(" · ".join(meta_bits))
        out.append("")
        out.append(e.summary_korean)
        if e.persisted_fqns:
            out.append("")
            out.append(f"**Persisted**: {', '.join(f'`{f}`' for f in e.persisted_fqns)}")
        if e.notable_gaps_or_concerns:
            out.append("")
            out.append("**미해결/주의**:")
            for g in e.notable_gaps_or_concerns:
                out.append(f"- {g}")
        out.append("")

    if body.cross_cutting_observations:
        out.append(f"## 종합 관찰 ({len(body.cross_cutting_observations)})")
        out.append("")
        for c in body.cross_cutting_observations:
            out.append(f"### {c.title}")
            out.append("")
            out.append(c.description_korean)
            if c.affected_entities:
                out.append("")
                out.append(f"_관련 entity_: {', '.join(c.affected_entities)}")
            out.append("")

    if body.decisions_made:
        out.append("## 이번 세션 결정")
        out.append("")
        for d in body.decisions_made:
            out.append(f"- {d}")
        out.append("")

    if body.next_steps_korean:
        out.append("## 다음 세션 follow-up")
        out.append("")
        for s in body.next_steps_korean:
            out.append(f"- {s}")
        out.append("")

    return "\n".join(out)


# ── Public API ───────────────────────────────────────────────────────


async def write_comprehensive_archive(
    req: ComprehensiveArchiveRequest,
    *,
    session_id: str,
    turn_no: int,
) -> ComprehensiveArchive:
    """Synthesise a session-level archive across all authored entities.

    Pure synthesis — no graph tools. Sonnet does the structured output;
    Python deterministically renders markdown.
    """
    user_prompt = _format_for_prompt(req)
    agent = _build_agent()

    with cost_mod.measure() as t:
        result = await agent.run(user_prompt, model_settings=_settings())

    body = result.output
    markdown = _render_markdown(body, repo_id=req.repo_id)

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
    logger.info(
        "authoring.comprehensive_archive session=%s turn=%d entities=%d "
        "observations=%d decisions=%d",
        session_id,
        turn_no,
        len(req.entities),
        len(body.cross_cutting_observations),
        len(body.decisions_made),
    )
    return ComprehensiveArchive(
        body=body,
        markdown=markdown,
        rendered_at=datetime.now(timezone.utc).isoformat(),
    )


def reset_caches() -> None:
    _system_prompt.cache_clear()
