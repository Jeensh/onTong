"""W65 — Verification snapshot + regression diff (CI hook).

The layered verification stack now has multiple gates that surface drift on
every run (W47 existence, W52 param, W56/W57 return-type, W63 exception).
In CI, blowing up on the *entire* drift surface is noisy — most of it is
inherited from previous commits. What teams actually want is the
**regression-only signal**: "what new drift did *this* commit introduce?"

This module captures one full verification pass as a frozen `VerificationSnapshot`,
then diffs two snapshots to produce a `RegressionReport` partitioning every
finding into **new**, **fixed**, or **unchanged**. The CI integration becomes
simple: persist the baseline snapshot in git (or artifact storage), run the
diff in CI, fail only when `new_findings` is non-empty.

Public API:
    - FindingKey                — (gate, action_fqn, status, key) immutable tuple
    - VerificationSnapshot      — frozen Pydantic, repo_id + findings list
    - RegressionReport          — frozen, new/fixed/unchanged sets per gate
    - take_snapshot(session, repo_id)
    - diff_snapshots(baseline, current)
    - snapshot_to_json / snapshot_from_json   — serialization helpers
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
)
from backend.sim_v2.core.verification.action_method_verifier import (
    verify_actions,
)
from backend.sim_v2.core.verification.exception_verifier import (
    verify_action_exceptions_batch,
)
from backend.sim_v2.core.verification.param_signature_verifier import (
    verify_action_param_signatures,
)
from backend.sim_v2.core.verification.return_type_verifier import (
    verify_action_return_types,
)


# Gate identifiers — stable across snapshots even if internal verifier modules
# move. CI baselines pin against these strings.
GATE_ACTION_METHOD   = "action_method_existence"   # W47
GATE_PARAM_SIGNATURE = "param_signature"           # W52
GATE_RETURN_TYPE     = "return_type"               # W56/W57
GATE_EXCEPTION       = "exception"                 # W63


# A "clean" status (no drift) per gate. Anything outside this is considered
# a finding worth tracking. NOTE: VERIFIED is universally clean; metadata
# statuses like NO_RECOMMENDATION are also clean (no actionable drift).
_CLEAN_STATUSES: dict[str, frozenset[str]] = {
    GATE_ACTION_METHOD:   frozenset({"VERIFIED", "NO_RECOMMENDATION"}),
    GATE_PARAM_SIGNATURE: frozenset({
        "VERIFIED", "NO_RECOMMENDATION", "NO_ACTION_PARAMS",
    }),
    GATE_RETURN_TYPE:     frozenset({"VERIFIED", "NO_RECOMMENDATION"}),
    GATE_EXCEPTION:       frozenset({"VERIFIED", "NO_RECOMMENDATION"}),
}


# ─────────────────────────────────────────────────────────────────────────────
# Finding model
# ─────────────────────────────────────────────────────────────────────────────


class FindingKey(BaseModel):
    """One verification finding, identified by gate + action + status + key.

    `key` is an opaque per-gate discriminator: the specific exception class for
    the exception gate, the diverging param positions tuple for the param gate,
    etc. Two findings with the same (gate, action_fqn, status, key) are
    considered "the same finding" across snapshots — `key` is what makes
    incremental diffs precise even when one action has multiple distinct
    drifts on the same gate.
    """
    model_config = ConfigDict(frozen=True)

    gate:       str
    action_fqn: str
    status:     str
    key:        str = ""

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.gate, self.action_fqn, self.status, self.key)


class VerificationSnapshot(BaseModel):
    """All findings from one verification pass on one repo."""
    model_config = ConfigDict(frozen=True)

    repo_id:    str
    findings:   tuple[FindingKey, ...] = Field(default_factory=tuple)


# ─────────────────────────────────────────────────────────────────────────────
# Per-gate finding extractors
# ─────────────────────────────────────────────────────────────────────────────


def _is_finding(gate: str, status: str) -> bool:
    return status not in _CLEAN_STATUSES.get(gate, frozenset())


def _action_method_findings(verifs) -> list[FindingKey]:
    out: list[FindingKey] = []
    for v in verifs:
        if _is_finding(GATE_ACTION_METHOD, v.status):
            out.append(FindingKey(
                gate=GATE_ACTION_METHOD,
                action_fqn=v.action_fqn,
                status=v.status,
                key=v.code_method_fqn or "",
            ))
    return out


def _param_findings(verifs) -> list[FindingKey]:
    out: list[FindingKey] = []
    for v in verifs:
        if not _is_finding(GATE_PARAM_SIGNATURE, v.status):
            continue
        # ParamVerification carries `action_params` + `method_params` tuples.
        # Compute the diverging positions on the fly so distinct drifts within
        # the same action (e.g. positions 3 vs 4) surface as separate findings.
        diverging: list[str] = []
        for i, (a, m) in enumerate(zip(v.action_params, v.method_params)):
            if a != m:
                diverging.append(f"{i}|{a}|{m}")
        if len(v.action_params) != len(v.method_params):
            diverging.append(f"arity:{len(v.action_params)}vs{len(v.method_params)}")
        key = ",".join(diverging) if diverging else (v.details or "")
        out.append(FindingKey(
            gate=GATE_PARAM_SIGNATURE,
            action_fqn=v.action_fqn,
            status=v.status,
            key=key,
        ))
    return out


def _return_type_findings(verifs) -> list[FindingKey]:
    out: list[FindingKey] = []
    for v in verifs:
        if _is_finding(GATE_RETURN_TYPE, v.status):
            # Encode (action_output, method_return) so type-drift specifics
            # are tracked. Same action with type changing across snapshots
            # is a new finding.
            key = f"{v.action_output or ''}→{v.method_return or ''}"
            out.append(FindingKey(
                gate=GATE_RETURN_TYPE,
                action_fqn=v.action_fqn,
                status=v.status,
                key=key,
            ))
    return out


def _exception_findings(verifs) -> list[FindingKey]:
    out: list[FindingKey] = []
    for v in verifs:
        if _is_finding(GATE_EXCEPTION, v.status):
            # One finding per (action, exception) pair — when a method adds a
            # new throw type, only that pair surfaces as new, not the
            # whole action.
            for exc in v.undeclared_only:
                out.append(FindingKey(
                    gate=GATE_EXCEPTION,
                    action_fqn=v.action_fqn,
                    status=v.status,
                    key=f"undeclared:{exc}",
                ))
            for exc in v.missing_only:
                out.append(FindingKey(
                    gate=GATE_EXCEPTION,
                    action_fqn=v.action_fqn,
                    status=v.status,
                    key=f"missing:{exc}",
                ))
            if not v.undeclared_only and not v.missing_only:
                # Should not happen for the above 3 statuses, but emit a
                # generic finding to avoid silently dropping it.
                out.append(FindingKey(
                    gate=GATE_EXCEPTION,
                    action_fqn=v.action_fqn,
                    status=v.status,
                    key="(no detail)",
                ))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot capture
# ─────────────────────────────────────────────────────────────────────────────


def take_snapshot(session: Session, repo_id: str) -> VerificationSnapshot:
    """Run all 4 surface gates and aggregate findings into a snapshot."""
    actions = load_actions(session, repo_id)
    findings: list[FindingKey] = []
    findings.extend(_action_method_findings(
        verify_actions(session, actions)))
    findings.extend(_param_findings(
        verify_action_param_signatures(session, actions)))
    findings.extend(_return_type_findings(
        verify_action_return_types(session, actions)))
    findings.extend(_exception_findings(
        verify_action_exceptions_batch(session, actions)))
    # Order-stable: sort by (gate, action_fqn, status, key) so equality of two
    # snapshots is deterministic.
    findings.sort(key=lambda f: f.as_tuple())
    return VerificationSnapshot(
        repo_id=repo_id, findings=tuple(findings),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Diff
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RegressionReport:
    """Diff of two snapshots — what's new, what's fixed, what's stable."""
    baseline_repo:   str
    current_repo:    str
    new_findings:    tuple[FindingKey, ...]
    fixed_findings:  tuple[FindingKey, ...]
    unchanged:       tuple[FindingKey, ...]

    @property
    def has_regression(self) -> bool:
        return len(self.new_findings) > 0

    def by_gate(
        self, findings: tuple[FindingKey, ...],
    ) -> dict[str, tuple[FindingKey, ...]]:
        grouped: dict[str, list[FindingKey]] = {}
        for f in findings:
            grouped.setdefault(f.gate, []).append(f)
        return {g: tuple(v) for g, v in grouped.items()}


