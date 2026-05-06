"""H — DiffReporter unit tests."""
from __future__ import annotations

from decimal import Decimal

from backend.modeling.simulation.diff_reporter import (
    CaseDiff,
    DiffReport,
    _classify_severity,
    _decimal_diff,
    _exception_diff,
    _mock_diff,
    _mutation_diff,
    _perf_diff,
    _value_diff,
    report_diff,
)


def _run(case_name="기본", return_value=None, exception=None, elapsed_ms=1.0,
         mock=None, mutated=None):
    return {
        "case_name": case_name,
        "return_value": return_value,
        "exception": exception,
        "elapsed_ms": elapsed_ms,
        "mock_calls_invoked": mock or [],
        "mutated_args": mutated or {},
    }


# ── _value_diff ────────────────────────────────────────────────────────────
def test_value_diff_equal_returns_none():
    assert _value_diff(1, 1) is None
    assert _value_diff("a", "a") is None
    assert _value_diff(None, None) is None


def test_value_diff_decimal_calc():
    d = _value_diff("100", "150")
    assert d == {"before": "100", "after": "150", "abs_diff": "50", "rel_pct": 50.0}


def test_value_diff_decimal_negative():
    d = _value_diff("200", "100")
    assert d["rel_pct"] == -50.0


def test_value_diff_string_fallback():
    d = _value_diff("hello", "world")
    assert d == {"before": "hello", "after": "world"}


def test_value_diff_none_handling():
    d = _value_diff(None, "abc")
    assert d == {"before": None, "after": "abc"}


# ── _decimal_diff ─────────────────────────────────────────────────────────
def test_decimal_diff_zero_before():
    d = _decimal_diff(Decimal("0"), Decimal("10"))
    assert d["abs_diff"] == "10"
    assert d["rel_pct"] is None


def test_decimal_diff_normal():
    d = _decimal_diff(Decimal("100"), Decimal("110"))
    assert d["abs_diff"] == "10"
    assert d["rel_pct"] == 10.0


# ── _mutation_diff ────────────────────────────────────────────────────────
def test_mutation_diff_empty():
    assert _mutation_diff({}, {}) is None


def test_mutation_diff_per_arg_per_key():
    before = {"0": {"a": "1", "b": "2"}}
    after = {"0": {"a": "1", "b": "5"}}     # b 변경, a 동일
    d = _mutation_diff(before, after)
    assert "0" in d
    assert "b" in d["0"]
    assert "a" not in d["0"]                  # 동일 key 는 제외


def test_mutation_diff_new_arg():
    before = {}
    after = {"1": {"x": "10"}}
    d = _mutation_diff(before, after)
    assert "1" in d


# ── _exception_diff ──────────────────────────────────────────────────────
def test_exception_diff_same_returns_none():
    assert _exception_diff("ValueError: x", "ValueError: x") is None


def test_exception_diff_improvement():
    d = _exception_diff("ValueError: x", None)
    assert d["kind"] == "improvement"


def test_exception_diff_regression():
    d = _exception_diff(None, "TypeError: y")
    assert d["kind"] == "regression"


def test_exception_diff_different_kinds():
    d = _exception_diff("ValueError: x", "TypeError: y")
    assert d["kind"] == "different"


# ── _mock_diff ────────────────────────────────────────────────────────────
def test_mock_diff_same_returns_none():
    assert _mock_diff(["a", "b"], ["b", "a"]) is None


def test_mock_diff_added_removed():
    d = _mock_diff(["a"], ["a", "b"])
    assert d == {"added": ["b"], "removed": []}


# ── _perf_diff ────────────────────────────────────────────────────────────
def test_perf_diff_within_threshold():
    assert _perf_diff(10.0, 11.0) is None         # 10% 변화 → 무시


def test_perf_diff_significant():
    d = _perf_diff(10.0, 50.0)
    assert d["rel_pct"] == 400.0


def test_perf_diff_zero_handling():
    assert _perf_diff(0, 0) is None


# ── _classify_severity ────────────────────────────────────────────────────
def test_classify_regression_from_exception():
    c = CaseDiff(case_name="x", exception_diff={"kind": "regression"})
    assert _classify_severity(c) == "regression"


def test_classify_improvement_from_exception():
    c = CaseDiff(case_name="x", exception_diff={"kind": "improvement"})
    assert _classify_severity(c) == "improvement"


def test_classify_major_when_large_return_change():
    c = CaseDiff(case_name="x", return_diff={"rel_pct": 100.0})
    assert _classify_severity(c) == "major"


def test_classify_minor_when_small_return_change():
    c = CaseDiff(case_name="x", return_diff={"rel_pct": 5.0})
    assert _classify_severity(c) == "minor"


def test_classify_none_when_no_diffs():
    c = CaseDiff(case_name="x")
    assert _classify_severity(c) == "none"


# ── report_diff (integration) ─────────────────────────────────────────────
def test_report_diff_no_changes():
    before = [_run(return_value="X")]
    after = [_run(return_value="X")]
    r = report_diff(before, after)
    assert r.overall_severity == "none"
    assert r.cases[0].severity == "none"


def test_report_diff_regression_detected():
    before = [_run(return_value="OK")]
    after = [_run(return_value=None, exception="ValueError: bad")]
    r = report_diff(before, after)
    assert r.overall_severity == "regression"
    assert "퇴행" in r.cases[0].summary


def test_report_diff_decimal_return():
    before = [_run(return_value="100")]
    after = [_run(return_value="200")]
    r = report_diff(before, after)
    assert r.cases[0].return_diff is not None
    assert r.cases[0].return_diff["rel_pct"] == 100.0


def test_report_diff_to_dict_shape():
    before = [_run(return_value="X")]
    after = [_run(return_value="Y")]
    d = report_diff(before, after).to_dict()
    assert "cases" in d
    assert "overall_severity" in d
    assert "differs_count" in d
    assert "total_cases" in d
