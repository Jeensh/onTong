"""Capability 8 — Naming (Sonnet, STANDARD tier).

Round 5 Step 13 §1: "표시명·식별자 결정 (한국어 + 영어 PascalCase)".

After the user accepts an OptionTable option (cap 6), this capability fixes
the final Korean display name and English PascalCase id for every entity that
option introduces, while checking collisions with existing entity names.

Public API:
    decide_names(
        hypothesis, accepted_option, *, existing_names=None,
        session_id, turn_no
    ) -> NamingDecision
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModelSettings

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities.code_extractor import _usage_from_result
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.capabilities.option_proposer import OntologyOption
from backend.application.authoring.llm_router import get_authoring_model, get_model_id
from backend.application.authoring.schemas import ModelTier

logger = logging.getLogger(__name__)

CAPABILITY_NAME = "naming"
TIER = ModelTier.STANDARD

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "naming.md"


# ── Output schema ────────────────────────────────────────────────────


EntityRole = Literal["root", "child", "standalone"]


class EntityName(BaseModel):
    korean_label: str = Field(..., description='Display name, e.g. "열연공장제약"')
    english_id: str = Field(..., description='PascalCase id, e.g. "HrPlantConstraint"')
    role: EntityRole
    parent_english_id: str | None = None
    description_short: str = Field(..., description="One short Korean tooltip line")


class NamingDecision(BaseModel):
    entities: list[EntityName] = Field(..., min_length=1)
    naming_conflicts: list[str] = Field(default_factory=list)
    naming_rationale: str
    alternatives_considered: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _children_must_have_resolvable_parent(self) -> NamingDecision:
        """child role requires parent_english_id present.

        We allow the parent to be either listed in this same NamingDecision
        OR (in real use) to come from `existing_names`, so we only check that
        the field is non-null for `child` roles. The richer cross-reference
        check happens in the API layer where existing_names is in scope.
        """
        for e in self.entities:
            if e.role == "child" and not e.parent_english_id:
                raise ValueError(
                    f"entity {e.english_id!r} has role='child' but parent_english_id is empty"
                )
            if e.role != "child" and e.parent_english_id:
                raise ValueError(
                    f"entity {e.english_id!r} has role={e.role!r} but parent_english_id is set"
                )
        return self


# ── Internals ────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _agent() -> Agent[None, NamingDecision]:
    return Agent(
        get_authoring_model(TIER),
        output_type=NamingDecision,
        system_prompt=_system_prompt(),
        retries=2,
        defer_model_check=True,
    )


def _settings() -> AnthropicModelSettings:
    return AnthropicModelSettings(anthropic_cache_instructions=True)


def _format_for_prompt(
    hypothesis: EntityHypothesis,
    accepted: OntologyOption,
    existing_names: list[str] | None,
) -> str:
    lines: list[str] = ["# Entity hypothesis (cap 2)"]
    lines.append(f"표시명 후보 (한): {hypothesis.candidate_term_korean}")
    lines.append(f"식별자 후보 (영): {hypothesis.candidate_term_english}")
    lines.append(f"domain_role: {hypothesis.domain_role}")

    lines.append("\n# Accepted option (cap 6)")
    lines.append(f"id: {accepted.id}")
    lines.append(f"name: {accepted.name}")
    lines.append(f"description: {accepted.description}")
    lines.append("structure_sketch:")
    for ln in accepted.structure_sketch.splitlines():
        lines.append(f"  {ln}")
    if accepted.pros:
        lines.append("pros: " + " | ".join(accepted.pros))
    if accepted.trade_offs_one_line:
        lines.append(f"trade_offs: {accepted.trade_offs_one_line}")

    lines.append("\n# Existing entity names (collision check)")
    if existing_names:
        for n in existing_names:
            lines.append(f"  - {n}")
    else:
        lines.append("  (none — cold start)")

    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────


async def decide_names(
    hypothesis: EntityHypothesis,
    accepted_option: OntologyOption,
    *,
    existing_names: list[str] | None = None,
    session_id: str,
    turn_no: int,
    user_comment: str | None = None,
) -> NamingDecision:
    """Fix final names for every entity the accepted option introduces.

    `existing_names` is an optional list of english_id strings already in the
    ontology. The capability uses it for collision checks; pass None or [] on
    cold start.

    `user_comment` (F3): correction text from ✏ 수정 on prior naming card.
    """
    user_prompt = _format_for_prompt(hypothesis, accepted_option, existing_names)
    if user_comment and user_comment.strip():
        user_prompt += (
            "\n\n# 사용자 정정·추가 (명명을 다듬어주세요)\n"
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
