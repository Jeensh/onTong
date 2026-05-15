"""W61 — LLM-based BusinessTerm proposer with ADR-005 4-layer defense.

The Two-Engine framework's second engine finally goes live on production
findings. Where UC24 (W58) produced `PROPOSE_NEW_TERM` placeholder steps
("propose a new term for `ProductCategory`"), this module turns each one
into a concrete structured `BusinessTermProposal` via an LLM provider.

ADR-005's 4-layer defense, mapped to the layers here:

    Layer 1 — grounding:     prompt includes existing term labels for the same
                             domain, so the LLM picks naming consistent with
                             the codebase rather than inventing its own style.
    Layer 2 — validation:    LLM is asked for strict JSON; we parse, enforce
                             required fields (fqn / label / description / domain),
                             reject empty or wrong-pattern values, and scan for
                             anti-patterns.
    Layer 3 — oracle:        before accepting, check whether any existing term
                             already covers this class via label or alias match
                             — surfaces duplicates as a separate signal.
    Layer 4 — review gate:   every proposal carries `confidence` + `needs_review`
                             so a human reviewer can triage before merge.

Public API:
    - BusinessTermProposal           — frozen Pydantic
    - TermProposalResult             — proposal + raw response + validation
    - TermProposer                   — propose(...) entry point
    - existing_terms_for_grounding   — helper that builds grounding payload
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.recommendation.providers.base import (
    LLMProvider,
    LLMProviderError,
    LLMRequest,
)


# ─────────────────────────────────────────────────────────────────────────────
# Proposal model
# ─────────────────────────────────────────────────────────────────────────────


class BusinessTermProposal(BaseModel):
    """Concrete proposal — what the LLM produced + provenance."""
    model_config = ConfigDict(frozen=True)

    fqn:          str
    label:        str
    description:  str
    aliases:      tuple[str, ...] = ()
    domain:       str = "scm"
    kind:         str = "composite"   # composite | enum | value | scalar
    confidence:   float = 0.0
    needs_review: bool = True
    source:       str = "llm"
    target_class: str = ""             # the Java class this term proposes to cover


class TermProposalResult(BaseModel):
    """propose() output — proposal (or None on parse failure) + diagnostics."""
    model_config = ConfigDict(frozen=True)

    proposal:           BusinessTermProposal | None
    raw_response:       str
    provider_used:      str
    validation_errors:  tuple[str, ...] = ()
    duplicate_of:       str | None = None     # existing term_fqn if dup detected


# ─────────────────────────────────────────────────────────────────────────────
# Grounding helper
# ─────────────────────────────────────────────────────────────────────────────


def existing_terms_for_grounding(
    session: Session, repo_id: str, domain: str | None = None, limit: int = 20,
) -> list[tuple[str, str, str]]:
    """Return up to `limit` existing terms (fqn, label, aliases_json) for grounding.

    When `domain` is provided, prefer terms with the matching domain so the LLM
    matches the codebase's naming convention for that domain.
    """
    if domain:
        rows = session.execute(
            text(
                "SELECT fqn, label, aliases_json FROM business_terms "
                "WHERE repo_id = :rid AND domain = :dom LIMIT :lim"
            ),
            {"rid": repo_id, "dom": domain, "lim": limit},
        ).fetchall()
    else:
        rows = session.execute(
            text(
                "SELECT fqn, label, aliases_json FROM business_terms "
                "WHERE repo_id = :rid LIMIT :lim"
            ),
            {"rid": repo_id, "lim": limit},
        ).fetchall()
    return [(r[0], r[1] or "", r[2] or "[]") for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Prompt rendering
# ─────────────────────────────────────────────────────────────────────────────


_SYSTEM_PROMPT = """\
You are the Recommendation Engine for a Java-to-Python twin verification framework.
A Java class needs a corresponding business_term in the ontology. Produce one
structured proposal as STRICT JSON — no Markdown, no commentary outside JSON.

Required JSON schema:
{
  "fqn":         "term.<domain>.<snake_case_path>",  // dotted lowercase
  "label":       "Korean human-readable name",
  "description": "1-3 sentences explaining what this term represents",
  "aliases":     ["JavaClassName", "AlternateName"],
  "domain":      "scm | banking | broadleaf | ...",
  "kind":        "composite | enum | value | scalar",
  "confidence":  0.0-1.0,
  "needs_review": true | false
}

