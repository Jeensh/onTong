"""W70 — Simulated post-merge snapshot generator.

The Two-Engine framework can detect drift and produce concrete remediation
proposals (W55/W58/W64/W67) which themselves can be driven through the
Integrator lifecycle (W62/W68/W69) until they MERGE. But the framework is
*read-only* with respect to the production ontology — it never actually
mutates `data/ontology.db`. That mutation is owned by Section 2.

This module computes what the snapshot *would* look like if every MERGED
proposal were applied to the underlying data. It lets us answer the
"how clean can v2 get?" question concretely without touching production data.

Algorithm:
    1. Start from a baseline `VerificationSnapshot` (output of W65).
    2. Walk each lifecycle result. If `final_state == "MERGED"`, identify
       which `FindingKey` would be eliminated by that fix, and remove it.
    3. Return a new `SimulatedSnapshot` (alias to VerificationSnapshot for
       diff convenience) that reflects the framework's projected clean state.

Per-axis finding ↔ lifecycle-result mapping:

    Effect axis (W68 EffectLifecycleResult):
      - source_axis="exception" + effect_kind="raises" + MERGED
        → drops `FindingKey(GATE_EXCEPTION, action, _, "undeclared:<exc>")`
        and the symmetric `missing:<exc>` if it were present.
      - source_axis="annotation" + MERGED
        → drops the corresponding annotation gate finding for that kind.

    Structural axis (W69 StructuralLifecycleResult):
      - source_axis="param" + kind="RENAME_ACTION_PARAM" + MERGED
        → drops the param-signature finding for that action_fqn (key encodes
          the specific position, but every position rename merging implies
          the action's signature is fixed end-to-end).
      - source_axis="return_type" + MERGED → drops the return-type finding
        for that action_fqn.

    Term axis (W62 LifecycleResult):
      - MERGED → no direct snapshot finding corresponds (terms are
        ontology additions, not drift markers). Still tracked so the
        capstone can report "N new terms merged".

Public API:
    - SimulatedSnapshot                — VerificationSnapshot alias (for clarity)
    - apply_merged_to_snapshot         — main entry point
    - SimulationReport                 — before/after + per-axis MERGED counts
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from backend.sim_v2.core.integrator.effect_proposal_pipeline import (
    EffectLifecycleResult,
)
from backend.sim_v2.core.integrator.structural_proposal_pipeline import (
    StructuralLifecycleResult,
)
from backend.sim_v2.core.integrator.term_proposal_pipeline import (
    LifecycleResult as TermLifecycleResult,
)
from backend.sim_v2.core.verification.snapshot import (
    GATE_ACTION_METHOD,
    GATE_EXCEPTION,
    GATE_PARAM_SIGNATURE,
    GATE_RETURN_TYPE,
    FindingKey,
    VerificationSnapshot,
)


# Alias for clarity at call sites; identical to VerificationSnapshot.
SimulatedSnapshot = VerificationSnapshot


# ─────────────────────────────────────────────────────────────────────────────
# Finding ↔ lifecycle-result matching
# ─────────────────────────────────────────────────────────────────────────────


def _effect_resolves(
    finding: FindingKey, result: EffectLifecycleResult,
) -> bool:
    if result.final_state != "MERGED":
        return False
    if finding.action_fqn != result.action_fqn:
        return False
    if result.source_axis == "exception":
        if finding.gate != GATE_EXCEPTION:
            return False
        # The exception finding's key carries `undeclared:<exc>` or
        # `missing:<exc>`. We only resolve the side matching the action taken.
        return (
            f"undeclared:{result.discriminator}" == finding.key
            or f"missing:{result.discriminator}" == finding.key
        )
    # source_axis == "annotation"
    return False  # annotation findings are not in the snapshot's 4 gates


def _structural_resolves(
    finding: FindingKey, result: StructuralLifecycleResult,
) -> bool:
    if result.final_state != "MERGED":
        return False
    if finding.action_fqn != result.action_fqn:
        return False
    if result.source_axis == "param":
        return finding.gate == GATE_PARAM_SIGNATURE
    if result.source_axis == "return_type":
        return finding.gate == GATE_RETURN_TYPE
    return False


def _term_resolves(
    finding: FindingKey, result: TermLifecycleResult,
) -> bool:
    # Term proposals don't directly clear snapshot findings; PROPOSE_NEW_TERM
    # return-type fixes are unblocked by them but tracked separately.
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SimulationReport:
    """Side-by-side comparison + provenance of fixes."""
    baseline:           VerificationSnapshot
    simulated:          SimulatedSnapshot
    effect_merged:      int = 0
    structural_merged:  int = 0
    term_merged:        int = 0
    resolved_findings:  tuple[FindingKey, ...] = ()
    remaining_findings: tuple[FindingKey, ...] = ()

    @property
    def baseline_count(self) -> int:
        return len(self.baseline.findings)

    @property
    def simulated_count(self) -> int:
        return len(self.simulated.findings)

    @property
    def reduction_pct(self) -> float:
        if self.baseline_count == 0:
            return 0.0
        return (
            (self.baseline_count - self.simulated_count)
            / self.baseline_count * 100.0
        )


def apply_merged_to_snapshot(
    baseline: VerificationSnapshot,
    *,
    effect_results: Iterable[EffectLifecycleResult] = (),
    structural_results: Iterable[StructuralLifecycleResult] = (),
    term_results: Iterable[TermLifecycleResult] = (),
) -> SimulationReport:
    """Compute the snapshot v2 would have if every MERGED proposal were applied."""
    effect_list      = list(effect_results)
    structural_list  = list(structural_results)
    term_list        = list(term_results)

    effect_merged_results = [
        r for r in effect_list if r.final_state == "MERGED"
    ]
    structural_merged_results = [
        r for r in structural_list if r.final_state == "MERGED"
    ]
    term_merged_results = [
        r for r in term_list if r.final_state == "MERGED"
    ]

    resolved: list[FindingKey] = []
    remaining: list[FindingKey] = []

    for finding in baseline.findings:
        if any(_effect_resolves(finding, r) for r in effect_merged_results):
            resolved.append(finding)
            continue
        if any(_structural_resolves(finding, r) for r in structural_merged_results):
            resolved.append(finding)
            continue
        # term_resolves currently always False — kept for symmetry
        if any(_term_resolves(finding, r) for r in term_merged_results):
            resolved.append(finding)
            continue
        remaining.append(finding)

    simulated = VerificationSnapshot(
        repo_id=baseline.repo_id,
        findings=tuple(remaining),
    )

    return SimulationReport(
        baseline=baseline,
        simulated=simulated,
        effect_merged=len(effect_merged_results),
        structural_merged=len(structural_merged_results),
        term_merged=len(term_merged_results),
        resolved_findings=tuple(resolved),
        remaining_findings=tuple(remaining),
    )


__all__ = [
    "SimulatedSnapshot",
    "SimulationReport",
    "apply_merged_to_snapshot",
]
