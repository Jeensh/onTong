"""변경 전후 sandbox 결과 비교 — 영향도 시각화용.

Agent 1이 룰 변경 영향도 분석 시 호출.
- 동일 표본 N개 주문에 대해 sandbox.pipeline을 2회 실행 (변경 전 / 후)
- Slab 매수, 단중, 누적 실수율의 분포 + 변동 통계
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


@dataclass
class _DistStats:
    """단일 분포 통계."""

    n: int = 0
    mean: float = 0.0
    median: float = 0.0
    min: float = 0.0
    max: float = 0.0


def _stats(values: list[float]) -> _DistStats:
    if not values:
        return _DistStats()
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mean = sum(sorted_vals) / n
    median = (
        sorted_vals[n // 2]
        if n % 2 == 1
        else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
    )
    return _DistStats(n=n, mean=mean, median=median, min=sorted_vals[0], max=sorted_vals[-1])


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _extract_metric(sandbox_result: dict | None, metric: str) -> float | None:
    """pipeline 결과에서 메트릭 추출.

    metric 종류:
      - "slab_count": slab.slabCountInProgress
      - "slab_weight": slab.slabWgtInProgress
      - "productivity": productivity 또는 cumulative_productivity
      - "split_wgt_high": slab.splitWgtHigh
    """
    if not sandbox_result:
        return None
    if metric == "productivity":
        return _to_float(sandbox_result.get("productivity") or sandbox_result.get("cumulative_productivity"))
    slab = sandbox_result.get("slab") or {}
    if metric == "slab_count":
        v = slab.get("slabCountInProgress")
        return float(v) if v is not None else None
    if metric == "slab_weight":
        return _to_float(slab.get("slabWgtInProgress"))
    if metric == "split_wgt_high":
        return _to_float(slab.get("splitWgtHigh"))
    return None


@dataclass
class DiffSummary:
    """전후 비교 요약."""

    sample_size: int = 0
    metrics: dict[str, dict] = field(default_factory=dict)
    """metric → {before: stats, after: stats, delta_mean, delta_pct, changed_orders}"""
    affected_count: int = 0
    """before vs after에서 결과(metric)가 달라진 주문 수."""
    failure_count_before: int = 0
    failure_count_after: int = 0
    # ── stage 전이 cross-tab (4셀) — 변경 전/후 stage(ok vs fail) 의 모든 조합 ──
    ok_to_ok: int = 0
    """변경 전·후 모두 OK 인 케이스 — 안전."""
    ok_to_fail: int = 0
    """변경 전 OK → 변경 후 Fail — 변경으로 새로 깨진 케이스 (★ 위험)."""
    fail_to_ok: int = 0
    """변경 전 Fail → 변경 후 OK — 변경으로 회복된 케이스."""
    fail_to_fail: int = 0
    """변경 전·후 모두 Fail — 이미 알려진 문제, 변경 영향 없음."""
    case_pairs: list[dict] = field(default_factory=list)
    """대표 케이스 (최대 20건): {idx, before_metric_X, after_metric_X, delta}"""

    def to_json(self) -> dict:
        return {
            "sample_size": self.sample_size,
            "metrics": self.metrics,
            "affected_count": self.affected_count,
            "failure_count_before": self.failure_count_before,
            "failure_count_after": self.failure_count_after,
            "stage_transitions": {
                "ok_to_ok": self.ok_to_ok,
                "ok_to_fail": self.ok_to_fail,
                "fail_to_ok": self.fail_to_ok,
                "fail_to_fail": self.fail_to_fail,
            },
            "case_pairs": self.case_pairs,
        }


def diff_results(
    before: list[Any],
    after: list[Any],
    *,
    metrics: tuple[str, ...] = ("slab_count", "productivity", "slab_weight", "split_wgt_high"),
    epsilon: float = 1e-6,
) -> DiffSummary:
    """동일 인덱스 sandbox 결과 두 리스트를 비교.

    Args:
        before, after: SandboxResult 리스트 (같은 길이, 같은 입력 순서).
        metrics: 추출할 메트릭들.
    """
    if len(before) != len(after):
        raise ValueError(f"before({len(before)}) != after({len(after)}) length")
    n = len(before)
    summary = DiffSummary(sample_size=n)
    metric_data: dict[str, dict] = {m: {"before_vals": [], "after_vals": [], "changed": 0} for m in metrics}

    affected = 0
    fail_before = 0
    fail_after = 0
    ok_ok = 0
    ok_fail = 0
    fail_ok = 0
    fail_fail = 0
    pairs: list[dict] = []

    for i, (b, a) in enumerate(zip(before, after)):
        b_res = getattr(b, "result", None) or {}
        a_res = getattr(a, "result", None) or {}
        b_stage = b_res.get("stage")
        a_stage = a_res.get("stage")
        # stage 가 None 일 때는 ok 로 간주 (단일 step 결과는 stage 없음 — 정상 실행 = ok)
        b_is_fail = bool(b_stage) and b_stage != "ok"
        a_is_fail = bool(a_stage) and a_stage != "ok"
        if b_is_fail:
            fail_before += 1
        if a_is_fail:
            fail_after += 1
        # 4-cell cross-tab
        if not b_is_fail and not a_is_fail:
            ok_ok += 1
        elif not b_is_fail and a_is_fail:
            ok_fail += 1
        elif b_is_fail and not a_is_fail:
            fail_ok += 1
        else:
            fail_fail += 1

        order_changed = False
        per_case: dict[str, Any] = {"idx": i}

        for m in metrics:
            bv = _extract_metric(b_res, m)
            av = _extract_metric(a_res, m)
            if bv is not None:
                metric_data[m]["before_vals"].append(bv)
            if av is not None:
                metric_data[m]["after_vals"].append(av)
            if bv is not None and av is not None and abs(bv - av) > epsilon:
                metric_data[m]["changed"] += 1
                order_changed = True
                per_case[f"{m}_before"] = bv
                per_case[f"{m}_after"] = av
                per_case[f"{m}_delta"] = av - bv

        if order_changed:
            affected += 1
        if order_changed and len(pairs) < 20:
            pairs.append(per_case)

    summary.affected_count = affected
    summary.failure_count_before = fail_before
    summary.failure_count_after = fail_after
    summary.ok_to_ok = ok_ok
    summary.ok_to_fail = ok_fail
    summary.fail_to_ok = fail_ok
    summary.fail_to_fail = fail_fail
    summary.case_pairs = pairs

    for m, d in metric_data.items():
        bs = _stats(d["before_vals"])
        as_ = _stats(d["after_vals"])
        delta_mean = as_.mean - bs.mean if bs.n > 0 and as_.n > 0 else 0.0
        delta_pct = ((as_.mean - bs.mean) / bs.mean * 100) if bs.n > 0 and bs.mean != 0 else 0.0
        summary.metrics[m] = {
            "before": {"n": bs.n, "mean": bs.mean, "median": bs.median, "min": bs.min, "max": bs.max},
            "after": {"n": as_.n, "mean": as_.mean, "median": as_.median, "min": as_.min, "max": as_.max},
            "delta_mean": delta_mean,
            "delta_pct": delta_pct,
            "changed_orders": d["changed"],
            "before_values": d["before_vals"][:1000],  # 차트용 — 1000건 cap
            "after_values": d["after_vals"][:1000],
        }
    return summary


def make_viz_data(summary: DiffSummary) -> dict:
    """Plotly 직접 사용 가능한 trace 데이터 생성."""
    metrics = summary.metrics
    return {
        "histograms": {
            m: {
                "before_values": metrics[m]["before_values"],
                "after_values": metrics[m]["after_values"],
                "delta_mean": metrics[m]["delta_mean"],
                "delta_pct": metrics[m]["delta_pct"],
            }
            for m in metrics
        },
        "case_pairs": summary.case_pairs,
        "affected_count": summary.affected_count,
        "sample_size": summary.sample_size,
        "stage_transitions": {
            "ok_to_ok": summary.ok_to_ok,
            "ok_to_fail": summary.ok_to_fail,
            "fail_to_ok": summary.fail_to_ok,
            "fail_to_fail": summary.fail_to_fail,
        },
    }