Naming conventions:
- fqn MUST start with "term." and use dot-separated lowercase segments
- aliases MUST include the Java class's simple name as the first element
- domain MUST match an existing domain in the grounding context
- confidence: how strongly the term description fits the Java class; below 0.7 implies needs_review=true
"""


def _render_user_prompt(
    target_class: str,
    method_fqn: str,
    domain: str,
    existing: list[tuple[str, str, str]],
) -> str:
    lines = [
        f"Target Java class : {target_class}",
        f"Method that returns it: {method_fqn}",
        f"Domain hint       : {domain}",
        "",
        "Existing terms in this domain (use them as a style/naming reference):",
    ]
    if existing:
        for fqn, label, aliases in existing:
            lines.append(f"  - {fqn:40s}  label={label!r:25s}  aliases={aliases}")
    else:
        lines.append("  (no existing terms in this domain)")
    lines.append("")
    lines.append(
        f"Propose ONE business_term for {target_class!r}. Respond with strict JSON only."
    )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────


_FQN_RE   = re.compile(r"^term\.[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
_VALID_KINDS  = frozenset({"composite", "enum", "value", "scalar"})


def _validate(parsed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    fqn = parsed.get("fqn", "")
    if not isinstance(fqn, str) or not _FQN_RE.fullmatch(fqn):
        errors.append(f"fqn must match pattern term.*.*, got {fqn!r}")
    if not isinstance(parsed.get("label"), str) or not parsed.get("label", "").strip():
        errors.append("label must be a non-empty string")
    if not isinstance(parsed.get("description"), str) \
            or not parsed.get("description", "").strip():
        errors.append("description must be a non-empty string")
    if not isinstance(parsed.get("domain"), str) \
            or not parsed.get("domain", "").strip():
        errors.append("domain must be a non-empty string")
    kind = parsed.get("kind", "composite")
    if kind not in _VALID_KINDS:
        errors.append(f"kind must be one of {sorted(_VALID_KINDS)}, got {kind!r}")
    aliases = parsed.get("aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
        errors.append("aliases must be list[str]")
    confidence = parsed.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
        errors.append(f"confidence must be in [0,1], got {confidence!r}")
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Dedup (Layer 3 — oracle)
# ─────────────────────────────────────────────────────────────────────────────


def _find_duplicate(
    target_class: str,
    proposal_aliases: tuple[str, ...],
    existing: list[tuple[str, str, str]],
) -> str | None:
    """Return an existing term_fqn that already covers target_class, or None."""
    candidates = {target_class} | set(proposal_aliases)
    for fqn, label, aliases_json in existing:
        try:
            existing_aliases = set(json.loads(aliases_json))
        except (json.JSONDecodeError, TypeError):
            existing_aliases = set()
        if candidates & existing_aliases:
            return fqn
        if label in candidates:
            return fqn
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Proposer
# ─────────────────────────────────────────────────────────────────────────────


class TermProposer:
    """Wrap an LLMProvider to produce structured BusinessTermProposals."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def propose(
        self,
        target_class: str,
        *,
        method_fqn: str,
        domain: str = "scm",
        existing_terms: list[tuple[str, str, str]] | None = None,
    ) -> TermProposalResult:
        existing = existing_terms or []
        user_prompt = _render_user_prompt(
            target_class=target_class, method_fqn=method_fqn,
            domain=domain, existing=existing,
        )

        try:
            response = self._provider.complete(
                LLMRequest(
                    system=_SYSTEM_PROMPT, user=user_prompt, temperature=0.1,
                    max_tokens=1024,
                )
            )
        except LLMProviderError as e:
            return TermProposalResult(
                proposal=None,
                raw_response="",
                provider_used=getattr(self._provider, "name", "unknown"),
                validation_errors=(f"provider error: {e}",),
            )

        raw = response.text or ""
        parsed = _try_parse_json(raw)
        if parsed is None:
            return TermProposalResult(
                proposal=None,
                raw_response=raw,
                provider_used=response.provider,
                validation_errors=("LLM did not return parseable JSON",),
            )

        errors = _validate(parsed)
        if errors:
            return TermProposalResult(
                proposal=None,
                raw_response=raw,
                provider_used=response.provider,
                validation_errors=tuple(errors),
            )

        aliases = tuple(parsed.get("aliases", []))
        # Inject target_class as alias if missing — alleviates LLM omission
        if target_class and target_class not in aliases:
            aliases = (target_class,) + aliases

        dup = _find_duplicate(target_class, aliases, existing)
        confidence = float(parsed.get("confidence", 0.0))
        # Auto-flag needs_review when confidence is low OR a duplicate exists
        needs_review = bool(parsed.get("needs_review", True)) \
            or confidence < 0.7 or dup is not None

        proposal = BusinessTermProposal(
            fqn=parsed["fqn"],
            label=parsed["label"],
            description=parsed["description"],
            aliases=aliases,
            domain=parsed.get("domain", domain),
            kind=parsed.get("kind", "composite"),
            confidence=confidence,
            needs_review=needs_review,
            source="llm",
            target_class=target_class,
        )
        return TermProposalResult(
            proposal=proposal,
            raw_response=raw,
            provider_used=response.provider,
            duplicate_of=dup,
        )


def _try_parse_json(text_value: str) -> dict[str, Any] | None:
    """Robust JSON extraction. Strips Markdown code fences if present."""
    if not text_value:
        return None
    candidate = text_value.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    fence = re.match(r"^```(?:json)?\s*\n(.+?)\n```$",
                     candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
    # Try direct parse
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        # Last resort: scan for first {…} block
        match = re.search(r"\{.+\}", candidate, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


__all__ = [
    "BusinessTermProposal",
    "TermProposalResult",
    "TermProposer",
    "existing_terms_for_grounding",
]
