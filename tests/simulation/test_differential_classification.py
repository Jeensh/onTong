"""Differential 응답 정합성 — 5 카테고리 분류 + normalize (STEP 3f-1).

사용자 불만:
- Java/Python raw 비교 어려움 → field_diffs 가 카테고리별 분류
- 필드 다름 → java_only / python_only 명시
- Python 응답 null 많음 → both_null 카운트 + normalize 로 noise 제거
"""

from __future__ import annotations

from decimal import Decimal


from backend.simulation.jvm_bridge.differential import (
    FieldDiff,
    _classify_diff,
    _normalize_payload,
)


# ─── 1. _normalize_payload ─────────────────────────────────────────


def test_normalize_removes_none_values():
    payload = {"a": 1, "b": None, "c": "hello"}
    assert _normalize_payload(payload) == {"a": 1, "c": "hello"}


def test_normalize_removes_empty_strings():
    payload = {"a": "value", "b": "", "c": "  "}
    assert _normalize_payload(payload) == {"a": "value"}


def test_normalize_recurses_into_nested_dicts():
    payload = {"outer": {"a": 1, "b": None, "c": {"x": None, "y": "keep"}}}
    assert _normalize_payload(payload) == {"outer": {"a": 1, "c": {"y": "keep"}}}


def test_normalize_drops_empty_dicts_after_cleaning():
    payload = {"a": 1, "b": {"x": None, "y": None}}
    # b 의 모든 값이 None 이라 b 는 빈 dict — drop
    assert _normalize_payload(payload) == {"a": 1}


def test_normalize_handles_lists():
    payload = {"items": [{"a": 1, "b": None}, {"x": None}, {"y": 2}]}
    cleaned = _normalize_payload(payload)
    # 빈 dict 제거 후 [{"a": 1}, {"y": 2}]
    assert cleaned["items"] == [{"a": 1}, {"y": 2}]


# ─── 2. _classify_diff ─────────────────────────────────────────────


REL = Decimal("1e-9")
ABS = Decimal("1e-12")


def test_classify_both_null():
    assert _classify_diff(None, None, rel=REL, abs_=ABS) == ("both_null", True)


def test_classify_python_only():
    """java=None, python=value → python_only."""
    cat, close = _classify_diff(None, 1180, rel=REL, abs_=ABS)
    assert cat == "python_only"
    assert close is False


def test_classify_java_only():
    cat, _ = _classify_diff(1180, None, rel=REL, abs_=ABS)
    assert cat == "java_only"


def test_classify_matched_numeric():
    cat, close = _classify_diff("1180", 1180, rel=REL, abs_=ABS)
    assert cat == "matched"
    assert close is True


def test_classify_mismatched():
    cat, close = _classify_diff(1180, 1200, rel=REL, abs_=ABS)
    assert cat == "mismatched"
    assert close is False


def test_classify_empty_string_treated_as_null():
    cat, _ = _classify_diff("", 1180, rel=REL, abs_=ABS)
    assert cat == "python_only"


# ─── 3. run_differential 통합 (mock — Java 가용 여부 무관) ────────


def test_differential_result_has_5_category_counts():
    """DifferentialResult 가 새 카테고리별 count 필드 보유."""
    from backend.simulation.jvm_bridge.differential import DifferentialResult

    r = DifferentialResult(java_available=True, java_ok=True, python_ok=True)
    assert hasattr(r, "matched_count")
    assert hasattr(r, "mismatched_count")
    assert hasattr(r, "java_only_count")
    assert hasattr(r, "python_only_count")
    assert hasattr(r, "both_null_count")
    assert hasattr(r, "summary")
    assert hasattr(r, "java_payload_normalized")
    assert hasattr(r, "python_payload_normalized")


