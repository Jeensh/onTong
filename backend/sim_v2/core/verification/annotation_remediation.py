"""W67 — Annotation drift remediation recommender.

Fifth axis of the Detect→Fix loop, after W48 (schema), W55 (param),
W58 (return-type), W64 (exception). Mirrors the same "code is ground truth"
pattern: when an action's `effects_json` disagrees with the method's
annotations, modify the action.

W66 detect → W67 remediation:
  UNDECLARED_ANNOTATION   → ADD_ANNOTATION_EFFECT      (add to effects_json)
  MISSING_ANNOTATION      → REMOVE_ANNOTATION_EFFECT   (remove from effects_json)
  DIVERGENT_ANNOTATIONS   → emit one ADD + one REMOVE per disagreement
  VERIFIED / METHOD_NOT_FOUND / NO_RECOMMENDATION → no step

Each ADD step's `effect_entry` is the minimal valid payload Section 2 can
paste into effects_json directly. For `rest_endpoint`, the rationale notes
that `http_method` + `path` should be filled by the human/LLM follow-up —
the verifier only knows the kind, not the original `@PostMapping(...)` args.

Public API:
    - AnnotationRemediationKind            — Literal enum
    - AnnotationRemediationStep            — frozen Pydantic
    - AnnotationRemediationReport          — bundle + summary
    - generate_annotation_remediation(verifs)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.sim_v2.core.verification.annotation_verifier import (
    AnnotationVerification,
)


AnnotationRemediationKind = Literal[
    "ADD_ANNOTATION_EFFECT",       # add a contract-kind effect to effects_json
    "REMOVE_ANNOTATION_EFFECT",    # action over-declares; remove the effect
]


# Kinds that need additional fields filled in (the verifier only sees the kind,
# not the original annotation's arguments).
_KINDS_NEEDING_DETAIL: frozenset[str] = frozenset({
    "rest_endpoint",   # http_method + path
    "scheduled",       # cron / fixedRate
    "cacheable",       # cache name + key
    "cache_evicting",  # cache name + key
})


class AnnotationRemediationStep(BaseModel):
    """One concrete annotation-side fix Section 2 can apply."""
    model_config = ConfigDict(frozen=True)

    action_fqn:       str
    code_method_fqn:  str
    kind:             AnnotationRemediationKind
    annotation_kind:  str                          # e.g. "transactional", "rest_endpoint"
    effect_entry:     dict | None = None           # payload to add (ADD only)
    recommendation:   str
    rationale:        str
    needs_detail:     bool = False                  # True for rest_endpoint/scheduled/cache
                                                    # → human/LLM fills extra fields


class AnnotationRemediationReport(BaseModel):
    """All annotation fix steps for one batch + a one-line summary."""
    model_config = ConfigDict(frozen=True)

    steps:   list[AnnotationRemediationStep] = Field(default_factory=list)
    summary: str = ""


def _add_step(
    v: AnnotationVerification, kind: str,
) -> AnnotationRemediationStep:
    needs_detail = kind in _KINDS_NEEDING_DETAIL
    payload = {"kind": kind}
    detail_note = ""
    if needs_detail:
        detail_note = (
            " — additional fields (http_method/path or cron etc.) should be "
            "filled in by the reviewer/LLM follow-up"
        )
    return AnnotationRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="ADD_ANNOTATION_EFFECT",
        annotation_kind=kind,
        effect_entry=payload,
        recommendation=(
            f"Add {payload!r} to action.effects_json — "
            f"method carries the corresponding annotation.{detail_note}"
        ),
        rationale=(
            f"Method has an annotation that resolves to contract kind "
            f"{kind!r}; action declares no matching effect. Code is ground "
            f"truth — document the cross-cutting effect."
        ),
        needs_detail=needs_detail,
    )


def _remove_step(
    v: AnnotationVerification, kind: str,
) -> AnnotationRemediationStep:
    return AnnotationRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="REMOVE_ANNOTATION_EFFECT",
        annotation_kind=kind,
        effect_entry=None,
        recommendation=(
            f"Remove effects_json entry with kind={kind!r} — "
            f"method has no matching annotation."
        ),
        rationale=(
            f"Action declares cross-cutting effect {kind!r} but the method "
            f"has no corresponding annotation. Code is ground truth — drop "
            f"the over-declared effect."
        ),
        needs_detail=False,
    )


def _decide_steps(
    v: AnnotationVerification,
) -> list[AnnotationRemediationStep]:
    if v.status == "UNDECLARED_ANNOTATION":
        return [_add_step(v, kind) for kind in v.undeclared_only]
    if v.status == "MISSING_ANNOTATION":
        return [_remove_step(v, kind) for kind in v.missing_only]
    if v.status == "DIVERGENT_ANNOTATIONS":
        adds    = [_add_step(v, k)    for k in v.undeclared_only]
        removes = [_remove_step(v, k) for k in v.missing_only]
        return adds + removes
    return []


def generate_annotation_remediation(
    verifications: list[AnnotationVerification],
) -> AnnotationRemediationReport:
    """Produce remediation steps for each AnnotationVerification in a fixable
    state. Order-preserving across input; within a single DIVERGENT case,
    ADDs come before REMOVEs (reviewer-friendly)."""
    steps: list[AnnotationRemediationStep] = []
    for v in verifications:
        steps.extend(_decide_steps(v))
    return AnnotationRemediationReport(
        steps=steps, summary=_summarize(steps),
    )


def _summarize(steps: list[AnnotationRemediationStep]) -> str:
    if not steps:
        return "No annotation drift to remediate."
    adds = sum(1 for s in steps if s.kind == "ADD_ANNOTATION_EFFECT")
    removes = sum(1 for s in steps if s.kind == "REMOVE_ANNOTATION_EFFECT")
    needs_detail = sum(1 for s in steps if s.needs_detail)
    parts: list[str] = []
    if adds:
        parts.append(f"{adds} ADD_ANNOTATION_EFFECT")
    if removes:
        parts.append(f"{removes} REMOVE_ANNOTATION_EFFECT")
    summary = "Remediation: " + ", ".join(parts)
    if needs_detail:
        summary += f" ({needs_detail} need extra detail fields)"
    return summary


__all__ = [
    "AnnotationRemediationKind",
    "AnnotationRemediationReport",
    "AnnotationRemediationStep",
    "generate_annotation_remediation",
]
