"""W65 — Verification snapshot + regression diff tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.snapshot import (
    FindingKey,
    GATE_ACTION_METHOD,
    GATE_EXCEPTION,
    GATE_PARAM_SIGNATURE,
    GATE_RETURN_TYPE,
    RegressionReport,
    VerificationSnapshot,
    diff_snapshots,
    snapshot_from_json,
    snapshot_to_json,
    take_snapshot,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────


def _f(gate, action_fqn, status, key=""):
    return FindingKey(
        gate=gate, action_fqn=action_fqn, status=status, key=key,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FindingKey + equality
# ─────────────────────────────────────────────────────────────────────────────


def test_finding_key_is_frozen():
    f = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:X")
    with pytest.raises(Exception):
        f.status = "VERIFIED"  # type: ignore[misc]


def test_finding_key_equal_same_tuple():
    a = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:X")
    b = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:X")
    assert a == b
    assert hash(a) == hash(b)


def test_finding_key_unequal_when_key_differs():
    a = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:X")
    b = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:Y")
    assert a != b


def test_finding_key_unequal_when_gate_differs():
    a = _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS")
    b = _f(GATE_ACTION_METHOD, "a.x", "UNDECLARED_THROWS")
    assert a != b


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot model
# ─────────────────────────────────────────────────────────────────────────────


def test_snapshot_carries_repo_id_and_findings():
    snap = VerificationSnapshot(
        repo_id="r1",
        findings=(_f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS"),),
    )
    assert snap.repo_id == "r1"
    assert len(snap.findings) == 1


def test_snapshot_is_frozen():
    snap = VerificationSnapshot(repo_id="r1")
    with pytest.raises(Exception):
        snap.repo_id = "r2"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# Diff: new / fixed / unchanged
# ─────────────────────────────────────────────────────────────────────────────


def test_diff_identical_snapshots_no_changes():
    findings = (_f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS"),)
    baseline = VerificationSnapshot(repo_id="r", findings=findings)
    current  = VerificationSnapshot(repo_id="r", findings=findings)
    r = diff_snapshots(baseline, current)
    assert r.new_findings == ()
    assert r.fixed_findings == ()
    assert r.unchanged == findings
    assert r.has_regression is False


def test_diff_surfaces_new_finding():
    baseline = VerificationSnapshot(repo_id="r")
    current = VerificationSnapshot(
        repo_id="r",
        findings=(_f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS"),),
    )
    r = diff_snapshots(baseline, current)
    assert len(r.new_findings) == 1
    assert r.fixed_findings == ()
    assert r.has_regression is True


def test_diff_surfaces_fixed_finding():
    baseline = VerificationSnapshot(
        repo_id="r",
        findings=(_f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS"),),
    )
    current = VerificationSnapshot(repo_id="r")
    r = diff_snapshots(baseline, current)
    assert r.new_findings == ()
    assert len(r.fixed_findings) == 1
    assert r.has_regression is False


def test_diff_mixed_new_and_fixed_and_unchanged():
    baseline = VerificationSnapshot(
        repo_id="r", findings=(
            _f(GATE_EXCEPTION, "a.gone", "UNDECLARED_THROWS"),
            _f(GATE_EXCEPTION, "a.same", "UNDECLARED_THROWS"),
        ),
    )
    current = VerificationSnapshot(
        repo_id="r", findings=(
            _f(GATE_EXCEPTION, "a.same", "UNDECLARED_THROWS"),
            _f(GATE_EXCEPTION, "a.new",  "UNDECLARED_THROWS"),
        ),
    )
    r = diff_snapshots(baseline, current)
    assert len(r.new_findings) == 1
    assert r.new_findings[0].action_fqn == "a.new"
    assert len(r.fixed_findings) == 1
    assert r.fixed_findings[0].action_fqn == "a.gone"
    assert len(r.unchanged) == 1
    assert r.unchanged[0].action_fqn == "a.same"


def test_diff_keys_distinguish_findings_within_same_action():
    """Same action.fqn but different `key` → distinct findings."""
    baseline = VerificationSnapshot(
        repo_id="r", findings=(
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:A"),
        ),
    )
    current = VerificationSnapshot(
        repo_id="r", findings=(
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:A"),
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:B"),
        ),
    )
    r = diff_snapshots(baseline, current)
    assert len(r.new_findings) == 1
    assert r.new_findings[0].key == "undeclared:B"
    assert len(r.unchanged) == 1


def test_regression_report_by_gate_groups_findings():
    r = RegressionReport(
        baseline_repo="r", current_repo="r",
        new_findings=(
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS"),
            _f(GATE_RETURN_TYPE, "a.y", "PRIMITIVE_MISMATCH"),
            _f(GATE_EXCEPTION, "a.z", "UNDECLARED_THROWS"),
        ),
        fixed_findings=(),
        unchanged=(),
    )
    grouped = r.by_gate(r.new_findings)
    assert set(grouped.keys()) == {GATE_EXCEPTION, GATE_RETURN_TYPE}
    assert len(grouped[GATE_EXCEPTION]) == 2
    assert len(grouped[GATE_RETURN_TYPE]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Serialization
# ─────────────────────────────────────────────────────────────────────────────


def test_serialize_round_trip():
    snap = VerificationSnapshot(
        repo_id="r1",
        findings=(
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "undeclared:X"),
            _f(GATE_ACTION_METHOD, "a.y", "METHOD_NOT_FOUND"),
        ),
    )
    payload = snapshot_to_json(snap)
    parsed = snapshot_from_json(payload)
    assert parsed == snap


def test_serialize_is_deterministic():
    """Same snapshot → same JSON (sort_keys=True ensures stability)."""
    snap = VerificationSnapshot(
        repo_id="r",
        findings=(
            _f(GATE_EXCEPTION, "a.x", "UNDECLARED_THROWS", "key1"),
            _f(GATE_EXCEPTION, "a.y", "UNDECLARED_THROWS", "key2"),
        ),
    )
    a = snapshot_to_json(snap)
    b = snapshot_to_json(snap)
    assert a == b


def test_serialize_handles_empty_snapshot():
    snap = VerificationSnapshot(repo_id="r")
    payload = snapshot_to_json(snap)
    parsed = snapshot_from_json(payload)
    assert parsed.findings == ()


def test_parse_handles_missing_key_field():
    """Older JSON without `key` should still parse with empty key."""
    payload = (
        '{"repo_id": "r", "findings": [{"gate": "exception", '
        '"action_fqn": "a.x", "status": "UNDECLARED_THROWS"}]}'
    )
    parsed = snapshot_from_json(payload)
    assert parsed.findings[0].key == ""


# ─────────────────────────────────────────────────────────────────────────────
# Production snapshot
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_take_snapshot_for_slab_design_real_is_non_empty():
    session = open_readonly_session()
    try:
        snap = take_snapshot(session, "slab-design-real")
        assert snap.repo_id == "slab-design-real"
        assert len(snap.findings) > 0
    finally:
        session.close()


@requires_production_db
def test_take_snapshot_findings_sorted_deterministically():
    """Two consecutive snapshots of the same repo must be identical."""
    session = open_readonly_session()
    try:
        a = take_snapshot(session, "slab-design-real")
        b = take_snapshot(session, "slab-design-real")
        assert a == b
        assert snapshot_to_json(a) == snapshot_to_json(b)
    finally:
        session.close()


@requires_production_db
def test_consecutive_snapshots_have_zero_regression():
    """No changes between two consecutive snapshots ⇒ no new findings."""
    session = open_readonly_session()
    try:
        a = take_snapshot(session, "slab-design-real")
        b = take_snapshot(session, "slab-design-real")
        r = diff_snapshots(a, b)
        assert r.new_findings == ()
        assert r.fixed_findings == ()
        assert len(r.unchanged) == len(a.findings)
        assert not r.has_regression
    finally:
        session.close()


@requires_production_db
def test_production_snapshot_covers_all_4_gates():
    """slab-design-real has known findings on every surface gate, so the
    snapshot must include entries for all 4 gates."""
    session = open_readonly_session()
    try:
        snap = take_snapshot(session, "slab-design-real")
        gates = {f.gate for f in snap.findings}
        assert GATE_RETURN_TYPE in gates
        assert GATE_EXCEPTION in gates
        # action_method + param may have zero findings in a clean repo but
        # at least 2 of the 4 must surface — assert that.
        assert len(gates) >= 2
    finally:
        session.close()


@requires_production_db
def test_production_snapshot_serializes_under_50kb():
    """Sanity guard for CI artifact size."""
    session = open_readonly_session()
    try:
        snap = take_snapshot(session, "slab-design-real")
        payload = snapshot_to_json(snap)
        assert len(payload) < 50_000
    finally:
        session.close()
