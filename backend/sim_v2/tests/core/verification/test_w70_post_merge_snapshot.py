"""W70 — Post-merge snapshot simulation tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.integrator.effect_proposal_pipeline import (
    EffectLifecycleResult,
)
from backend.sim_v2.core.integrator.structural_proposal_pipeline import (
    StructuralLifecycleResult,
)
from backend.sim_v2.core.integrator.term_proposal_pipeline import (
    LifecycleResult as TermLifecycleResult,
)
from backend.sim_v2.core.verification.post_merge_snapshot import (
    SimulationReport,
    apply_merged_to_snapshot,
)
from backend.sim_v2.core.verification.snapshot import (
    FindingKey,
    GATE_ACTION_METHOD,
    GATE_EXCEPTION,
    GATE_PARAM_SIGNATURE,
    GATE_RETURN_TYPE,
    VerificationSnapshot,
)


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────


def _finding(gate, action_fqn, status="X", key=""):
    return FindingKey(gate=gate, action_fqn=action_fqn,
                      status=status, key=key)


def _effect_merged(action, axis, kind, disc=""):
    return EffectLifecycleResult(
        source_axis=axis, action_fqn=action, effect_kind=kind,
        discriminator=disc, proposal_id="p", states_visited=("MERGED",),
        final_state="MERGED", oracle_status="PASS", revision_id="r",
    )


def _structural_merged(action, axis, kind):
    return StructuralLifecycleResult(
        source_axis=axis, kind=kind, action_fqn=action,
        proposal_id="p", states_visited=("MERGED",),
        final_state="MERGED", oracle_status="PASS", revision_id="r",
    )


def _term_merged(target, fqn):
    return TermLifecycleResult(
        target_class=target, term_fqn=fqn, proposal_id="p",
        states_visited=("MERGED",), final_state="MERGED",
        oracle_status="PASS", revision_id="r",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Empty / no-op cases
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_snapshot_yields_empty_report():
    base = VerificationSnapshot(repo_id="r")
    rep = apply_merged_to_snapshot(base)
    assert rep.baseline_count == 0
    assert rep.simulated_count == 0
    assert rep.reduction_pct == 0.0


def test_no_lifecycle_results_yields_unchanged_snapshot():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(_finding(GATE_EXCEPTION, "a.x"),),
    )
    rep = apply_merged_to_snapshot(base)
    assert rep.baseline == rep.simulated
    assert rep.simulated_count == 1


def test_non_merged_results_dont_clear_findings():
    """REJECTED / DRAFT lifecycle results don't resolve any finding."""
    base = VerificationSnapshot(
        repo_id="r",
        findings=(_finding(GATE_EXCEPTION, "a.x", key="undeclared:X"),),
    )
    rejected = EffectLifecycleResult(
        source_axis="exception", action_fqn="a.x", effect_kind="raises",
        discriminator="X", proposal_id="p", states_visited=("REJECTED",),
        final_state="REJECTED",
    )
    rep = apply_merged_to_snapshot(base, effect_results=[rejected])
    assert rep.simulated_count == 1
    assert rep.effect_merged == 0


# ─────────────────────────────────────────────────────────────────────────────
# Per-axis resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_effect_merged_clears_matching_exception_finding():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS",
                     "undeclared:AlgorithmException"),
        ),
    )
    merged = _effect_merged(
        "a.x", "exception", "raises", "AlgorithmException",
    )
    rep = apply_merged_to_snapshot(base, effect_results=[merged])
    assert rep.simulated_count == 0
    assert rep.effect_merged == 1
    assert len(rep.resolved_findings) == 1


def test_effect_merged_only_clears_matching_action():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS",
                     "undeclared:X"),
            _finding(GATE_EXCEPTION, "a.y", "UNDECLARED_THROWS",
                     "undeclared:X"),
        ),
    )
    merged = _effect_merged("a.x", "exception", "raises", "X")
    rep = apply_merged_to_snapshot(base, effect_results=[merged])
    assert rep.simulated_count == 1
    # a.y still unresolved
    assert rep.simulated.findings[0].action_fqn == "a.y"


