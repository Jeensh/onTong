"""UC31 — Regression-only CI demo verification — W65.3."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.snapshot import (
    FindingKey,
    GATE_EXCEPTION,
    VerificationSnapshot,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc31_regression_only.run import (
    DEFAULT_REPO,
    UC31Result,
    main,
    run_demo,
    synthesize_post_commit_snapshot,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc31_regression_only import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# synthesize_post_commit_snapshot
# ─────────────────────────────────────────────────────────────────────────────


def test_synth_adds_one_finding_and_removes_one():
    baseline = VerificationSnapshot(
        repo_id="r",
        findings=(
            FindingKey(gate=GATE_EXCEPTION, action_fqn="a.1",
                       status="UNDECLARED_THROWS"),
            FindingKey(gate=GATE_EXCEPTION, action_fqn="a.2",
                       status="UNDECLARED_THROWS"),
        ),
    )
    current = synthesize_post_commit_snapshot(baseline)
    assert len(current.findings) == 2   # -1 +1 = same total
    fqns = {f.action_fqn for f in current.findings}
    # The synthetic new action FQN should appear
    assert "action.scm.demo.uc31_new_action" in fqns


def test_synth_handles_empty_baseline():
    baseline = VerificationSnapshot(repo_id="r")
    current = synthesize_post_commit_snapshot(baseline)
    # Only the new finding is added; nothing to remove
    assert len(current.findings) == 1


def test_synth_preserves_repo_id():
    baseline = VerificationSnapshot(repo_id="my-repo")
    current = synthesize_post_commit_snapshot(baseline)
    assert current.repo_id == "my-repo"


# ─────────────────────────────────────────────────────────────────────────────
# run_demo end-to-end
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_run_demo_yields_one_new_and_one_fixed():
    session = open_readonly_session()
    try:
        result = run_demo(session)
        assert isinstance(result, UC31Result)
        assert len(result.regression.new_findings) == 1
        assert len(result.regression.fixed_findings) == 1
        assert result.regression.has_regression is True
    finally:
        session.close()


@requires_production_db
def test_run_demo_new_finding_is_synthetic():
    session = open_readonly_session()
    try:
        result = run_demo(session)
        new = result.regression.new_findings[0]
        assert new.action_fqn == "action.scm.demo.uc31_new_action"
        assert new.gate == GATE_EXCEPTION
    finally:
        session.close()


@requires_production_db
def test_run_demo_unchanged_carries_most_findings():
    """The baseline has >20 findings; most should pass through as unchanged."""
    session = open_readonly_session()
    try:
        result = run_demo(session)
        assert len(result.regression.unchanged) > 10
        assert len(result.regression.unchanged) >= len(result.baseline.findings) - 2
    finally:
        session.close()


@requires_production_db
def test_run_demo_baseline_has_known_size():
    """slab-design-real has ~23 findings across the 4 gates as of W63."""
    session = open_readonly_session()
    try:
        result = run_demo(session)
        # Sanity bound — should be more than 10, less than 200
        assert 10 < len(result.baseline.findings) < 200
    finally:
        session.close()


def test_default_repo_constant():
    assert DEFAULT_REPO == "slab-design-real"
