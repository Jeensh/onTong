"""Test case builder — Hypothesis strategy → 입력 case 리스트.

Agent 2가 호출하는 핵심 헬퍼. step_id + case_types + count → list[CaseSpec].
각 CaseSpec은 sandbox runner에 그대로 넣을 수 있는 inputs dict + 메타 정보.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis.strategies import SearchStrategy

from .hypothesis_strategies import CaseType, strategy_for


@dataclass
class CaseSpec:
    """Sandbox 한 회 실행 단위."""

    case_id: str
    case_type: CaseType
    description: str
    sandbox_inputs: dict
    expected: dict = field(default_factory=dict)


def _sample_one(strategy: SearchStrategy, max_examples: int = 1) -> Any:
    """Hypothesis strategy로부터 하나의 example을 뽑아낸다.

    Hypothesis는 .example()을 test context 외에서 쓰는 걸 경고하지만,
    우리 use case (Agent 2가 runtime에 N개 case 생성)에선 정확한 API.
    경고는 caller 측 warnings.simplefilter로 억제.
    """
    import warnings
    from hypothesis.errors import NonInteractiveExampleWarning
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", NonInteractiveExampleWarning)
        return strategy.example()


def build_cases(
    *,
    step_id: str,
    case_types: list[CaseType],
    count_per_type: int = 5,
    rules: dict[str, Any] | None = None,
) -> list[CaseSpec]:
    """N개 case_type별로 count_per_type건씩 생성.

    Args:
        step_id: sandbox registry의 step ("validator" / "productivity" / "pipeline" 등).
        case_types: ["normal", "boundary", "error", "performance"] 부분집합.
        count_per_type: 각 case_type 별 생성 개수.
        rules: pipeline에서 룰 변경 시뮬용 (예: {"hrf": "0.85"}).

    Returns:
        CaseSpec 리스트 (case_id 1번부터 순서대로).
    """
    rules = rules or {}
    cases: list[CaseSpec] = []
    seq = 0
    for ct in case_types:
        strat = strategy_for(ct)
        for _ in range(count_per_type):
            seq += 1
            overrides = _sample_one(strat)
            # 메타 필드는 sandbox inputs 에서 분리
            expected_dg = overrides.pop("_expected_dg", None) if isinstance(overrides, dict) else None
            boundary_kind = overrides.pop("_boundary_kind", None) if isinstance(overrides, dict) else None
            sandbox_inputs: dict = {"order": overrides}
            if rules:
                sandbox_inputs["rules"] = dict(rules)
            cases.append(CaseSpec(
                case_id=f"TC{seq:04d}",
                case_type=ct,
                description=_describe_case(ct, expected_dg, boundary_kind),
                sandbox_inputs=sandbox_inputs,
                expected={"dg": expected_dg} if expected_dg else {},
            ))
    return cases


_DG_HINT = {
    "DG001": "재고주문 (stockCode=1)",
    "DG002": "주문 폭/길이 양수 아님",
    "DG003": "포장단중 하한 > 상한",
    "DG004": "설계대기량상한 < 포장단중하한",
    "DG005": "작업기한일 미래 아님",
}

_BOUNDARY_HINT = {
    "very_small_pend": "설계대기량상한 0.5 (step 9 매수<1 트리거)",
    "exact_match_pkg_low": "포장단중하한 = 설계대기량상한 (DG004 경계)",
    "single_active_proc": "공정 1자리만 활성 (HR만, ' K      ')",
    "long_due_chain": "작업기한일 = 내일 (최단 미래)",
}


def _describe_case(case_type: CaseType, expected_dg: str | None,
                   boundary_kind: str | None = None) -> str:
    if case_type == "error" and expected_dg:
        hint = _DG_HINT.get(expected_dg, "")
        return f"{expected_dg} 트리거 — {hint}" if hint else f"{expected_dg} 트리거"
    if case_type == "boundary" and boundary_kind:
        return _BOUNDARY_HINT.get(boundary_kind, f"경계 — {boundary_kind}")
    return {
        "normal": "정상 분포 case",
        "boundary": "경계값 case",
        "error": "validation 실패 case",
        "performance": "대량 Slab case",
    }[case_type]


# ─── 결과 분석 헬퍼 ─────────────────────────────────────────────────


@dataclass
class CaseOutcome:
    """sandbox 실행 결과 + 메타."""

    case_id: str
    case_type: CaseType
    description: str
    inputs: dict
    expected: dict
    sandbox_ok: bool
    sandbox_result: dict | None
    sandbox_error: dict | None
    elapsed_ms: int
    matches_expectation: bool = False


def analyze_outcome(case: CaseSpec, sandbox_result_obj: Any) -> CaseOutcome:
    """SandboxResult → CaseOutcome.

    expected.dg가 설정된 case (error 타입)의 경우, 실제 validation의 error_code가 일치하는지 점검.
    """
    sandbox_ok = bool(getattr(sandbox_result_obj, "ok", False))
    sandbox_result = getattr(sandbox_result_obj, "result", None)
    sandbox_error = getattr(sandbox_result_obj, "error", None)
    elapsed_ms = int(getattr(sandbox_result_obj, "elapsed_ms", 0))

    matches = False
    if case.expected.get("dg"):
        expected = case.expected["dg"]
        # pipeline step의 경우: stage=validate + error_code 일치
        if sandbox_result and sandbox_result.get("stage") == "validate":
            ec = (sandbox_result.get("validation") or {}).get("error_code")
            matches = ec == expected
        # validator step 직접 호출
        elif sandbox_result and "validation" in sandbox_result:
            ec = sandbox_result["validation"].get("error_code")
            matches = ec == expected
    else:
        # error 의도가 없는 case는 sandbox 자체가 ok이고 비즈니스도 통과해야 매치
        if sandbox_ok and sandbox_result:
            stage = sandbox_result.get("stage")
            if stage in (None, "ok"):
                matches = True

    return CaseOutcome(
        case_id=case.case_id,
        case_type=case.case_type,
        description=case.description,
        inputs=case.sandbox_inputs,
        expected=case.expected,
        sandbox_ok=sandbox_ok,
        sandbox_result=sandbox_result,
        sandbox_error=sandbox_error,
        elapsed_ms=elapsed_ms,
        matches_expectation=matches,
    )


def summarize(outcomes: Iterable[CaseOutcome]) -> dict:
    """다수 케이스 결과 요약 — 차트용 통계 추출."""
    outcomes = list(outcomes)
    total = len(outcomes)
    by_type: dict[str, dict] = {}
    fail_cases: list[dict] = []
    slab_count_dist: list[int] = []
    productivity_dist: list[float] = []
    elapsed_total = 0

    for o in outcomes:
        slot = by_type.setdefault(o.case_type, {"total": 0, "matched": 0, "failed": 0})
        slot["total"] += 1
        if o.matches_expectation:
            slot["matched"] += 1
        if not o.matches_expectation:
            fail_cases.append({
                "case_id": o.case_id,
                "case_type": o.case_type,
                "description": o.description,
                "expected": o.expected,
                "actual_stage": (o.sandbox_result or {}).get("stage"),
                "actual_error": ((o.sandbox_result or {}).get("validation") or {}).get("error_code"),
                "sandbox_error": o.sandbox_error,
            })
            slot["failed"] += 1

        elapsed_total += o.elapsed_ms
        if o.sandbox_result:
            slab = o.sandbox_result.get("slab")
            if slab and slab.get("slabCountInProgress"):
                slab_count_dist.append(int(slab["slabCountInProgress"]))
            prod = o.sandbox_result.get("productivity") or o.sandbox_result.get("cumulative_productivity")
            if prod:
                try:
                    productivity_dist.append(float(prod))
                except (TypeError, ValueError):
                    pass

    return {
        "total": total,
        "by_type": by_type,
        "failed_count": sum(1 for o in outcomes if not o.matches_expectation),
        "fail_cases": fail_cases[:20],  # 상위 20건만
        "slab_count_distribution": slab_count_dist,
        "productivity_distribution": productivity_dist,
        "avg_elapsed_ms": (elapsed_total / total) if total else 0,
    }