def test_effect_merged_only_clears_matching_exception_class():
    """Same action, different exception → only the matching one cleared."""
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS",
                     "undeclared:A"),
            _finding(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS",
                     "undeclared:B"),
        ),
    )
    merged = _effect_merged("a.x", "exception", "raises", "A")
    rep = apply_merged_to_snapshot(base, effect_results=[merged])
    assert rep.simulated_count == 1
    assert rep.simulated.findings[0].key == "undeclared:B"


def test_structural_param_merged_clears_param_finding():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_PARAM_SIGNATURE, "a.x", "NAME_MISMATCH",
                     "3|old|new"),
        ),
    )
    merged = _structural_merged("a.x", "param", "RENAME_ACTION_PARAM")
    rep = apply_merged_to_snapshot(base, structural_results=[merged])
    assert rep.simulated_count == 0
    assert rep.structural_merged == 1


def test_structural_return_type_merged_clears_return_finding():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_RETURN_TYPE, "a.x", "PRIMITIVE_MISMATCH"),
        ),
    )
    merged = _structural_merged("a.x", "return_type", "CHANGE_PRIMITIVE_TYPE")
    rep = apply_merged_to_snapshot(base, structural_results=[merged])
    assert rep.simulated_count == 0


def test_term_merged_does_not_directly_clear_findings():
    """Term proposals add new terms — they don't clear existing findings."""
    base = VerificationSnapshot(
        repo_id="r",
        findings=(_finding(GATE_RETURN_TYPE, "a.x"),),
    )
    merged = _term_merged("Foo", "term.x.foo")
    rep = apply_merged_to_snapshot(base, term_results=[merged])
    assert rep.simulated_count == 1
    assert rep.term_merged == 1


# ─────────────────────────────────────────────────────────────────────────────
# Combined / reduction stats
# ─────────────────────────────────────────────────────────────────────────────


def test_combined_clears_correct_subset():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", key="undeclared:Algo"),
            _finding(GATE_PARAM_SIGNATURE, "a.y", "NAME_MISMATCH"),
            _finding(GATE_RETURN_TYPE, "a.z", "PRIMITIVE_MISMATCH"),
            _finding(GATE_ACTION_METHOD, "a.w", "METHOD_NOT_FOUND"),
        ),
    )
    rep = apply_merged_to_snapshot(
        base,
        effect_results=[_effect_merged("a.x", "exception", "raises", "Algo")],
        structural_results=[
            _structural_merged("a.y", "param", "RENAME_ACTION_PARAM"),
            _structural_merged("a.z", "return_type", "CHANGE_PRIMITIVE_TYPE"),
        ],
    )
    # 3 of 4 cleared; a.w (METHOD_NOT_FOUND) remains
    assert rep.simulated_count == 1
    assert rep.simulated.findings[0].action_fqn == "a.w"
    assert rep.effect_merged == 1
    assert rep.structural_merged == 2


def test_reduction_pct_correct():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", key="undeclared:X"),
            _finding(GATE_EXCEPTION, "a.y", key="undeclared:Y"),
        ),
    )
    rep = apply_merged_to_snapshot(
        base,
        effect_results=[_effect_merged("a.x", "exception", "raises", "X")],
    )
    assert rep.reduction_pct == 50.0


def test_resolved_findings_carry_provenance():
    base = VerificationSnapshot(
        repo_id="r",
        findings=(
            _finding(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS",
                     "undeclared:X"),
        ),
    )
    rep = apply_merged_to_snapshot(
        base,
        effect_results=[_effect_merged("a.x", "exception", "raises", "X")],
    )
    assert len(rep.resolved_findings) == 1
    assert rep.resolved_findings[0].key == "undeclared:X"


def test_simulated_snapshot_repo_id_preserved():
    base = VerificationSnapshot(repo_id="my-repo")
    rep = apply_merged_to_snapshot(base)
    assert rep.simulated.repo_id == "my-repo"