def diff_snapshots(
    baseline: VerificationSnapshot, current: VerificationSnapshot,
) -> RegressionReport:
    """Diff baseline vs current. Returns sets of new / fixed / unchanged."""
    baseline_set = set(baseline.findings)
    current_set  = set(current.findings)
    new   = sorted(current_set - baseline_set, key=lambda f: f.as_tuple())
    fixed = sorted(baseline_set - current_set, key=lambda f: f.as_tuple())
    same  = sorted(baseline_set & current_set, key=lambda f: f.as_tuple())
    return RegressionReport(
        baseline_repo=baseline.repo_id,
        current_repo=current.repo_id,
        new_findings=tuple(new),
        fixed_findings=tuple(fixed),
        unchanged=tuple(same),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Serialization (for git-checked baseline)
# ─────────────────────────────────────────────────────────────────────────────


def snapshot_to_json(snapshot: VerificationSnapshot, *, indent: int | None = 2) -> str:
    """Render a snapshot as deterministic JSON suitable for git versioning."""
    payload: dict[str, Any] = {
        "repo_id":  snapshot.repo_id,
        "findings": [
            {
                "gate":       f.gate,
                "action_fqn": f.action_fqn,
                "status":     f.status,
                "key":        f.key,
            }
            for f in snapshot.findings
        ],
    }
    return json.dumps(payload, indent=indent, sort_keys=True, ensure_ascii=False)


def snapshot_from_json(payload: str) -> VerificationSnapshot:
    """Parse JSON produced by `snapshot_to_json`."""
    obj = json.loads(payload)
    findings = tuple(
        FindingKey(
            gate=f["gate"], action_fqn=f["action_fqn"],
            status=f["status"], key=f.get("key", ""),
        )
        for f in obj.get("findings", [])
    )
    return VerificationSnapshot(
        repo_id=obj.get("repo_id", ""), findings=findings,
    )


__all__ = [
    "FindingKey",
    "GATE_ACTION_METHOD",
    "GATE_EXCEPTION",
    "GATE_PARAM_SIGNATURE",
    "GATE_RETURN_TYPE",
    "RegressionReport",
    "VerificationSnapshot",
    "diff_snapshots",
    "snapshot_from_json",
    "snapshot_to_json",
    "take_snapshot",
]
