"""testgen 단위 테스트 — Hypothesis strategy + case_builder."""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.simulation.testgen import case_builder
from backend.simulation.testgen.hypothesis_strategies import (
    boundary_order_overrides,
    confirmed_plant_with_active_sm,
    error_order_overrides,
    normal_order_overrides,
    performance_order_overrides,
    strategy_for,
)


class TestStrategies:
    def test_normal_returns_dict(self):
        sample = normal_order_overrides().example()
        assert isinstance(sample, dict)
        assert sample["stockCode"] == 0
        assert "confirmedPlantCd" in sample
        # 제강 활성
        assert sample["confirmedPlantCd"][0] != " "

    def test_boundary_returns_dict(self):
        sample = boundary_order_overrides().example()
        assert isinstance(sample, dict)

    def test_error_marks_expected_dg(self):
        sample = error_order_overrides().example()
        assert "_expected_dg" in sample
        assert sample["_expected_dg"] in {"DG001", "DG002", "DG003", "DG004", "DG005"}

    def test_performance_large_pend(self):
        sample = performance_order_overrides().example()
        assert Decimal(sample["designPendQty"]) >= Decimal("10000")

    def test_confirmed_plant_active_sm(self):
        sample = confirmed_plant_with_active_sm().example()
        assert len(sample) == 8
        assert sample[0] != " "

    def test_strategy_dispatch(self):
        for ct in ("normal", "boundary", "error", "performance"):
            s = strategy_for(ct)  # type: ignore[arg-type]
            ex = s.example()
            assert isinstance(ex, dict)


class TestCaseBuilder:
    def test_build_simple(self):
        cases = case_builder.build_cases(
            step_id="pipeline",
            case_types=["normal", "error"],
            count_per_type=3,
        )
        assert len(cases) == 6
        ids = [c.case_id for c in cases]
        assert ids == ["TC0001", "TC0002", "TC0003", "TC0004", "TC0005", "TC0006"]
        # error 케이스는 expected.dg가 채워짐
        error_cases = [c for c in cases if c.case_type == "error"]
        assert len(error_cases) == 3
        assert all(c.expected.get("dg") in {"DG001", "DG002", "DG003", "DG004", "DG005"}
                   for c in error_cases)

    def test_build_with_rules(self):
        cases = case_builder.build_cases(
            step_id="pipeline",
            case_types=["normal"],
            count_per_type=2,
            rules={"hrf": "0.85"},
        )
        for c in cases:
            assert c.sandbox_inputs.get("rules") == {"hrf": "0.85"}

    def test_no_internal_meta_in_inputs(self):
        cases = case_builder.build_cases(
            step_id="pipeline",
            case_types=["error"],
            count_per_type=2,
        )
        for c in cases:
            order = c.sandbox_inputs.get("order", {})
            assert "_expected_dg" not in order  # 메타는 expected로 분리됨


class TestOutcomeAnalysis:
    """sandbox 결과 분석 + summary 계산."""

    def test_analyze_matches_dg001_expectation(self):
        case = case_builder.CaseSpec(
            case_id="TC0001",
            case_type="error",
            description="DG001 trigger",
            sandbox_inputs={"order": {"stockCode": 1}},
            expected={"dg": "DG001"},
        )

        class FakeResult:
            ok = True
            result = {"stage": "validate", "validation": {"passed": False, "error_code": "DG001"}}
            error = None
            elapsed_ms = 5

        outcome = case_builder.analyze_outcome(case, FakeResult)
        assert outcome.matches_expectation is True

    def test_analyze_mismatch_dg(self):
        case = case_builder.CaseSpec(
            case_id="TC0002",
            case_type="error",
            description="DG002 expected",
            sandbox_inputs={"order": {}},
            expected={"dg": "DG002"},
        )

        class FakeResult:
            ok = True
            result = {"stage": "validate", "validation": {"passed": False, "error_code": "DG003"}}
            error = None
            elapsed_ms = 5

        outcome = case_builder.analyze_outcome(case, FakeResult)
        assert outcome.matches_expectation is False

    def test_analyze_normal_passes(self):
        case = case_builder.CaseSpec(
            case_id="TC0003",
            case_type="normal",
            description="normal",
            sandbox_inputs={"order": {}},
        )

        class FakeResult:
            ok = True
            result = {"stage": "ok", "slab": {"slabCountInProgress": 12}, "productivity": "0.85"}
            error = None
            elapsed_ms = 10

        outcome = case_builder.analyze_outcome(case, FakeResult)
        assert outcome.matches_expectation is True

    def test_summarize(self):
        # 가짜 outcome 3건 만들어서 summarize 동작 확인
        outcomes = []
        for i, ct in enumerate(["normal", "normal", "error"]):
            outcomes.append(case_builder.CaseOutcome(
                case_id=f"TC000{i+1}",
                case_type=ct,  # type: ignore[arg-type]
                description="",
                inputs={},
                expected={"dg": "DG001"} if ct == "error" else {},
                sandbox_ok=True,
                sandbox_result={"stage": "ok", "slab": {"slabCountInProgress": 5 + i}, "productivity": "0.8"},
                sandbox_error=None,
                elapsed_ms=10,
                matches_expectation=(ct != "error"),  # error는 stage=ok이므로 mismatch
            ))
        summary = case_builder.summarize(outcomes)
        assert summary["total"] == 3
        assert summary["failed_count"] == 1
        assert "normal" in summary["by_type"]
        assert summary["by_type"]["normal"]["matched"] == 2
        assert len(summary["slab_count_distribution"]) == 3