def test_to_dict_includes_new_fields():
    from backend.simulation.jvm_bridge.differential import DifferentialResult

    r = DifferentialResult(
        java_available=True, java_ok=True, python_ok=True,
        matched_count=5, java_only_count=2, python_only_count=1,
        summary="5 matched / 0 mismatched / 2 java_only / 1 python_only",
    )
    d = r.to_dict()
    assert d["matched_count"] == 5
    assert d["java_only_count"] == 2
    assert d["python_only_count"] == 1
    assert "summary" in d
    assert "java_only" in d["summary"]


def test_field_diff_includes_category():
    fd = FieldDiff(path="a.b", java=1, python=2, is_close=False, category="mismatched")
    assert fd.category == "mismatched"


# ─── 4. e2e 시나리오 — Python 만 동작, Java 미가용 ────────────────


def test_run_differential_when_java_unavailable_marks_python_only():
    """Java bridge 미가용 → java_available=False, python 만 실행."""
    from backend.simulation.jvm_bridge import differential as diff_mod

    # Java unavailable mock
    original_avail = diff_mod.is_bridge_available
    original_run_py = diff_mod._run_python_pipeline

    diff_mod.is_bridge_available = lambda: False
    diff_mod._run_python_pipeline = lambda inputs: (
        True,
        {"thickness": 220, "width": 1180, "extra_python_only": "x"},
        0.01, None,
    )

    try:
        result = diff_mod.run_differential({})
        assert result.java_available is False
        assert result.python_ok is True
        # Java 안 돌았으니 비교 불가 — diffs 빈 리스트 / counts 0
        assert result.matched_count == 0
        assert result.mismatched_count == 0
        # summary 가 사용자에게 알림
        assert "비교 불가" in result.summary
    finally:
        diff_mod.is_bridge_available = original_avail
        diff_mod._run_python_pipeline = original_run_py


def test_run_differential_with_mock_both_ok_categorizes_correctly():
    """양쪽 ok + payload 다름 → 5 카테고리 분류."""
    from backend.simulation.jvm_bridge import differential as diff_mod

    original_avail = diff_mod.is_bridge_available
    original_run_java = diff_mod.run_java
    original_run_py = diff_mod._run_python_pipeline

    diff_mod.is_bridge_available = lambda: True

    class _MockJavaResult:
        ok = True
        payload = {
            "thickness": 220,        # matched
            "width": 1180,           # matched (numeric tolerance)
            "java_only_field": "X",  # java_only
            "weight": 13000,         # mismatched
            "null_in_python": "j",   # python_only category? aniyao — java_only (python 에 None)
        }
        elapsed_sec = 0.05
        stderr = ""

    diff_mod.run_java = lambda inputs, timeout_sec: _MockJavaResult()
    diff_mod._run_python_pipeline = lambda inputs: (
        True,
        {
            "thickness": "220",        # matched (string vs numeric)
            "width": 1180.0,           # matched
            "weight": 13500,           # mismatched
            "python_only_field": 99,   # python_only
            "null_in_python": None,    # both have it but python=None → java_only
        },
        0.02, None,
    )

    try:
        result = diff_mod.run_differential({})
        assert result.java_ok and result.python_ok

        # 카테고리별 카운트 검증
        # matched: thickness, width = 2
        # mismatched: weight = 1
        # java_only: java_only_field, null_in_python = 2
        # python_only: python_only_field = 1
        assert result.matched_count == 2
        assert result.mismatched_count == 1
        assert result.java_only_count == 2
        assert result.python_only_count == 1

        # summary
        assert "2 matched" in result.summary
        assert "1 mismatched" in result.summary

        # field_diffs 에 category 분류 정보
        cats = [d.category for d in result.field_diffs]
        # both_null 은 diff list 에서 제외 — count 만
        assert "matched" in cats
        assert "mismatched" in cats
        assert "java_only" in cats
        assert "python_only" in cats

        # normalized payload — null 제거됨 (python 의 null_in_python 이 사라짐)
        assert result.python_payload_normalized is not None
        assert "null_in_python" not in result.python_payload_normalized
    finally:
        diff_mod.is_bridge_available = original_avail
        diff_mod.run_java = original_run_java
        diff_mod._run_python_pipeline = original_run_py
