"""W64 — Exception drift remediation recommender.

Sister to W55 (param remediation, UC22) and W58 (return-type remediation,
UC24) on the exception axis. W63 *detects* a mismatch between an action's
declared `effects_json` raises and the method body's `throw new ...`s; this
module turns each finding into a concrete fix step Section 2 can apply.

Same "code is ground truth" principle:
  - UNDECLARED_THROWS    → ADD_RAISES_EFFECT      (add to action.effects_json)
  - MISSING_THROWS       → REMOVE_DECLARED_EFFECT (action over-declares; remove)
  - DIVERGENT_THROWS     → one ADD + one REMOVE per disagreement (explicit per
                           exception so reviewers can triage each independently)

VERIFIED / METHOD_NOT_FOUND / NO_RECOMMENDATION emit no steps — there is
nothing actionable to do at the effects_json level.

Public API:
    - ExceptionRemediationKind          — Literal enum
    - ExceptionRemediationStep          — frozen Pydantic
    - ExceptionRemediationReport        — bundle + summary
    - generate_exception_remediation(verifs)
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.sim_v2.core.verification.exception_verifier import (
    ExceptionVerification,
)


ExceptionRemediationKind = Literal[
    "ADD_RAISES_EFFECT",       # add a {"kind":"raises","exception":X} to effects_json
    "REMOVE_DECLARED_EFFECT",  # remove an over-declared exception from effects_json
]


class ExceptionRemediationStep(BaseModel):
    """One concrete exception-side fix Section 2 can apply."""
    model_config = ConfigDict(frozen=True)

    action_fqn:       str
    code_method_fqn:  str
    kind:             ExceptionRemediationKind
    exception:        str              # the exception simple name being added/removed
    effect_entry:     dict | None = None  # payload to add (ADD only)
    recommendation:   str
    rationale:        str


class ExceptionRemediationReport(BaseModel):
    """All steps for one batch of verifications, plus a one-line summary."""
    model_config = ConfigDict(frozen=True)

    steps:   list[ExceptionRemediationStep] = Field(default_factory=list)
    summary: str = ""


def _add_step(
    v: ExceptionVerification, exception: str,
) -> ExceptionRemediationStep:
    effect = {"kind": "raises", "exception": exception}
    return ExceptionRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="ADD_RAISES_EFFECT",
        exception=exception,
        effect_entry=effect,
        recommendation=(
            f"Add {effect!r} to action.effects_json — "
            f"method actually throws {exception}."
        ),
        rationale=(
            f"Method body contains `throw new {exception}(...)`; "
            f"action does not declare it. Code is ground truth — "
            f"document the raises effect."
        ),
    )


def _remove_step(
    v: ExceptionVerification, exception: str,
) -> ExceptionRemediationStep:
    return ExceptionRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="REMOVE_DECLARED_EFFECT",
        exception=exception,
        effect_entry=None,
        recommendation=(
            f"Remove raises:{exception!r} from action.effects_json — "
            f"method body does not actually throw it."
        ),
        rationale=(
            f"Action declares it can raise {exception} but the method body "
            f"has no matching `throw new {exception}(...)`. Code is ground "
            f"truth — drop the over-declared effect."
        ),
    )


def _decide_steps(
    v: ExceptionVerification,
) -> list[ExceptionRemediationStep]:
    if v.status == "UNDECLARED_THROWS":
        # Action declares nothing OR a strict subset; emit one ADD per undeclared
        # exception. `undeclared_only` is the precise list.
        return [_add_step(v, exc) for exc in v.undeclared_only]
    if v.status == "MISSING_THROWS":
        return [_remove_step(v, exc) for exc in v.missing_only]
    if v.status == "DIVERGENT_THROWS":
        # Both sides non-empty AND differ. Emit one step per disagreement.
        adds    = [_add_step(v, exc)    for exc in v.undeclared_only]
        removes = [_remove_step(v, exc) for exc in v.missing_only]
        return adds + removes
    # VERIFIED / METHOD_NOT_FOUND / NO_RECOMMENDATION → no steps
    return []


def generate_exception_remediation(
    verifications: list[ExceptionVerification],
) -> ExceptionRemediationReport:
    """Walk verifications, emit one or more steps for each fixable status.

    Order is preserved: each verification's steps are emitted contiguously,
    ADDs before REMOVEs within a single DIVERGENT_THROWS verification.
    """
    steps: list[ExceptionRemediationStep] = []
    for v in verifications:
        steps.extend(_decide_steps(v))
    return ExceptionRemediationReport(
        steps=steps, summary=_summarize(steps),
    )


def _summarize(steps: list[ExceptionRemediationStep]) -> str:
    if not steps:
        return "No exception drift to remediate."
    adds    = sum(1 for s in steps if s.kind == "ADD_RAISES_EFFECT")
    removes = sum(1 for s in steps if s.kind == "REMOVE_DECLARED_EFFECT")
    parts: list[str] = []
    if adds:
        parts.append(f"{adds} ADD_RAISES_EFFECT")
    if removes:
        parts.append(f"{removes} REMOVE_DECLARED_EFFECT")
    return "Remediation: " + ", ".join(parts)


__all__ = [
    "ExceptionRemediationKind",
    "ExceptionRemediationReport",
    "ExceptionRemediationStep",
    "generate_exception_remediation",
]
