"""hypothesis intent 전용 workflow — '신규 X 가 추가되면?' 가설.

사용자 시나리오: "신규 강종 SS500 (productivity 5% 낮음) 이 추가되면
ORD20260510001 의 slab 설계 결과가 어떻게 달라져?"

4단계:
  1) analyze_existing: base_grade 의 master row 조회 (실측 데이터)
  2) synthesize_virtual_grade: new_grade row 가상 합성 (productivity 곱)
  3) synthesize_virtual_order: base_order 복제 후 GRADE_CD 만 변경
  4) preview_projection: baseline slab + productivity 차이로 추론
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.section3.agents.simulation import domain_data
from backend.section3.agents.simulation.slab_design_runner import run_full_design

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 모델
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class HypothesisResult:
    base_grade: str
    new_grade: str
    productivity_multiplier: float
    base_order_no: str

    # 1단계: 기존 데이터
    existing_productivity_rows: list[dict] = field(default_factory=list)
    existing_order_rows: dict[str, dict] = field(default_factory=dict)
    # 2단계: 가상 강종 합성
    virtual_productivity_rows: list[dict] = field(default_factory=list)
    # 3단계: 가상 주문 합성
    virtual_order_rows: dict[str, dict] = field(default_factory=dict)
    # 4단계: 시뮬 결과 추론
    baseline_slab: dict | None = None
    baseline_trace: list[dict] = field(default_factory=list)
    projected_slab: dict | None = None
    diff_summary: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _filter_rows(table_name: str, **eq: Any) -> list[dict]:
    """seed row 중 eq 조건 모두 매칭."""
    out: list[dict] = []
    for r in domain_data.list_rows(table_name, limit=1000):
        v = r.values
        if all(str(v.get(k)) == str(val) for k, val in eq.items()):
            out.append(v)
    return out


def _synthesize_grade_row(base_row: dict, new_grade: str, mult: float) -> dict:
    """SD_PRODUCTIVITY_STD 한 row 의 GRADE_CD 와 PRODUCTIVITY 변경."""
    out = dict(base_row)
    out["GRADE_CD"] = new_grade
    if "PRODUCTIVITY" in out and out["PRODUCTIVITY"] is not None:
        out["PRODUCTIVITY"] = round(float(out["PRODUCTIVITY"]) * mult, 4)
    out["_virtual"] = True
    return out


def _synthesize_order_row(base_row: dict, new_order_no: str, new_grade: str | None) -> dict:
    out = dict(base_row)
    out["ORDER_NO"] = new_order_no
    if new_grade and "GRADE_CD" in out:
        out["GRADE_CD"] = new_grade
    out["_virtual"] = True
    return out


def _project_slab(
    baseline_slab: dict, base_mult: float, new_mult: float,
) -> tuple[dict, list[dict]]:
    """baseline slab 의 단중 계열 필드를 productivity 비율로 추론.

    cumulativeProductivity 가 누적 곱이므로 (new_mult/base_mult)^n 영향.
    여기서는 단순화 — slabWgt 등 단중 계열만 비율 적용, 두께·폭은 강종 무관 (HR_SPEC).
    """
    projected = dict(baseline_slab)
    diff: list[dict] = []
    ratio = new_mult / base_mult if base_mult else 1.0

    # 단중 계열만 영향
    WGT_FIELDS = (
        "slabWgt", "slabWgtLow", "slabWgtHigh",
        "slabWgt1", "slabWgtLow1", "slabWgtHigh1",
        "firstWgtLow", "firstWgtHigh",
        "secondWgtLow", "secondWgtHigh",
        "splitWgtLow", "splitWgtHigh",
        "slabWgtInProgress",
    )
    for k in WGT_FIELDS:
        v = baseline_slab.get(k)
        if v is None:
            continue
        try:
            old = float(v)
            new = round(old * ratio, 3)
            projected[k] = new
            if abs(old - new) > 0.001:
                diff.append({
                    "field": k, "before": old, "after": new,
                    "delta": round(new - old, 3),
                    "delta_pct": round((new - old) / old * 100, 2) if old else 0,
                })
        except Exception:
            continue
    projected["_projected"] = True
    return projected, diff


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def run_hypothesis(
    *, base_grade: str = "SS400",
    new_grade: str = "SS500",
    productivity_multiplier: float = 0.95,
    base_order_no: str = "ORD20260510001",
    repo_id: str = "slab-design-real-v2",
) -> HypothesisResult:
    """4-step hypothesis workflow.

    사용자 시나리오:
      "신규 강종 ${new_grade} (${base_grade} 대비 productivity ${mult}배) 가
       추가되면 ${base_order_no} 와 동일 사양 주문의 slab 결과는?"
    """
    result = HypothesisResult(
        base_grade=base_grade, new_grade=new_grade,
        productivity_multiplier=productivity_multiplier,
        base_order_no=base_order_no,
    )

    # 1) 기존 데이터 분석
    existing_prod = _filter_rows("SD_PRODUCTIVITY_STD", GRADE_CD=base_grade)
    result.existing_productivity_rows = existing_prod
    for tbl in ("ORDER_OS", "ORDER_OM", "ORDER_QD", "ORDER_CHEMICAL"):
        rows = _filter_rows(tbl, ORDER_NO=base_order_no)
        if rows:
            result.existing_order_rows[tbl] = rows[0]

    result.notes.append(
        f"{base_grade} 강종의 SD_PRODUCTIVITY_STD row {len(existing_prod)}건 발견. "
        f"평균 productivity = "
        f"{sum(float(r.get('PRODUCTIVITY') or 0) for r in existing_prod) / max(len(existing_prod), 1):.4f}"
    )

    # 2) 가상 강종 합성
    result.virtual_productivity_rows = [
        _synthesize_grade_row(r, new_grade, productivity_multiplier)
        for r in existing_prod
    ]
    result.notes.append(
        f"{new_grade} 강종 row {len(result.virtual_productivity_rows)}건 합성 — "
        f"productivity 에 ×{productivity_multiplier} 적용."
    )

    # 3) 가상 주문 합성
    new_order_no = f"V{base_order_no[1:]}"  # 'ORD...' → 'VRD...'
    for tbl, base in result.existing_order_rows.items():
        result.virtual_order_rows[tbl] = _synthesize_order_row(
            base, new_order_no,
            new_grade if tbl == "ORDER_QD" else None,
        )
    if not result.virtual_order_rows:
        result.notes.append(f"⚠ base_order={base_order_no} 의 seed row 가 없어 가상 주문 합성 실패")
        return result
    result.notes.append(
        f"가상 주문 {new_order_no} 합성 — 4 table (OS/OM/QD/CHEMICAL) 복제, ORDER_QD.GRADE_CD 만 {new_grade}."
    )

    # 4) baseline Java 실행 + projection
    try:
        baseline = await run_full_design(order_no=base_order_no)
        slabs = baseline.get("slab_results") or []
        trace = baseline.get("trace") or []
        if slabs:
            result.baseline_slab = slabs[0]
            result.baseline_trace = trace[:5]  # 첫 5 step 만
            # productivity 평균
            base_mult = sum(float(r.get("PRODUCTIVITY") or 0) for r in existing_prod) / max(len(existing_prod), 1)
            new_mult = base_mult * productivity_multiplier
            projected, diff = _project_slab(result.baseline_slab, base_mult, new_mult)
            result.projected_slab = projected
            result.diff_summary = diff
            result.notes.append(
                f"projection 모델: 단중 계열은 cumulativeProductivity 비율 적용. "
                f"두께·폭·길이는 강종 무관 (HR_SPEC) 이라 변경 없음."
            )
        else:
            result.notes.append(f"⚠ baseline 주문 {base_order_no} 의 slab 결과 없음")
    except Exception as e:  # noqa: BLE001
        logger.exception("baseline 실행 실패")
        result.notes.append(f"⚠ baseline Java 실행 실패: {e}")

    return result
