"""W55 — Drift remediation recommender.

W52's `param_signature_verifier` *detects* cross-layer drift (action.params_json
vs code_methods.params_json mismatches). W55 turns those findings into
*actionable* remediation steps Section 2 can consume.

Default convention: **code is the ground truth.** The verifier surfaces an
action whose declared params diverge from the method's actual params, and the
remediation suggests renaming the action's params to match the method.

This is the cheapest fix in 95% of cases — production Java code is the source
of truth for the framework's authoring pipeline, and aligning declarations to
match it is straightforward.

Public API:
    - RemediationKind                — enum of action types
    - RemediationStep                — frozen Pydantic record
    - generate_remediation(verifs)   — walks NAME_MISMATCH / ARITY_MISMATCH cases
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.sim_v2.core.verification.param_signature_verifier import (
    ParamVerification,
)


RemediationKind = Literal[
    "RENAME_ACTION_PARAM",
    "RESIZE_ACTION_PARAMS",
]


class RemediationStep(BaseModel):
    """One concrete fix Section 2 can apply."""
    model_config = ConfigDict(frozen=True)

    action_fqn:       str
    code_method_fqn:  str
    kind:             RemediationKind
    param_position:   int | None = None
    current_name:     str | None = None
    expected_name:    str | None = None
    recommendation:   str
    rationale:        str


class RemediationReport(BaseModel):
    """All steps for one repo, plus a one-line summary."""
    model_config = ConfigDict(frozen=True)

    steps:    list[RemediationStep] = Field(default_factory=list)
    summary:  str = ""


def generate_remediation(
    verifications: list[ParamVerification],
) -> RemediationReport:
    """Produce remediation steps for every verification in NAME_MISMATCH or
    ARITY_MISMATCH state. Order-preserving over input."""
    steps: list[RemediationStep] = []

    for v in verifications:
        if v.status == "NAME_MISMATCH":
            for pos, (a_name, m_name) in enumerate(
                zip(v.action_params, v.method_params)
            ):
                if a_name == m_name:
                    continue
                steps.append(RemediationStep(
                    action_fqn=v.action_fqn,
                    code_method_fqn=v.code_method_fqn or "",
                    kind="RENAME_ACTION_PARAM",
                    param_position=pos,
                    current_name=a_name,
                    expected_name=m_name,
                    recommendation=(
                        f"Rename action param #{pos} from {a_name!r} to {m_name!r}"
                    ),
                    rationale=(
                        f"Java method declares param #{pos} as {m_name!r}; "
                        f"action declares {a_name!r}. Code is ground truth — "
                        f"realign action declaration."
                    ),
                ))
        elif v.status == "ARITY_MISMATCH":
            steps.append(RemediationStep(
                action_fqn=v.action_fqn,
                code_method_fqn=v.code_method_fqn or "",
                kind="RESIZE_ACTION_PARAMS",
                param_position=None,
                current_name=None,
                expected_name=None,
                recommendation=(
                    f"Resize action params: action has {len(v.action_params)}, "
                    f"method has {len(v.method_params)}. Update action declaration."
                ),
                rationale=v.details or "arity mismatch between action and method",
            ))

    summary = _summarize(verifications, steps)
    return RemediationReport(steps=steps, summary=summary)


def _summarize(
    verifications: list[ParamVerification],
    steps: list[RemediationStep],
) -> str:
    name_count = sum(1 for v in verifications if v.status == "NAME_MISMATCH")
    arity_count = sum(1 for v in verifications if v.status == "ARITY_MISMATCH")
    rename_steps = sum(1 for s in steps if s.kind == "RENAME_ACTION_PARAM")
    resize_steps = sum(1 for s in steps if s.kind == "RESIZE_ACTION_PARAMS")
    if rename_steps == 0 and resize_steps == 0:
        return "No drift to remediate."
    parts: list[str] = []
    if name_count:
        parts.append(f"{name_count} NAME_MISMATCH action(s) → {rename_steps} rename step(s)")
    if arity_count:
        parts.append(f"{arity_count} ARITY_MISMATCH action(s) → {resize_steps} resize step(s)")
    return "Remediation: " + "; ".join(parts)


__all__ = [
    "RemediationKind",
    "RemediationReport",
    "RemediationStep",
    "generate_remediation",
]
