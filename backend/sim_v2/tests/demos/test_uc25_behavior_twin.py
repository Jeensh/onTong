"""UC25 — Behavior-level twin demo verification — W59.3."""
from __future__ import annotations

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorTwinRunner,
)
from backend.sim_v2.core.verification.engine import VerificationEngine
from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.demos.uc25_behavior_twin.run import (
    JAVA_SOURCES,
    build_store,
    main,
    translate_methods,
)


def test_main_returns_zero():
    assert main() == 0


def test_translate_methods_emits_all_three():
    twins = translate_methods()
    assert set(twins.keys()) == {"addPositives", "cumulativeSum", "buggyAverage"}
    for t in twins.values():
        assert "def" in t.python_source


def test_build_store_has_expected_fixture_ids():
    twins = translate_methods()
    store = build_store(twins)
    ids = set(store.ids())
    assert {"addPos.both_pos", "addPos.left_neg", "addPos.both_zero"} <= ids
    assert {"sum.n_5", "sum.n_10", "sum.n_0"} <= ids
    assert {"avg.even", "avg.odd_baseline_wrong"} <= ids


def test_add_positives_group_passes():
    twins = translate_methods()
    store = build_store(twins)
    engine = VerificationEngine(
        fixture_runner=BehaviorTwinRunner(store), plugin="t",
    )
    req = OracleRequest(
        proposal_id="addPos",
        fixture_subset=[f for f in store.ids() if f.startswith("addPos")],
    )
    result = engine.run_oracle(req)
    assert result.aggregate_status == "PASS"
    assert len(result.by_fixture) == 3


def test_cumulative_sum_group_passes():
    twins = translate_methods()
    store = build_store(twins)
    engine = VerificationEngine(
        fixture_runner=BehaviorTwinRunner(store), plugin="t",
    )
    req = OracleRequest(
        proposal_id="sum",
        fixture_subset=[f for f in store.ids() if f.startswith("sum")],
    )
    result = engine.run_oracle(req)
    assert result.aggregate_status == "PASS"
    assert len(result.by_fixture) == 3


def test_buggy_average_surfaces_fail_breaking():
    """Aggregate FAIL_BREAKING with exactly 1 PASS + 1 FAIL_OUTPUT."""
    twins = translate_methods()
    store = build_store(twins)
    engine = VerificationEngine(
        fixture_runner=BehaviorTwinRunner(store), plugin="t",
    )
    req = OracleRequest(
        proposal_id="avg",
        fixture_subset=[f for f in store.ids() if f.startswith("avg")],
    )
    result = engine.run_oracle(req)
    assert result.aggregate_status == "FAIL_BREAKING"
    statuses = {r.status for r in result.by_fixture.values()}
    assert statuses == {"PASS", "FAIL_OUTPUT"}


def test_buggy_average_fail_carries_diff_summary():
    twins = translate_methods()
    store = build_store(twins)
    runner = BehaviorTwinRunner(store)
    r = runner.run_fixture("avg.odd_baseline_wrong", plugin="t", apply_diffs={})
    assert r.status == "FAIL_OUTPUT"
    # twin produces 3.5, baseline asserts 4 → diff 0.5
    assert "0.5" in r.output_diff.summary


def test_java_sources_define_three_methods():
    assert set(JAVA_SOURCES.keys()) == {
        "addPositives", "cumulativeSum", "buggyAverage",
    }
