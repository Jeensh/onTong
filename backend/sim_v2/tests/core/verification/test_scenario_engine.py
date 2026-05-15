"""ScenarioVerificationEngine tests — W15.1."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.verification.oracle import OracleRequest
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper callables
# ─────────────────────────────────────────────────────────────────────────────


def _identity_add(a, b):
    return a + b


def _broken_add(a, b):
    return a + b + 1  # 1 off — should FAIL


def _raises_value_error(a, b):
    raise ValueError("nope")


# ─────────────────────────────────────────────────────────────────────────────
# Single-fixture cases
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_pass_when_translated_matches_baseline():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_identity_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert result.aggregate_status == "PASS"
    assert result.by_fixture["F1"].status == "PASS"


def test_engine_fail_breaking_when_outputs_differ():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_broken_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert result.aggregate_status == "FAIL_BREAKING"
    assert result.by_fixture["F1"].status == "FAIL_OUTPUT"
    assert "value mismatch" in result.by_fixture["F1"].output_diff.summary


def test_engine_pass_when_both_raise_same_exception():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_exception=ValueError)}
    engine = ScenarioVerificationEngine(
        _raises_value_error, _raises_value_error, fixtures
    )
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert result.aggregate_status == "PASS"
    assert result.by_fixture["F1"].status == "PASS"


def test_engine_fail_when_only_translated_raises():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_raises_value_error, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert result.aggregate_status == "FAIL_BREAKING"
    assert "raise mismatch" in result.by_fixture["F1"].output_diff.summary


def test_engine_fail_when_only_baseline_raises():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_identity_add, _raises_value_error, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert result.aggregate_status == "FAIL_BREAKING"


def test_engine_missing_fixture_marked_error():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_identity_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["NOPE"]))
    assert result.by_fixture["NOPE"].status == "ERROR"
    # ERROR (no FAIL_*) → INCONCLUSIVE
    assert result.aggregate_status == "INCONCLUSIVE"


# ─────────────────────────────────────────────────────────────────────────────
# Multi-fixture aggregation
# ─────────────────────────────────────────────────────────────────────────────


def test_engine_aggregate_pass_when_all_fixtures_pass():
    fixtures = {
        "F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3),
        "F2": Scenario("F2", {"a": 10, "b": 20}, expected_output=30),
    }
    engine = ScenarioVerificationEngine(_identity_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1", "F2"]))
    assert result.aggregate_status == "PASS"
    assert result.summary == "2 fixture(s): PASS=2"


def test_engine_aggregate_fail_breaking_with_one_bad_fixture():
    fixtures = {
        "F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3),
        "F2": Scenario("F2", {"a": 10, "b": 20}, expected_output=30),
    }
    # broken on F2 only — but the engine runs both, broken differs from baseline
    engine = ScenarioVerificationEngine(_broken_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1", "F2"]))
    assert result.aggregate_status == "FAIL_BREAKING"


def test_engine_summary_includes_status_counts():
    fixtures = {
        "F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3),
    }
    engine = ScenarioVerificationEngine(_identity_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    assert "PASS=1" in result.summary


# ─────────────────────────────────────────────────────────────────────────────
# OracleResult shape integrity
# ─────────────────────────────────────────────────────────────────────────────


def test_oracle_result_proposal_id_passthrough():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_identity_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="proposal-xyz", fixture_subset=["F1"]))
    assert result.proposal_id == "proposal-xyz"


def test_fixture_output_diff_has_summary():
    fixtures = {"F1": Scenario("F1", {"a": 1, "b": 2}, expected_output=3)}
    engine = ScenarioVerificationEngine(_broken_add, _identity_add, fixtures)
    result = engine.run_oracle(OracleRequest(proposal_id="p", fixture_subset=["F1"]))
    diff = result.by_fixture["F1"].output_diff
    assert diff.is_equivalent is False
    assert len(diff.summary) > 0
