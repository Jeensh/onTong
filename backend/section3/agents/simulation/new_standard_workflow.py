"""신규 기준 추가 (신규 품종 / 강종 / 고객 등) → 가상 주문 → 시뮬 결과 + 코드 영향.

사용자 시나리오: "신규 품종이 하나 추가되면, 코드의 어느 부분이 영향이 있을까?"

흐름:
  1) 신규 기준 row (예: CAST_SPEC.PRODUCT_CD = 'SHEET') 정의 (사용자 입력)
  2) 그 기준과 매칭되는 기존 주문 검색 — 매칭 없으면 가상 주문 합성
  3) 가상 주문 + 신규 기준 적용 → baseline (closest 기존 주문) 대비 변경 결과 추론
  4) 영향받는 Java method 찾기 → Python 변환
  5) 코드 수정 필요 여부 판정 (신규 PRODUCT_CD 면 SdConstants enum 추가 필요 등)
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from backend.section3.agents.simulation import domain_data
from backend.section3.agents.simulation.impact_compare import (
    PROPAGATION_RULES, DIRECT_MAP, transpile_methods,
)
from backend.section3.agents.simulation.slab_design_runner import run_full_design

logger = logging.getLogger(__name__)


def _find_closest_existing_order(*, product_cd: str | None, grade_cd: str | None) -> dict[str, Any] | None:
    """신규 기준에 가장 가까운 기존 주문 찾기 (PRODUCT_CD 또는 GRADE_CD)."""
    om_rows = domain_data.list_rows("ORDER_OM", limit=50)
    qd_rows = domain_data.list_rows("ORDER_QD", limit=50)
    qd_by_order: dict[str, dict] = {str(r.values.get("ORDER_NO")): r.values for r in qd_rows}

    candidates: list[dict[str, Any]] = []
    for om in om_rows:
        v = om.values
        order_no = str(v.get("ORDER_NO"))
        qd = qd_by_order.get(order_no, {})
        score = 0
        if product_cd and str(v.get("PRODUCT_CD")) == product_cd:
            score += 2
        if grade_cd and str(qd.get("GRADE_CD")) == grade_cd:
            score += 3
        candidates.append({
            "order_no": order_no,
            "PRODUCT_CD": v.get("PRODUCT_CD"),
            "GRADE_CD": qd.get("GRADE_CD"),
            "ORDER_WIDTH": v.get("ORDER_WIDTH"),
            "ORDER_LENGTH": v.get("ORDER_LENGTH"),
            "DESIGN_PEND_QTY": v.get("DESIGN_PEND_QTY"),
            "score": score,
        })
    candidates.sort(key=lambda c: -c["score"])
    return candidates[0] if candidates else None


def _synthesize_virtual_order(
    *, new_product_cd: str | None = None,
    new_grade_cd: str | None = None,
    base_order_no: str = "ORD20260510001",
) -> dict[str, dict[str, Any]]:
    """기존 base_order 를 복제 + 변경된 column 만 새 값으로."""
    new_order_no = f"V-{(new_product_cd or new_grade_cd or 'NEW')[:6]}-{base_order_no[-4:]}"
    out: dict[str, dict[str, Any]] = {}
    for tbl in ("ORDER_OS", "ORDER_OM", "ORDER_QD", "ORDER_CHEMICAL"):
        rows = domain_data.list_rows(tbl, limit=20)
        for r in rows:
            if str(r.values.get("ORDER_NO")) == base_order_no:
                cloned = dict(r.values)
                cloned["ORDER_NO"] = new_order_no
                if tbl == "ORDER_OM" and new_product_cd:
                    cloned["PRODUCT_CD"] = new_product_cd
                if tbl == "ORDER_QD" and new_grade_cd:
                    cloned["GRADE_CD"] = new_grade_cd
                cloned["_virtual"] = True
                out[tbl] = cloned
                break
    return out


def _check_code_changes_needed(
    *, new_product_cd: str | None, new_grade_cd: str | None,
) -> list[dict[str, str]]:
    """신규 값이 hard-coded enum 등에 등록돼야 하는지 판정. 코드 수정 필요 항목 list."""
    issues: list[dict[str, str]] = []
    if new_product_cd and new_product_cd not in ("COIL", "FS"):
        issues.append({
            "severity": "high",
            "file": "slab-design-feature/.../SdConstants.java",
            "issue": f"PRODUCT_CD '{new_product_cd}' 가 SdConstants 의 enum (COIL/FS) 에 없음",
            "action": f"SdConstants 에 '{new_product_cd}' 추가 또는 SdProductCategory wrapper 분기 추가 필요",
        })
        issues.append({
            "severity": "high",
            "file": "slab-design-boot/src/main/resources/db/seed/01_master.sql",
            "issue": f"CAST_SPEC 에 PRODUCT_CD='{new_product_cd}' row 가 없음",
            "action": f"CAST_SPEC INSERT — slab_thickness, width/length 범위, wgt 범위 정의 필요",
        })
    if new_grade_cd and new_grade_cd not in ("SS400", "SS41"):
        issues.append({
            "severity": "medium",
            "file": "slab-design-boot/src/main/resources/db/seed/01_master.sql",
            "issue": f"SD_PRODUCTIVITY_STD 에 GRADE_CD='{new_grade_cd}' row 가 없음",
            "action": f"공정별 (SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF) 8 row INSERT 필요",
        })
    if not issues:
        issues.append({
            "severity": "info",
            "file": "(none)",
            "issue": "기존 enum/seed 만으로 운영 가능 — 신규 값이 이미 등록된 도메인 안",
            "action": "코드 수정 불필요",
        })
    return issues


async def run_new_standard_workflow(
    *, new_product_cd: str | None = None,
    new_grade_cd: str | None = None,
    new_custom_attrs: dict[str, Any] | None = None,
    base_order_no: str = "ORD20260510001",
    repo_id: str = "slab-design-real-v2",
) -> dict[str, Any]:
    """신규 기준 추가 시나리오의 통합 워크플로."""
    # 1) 가장 가까운 기존 주문
    closest = _find_closest_existing_order(product_cd=new_product_cd, grade_cd=new_grade_cd)

    # 2) 매칭 주문이 점수 5 (제품+강종 일치) 이상이면 그대로 사용, 그 외엔 가상 합성
    use_virtual = not (closest and closest["score"] >= 5)
    virtual_order: dict[str, dict[str, Any]] = {}
    if use_virtual:
        virtual_order = _synthesize_virtual_order(
            new_product_cd=new_product_cd, new_grade_cd=new_grade_cd,
            base_order_no=base_order_no,
        )

    # 3) baseline = 가장 가까운 기존 주문의 Java :8080 실행 결과
    baseline_order_no = closest["order_no"] if closest else base_order_no
    baseline = await run_full_design(order_no=baseline_order_no)
    slabs = baseline.get("slab_results") or []
    baseline_slab = slabs[0] if slabs else None

    # 4) projected — 신규 기준 적용 시 baseline 어떻게 변할지 (단순 추론)
    projected_slab: dict | None = None
    diff: list[dict[str, Any]] = []
    notes: list[str] = []
    if baseline_slab:
        projected_slab = copy.deepcopy(baseline_slab)
        if new_grade_cd and new_grade_cd != closest.get("GRADE_CD"):
            # 강종 변경 시 productivity ratio (간단 - 0.95 가정 또는 미지정)
            ratio = 0.95
            notes.append(f"신규 강종 {new_grade_cd} → SS400 대비 productivity ×{ratio} 가정 (추론)")
            for f in ("slabWgt", "slabWgtLow", "slabWgtHigh", "slabWgt1",
                      "firstWgtLow", "firstWgtHigh", "secondWgtLow", "secondWgtHigh"):
                if f in projected_slab and projected_slab[f] is not None:
                    try:
                        old = float(projected_slab[f])
                        projected_slab[f] = round(old * ratio, 3)
                    except Exception:
                        pass
        if new_product_cd and new_product_cd not in ("COIL", "FS"):
            notes.append(
                f"신규 품종 {new_product_cd} 의 CAST_SPEC row 가 없어 Java 실행은 DG10x 오류 가능. "
                "추론은 baseline (closest 주문) 그대로 표시."
            )
        # diff
        for k in baseline_slab:
            b = baseline_slab[k]
            a = projected_slab.get(k)
            if isinstance(b, (int, float)) and isinstance(a, (int, float)) and abs(float(b) - float(a)) > 0.001:
                diff.append({
                    "field": k, "before": b, "after": a,
                    "delta": round(float(a) - float(b), 3),
                    "delta_pct": round((float(a) - float(b)) / float(b) * 100, 2) if float(b) else 0,
                })

    # 5) 영향받는 Java method (heuristic — 신규 PRODUCT_CD 면 SdProductCategory, 신규 GRADE 면 SD_PRODUCTIVITY 관련)
    affected_method_fqns: list[str] = []
    if new_product_cd:
        affected_method_fqns.extend([
            "com.example.slabdesign.feature.sd.process.working.wrapper.SdProductCategory.from(String)",
            "com.example.slabdesign.feature.sd.process.working.action.SdThicknessAction.execute(SDOrderEntity,SDSlabEntity)",
        ])
    if new_grade_cd:
        affected_method_fqns.extend([
            "com.example.slabdesign.feature.sd.process.std.service.ProductivityService.cumulativeProductivity(String,String,String,String,String,String)",
            "com.example.slabdesign.feature.sd.process.std.service.HrSpecService.findByPlantAndProduct(String,String,String)",
        ])
    transpiled = await transpile_methods(affected_method_fqns, repo_id=repo_id)

    # 6) 코드 수정 필요 여부
    code_changes = _check_code_changes_needed(
        new_product_cd=new_product_cd, new_grade_cd=new_grade_cd,
    )

    return {
        "new_product_cd": new_product_cd,
        "new_grade_cd": new_grade_cd,
        "new_custom_attrs": new_custom_attrs or {},
        "closest_existing_order": closest,
        "use_virtual": use_virtual,
        "virtual_order": virtual_order,
        "baseline_order_no": baseline_order_no,
        "baseline_slab": baseline_slab,
        "projected_slab": projected_slab,
        "diff": diff,
        "notes": notes,
        "transpiled_methods": transpiled,
        "code_changes_needed": code_changes,
    }
