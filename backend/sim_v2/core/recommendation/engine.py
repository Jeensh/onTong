"""Recommendation Engine — LLM-based proposal generation + refinement (ADR-002 + ADR-005).

ADR-005 의 4-layer defense 중 Layer 2 (output validation via anti-pattern catalog)
와 directly integrated. Layer 1 (grounding) 는 ProposalContext 의 ontology hint 로 시작 →
fuller impl W6+.

Public API:
    - RecommendationEngine — propose / refine
    - ProposalContext — propose() input
    - ValidationResult — anti-pattern scan outcome
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.sim_v2.core.integrator.proposal import Proposal, ProposalType
from backend.sim_v2.core.recommendation.anti_patterns.catalog import (
    AntiPatternHit,
    AntiPatternScanner,
)
from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMRequest,
)


@dataclass(frozen=True)
class ProposalContext:
    """propose() input — ontology grounding + plugin hint."""
    plugin:           str
    proposal_type:    ProposalType
    user_intent:      str
    ontology_context: dict[str, Any] = field(default_factory=dict)
    # ontology_context = grounding payload (entity/term/schema 의 LLM-readable summary)


@dataclass(frozen=True)
class ValidationResult:
    """Anti-pattern scan outcome — Layer 2."""
    hits:        tuple[AntiPatternHit, ...]
    has_errors:  bool
    summary:     str


@dataclass(frozen=True)
class RecommendationResult:
    """propose() output — Proposal + validation."""
    proposal:        Proposal
    raw_response:    str
    validation:      ValidationResult
    provider_used:   str


_PROPOSAL_SYSTEM_PROMPT = """\
You are a Recommendation Engine for a Two-Engine Plugin Framework targeting Java twin verification.

When asked to propose a change (schema / code / ontology evolution), output:
1. A description of the change (1-3 sentences).
2. The diff payload as a JSON-like dict structure.

Avoid the following anti-patterns (Phase α lessons):
- Calling `BigDecimal(...)` as a class — runtime uses `bd()` factory.
- Using `MathContext.DECIMAL64` / `RoundingMode.X` / `SdConstants.X` namespace forms
  unless the plugin contract explicitly exposes them.
- Hardcoding fixture tolerance (`abs_tol=1e-6` etc.) — use per-fixture metadata.toml.

When uncertain, mark unclear sections explicitly rather than fabricating contract details.
"""


class RecommendationEngine:
    """LLM-based proposal generator with anti-pattern scan.

    Implements `backend.sim_v2.core.integrator.integrator.RecommendationEngine` Protocol
    via `refine()` method.
    """

    def __init__(
        self,
        provider: LLMProvider,
        scanner: AntiPatternScanner | None = None,
    ) -> None:
        self._provider = provider
        self._scanner = scanner or AntiPatternScanner()

    # ─────────────────────────────────────────────────────────────────────
    # propose — generate new Proposal in DRAFT state
    # ─────────────────────────────────────────────────────────────────────

    def propose(self, context: ProposalContext) -> RecommendationResult:
        user_prompt = self._render_user_prompt(context)
        response = self._provider.complete(
            LLMRequest(
                system=_PROPOSAL_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.2,
            )
        )
        validation = self._validate(response.text)

        # Sprint W5 simplification: proposal is created with placeholder diffs
        # (LLM raw text). Production parse logic in W6+.
        proposal = Proposal(
            type=context.proposal_type,
            description=context.user_intent,
            schema_diff={"raw_llm_output": response.text} if context.proposal_type == "schema_change" else None,
            code_diff={"raw_llm_output": response.text} if context.proposal_type == "code_change" else None,
            ontology_diff={"raw_llm_output": response.text} if context.proposal_type == "ontology_evolution" else None,
            plugin=context.plugin,
        )

        return RecommendationResult(
            proposal=proposal,
            raw_response=response.text,
            validation=validation,
            provider_used=response.provider,
        )

    # ─────────────────────────────────────────────────────────────────────
    # refine — Integrator's RecommendationEngine Protocol implementation
    # ─────────────────────────────────────────────────────────────────────

    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        """Refine existing proposal with hints (user feedback / oracle failure)."""
        user_prompt = (
            f"Refine the following proposal based on hints.\n\n"
            f"Original description: {proposal.description}\n\n"
            f"Existing schema_diff: {proposal.schema_diff}\n"
            f"Existing code_diff: {proposal.code_diff}\n"
            f"Existing ontology_diff: {proposal.ontology_diff}\n\n"
            f"Hints: {hints}\n\n"
            f"Provide a refined version."
        )
        response = self._provider.complete(
            LLMRequest(
                system=_PROPOSAL_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.2,
            )
        )
        # Mutate proposal in place — refinement payload as raw LLM output (W5 simplification)
        if proposal.schema_diff is not None:
            proposal.schema_diff = {**proposal.schema_diff, "refined_llm_output": response.text}
        if proposal.code_diff is not None:
            proposal.code_diff = {**proposal.code_diff, "refined_llm_output": response.text}
        if proposal.ontology_diff is not None:
            proposal.ontology_diff = {**proposal.ontology_diff, "refined_llm_output": response.text}
        return proposal

    # ─────────────────────────────────────────────────────────────────────
    # Internal — prompt rendering + anti-pattern scan
    # ─────────────────────────────────────────────────────────────────────

    def _render_user_prompt(self, context: ProposalContext) -> str:
        lines = [
            f"Plugin: {context.plugin}",
            f"Proposal type: {context.proposal_type}",
            f"User intent: {context.user_intent}",
        ]
        if context.ontology_context:
            lines.append("\nOntology grounding (relevant entities / terms / schema):")
            for key, value in context.ontology_context.items():
                lines.append(f"  - {key}: {value}")
        lines.append("\nPropose the change (description + diff).")
        return "\n".join(lines)

    def _validate(self, source: str) -> ValidationResult:
        hits = tuple(self._scanner.scan(source))
        has_errors = any(h.severity == "ERROR" for h in hits)
        summary = (
            f"{len(hits)} anti-pattern hit(s); has_errors={has_errors}"
            if hits else "clean (no anti-pattern hits)"
        )
        return ValidationResult(hits=hits, has_errors=has_errors, summary=summary)


__all__ = [
    "ProposalContext",
    "RecommendationEngine",
    "RecommendationResult",
    "ValidationResult",
]
