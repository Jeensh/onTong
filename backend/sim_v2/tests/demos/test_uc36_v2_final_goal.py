"""UC36 — v2 final-goal capstone tests — W70.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc36_v2_final_goal.run import (
    TARGET_REPO,
    V2FinalGoalResult,
    main,
    run_v2_final_goal,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc36_v2_final_goal import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_v2_baseline_has_expected_findings():
    """v2 baseline ~23 findings after the NO_ACTION_PARAMS filter."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        assert isinstance(r, V2FinalGoalResult)
        assert 15 < r.baseline_findings < 40
    finally:
        session.close()


@requires_production_db
def test_v2_reaches_fully_clean_state():
    """Framework's projected final state for v2 = 0 remaining findings."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        assert r.simulated_findings == 0
        assert r.reduction_pct == 100.0
    finally:
        session.close()


@requires_production_db
def test_v2_effect_axis_majority_merge():
    """16 effect lifecycles → 15 MERGED + 1 DRAFT (rest_endpoint needs detail)."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        assert len(r.effect_lifecycles) == 16
        merged = sum(1 for e in r.effect_lifecycles
                     if e.final_state == "MERGED")
        assert merged == 15
    finally:
        session.close()


@requires_production_db
def test_v2_structural_axis_three_param_rename_merge():
    """The 3 v2-specific RENAME_ACTION_PARAM steps all MERGE."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        renames = [s for s in r.struct_lifecycles
                   if s.kind == "RENAME_ACTION_PARAM"]
        assert len(renames) == 3
        assert all(s.final_state == "MERGED" for s in renames)
    finally:
        session.close()


@requires_production_db
def test_v2_term_axis_two_merge_with_unblocked_cascade():
    """ProductCategory + BatchResult merge; each unblocks 2 PROPOSE_NEW_TERM
    return-type cases → 4 total unblocked."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        term_merged = sum(1 for t in r.term_lifecycles
                          if t.final_state == "MERGED")
        assert term_merged == 2
        assert r.term_unblocked_count == 4
    finally:
        session.close()


@requires_production_db
def test_v2_no_rejected_proposals():
    """The framework's deterministic pipelines should never reject a v2
    proposal — DRAFT (needs follow-up) is allowed, REJECT is not expected."""
    session = open_readonly_session()
    try:
        r = run_v2_final_goal(session)
        rejected = [
            e for e in r.effect_lifecycles if e.final_state == "REJECTED"
        ] + [
            s for s in r.struct_lifecycles if s.final_state == "REJECTED"
        ] + [
            t for t in r.term_lifecycles if t.final_state == "REJECTED"
        ]
        assert rejected == []
    finally:
        session.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
