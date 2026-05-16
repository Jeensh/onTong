"""UC37 — production fixture coverage tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc37_production_fixture_coverage.run import (
    CoverageReport,
    TARGET_REPO,
    main,
    run_production_coverage,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc37_production_fixture_coverage import run as r
    monkeypatch.setattr(r, "open_readonly_session", lambda *a, **kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_v2_produces_at_least_some_driveable_actions():
    """The synthesizer should drive at least a handful of v2 actions."""
    s = open_readonly_session()
    try:
        r = run_production_coverage(s)
        assert isinstance(r, CoverageReport)
        assert r.total_actions == 38
        assert r.directly_driveable >= 8     # ~11 expected, leave margin
        assert r.total_fixtures >= 100        # ~151 expected
    finally:
        s.close()


@requires_production_db
def test_v2_full_primitive_actions_have_max_combinations_fixtures():
    """FULL_PRIMITIVE rows should hit the 12-combo cap on multi-param methods."""
    s = open_readonly_session()
    try:
        r = run_production_coverage(s)
        full = [row for row in r.rows if row.status == "FULL_PRIMITIVE"]
        assert len(full) >= 5
        capped = [row for row in full if row.fixtures == 12]
        assert capped, "expected at least one 12-fixture FULL_PRIMITIVE row"
    finally:
        s.close()


@requires_production_db
def test_v2_object_ref_actions_classified_as_all_null():
    """Most v2 actions take only object_refs → ALL_NULL."""
    s = open_readonly_session()
    try:
        r = run_production_coverage(s)
        all_null = sum(1 for row in r.rows if row.status == "ALL_NULL")
        assert all_null >= 15       # roughly 25 observed in survey
    finally:
        s.close()


@requires_production_db
def test_v2_no_translate_failures():
    """Production bodies should all translate (UC11 + UC25 already cover the
    translator on real data). Any regression here means a translator gap."""
    s = open_readonly_session()
    try:
        r = run_production_coverage(s)
        failures = [row for row in r.rows if row.status == "TRANSLATE_FAIL"]
        assert failures == [], (
            f"unexpected translator failures: "
            f"{[(f.action_fqn, f.error[:80]) for f in failures]}"
        )
    finally:
        s.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
