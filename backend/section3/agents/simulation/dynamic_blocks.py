"""동적 UI block 생성 — 사용자 자연어 질문 → LLM 이 응답 plan 결정 → 실제 데이터 합성.

2026-05-25 신설 — 정적 LLM 분석 텍스트(card 1개) 를 넘어, 질문별로 적합한 UI block 들을
LLM 이 직접 결정해서 frontend 가 가변 렌더하도록 한다.

Block types:
  - metric_grid : 핵심 수치 카드 (label + value + unit + delta)
  - table       : 행/열 데이터 (헤더 + rows)
  - sweep_chart : 시계열/sweep 변화 (x, y[], best 강조)
  - comparison  : 변경 전/후 2열 비교 (rows: [{label, before, after, change_pct}])
  - step_callout: 21-step 어느 단계가 관여하는지 highlight (step_no + summary)
  - formula     : 수식 + 설명 + 변수 의미
  - text        : 한 단락 자연어 (heading + body)

Backend 가 LLM 으로 plan 만 받고, 가능한 경우 ontology + sweep API 로 실제 데이터를 채움.
LLM 이 만든 추정 data 는 _estimated=True 로 마킹.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """당신은 제조 IT 시뮬레이션 에이전트의 UI 디자이너입니다.
사용자의 자연어 질문 + 매칭된 ontology 컨텍스트를 받아, 가장 적절한 응답 UI block 들을
JSON 으로 설계합니다. 매번 같은 템플릿이 아니라 질문 의도에 맞춤화하세요.

사용 가능한 block type:
  1. metric_grid — 핵심 수치를 카드형 grid 로 표시
     data: {items: [{label, value (수치 또는 문자열), unit (선택), delta (선택), tone ("default"|"positive"|"negative"|"neutral")}]}
  2. table — 표
     data: {columns: [{key, label, align?}], rows: [{...key:value}]}
  3. sweep_chart — 변화 추이 (조건/스텝별 결과)
     data: {x_label, y_label, points: [{x, y, label?}], best_index? (선택)}
  4. comparison — 변경 전/후 2열 비교
     data: {before_label, after_label, rows: [{label, before, after, change_pct? (-100~+inf)}]}
  5. step_callout — 21-step 강조
     data: {steps: [{phase, step_no, title, why}]}
  6. formula — 산식
     data: {expr, vars: [{name, meaning}], note?}
  7. text — 단락 자연어
     data: {body}

각 block 은 {type, title, data, _estimated? (true 면 실제 데이터 없이 LLM 추정)} 형식.

설계 지침:
  - 사용자 질문이 sweep/추이 의도 (예: "X 를 N씩 M번 증가시키면 ...") → sweep_chart + comparison + step_callout 조합
  - 변경 영향 질문 (예: "X 바꾸면 어떻게 돼?") → metric_grid + comparison + step_callout
  - 위치/설명 질문 → text + table (관련 항목들) + step_callout
  - 신규 추가 가설 → comparison (기존 vs 신규) + metric_grid
  - 단순 정의 질문 → text + table (별칭/구성요소)
  - block 개수는 2~5개. 너무 많으면 사용자가 압도됨.
  - 실제 데이터를 모르면 _estimated: true 로 표기하고 ontology 산식 기반 추정값 사용.

응답: 반드시 다음 JSON
{
  "blocks": [
    {"type": "...", "title": "...", "data": {...}, "_estimated": false},
    ...
  ],
  "sweep_request": {  // 선택 — sweep 의도가 명확하면 backend 가 실제 실행 시도
    "variable": "designPendQtyHigh",  // ontology FQN 또는 별칭
    "start": 10000, "step": 10, "count": 10, "direction": "increase",
    "target_metric": "slabWgt"
  } | null
}"""


def _virtual_base_order() -> dict:
    """기본 가상 주문 — sweep 실행이 항상 의미있는 값 갖도록.
    실제 ORDER 테이블 없이도 LLM context + comparison block 에 쓸 reference 주문.
    """
    return {
        "ORDER_NO": "VIRT-DEMO-001",
        "ORDER_WIDTH": 1500,
        "ORDER_LENGTH": 8000,
        "ORDER_WGT_LOW": 10000,
        "ORDER_WGT_HIGH": 20000,
        "DESIGN_PEND_QTY": 40000,
        "_HR_MAX_WGT": 25000,
        "_HR_MIN_WGT": 8000,
        "_THICKNESS": 230,
        "_PRODUCTIVITY": 0.90307,
    }


def _run_quick_sweep(base: dict, variable: str, step: float, count: int, direction: str) -> list[dict]:
    """가상 주문 baseline 에서 변수를 step×count 만큼 변화시킨 sweep — walkthrough.md 산식 정확 반영.

    21-step 알고리즘 핵심 산식:
      Step 5: secondWgtLow  = max(firstWgtLow, HR_MIN_WGT)
      Step 6: secondWgtHigh = min(firstWgtHigh, HR_MAX_WGT, ORDER_WGT_HIGH, DPQ/productivity)
      Step 7: maxSplitCountUpper = ceil(secondWgtHigh / ORDER_WGT_HIGH / productivity)
      A-a Step 8: split = N→1 decrement
                  splitWgtLow  = max(ORDER_WGT_LOW × split / productivity, secondWgtLow)
                  splitWgtHigh = min(ORDER_WGT_HIGH × split / productivity, secondWgtHigh)
      Step 9: slabCount = floor(DPQ / productivity / splitWgtHigh)
      Step 10: slabWgt = splitWgtHigh   (이게 Slab 한 장의 단중)

    핵심: DPQ 증가 → splitWgtHigh 는 ow_high·hr_max 한계에 막혀 잘 안 늘어남.
          slabCount(매수) 만 증가. 즉 DPQ 가 두 배 되면 Slab 2배 매수 만듦.
    """
    import math
    hr_max = float(base.get("_HR_MAX_WGT", 25000))
    hr_min = float(base.get("_HR_MIN_WGT", 8000))
    productivity = float(base.get("_PRODUCTIVITY", 0.90307))
    baseline_var = float(base.get(variable, 0)) or 10000.0
    sign = -1 if direction in ("감소", "decrease") else 1
    points: list[dict] = []
    for i in range(count + 1):  # baseline 포함 count+1 점
        val = baseline_var + sign * step * i
        b2 = {**base, variable: val}
        ow_high = float(b2.get("ORDER_WGT_HIGH", hr_max))
        ow_low = float(b2.get("ORDER_WGT_LOW", hr_min))
        dpq = float(b2.get("DESIGN_PEND_QTY", hr_max))

        # Step 5/6 — second weight low/high
        yield_adj_high = dpq / productivity if productivity else dpq
        sw_high = min(ow_high, hr_max, yield_adj_high)
        sw_low = max(hr_min, ow_low)

        # Step 7 — maxSplit upper
        if ow_high and productivity:
            max_split = max(1, math.ceil(sw_high / ow_high / productivity))
        else:
            max_split = 1

        # A-a 루프 (Step 8) — split=max_split→1 decrement
        slab_wgt = 0.0
        opt_split = 0
        for split_try in range(max_split, 0, -1):
            split_wgt_low = max(ow_low * split_try / productivity, sw_low)
            split_wgt_high = min(ow_high * split_try / productivity, sw_high)
            if split_wgt_low <= split_wgt_high:
                opt_split = split_try
                slab_wgt = split_wgt_high
                break
        if opt_split == 0:
            # 모든 split 실패 → DG108 throw 상태로 표시
            points.append({
                "i": i, variable: round(val, 1),
                "slab_wgt": 0, "split_count": 0, "slab_count": 0,
                "feasible": False,
                "violation": "DG108 — splitWgtLow > splitWgtHigh (모든 split 시도 실패)",
            })
            continue

        # Step 9 — slabCount (한 주문에 필요한 총 Slab 매수)
        slab_count = max(1, math.floor(dpq / productivity / slab_wgt)) if slab_wgt else 1

        # Step 10 — slabWgt 검증 (slabCount × slab_wgt ∈ designPendQty 범위?)
        total_produced = slab_wgt * slab_count
        yield_low = dpq * 0.8 / productivity   # 단순화 — pendQtyLow 별도 없으면 dpq*0.8
        feasible = yield_low <= total_produced <= yield_adj_high * 1.05

        points.append({
            "i": i, variable: round(val, 1),
            "slab_wgt": round(slab_wgt, 1),
            "split_count": opt_split,
            "slab_count": slab_count,
            "total_produced": round(total_produced, 1),
            "feasible": feasible,
        })
    return points


def _fill_sweep_blocks(blocks: list[dict], sweep_request: dict | None, base: dict) -> list[dict]:
    """LLM 이 생성한 blocks 의 sweep_chart / comparison 의 data 를 실제 sweep 값으로 교체.
    sweep_request 없으면 그대로 둠.
    """
    if not sweep_request:
        return blocks
    variable = str(sweep_request.get("variable") or "DESIGN_PEND_QTY")
    # 한국어/별칭 → 표준 키 매핑
    var_map = {
        "설계대기량": "DESIGN_PEND_QTY", "designPendQty": "DESIGN_PEND_QTY",
        "설계 대기량": "DESIGN_PEND_QTY", "설계대기량 상한": "DESIGN_PEND_QTY",
        "주문 무게": "ORDER_WGT_HIGH", "orderWgt": "ORDER_WGT_HIGH",
        "포장단중 상한": "ORDER_WGT_HIGH", "pkgWgtHigh": "ORDER_WGT_HIGH",
        "포장단중 하한": "ORDER_WGT_LOW", "pkgWgtLow": "ORDER_WGT_LOW",
        "주문 폭": "ORDER_WIDTH", "orderWidth": "ORDER_WIDTH",
    }
    variable = var_map.get(variable, variable)
    if variable not in ("ORDER_WGT_HIGH", "ORDER_WGT_LOW", "DESIGN_PEND_QTY", "ORDER_WIDTH"):
        variable = "DESIGN_PEND_QTY"
    step = float(sweep_request.get("step") or 10)
    count = int(sweep_request.get("count") or 10)
    direction = str(sweep_request.get("direction") or "increase")
    points = _run_quick_sweep(base, variable, step, count, direction)
    if not points:
        return blocks

    baseline_point = points[0]
    last_point = points[-1]
    best_point = max((p for p in points if p.get("feasible")), key=lambda p: p["slab_wgt"], default=last_point)
    best_idx = points.index(best_point)

    for b in blocks:
        if b.get("type") == "sweep_chart":
            b["data"] = {
                "x_label": f"{variable} (각 step {direction} {step})",
                "y_label": "Slab 단중 (kg)",
                "points": [
                    {"x": f"+{i * step:.0f}" if direction != "감소" else f"-{i * step:.0f}",
                     "y": p["slab_wgt"], "label": f"split={p['split_count']}"}
                    for i, p in enumerate(points)
                ],
                "best_index": best_idx,
            }
            b["_estimated"] = False
        elif b.get("type") == "comparison":
            def _pct(a, b_):
                if not b_ or b_ == 0: return None
                return (a - b_) / b_ * 100
            b["data"] = {
                "before_label": f"baseline ({variable}={baseline_point[variable]:,.0f})",
                "after_label": f"after ({count}회 {direction} → {variable}={last_point[variable]:,.0f})",
                "rows": [
                    {
                        "label": f"입력 변수: {variable}",
                        "before": baseline_point[variable],
                        "after": last_point[variable],
                        "change_pct": _pct(last_point[variable], baseline_point[variable]),
                    },
                    {
                        "label": "Slab 한 장 단중 (Step 10 splitWgtHigh)",
                        "before": baseline_point["slab_wgt"],
                        "after": last_point["slab_wgt"],
                        "change_pct": _pct(last_point["slab_wgt"], baseline_point["slab_wgt"]),
                    },
                    {
                        "label": "분할수 (Step 7~8 optimalSplitCount)",
                        "before": baseline_point["split_count"],
                        "after": last_point["split_count"],
                        "change_pct": _pct(last_point["split_count"], baseline_point["split_count"]),
                    },
                    {
                        "label": "총 Slab 매수 (Step 9 slabCount)",
                        "before": baseline_point.get("slab_count", 1),
                        "after": last_point.get("slab_count", 1),
                        "change_pct": _pct(last_point.get("slab_count", 1), baseline_point.get("slab_count", 1)),
                    },
                    {
                        "label": "총 생산 단중 (slabWgt × slabCount)",
                        "before": baseline_point.get("total_produced", baseline_point["slab_wgt"]),
                        "after": last_point.get("total_produced", last_point["slab_wgt"]),
                        "change_pct": _pct(last_point.get("total_produced", 0), baseline_point.get("total_produced", 0)),
                    },
                    {
                        "label": "feasibility (Step 10 검증)",
                        "before": "OK" if baseline_point["feasible"] else "NG",
                        "after": "OK" if last_point["feasible"] else "NG",
                    },
                ],
            }
            # 핵심 인사이트 메모 — slab_wgt 가 변하지 않으면 명시
            if abs(baseline_point["slab_wgt"] - last_point["slab_wgt"]) < 0.01:
                b["title"] = (b.get("title") or "비교") + " — 한 장 단중은 동일, 매수만 변동"
            b["_estimated"] = False
    return blocks


def _try_extract_sweep_params(user_query: str) -> dict | None:
    """간단 정규식 — "X 를 N kg 씩 M 번 증가" 패턴 추출."""
    m = re.search(
        r"([가-힣A-Za-z][가-힣A-Za-z0-9_ ·]*?)\s*(?:값을\s*)?(\d+)\s*([a-zA-Z가-힣]+)?\s*씩\s*(\d+)\s*번\s*(증가|감소|변경|증감)",
        user_query,
    )
    if not m:
        return None
    return {
        "variable": m.group(1).strip(),
        "step": int(m.group(2)),
        "step_unit": m.group(3) or "",
        "count": int(m.group(4)),
        "direction": m.group(5),
    }


def _build_ontology_ctx(payload: dict) -> dict[str, Any]:
    """LLM 에 줄 ontology 컨텍스트 — payload 에서 핵심만 추출."""
    dt = payload.get("_detected_terms") or []
    te = payload.get("_term_explain") or {}
    ws = payload.get("_weight_sweep") or {}
    wc = payload.get("_weight_catalog") or {}
    tc = payload.get("_target_change") or {}
    wkstep = payload.get("_walkthrough_steps") or []
    rules = payload.get("business_rules") or payload.get("_affected_rules") or []

    return {
        "detected_terms": [{"label": d.get("label"), "fqn": d.get("term_fqn"),
                             "definition": (d.get("definition") or "")[:200]} for d in dt[:8]],
        "term_explain_summary": {
            "term_label": (te.get("term") or {}).get("label"),
            "related_actions": len(te.get("related_actions") or []),
            "business_rules": len(te.get("business_rules") or []),
            "anchor_bindings": len(te.get("anchor_bindings") or []),
        } if te else None,
        "weight_catalog_variables": [v.get("variable") for v in (wc.get("variables") or [])[:8]] if wc else [],
        "target_change": tc if tc else None,
        "sweep_best": ws.get("best") if ws else None,
        "walkthrough_steps_brief": [
            {"step_no": s.get("step_no"), "title": s.get("title"), "phase": s.get("phase")}
            for s in wkstep[:6] if s.get("step_no")
        ],
        "business_rules_brief": [
            {"fqn": r.get("fqn"), "statement": (r.get("statement") or "")[:120]}
            for r in (rules or [])[:5]
        ],
        "affected_methods_count": len(payload.get("affected_methods") or []),
        "affected_orders_count": len(payload.get("_affected_orders") or []),
    }


def _build_clarify_form(*, intent: str, user_query: str, target_key: str | None,
                        current_val: float | None) -> dict:
    """범용 입력 폼 block — 사용자 애매한 질문에 필요한 입력을 받는다.

    예) "slab 단중 하한 8000→9000 으로 바꾸면 어떤 주문이 fail?" 같은 질문도
    가상주문 N건, baseline 값, after 값, 적용 주문 선택, 비교 기준 등을 폼으로 받고
    승인 시 그 입력으로 재시뮬.
    """
    fields: list[dict] = [
        {
            "key": "n_orders", "label": "가상 주문 개수",
            "default": 5, "type": "number", "unit": "건",
            "hint": "기준 데이터에서 random 합성할 가상 주문 수 (1~10)",
        },
    ]
    if target_key and current_val is not None:
        fields.append({
            "key": "before_val", "label": f"변경 전 ({target_key})",
            "default": current_val, "type": "number",
            "hint": "현재 baseline 값",
        })
        fields.append({
            "key": "after_val", "label": f"변경 후 ({target_key})",
            "default": float(current_val) * 1.05, "type": "number",
            "hint": "비교할 변경값 — 직접 입력",
        })
    # 결과 표시 옵션
    fields.append({
        "key": "compare_mode", "label": "비교 방식",
        "default": "diff_only", "type": "select",
        "options": [
            {"value": "diff_only", "label": "변화 있는 것만 (차이 행만)"},
            {"value": "all", "label": "전체 주문 (변화 없어도 포함)"},
            {"value": "fail_only", "label": "fail 케이스만 (DG 위반)"},
        ],
        "hint": "결과 표에 어떤 행만 표시할지 선택",
    })
    # 2026-05-25 — 시뮬 결과 범위 선택
    fields.append({
        "key": "result_scope", "label": "시뮬 결과 범위",
        "default": "all_steps", "type": "select",
        "options": [
            {"value": "all_steps", "label": "전체 21-step 결과 (두께/폭/길이/단중/분할수/매수)"},
            {"value": "wgt_only", "label": "단중 관련만 (Step 4·5·6·10)"},
            {"value": "split_only", "label": "분할수·매수만 (Step 7·8·9)"},
            {"value": "final_only", "label": "최종 결과만 (Step 18·19·20: 목표 폭/길이/매수)"},
        ],
        "hint": "시뮬 결과에서 어떤 step 의 값을 surface 할지 선택",
    })
    fields.append({
        "key": "excel_export_items", "label": "Excel 추출 항목 (multi-select)",
        "default": "all", "type": "select",
        "options": [
            {"value": "all", "label": "전체 (가상 주문 + 21-step + 비교 + 산식 trace)"},
            {"value": "orders_only", "label": "가상 주문 입력값만"},
            {"value": "results_only", "label": "21-step 설계 결과만"},
            {"value": "comparison_only", "label": "비교 (before/after) 만"},
            {"value": "best_only", "label": "최적 추천 + 권장 변수만"},
        ],
        "hint": "Excel 추출 시 어떤 카드의 데이터를 포함할지 선택",
    })
    return {
        "type": "clarify_form",
        "title": "🛠 시뮬 입력 — 값 직접 지정 후 [✓ 승인] 누르세요",
        "data": {
            "intent": intent,
            "target_key": target_key,
            "fields": fields,
            "submit_label": "✓ 승인하고 가상 주문 합성 + 21-step 시뮬 실행",
        },
        "_estimated": False,
    }


def _design_one_slab(order: dict) -> dict:
    """단일 가상 주문 → 21-step 실행 결과 (Phase 1~Save). walkthrough.md 산식 그대로."""
    import math
    productivity = float(order.get("_PRODUCTIVITY", 0.90307))
    hr_max = float(order.get("_HR_MAX_WGT", 25000))
    hr_min = float(order.get("_HR_MIN_WGT", 8000))
    density = 7.82
    thickness = float(order.get("_THICKNESS", 230))
    width  = float(order.get("ORDER_WIDTH", 0) or 0)
    length = float(order.get("ORDER_LENGTH", 0) or 0)
    ow_high = float(order.get("ORDER_WGT_HIGH", 0) or 0)
    ow_low  = float(order.get("ORDER_WGT_LOW", 0) or 0)
    dpq     = float(order.get("DESIGN_PEND_QTY", 0) or 0)

    out: dict = {"order_no": order.get("ORDER_NO", "?"),
                 "case_label": order.get("_case_label", ""),
                 "case_kind":  order.get("_case_kind",  ""),
                 "thickness":  thickness}

    # Step 4 — 1차 무게 범위 (폭/길이 양 끝값으로 — walkthrough firstWgtLow/High)
    # 단순화: 1차는 thickness × width × length × density (단일점) + ±10% 범위로 폭/길이 변동 가정.
    fw_mid = thickness * width * length * density * 1e-6 if (width and length) else 0
    fw_high = fw_mid * 1.0   # 폭 상한 가정 — 동일점
    fw_low  = fw_mid * 0.85  # 폭/길이 하한 가정
    out["first_wgt"] = round(fw_high, 1)
    out["first_wgt_low"] = round(fw_low, 1)

    # Step 5/6 — second weight ★ walkthrough Step 6 산식 정확 반영:
    #   secondWgtHigh = min(firstWgtHigh, HR_MAX_WGT, ORDER_WGT_HIGH, DPQ/productivity)
    #   ← firstWgtHigh 가 빠지면 두께/폭/길이 변경 영향이 사라짐
    yield_adj = dpq / productivity if productivity else 0
    sw_high_candidates = [c for c in [fw_high if fw_high else None, ow_high if ow_high else None,
                                       hr_max, yield_adj if yield_adj else None] if c]
    sw_high = min(sw_high_candidates) if sw_high_candidates else 0
    sw_low_candidates = [c for c in [fw_low if fw_low else None, ow_low if ow_low else None,
                                      hr_min] if c]
    sw_low = max(sw_low_candidates) if sw_low_candidates else 0
    out["second_wgt_high"] = round(sw_high, 1)
    out["second_wgt_low"]  = round(sw_low, 1)

    # Step 7 — maxSplit
    if sw_high and ow_high and productivity:
        max_split = max(1, math.ceil(sw_high / ow_high / productivity))
    else:
        max_split = 0
        out["error"] = "DG106/107 — HR_MIN/MAX 또는 ORDER_WGT_HIGH 없음"
        return out
    out["max_split"] = max_split

    # A-a (Step 8) — split 결정
    slab_wgt = 0.0
    opt_split = 0
    for split_try in range(max_split, 0, -1):
        split_wgt_low = max(ow_low * split_try / productivity, sw_low)
        split_wgt_high = min(ow_high * split_try / productivity, sw_high)
        if split_wgt_low <= split_wgt_high:
            opt_split = split_try
            slab_wgt = split_wgt_high
            break
    if opt_split == 0:
        out["error"] = "DG108 — 모든 split 시도 실패"
        return out
    out["optimal_split"] = opt_split
    out["slab_wgt"] = round(slab_wgt, 1)

    # Step 9 — slabCount
    slab_count = max(1, math.floor(dpq / productivity / slab_wgt)) if slab_wgt else 1
    out["slab_count"] = slab_count

    # Step 16~19 — 최종 폭/길이 (역산)
    if slab_wgt and length and thickness:
        final_w_low = math.ceil(slab_wgt * 1e6 / (length * thickness * density))
        final_w_high = math.floor(slab_wgt * 1e6 / (4000 * thickness * density))
        out["final_width_low"]  = final_w_low
        out["final_width_high"] = final_w_high
        # Step 18 — targetSlabWidth 10mm 단위
        target_w_raw = slab_wgt * 1e6 / (length * thickness * density)
        out["target_width"] = math.ceil(target_w_raw / 10) * 10
        # Step 19 — targetSlabLength 1mm 단위
        if out["target_width"]:
            out["target_length"] = math.floor(slab_wgt * 1e6 / (out["target_width"] * thickness * density))
    out["total_produced"] = round(slab_wgt * slab_count, 1)
    out["feasible"] = True
    return out


def _extract_impact_target(user_query: str) -> dict | None:
    """impact 질문에서 대상 변수 + 변화량 추출 (regex 단순).

    예: "HR_MAX_WGT 를 5% 올리면" → {target, pct:5, direction:"increase", awaiting_input:False}
        "ORDER_WGT_HIGH 10000 으로 변경하면" → {target, absolute:10000}
        "포장단중 상한 10% 줄이면" → {target, pct:10, direction:"decrease"}
        "slab 두께 변경하면 어떻게 돼?" → {target, awaiting_input: True} (변경량 미명시)
    """
    import re
    q = user_query
    # 한국어 키워드 → 표준 키 매핑
    KEY_MAP = [
        (("HR_MAX_WGT", "압연 최대 단중", "압연최대", "HR MAX"), "HR_MAX_WGT"),
        (("HR_MIN_WGT", "압연 최소 단중", "압연최소", "HR MIN"), "HR_MIN_WGT"),
        (("ORDER_WGT_HIGH", "포장단중 상한", "포장 단중 상한", "주문 단중 상한", "단중 상한"), "ORDER_WGT_HIGH"),
        (("ORDER_WGT_LOW", "포장단중 하한", "포장 단중 하한", "주문 단중 하한", "단중 하한"), "ORDER_WGT_LOW"),
        (("DESIGN_PEND_QTY", "설계대기량", "설계 대기량", "대기량"), "DESIGN_PEND_QTY"),
        (("ORDER_WIDTH", "주문 폭", "주문폭"), "ORDER_WIDTH"),
        # 추가 — slab 두께 / 연주설비사양
        (("slab 두께", "slab두께", "Slab 두께", "Slab두께", "슬랩 두께", "슬래브 두께",
          "slabThickness", "두께"), "_THICKNESS"),
        (("EDGING", "엣징", "edging cap", "엣징 cap"), "EDGING_CAP"),
    ]
    target = None
    for kws, key in KEY_MAP:
        for kw in kws:
            if kw in q:
                target = key
                break
        if target: break
    if not target:
        return None
    # % 추출
    m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(올리|증가|상향|키우|늘리|내리|감소|하향|줄이)", q)
    direction = "increase"
    if m_pct:
        pct = float(m_pct.group(1))
        verb = m_pct.group(2)
        if verb in ("내리", "감소", "하향", "줄이"):
            direction = "decrease"
        return {"target": target, "pct": pct, "direction": direction, "awaiting_input": False}
    # 절대값
    m_abs = re.search(r"(\d{2,})\s*(?:kg|mm|%)?\s*(?:으로|로)\s*(?:변경|설정|바꾸|올리|내리)", q)
    if m_abs:
        return {"target": target, "absolute": float(m_abs.group(1)), "awaiting_input": False}
    # 변경량 미명시 — awaiting_input=True 로 3-시나리오 비교 모드 진입
    return {"target": target, "awaiting_input": True}


def _build_impact_blocks(payload: dict, user_query: str) -> list[dict]:
    """impact intent — 가상 주문 + 변경 전/후 21-step 비교 자동.

    1) 변경 대상 추출 (HR_MAX_WGT, ORDER_WGT_HIGH, DESIGN_PEND_QTY, EDGING_CAP 등)
    2) 가상 주문 1건 random 합성 (정상 중앙 범위)
    3) baseline + after 두 케이스로 21-step 실행
    4) comparison + metric_grid + step_callout blocks
    """
    import random, copy
    rng = random.Random()
    target = _extract_impact_target(user_query)
    if not target:
        return []  # 못 잡으면 LLM 경로

    base = _virtual_base_order()
    # 정상 중앙 범위에서 random 가상 주문 1건
    def _r(low, high, unit=100):
        return rng.randint(low // unit, high // unit) * unit
    base["ORDER_NO"] = f"VIRT-IMP{rng.randint(1000,9999)}"
    base["ORDER_WIDTH"]   = _r(1100, 1700, 50)
    base["ORDER_LENGTH"]  = _r(6000, 9500, 100)
    base["ORDER_WGT_LOW"] = _r(9000, 12500, 250)
    base["ORDER_WGT_HIGH"]= _r(15000, 22000, 250)
    base["DESIGN_PEND_QTY"]= _r(28000, 50000, 500)

    # 변경 적용
    target_key = target["target"]
    pct = target.get("pct")
    absv = target.get("absolute")
    direction = target.get("direction", "increase")
    awaiting = bool(target.get("awaiting_input"))

    # 변경 대상이 _HR_MAX_WGT/_HR_MIN_WGT 같은 backend 내부 상수일 수도
    key_in_base = target_key
    if target_key == "HR_MAX_WGT":
        key_in_base = "_HR_MAX_WGT"
    elif target_key == "HR_MIN_WGT":
        key_in_base = "_HR_MIN_WGT"
    elif target_key == "EDGING_CAP":
        key_in_base = "ORDER_WIDTH"
    elif target_key == "_THICKNESS":
        key_in_base = "_THICKNESS"

    cur_val = float(base.get(key_in_base, 0)) or 0

    # ── 모든 impact 응답 첫 줄에 clarify_form (값 직접 입력 받기) ──
    _form_block = _build_clarify_form(
        intent="impact", user_query=user_query,
        target_key=key_in_base, current_val=cur_val,
    )

    # ── awaiting_input 모드 — 3 시나리오 자동 비교 + 사용자 input 안내 ──
    if awaiting and cur_val:
        scenarios = [
            ("-10%", -10, "감소"),
            ("+5%",   +5, "소폭 증가"),
            ("+20%", +20, "대폭 증가"),
        ]
        designs_by_label = {}
        designs_by_label["baseline (0%)"] = _design_one_slab(base)
        for label, pct_, _ in scenarios:
            v = cur_val + cur_val * (pct_ / 100.0)
            b2 = copy.deepcopy(base)
            b2[key_in_base] = round(v, 1)
            designs_by_label[f"{label} ({key_in_base}={int(v)})"] = _design_one_slab(b2)

        blocks: list[dict] = [_form_block]
        blocks.append({
            "type": "text",
            "title": f"⚙️ 변경 대상 확인 — {target_key}",
            "data": {"body": (
                f"질문에서 변경량(예: '5% 증가', '300mm 로 변경') 이 명시되지 않아 "
                f"3가지 시나리오 (10% 감소 / 5% 증가 / 20% 증가) 를 동시 시뮬했습니다.\n"
                f"원하는 변경량을 직접 지정하시려면 아래 인터랙티브 패널에서 "
                f"{key_in_base} 값을 입력하시면 자동 재계산됩니다."
            )},
        })
        blocks.append({
            "type": "metric_grid",
            "title": f"🧪 합성된 가상 주문 ({base['ORDER_NO']})",
            "data": {"items": [
                {"label": "주문 폭", "value": base["ORDER_WIDTH"], "unit": "mm"},
                {"label": "주문 길이", "value": base["ORDER_LENGTH"], "unit": "mm"},
                {"label": "주문 단중 하한", "value": base["ORDER_WGT_LOW"], "unit": "kg"},
                {"label": "주문 단중 상한", "value": base["ORDER_WGT_HIGH"], "unit": "kg"},
                {"label": "설계 대기량", "value": base["DESIGN_PEND_QTY"], "unit": "kg"},
                {"label": f"현재 {key_in_base}", "value": int(cur_val), "tone": "neutral"},
            ]},
            "_estimated": False,
        })
        # 4 시나리오 비교 표
        def _row(label, d):
            return {
                "case": label, "thickness": f"{d.get('thickness','-')} mm",
                "first_wgt": f"{d.get('first_wgt','-'):,} kg" if isinstance(d.get('first_wgt'),(int,float)) else "-",
                "second_wgt_high": f"{d.get('second_wgt_high','-'):,} kg" if isinstance(d.get('second_wgt_high'),(int,float)) else "-",
                "max_split": d.get("max_split", "-"),
                "optimal_split": d.get("optimal_split", "-"),
                "slab_count": d.get("slab_count", "-"),
                "slab_wgt": f"{d.get('slab_wgt','-'):,} kg" if isinstance(d.get('slab_wgt'),(int,float)) else "-",
                "target_width": f"{d.get('target_width','-'):,} mm" if isinstance(d.get('target_width'),(int,float)) else "-",
                "target_length": f"{d.get('target_length','-'):,} mm" if isinstance(d.get('target_length'),(int,float)) else "-",
                "result": "✅ OK" if d.get("feasible") else f"❌ {d.get('error','실패')}",
            }
        blocks.append({
            "type": "table",
            "title": f"📐 {target_key} 변경 시나리오 4종 — 21-step 결과 비교",
            "data": {
                "columns": [
                    {"key": "case", "label": "시나리오"},
                    {"key": "thickness", "label": "Step1: 두께", "align": "right"},
                    {"key": "first_wgt", "label": "Step4: 1차", "align": "right"},
                    {"key": "second_wgt_high", "label": "Step6: 2차상한", "align": "right"},
                    {"key": "max_split", "label": "Step7", "align": "right"},
                    {"key": "optimal_split", "label": "Step8 분할", "align": "right"},
                    {"key": "slab_count", "label": "Step9 매수", "align": "right"},
                    {"key": "slab_wgt", "label": "Step10 단중", "align": "right"},
                    {"key": "target_width", "label": "Step18 폭", "align": "right"},
                    {"key": "target_length", "label": "Step19 길이", "align": "right"},
                    {"key": "result", "label": "결과"},
                ],
                "rows": [_row(label, d) for label, d in designs_by_label.items()],
            },
            "_estimated": False,
        })
        # baseline vs +20% comparison (가장 큰 변화)
        bd = designs_by_label["baseline (0%)"]
        last_label = list(designs_by_label.keys())[-1]
        ad = designs_by_label[last_label]
        def _pct(a, b): return (a - b) / b * 100 if b else None
        blocks.append({
            "type": "comparison",
            "title": "📊 핵심 변화 (baseline vs 최대 변경) — 실측 비교",
            "data": {
                "before_label": "baseline (현재)",
                "after_label": last_label,
                "rows": [
                    {"label": "Slab 한 장 단중 (kg)", "before": bd.get("slab_wgt",0), "after": ad.get("slab_wgt",0),
                     "change_pct": _pct(ad.get("slab_wgt",0), bd.get("slab_wgt",0))},
                    {"label": "분할수", "before": bd.get("optimal_split",0), "after": ad.get("optimal_split",0),
                     "change_pct": _pct(ad.get("optimal_split",0), bd.get("optimal_split",0))},
                    {"label": "총 매수", "before": bd.get("slab_count",0), "after": ad.get("slab_count",0),
                     "change_pct": _pct(ad.get("slab_count",0), bd.get("slab_count",0))},
                    {"label": "총 생산 단중 (kg)", "before": bd.get("total_produced",0), "after": ad.get("total_produced",0),
                     "change_pct": _pct(ad.get("total_produced",0), bd.get("total_produced",0))},
                    {"label": "feasibility", "before": "OK" if bd.get("feasible") else "NG",
                     "after": "OK" if ad.get("feasible") else "NG"},
                ],
            },
            "_estimated": False,
        })
        blocks.append({
            "type": "step_callout",
            "title": f"📚 {target_key} 변경 영향 단계",
            "data": {"steps": [
                {"phase": "phase_2a", "step_no": 1, "title": "Slab 두께 결정",
                 "why": "CAST_SPEC.slabThickness — 모든 후속 무게 산식의 입력"},
                {"phase": "phase_2a", "step_no": 4, "title": "1차 무게",
                 "why": "두께 × 폭 × 길이 × 비중 — 두께가 직접 인자"},
                {"phase": "phase_2a", "step_no": 6, "title": "2차 무게 상한",
                 "why": "1차 무게 상한 → min(HR_MAX, ORDER_WGT_HIGH, DPQ/p) 와 함께 좁힘"},
                {"phase": "phase_2c", "step_no": 18, "title": "목표 폭 (역산)",
                 "why": "Slab 단중에서 폭/길이를 거꾸로 계산 — 두께가 분모"},
            ]},
        })
        return blocks

    # ── 단일 시나리오 (변경량 명시) ──
    after = copy.deepcopy(base)
    if pct is not None and cur_val:
        delta = cur_val * (pct / 100.0)
        new_val = cur_val + delta if direction == "increase" else cur_val - delta
    elif absv is not None:
        new_val = absv
    else:
        new_val = cur_val
    after[key_in_base] = round(new_val, 1)

    # baseline + after 설계
    d_before = _design_one_slab(base)
    d_after = _design_one_slab(after)
    direction_ko = "증가" if direction == "increase" else "감소"

    blocks: list[dict] = [_form_block]

    # 1) 가상 주문 정보 (1건)
    blocks.append({
        "type": "metric_grid",
        "title": f"🧪 합성된 가상 주문 ({base['ORDER_NO']}) — 기준 데이터 범위에서 random 생성",
        "data": {
            "items": [
                {"label": "주문 폭", "value": base["ORDER_WIDTH"], "unit": "mm"},
                {"label": "주문 길이", "value": base["ORDER_LENGTH"], "unit": "mm"},
                {"label": "주문 단중 하한", "value": base["ORDER_WGT_LOW"], "unit": "kg"},
                {"label": "주문 단중 상한", "value": base["ORDER_WGT_HIGH"], "unit": "kg"},
                {"label": "설계 대기량", "value": base["DESIGN_PEND_QTY"], "unit": "kg"},
                {"label": "강 비중", "value": 7.82, "unit": "g/cm³"},
            ],
        },
        "_estimated": False,
    })

    # 2) 변경 대상 — 변경 전/후 highlight
    blocks.append({
        "type": "metric_grid",
        "title": f"🔄 변경 대상: {target_key} ({direction_ko} " + (f"{pct}%" if pct else f"→ {absv}") + ")",
        "data": {
            "items": [
                {"label": "변경 전", "value": int(cur_val) if cur_val.is_integer() else cur_val,
                 "tone": "neutral"},
                {"label": "변경 후", "value": int(new_val) if float(new_val).is_integer() else new_val,
                 "tone": "positive"},
                {"label": "차이",
                 "value": f"{'+' if new_val > cur_val else ''}{int(new_val - cur_val)}",
                 "tone": "positive" if new_val > cur_val else "negative"},
            ],
        },
        "_estimated": False,
    })

    # 3) 21-step 결과 비교 (변경 전/후 row 2개)
    def _row(d, label):
        return {
            "case": label, "thickness": f"{d.get('thickness','-')} mm",
            "first_wgt": f"{d.get('first_wgt','-'):,} kg" if isinstance(d.get('first_wgt'),(int,float)) else "-",
            "second_wgt_high": f"{d.get('second_wgt_high','-'):,} kg" if isinstance(d.get('second_wgt_high'),(int,float)) else "-",
            "max_split": d.get("max_split", "-"),
            "optimal_split": d.get("optimal_split", "-"),
            "slab_count": d.get("slab_count", "-"),
            "slab_wgt": f"{d.get('slab_wgt','-'):,} kg" if isinstance(d.get('slab_wgt'),(int,float)) else "-",
            "target_width": f"{d.get('target_width','-'):,} mm" if isinstance(d.get('target_width'),(int,float)) else "-",
            "target_length": f"{d.get('target_length','-'):,} mm" if isinstance(d.get('target_length'),(int,float)) else "-",
            "result": "✅ OK" if d.get("feasible") else f"❌ {d.get('error','실패')}",
        }
    blocks.append({
        "type": "table",
        "title": f"📐 21-step 설계 결과 — 변경 전/후 비교",
        "data": {
            "columns": [
                {"key": "case", "label": "구분"},
                {"key": "thickness", "label": "Step1: 두께", "align": "right"},
                {"key": "first_wgt", "label": "Step4: 1차 무게", "align": "right"},
                {"key": "second_wgt_high", "label": "Step6: 2차 상한", "align": "right"},
                {"key": "max_split", "label": "Step7: 최대분할", "align": "right"},
                {"key": "optimal_split", "label": "Step8: 분할수", "align": "right"},
                {"key": "slab_count", "label": "Step9: 매수", "align": "right"},
                {"key": "slab_wgt", "label": "Step10: Slab단중", "align": "right"},
                {"key": "target_width", "label": "Step18: 목표폭", "align": "right"},
                {"key": "target_length", "label": "Step19: 목표길이", "align": "right"},
                {"key": "result", "label": "결과"},
            ],
            "rows": [
                _row(d_before, f"baseline ({target_key}={int(cur_val)})"),
                _row(d_after,  f"after ({target_key}={int(new_val)})"),
            ],
        },
        "_estimated": False,
    })

    # 4) 핵심 변화 — Slab 단중·매수·총 생산 비교 (사용자가 가장 보고 싶은 것)
    def _pct(a, b):
        if not b: return None
        return (a - b) / b * 100
    sw_b = d_before.get("slab_wgt", 0) or 0
    sw_a = d_after.get("slab_wgt", 0) or 0
    sc_b = d_before.get("slab_count", 0) or 0
    sc_a = d_after.get("slab_count", 0) or 0
    tp_b = d_before.get("total_produced", 0) or 0
    tp_a = d_after.get("total_produced", 0) or 0
    blocks.append({
        "type": "comparison",
        "title": "📊 핵심 변화 — Slab 결과 비교",
        "data": {
            "before_label": f"baseline ({target_key}={int(cur_val)})",
            "after_label": f"after ({target_key}={int(new_val)} = {direction_ko} {pct}%)" if pct else f"after ({target_key}={int(new_val)})",
            "rows": [
                {"label": "Slab 한 장 단중 (kg)", "before": sw_b, "after": sw_a, "change_pct": _pct(sw_a, sw_b)},
                {"label": "분할수 (split)", "before": d_before.get("optimal_split", 0),
                 "after": d_after.get("optimal_split", 0),
                 "change_pct": _pct(d_after.get("optimal_split", 0), d_before.get("optimal_split", 0))},
                {"label": "총 매수 (slabCount)", "before": sc_b, "after": sc_a, "change_pct": _pct(sc_a, sc_b)},
                {"label": "총 생산 단중 (kg)", "before": tp_b, "after": tp_a, "change_pct": _pct(tp_a, tp_b)},
                {"label": "최대 분할수 (Step7)", "before": d_before.get("max_split", 0),
                 "after": d_after.get("max_split", 0),
                 "change_pct": _pct(d_after.get("max_split", 0), d_before.get("max_split", 0))},
                {"label": "feasibility", "before": "OK" if d_before.get("feasible") else "NG",
                 "after": "OK" if d_after.get("feasible") else "NG"},
            ],
        },
        "_estimated": False,
    })

    # 5) 영향 단계 강조
    blocks.append({
        "type": "step_callout",
        "title": f"📚 {target_key} 변경이 영향을 주는 21-step 단계",
        "data": {
            "steps": [
                {"phase": "phase_2a", "step_no": 6, "title": "2차 무게 상한",
                 "why": f"min(firstWgtHigh, HR_MAX_WGT, ORDER_WGT_HIGH, DPQ/p) — {target_key} 가 직접 인자"},
                {"phase": "phase_2a", "step_no": 7, "title": "최대 분할수",
                 "why": "secondWgtHigh 가 변하면 maxSplit 도 ceil 로 영향"},
                {"phase": "phase_2b", "step_no": 8, "title": "A-a 루프: split 결정",
                 "why": "split 별 splitWgtHigh = min(ow_high×split/p, secondWgtHigh)"},
                {"phase": "phase_2b", "step_no": 10, "title": "Slab 단중 확정",
                 "why": "slabWgt = splitWgtHigh — 한 장 단중 결정"},
            ],
        },
    })

    return blocks


def _extract_new_standard(user_query: str) -> dict:
    """질문에서 추가할 신규 기준 종류 추출. 예: '신규 고객사' → kind=customer + 제안 default.

    return: {kind, label, fields:[{key,label,default,unit?}]}
    """
    q = user_query
    if any(k in q for k in ("신규 고객사", "새 고객사", "고객사 추가", "신규 고객", "고객 추가")):
        return {
            "kind": "customer", "label": "신규 고객사 (CUSTOMER_STD)",
            "fields": [
                {"key": "customerCd", "label": "고객사 코드", "default": "CUST-NEW", "type": "string"},
                {"key": "pkgWgtLow",  "label": "포장단중 하한 (kg)", "default": 10000, "type": "number", "unit": "kg"},
                {"key": "pkgWgtHigh", "label": "포장단중 상한 (kg)", "default": 22000, "type": "number", "unit": "kg"},
                {"key": "productCd",  "label": "허용 품종", "default": "COIL", "type": "string"},
            ],
        }
    if any(k in q for k in ("신규 강종", "새 강종", "강종 추가")):
        return {
            "kind": "grade", "label": "신규 강종 (SD_PRODUCTIVITY_STD)",
            "fields": [
                {"key": "gradeCd", "label": "강종 코드", "default": "SS500", "type": "string"},
                {"key": "smProductivity",  "label": "SM 실수율", "default": 0.97, "type": "number"},
                {"key": "hrProductivity",  "label": "HR 실수율", "default": 0.96, "type": "number"},
                {"key": "crProductivity",  "label": "CR 실수율", "default": 0.94, "type": "number"},
                {"key": "specificGravity", "label": "강 비중 (g/cm³)", "default": 7.82, "type": "number", "unit": "g/cm³"},
            ],
        }
    if any(k in q for k in ("신규 품종", "새 품종", "품종 추가")):
        return {
            "kind": "product", "label": "신규 품종 (CAST_SPEC)",
            "fields": [
                {"key": "productCd", "label": "품종 코드", "default": "SHEET", "type": "string"},
                {"key": "slabThickness", "label": "Slab 두께 (mm)", "default": 230, "type": "number", "unit": "mm"},
                {"key": "widthLow",  "label": "폭 하한 (mm)", "default": 800, "type": "number", "unit": "mm"},
                {"key": "widthHigh", "label": "폭 상한 (mm)", "default": 2200, "type": "number", "unit": "mm"},
                {"key": "lengthLow", "label": "길이 하한 (mm)", "default": 4000, "type": "number", "unit": "mm"},
                {"key": "lengthHigh","label": "길이 상한 (mm)", "default": 12000, "type": "number", "unit": "mm"},
            ],
        }
    if any(k in q for k in ("신규 EDGING", "새 EDGING", "EDGING 추가", "신규 엣징", "엣징 추가")):
        return {
            "kind": "edging_group", "label": "신규 EDGING 그룹 (EDGING_GROUP/EDGING_SPEC)",
            "fields": [
                {"key": "edgingGroupCd", "label": "EDGING 그룹 코드", "default": "EG-NEW", "type": "string"},
                {"key": "gradeCd",  "label": "강종", "default": "SS400", "type": "string"},
                {"key": "productCd","label": "품종", "default": "COIL", "type": "string"},
                {"key": "customerCd","label": "고객사", "default": "CUST-001", "type": "string"},
                {"key": "edgingCapLow",  "label": "엣징 cap 하한 (mm)", "default": -50, "type": "number", "unit": "mm"},
                {"key": "edgingCapHigh", "label": "엣징 cap 상한 (mm)", "default": 50, "type": "number", "unit": "mm"},
            ],
        }
    # 기본 — 추가할 기준 종류 미상 (LLM 이 fallback)
    return {
        "kind": "unknown", "label": "신규 기준 (종류 미식별)",
        "fields": [
            {"key": "name", "label": "기준 명", "default": "NEW-STD", "type": "string"},
            {"key": "value", "label": "값", "default": 1.0, "type": "number"},
        ],
    }


def _build_new_standard_blocks(payload: dict, user_query: str) -> list[dict]:
    """신규 기준 추가 시나리오 — 3단계 interactive flow.

    1) 확인 텍스트 — '어떤 기준을 추가하려는지 맞는지 확인'
    2) editable 폼 — 사용자가 default 값 수정 가능 (frontend `new_standard_form` block type)
    3) 미리보기 — default 값으로 즉시 시뮬한 결과 (사용자가 폼 수정+승인 시 재시뮬)
    """
    import random
    rng = random.Random()
    spec = _extract_new_standard(user_query)
    blocks: list[dict] = []

    # 1) 확인 안내
    blocks.append({
        "type": "text",
        "title": f"1단계 · 추가하려는 기준 확인: {spec['label']}",
        "data": {
            "body": (
                f"질문에서 [{spec['label']}] 추가 의도를 감지했습니다.\n"
                f"맞으신가요? 아래 폼에서 값을 직접 수정 후 [✓ 승인] 을 누르시면 "
                f"해당 신규 기준 + 기존 CAST/HR/EDGING 데이터를 기반으로 가상 주문을 합성하고 "
                f"21-step Slab 설계 결과를 다시 계산합니다."
            ),
        },
    })

    # 2) editable 폼 — frontend 가 input 으로 렌더, 승인 버튼 + 재시뮬
    blocks.append({
        "type": "new_standard_form",
        "title": f"2단계 · 신규 {spec['kind']} 기준 입력 폼 (수정 후 승인)",
        "data": {
            "kind": spec["kind"],
            "fields": spec["fields"],
            "submit_label": "✓ 승인하고 가상 주문 + 21-step 시뮬",
        },
        "_estimated": False,
    })

    # 3) 신규 기준 + 기존 base 합쳐 가상 주문 random 합성
    base = _virtual_base_order()
    def _r(low, high, unit=100):
        return rng.randint(low // unit, high // unit) * unit
    base["ORDER_NO"] = f"VIRT-NEW-{spec['kind'].upper()[:3]}{rng.randint(100,999)}"
    base["ORDER_WIDTH"]   = _r(1100, 1700, 50)
    base["ORDER_LENGTH"]  = _r(6000, 9500, 100)
    base["ORDER_WGT_LOW"] = _r(9000, 12500, 250)
    base["ORDER_WGT_HIGH"]= _r(15000, 22000, 250)
    base["DESIGN_PEND_QTY"]= _r(28000, 50000, 500)

    # 신규 기준 적용 (간단 매핑)
    field_map = {f["key"]: f["default"] for f in spec["fields"]}
    if spec["kind"] == "customer":
        base["ORDER_WGT_LOW"] = max(base["ORDER_WGT_LOW"], int(field_map.get("pkgWgtLow", 0) or 0))
        base["ORDER_WGT_HIGH"] = min(base["ORDER_WGT_HIGH"], int(field_map.get("pkgWgtHigh", 99999) or 99999))
    elif spec["kind"] == "grade":
        base["_PRODUCTIVITY"] = (
            float(field_map.get("smProductivity", 0.98)) *
            float(field_map.get("hrProductivity", 0.97)) *
            float(field_map.get("crProductivity", 0.95))
        )
    elif spec["kind"] == "product":
        base["_THICKNESS"] = float(field_map.get("slabThickness", 230))

    design = _design_one_slab(base)

    # 4) 합성된 가상 주문 + 적용한 신규 기준
    blocks.append({
        "type": "metric_grid",
        "title": f"🧪 합성된 가상 주문 ({base['ORDER_NO']}) — 신규 {spec['kind']} 기준 적용",
        "data": {
            "items": [
                {"label": "주문 폭", "value": base["ORDER_WIDTH"], "unit": "mm"},
                {"label": "주문 길이", "value": base["ORDER_LENGTH"], "unit": "mm"},
                {"label": "주문 단중 하한", "value": base["ORDER_WGT_LOW"], "unit": "kg"},
                {"label": "주문 단중 상한", "value": base["ORDER_WGT_HIGH"], "unit": "kg"},
                {"label": "설계 대기량", "value": base["DESIGN_PEND_QTY"], "unit": "kg"},
                {"label": "적용 비중",  "value": round(base.get("_THICKNESS", 230) * 0 + 7.82, 2), "unit": "g/cm³"},
            ],
        },
        "_estimated": False,
    })

    # 5) 21-step 설계 결과 (1 row)
    blocks.append({
        "type": "table",
        "title": f"📐 신규 {spec['kind']} 기준 적용 → 21-step Slab 설계 결과",
        "data": {
            "columns": [
                {"key": "order", "label": "주문"},
                {"key": "thickness", "label": "Step1: 두께", "align": "right"},
                {"key": "first_wgt", "label": "Step4: 1차 무게", "align": "right"},
                {"key": "second_wgt_high", "label": "Step6: 2차 상한", "align": "right"},
                {"key": "max_split", "label": "Step7: 최대분할", "align": "right"},
                {"key": "optimal_split", "label": "Step8: 분할수", "align": "right"},
                {"key": "slab_count", "label": "Step9: 매수", "align": "right"},
                {"key": "slab_wgt", "label": "Step10: Slab단중", "align": "right"},
                {"key": "target_width", "label": "Step18: 목표폭", "align": "right"},
                {"key": "target_length", "label": "Step19: 목표길이", "align": "right"},
                {"key": "result", "label": "결과"},
            ],
            "rows": [{
                "order": base["ORDER_NO"],
                "thickness": f"{design.get('thickness','-')} mm",
                "first_wgt": f"{design.get('first_wgt','-'):,} kg" if isinstance(design.get('first_wgt'),(int,float)) else "-",
                "second_wgt_high": f"{design.get('second_wgt_high','-'):,} kg" if isinstance(design.get('second_wgt_high'),(int,float)) else "-",
                "max_split": design.get("max_split", "-"),
                "optimal_split": design.get("optimal_split", "-"),
                "slab_count": design.get("slab_count", "-"),
                "slab_wgt": f"{design.get('slab_wgt','-'):,} kg" if isinstance(design.get('slab_wgt'),(int,float)) else "-",
                "target_width": f"{design.get('target_width','-'):,} mm" if isinstance(design.get('target_width'),(int,float)) else "-",
                "target_length": f"{design.get('target_length','-'):,} mm" if isinstance(design.get('target_length'),(int,float)) else "-",
                "result": "✅ 설계 완료" if design.get("feasible") else f"❌ {design.get('error','실패')}",
            }],
        },
        "_estimated": False,
    })

    return blocks


def _extract_order_count(user_query: str) -> int | None:
    """질문에서 '주문 N건' 명시 추출. 미명시 None.
    예: '가상 주문 1건' / '5 건' / '주문 3개'.
    """
    import re
    m = re.search(r"(?:가상\s*)?주문\s*(\d+)\s*(?:건|개)", user_query)
    if m: return int(m.group(1))
    # "1건 합성" 패턴
    m = re.search(r"(\d+)\s*건\s*(?:합성|시뮬|만들|돌려|보여)", user_query)
    if m: return int(m.group(1))
    return None


def _build_simulate_blocks(payload: dict, user_query: str) -> list[dict]:
    """simulate intent — 사용자 명시 N건이면 그만큼, 미명시면 clarify_form 으로 묻기.

    명시 케이스:
      "가상 주문 1건" → 1건 (정상 중앙)
      "5건"          → 5건 (5 케이스 분포)
    미명시:
      clarify_form 표시 — 개수 + 케이스 분포 (정상/에러/경계 비율) 묻기.
    """
    import random
    rng = random.Random()
    base_pool = _virtual_base_order()
    n_explicit = _extract_order_count(user_query)

    # ── 미명시 → clarify_form 먼저 ──
    if n_explicit is None:
        return [{
            "type": "clarify_form",
            "title": "🛠 가상 주문 개수 + 케이스 분포 선택",
            "data": {
                "intent": "simulate", "target_key": None,
                "fields": [
                    {"key": "n_orders", "label": "가상 주문 개수",
                     "default": 5, "type": "number", "unit": "건",
                     "hint": "몇 건 합성할지 (1~20)"},
                    {"key": "case_mix", "label": "케이스 분포",
                     "default": "diverse", "type": "select",
                     "options": [
                         {"value": "diverse", "label": "다양 (정상중앙 + 경계 + 에러 mix)"},
                         {"value": "normal_only", "label": "정상 중앙만"},
                         {"value": "boundary_only", "label": "경계 (하한/상한) 만"},
                         {"value": "error_only", "label": "에러 (DG104/107/103) 만"},
                     ],
                     "hint": "주문 N건의 케이스 비율을 선택"},
                    {"key": "result_scope", "label": "결과 surface 범위",
                     "default": "all_steps", "type": "select",
                     "options": [
                         {"value": "all_steps", "label": "21-step 전체"},
                         {"value": "wgt_only", "label": "단중 관련만"},
                         {"value": "split_only", "label": "분할수·매수만"},
                         {"value": "final_only", "label": "최종 결과만 (목표 폭/길이/매수)"},
                     ]},
                ],
                "submit_label": "✓ 승인하고 가상 주문 + 21-step 시뮬",
            },
        }, {
            "type": "text",
            "title": "ℹ 안내",
            "data": {"body": (
                "질문에 '가상 주문 N건' 같이 개수가 명시되지 않아 위 폼에서 입력을 받습니다.\n"
                "예: '가상 주문 3건 합성해서 보여줘' 처럼 다음엔 직접 지정 가능합니다."
            )},
        }]

    # ── 명시 N건 → 그만큼만 ──
    cases_full = [
        ("🔽 하한 경계", "boundary_low", {
            "ORDER_WIDTH": (800, 1100, 50), "ORDER_LENGTH": (4000, 5500, 100),
            "ORDER_WGT_LOW": (8000, 9500, 250), "ORDER_WGT_HIGH": (9500, 11500, 250),
            "DESIGN_PEND_QTY": (10000, 14000, 500),
        }),
        ("✅ 정상 중앙", "typical", {
            "ORDER_WIDTH": (1100, 1700, 50), "ORDER_LENGTH": (6000, 9500, 100),
            "ORDER_WGT_LOW": (9000, 12500, 250), "ORDER_WGT_HIGH": (15000, 22000, 250),
            "DESIGN_PEND_QTY": (28000, 50000, 500),
        }),
        ("🔼 상한 경계", "boundary_high", {
            "ORDER_WIDTH": (1800, 2200, 50), "ORDER_LENGTH": (10000, 12000, 100),
            "ORDER_WGT_LOW": (16000, 19000, 250), "ORDER_WGT_HIGH": (22000, 25000, 250),
            "DESIGN_PEND_QTY": (45000, 70000, 500),
        }),
        ("⚠️ 범위 초과 (DG104/107)", "error_oor", {
            "ORDER_WIDTH": (3000, 4000, 100), "ORDER_LENGTH": (6000, 9000, 100),
            "ORDER_WGT_LOW": (10000, 13000, 250), "ORDER_WGT_HIGH": (28000, 38000, 500),
            "DESIGN_PEND_QTY": (50000, 75000, 500),
        }),
        ("⚠️ 매칭 실패 (DG103)", "error_nom", {
            "ORDER_WIDTH": (1200, 1700, 50), "ORDER_LENGTH": (6000, 9000, 100),
            "ORDER_WGT_LOW": (20, 200, 1), "ORDER_WGT_HIGH": (150, 800, 1),
            "DESIGN_PEND_QTY": (800, 2500, 100),
        }),
    ]
    # n=1 이면 정상 중앙만, n>=5 면 5 케이스 모두, 중간이면 정상 우선
    if n_explicit == 1:
        chosen = [cases_full[1]]  # 정상 중앙만
    elif n_explicit <= 3:
        chosen = [cases_full[0], cases_full[1], cases_full[2]][:n_explicit]
    else:
        chosen = cases_full[:min(n_explicit, 5)]
    # n_explicit > 5 면 정상 중앙 반복으로 채움
    while len(chosen) < n_explicit:
        chosen.append(cases_full[1])
    chosen = chosen[:n_explicit]

    def _r(lo, hi, unit):
        if unit == 1: return rng.randint(int(lo), int(hi))
        return rng.randint(int(lo // unit), int(hi // unit)) * unit

    def _r(low: int, high: int, unit: int = 100) -> int:
        """[low, high] 범위에서 unit 단위 random int."""
        n = rng.randint(low // unit, high // unit)
        return n * unit

    # chosen (위에서 n_explicit 기반) 순회 — 각 케이스에서 random 값 합성
    cases = []
    for idx, (case_label, case_kind, ranges) in enumerate(chosen):
        c = {**base_pool,
             "ORDER_NO": f"VIRT-{case_kind[:3].upper()}{idx+1:03d}",
             "_case_label": case_label, "_case_kind": case_kind}
        for k, (lo, hi, unit) in ranges.items():
            c[k] = _r(lo, hi, unit)
        cases.append(c)
    designs = [_design_one_slab(c) for c in cases]
    n_actual = len(cases)

    blocks: list[dict] = []

    # 1) 가상 주문 N건 table (사용자 명시 N 반영)
    blocks.append({
        "type": "table",
        "title": f"🧪 가상 주문 {n_actual}건 (기준 데이터에 맞춰 합성)",
        "data": {
            "columns": [
                {"key": "ORDER_NO", "label": "주문번호"},
                {"key": "case", "label": "케이스"},
                {"key": "ORDER_WIDTH", "label": "폭(mm)", "align": "right"},
                {"key": "ORDER_LENGTH", "label": "길이(mm)", "align": "right"},
                {"key": "ORDER_WGT_LOW", "label": "단중 하한", "align": "right"},
                {"key": "ORDER_WGT_HIGH", "label": "단중 상한", "align": "right"},
                {"key": "DESIGN_PEND_QTY", "label": "설계대기량", "align": "right"},
            ],
            "rows": [
                {"ORDER_NO": c["ORDER_NO"], "case": c["_case_label"],
                 "ORDER_WIDTH": c["ORDER_WIDTH"], "ORDER_LENGTH": c["ORDER_LENGTH"],
                 "ORDER_WGT_LOW": c["ORDER_WGT_LOW"], "ORDER_WGT_HIGH": c["ORDER_WGT_HIGH"],
                 "DESIGN_PEND_QTY": c["DESIGN_PEND_QTY"]}
                for c in cases
            ],
        },
        "_estimated": False,
    })

    # 2) 21-step 설계 결과 (walkthrough.md 형식 — 주문별 step 단계 → 결정값)
    blocks.append({
        "type": "table",
        "title": "📐 21-step Slab 설계 결과 — 주문별 결정값 (walkthrough 형식)",
        "data": {
            "columns": [
                {"key": "order", "label": "주문"},
                {"key": "case", "label": "케이스"},
                {"key": "thickness", "label": "Step1: 두께", "align": "right"},
                {"key": "first_wgt", "label": "Step4: 1차 무게", "align": "right"},
                {"key": "second_wgt_high", "label": "Step6: 2차 상한", "align": "right"},
                {"key": "max_split", "label": "Step7: 최대분할", "align": "right"},
                {"key": "optimal_split", "label": "Step8: 분할수", "align": "right"},
                {"key": "slab_count", "label": "Step9: 매수", "align": "right"},
                {"key": "slab_wgt", "label": "Step10: Slab단중", "align": "right"},
                {"key": "target_width", "label": "Step18: 목표폭", "align": "right"},
                {"key": "target_length", "label": "Step19: 목표길이", "align": "right"},
                {"key": "result", "label": "결과"},
            ],
            "rows": [
                {
                    "order": d["order_no"], "case": d["case_label"],
                    "thickness": f"{d.get('thickness','-')} mm",
                    "first_wgt": f"{d.get('first_wgt','-'):,} kg" if isinstance(d.get('first_wgt'),(int,float)) else "-",
                    "second_wgt_high": f"{d.get('second_wgt_high','-'):,} kg" if isinstance(d.get('second_wgt_high'),(int,float)) else "-",
                    "max_split": d.get("max_split", "-"),
                    "optimal_split": d.get("optimal_split", "-"),
                    "slab_count": d.get("slab_count", "-"),
                    "slab_wgt": f"{d.get('slab_wgt','-'):,} kg" if isinstance(d.get('slab_wgt'),(int,float)) else "-",
                    "target_width": f"{d.get('target_width','-'):,} mm" if isinstance(d.get('target_width'),(int,float)) else "-",
                    "target_length": f"{d.get('target_length','-'):,} mm" if isinstance(d.get('target_length'),(int,float)) else "-",
                    "result": "✅ 설계 완료" if d.get("feasible") else f"❌ {d.get('error','실패')}",
                }
                for d in designs
            ],
        },
        "_estimated": False,
    })

    # 3) 정상 중앙 케이스 metric_grid — 결정된 Slab 사양 (없으면 첫 feasible 케이스)
    mid = next((d for d in designs if d.get("case_kind") == "typical"), None)
    if mid is None:
        mid = next((d for d in designs if d.get("feasible")), designs[0] if designs else {})
    if mid.get("feasible"):
        blocks.append({
            "type": "metric_grid",
            "title": f"🎯 정상 중앙 케이스 ({mid['order_no']}) — 결정된 Slab 사양",
            "data": {
                "items": [
                    {"label": "두께", "value": mid.get("thickness"), "unit": "mm", "tone": "neutral"},
                    {"label": "목표 폭",   "value": mid.get("target_width"), "unit": "mm", "tone": "positive"},
                    {"label": "목표 길이", "value": mid.get("target_length"), "unit": "mm", "tone": "positive"},
                    {"label": "Slab 한 장 단중", "value": int(mid.get("slab_wgt", 0)), "unit": "kg", "tone": "positive"},
                    {"label": "분할수", "value": mid.get("optimal_split"), "tone": "default"},
                    {"label": "총 매수", "value": mid.get("slab_count"), "tone": "default"},
                    {"label": "총 생산 단중", "value": int(mid.get("total_produced", 0)), "unit": "kg", "tone": "neutral"},
                    {"label": "최대 분할수 (Step7)", "value": mid.get("max_split"), "tone": "neutral"},
                ],
            },
            "_estimated": False,
        })

    # 4) walkthrough 산식 단계 강조
    blocks.append({
        "type": "step_callout",
        "title": "📚 21-step 알고리즘 단계 (walkthrough.md)",
        "data": {
            "steps": [
                {"phase": "phase_2a", "step_no": 1, "title": "Slab 두께 결정",
                 "why": "CAST_SPEC 룩업 (smCd, castCd, machineCd, productCd)"},
                {"phase": "phase_2a", "step_no": 4, "title": "1차 무게 (순수 산식)",
                 "why": "두께 × 폭 × 길이 × 비중(7.82) × 1e-6"},
                {"phase": "phase_2a", "step_no": 6, "title": "2차 무게 상한 ★",
                 "why": "min(firstWgtHigh, HR_MAX, ORDER_WGT_HIGH, DPQ/productivity)"},
                {"phase": "phase_2b", "step_no": 8, "title": "A-a 루프: split 결정",
                 "why": "splitWgtLow ≤ splitWgtHigh PASS 까지 split -1 반복"},
                {"phase": "phase_2c", "step_no": 18, "title": "목표 폭 (10mm 단위)",
                 "why": "ceil(raw/10)×10 — 현장 가공 편의"},
                {"phase": "save", "step_no": 20, "title": "SLAB_RESULT insert",
                 "why": "slabWgt × slabCount → 매수만큼 row insert"},
            ],
        },
    })

    return blocks


def _make_fallback_blocks(intent: str, user_query: str, payload: dict) -> list[dict]:
    """LLM 실패 시 ontology 데이터만으로 최소한의 동적 blocks 합성."""
    blocks: list[dict] = []
    dt = payload.get("_detected_terms") or []
    if dt:
        blocks.append({
            "type": "table",
            "title": "🔎 질문에서 매칭된 ontology 용어",
            "data": {
                "columns": [
                    {"key": "label", "label": "용어"},
                    {"key": "term_fqn", "label": "FQN"},
                    {"key": "definition", "label": "정의"},
                ],
                "rows": [
                    {"label": d.get("label", ""), "term_fqn": d.get("term_fqn", ""),
                     "definition": (d.get("definition") or "")[:120]}
                    for d in dt[:6]
                ],
            },
        })
    wkstep = payload.get("_walkthrough_steps") or []
    if wkstep:
        blocks.append({
            "type": "step_callout",
            "title": "📍 관련 21-step 단계",
            "data": {
                "steps": [
                    {"phase": s.get("phase", ""), "step_no": s.get("step_no"),
                     "title": s.get("title", ""), "why": (s.get("purpose") or "")[:140]}
                    for s in wkstep[:5] if s.get("step_no")
                ],
            },
        })
    tc = payload.get("_target_change") or {}
    if tc and tc.get("table"):
        blocks.append({
            "type": "metric_grid",
            "title": "🎯 변경 대상",
            "data": {
                "items": [
                    {"label": "테이블", "value": tc.get("table", "-")},
                    {"label": "컬럼", "value": tc.get("column", "-")},
                    {"label": "변경 전", "value": tc.get("before") or "미입력", "tone": "neutral"},
                    {"label": "변경 후", "value": tc.get("after") or "미입력", "tone": "positive"},
                ],
            },
        })
    return blocks


def _post_strip_placeholder_rows(blocks: list[dict]) -> list[dict]:
    """LLM 이 만든 comparison block 의 placeholder 행 제거 (backend 검증 단계).
    rows 모두 placeholder 면 block 자체 제거.
    """
    import re
    PH = re.compile(r"(변경\s*전|변경\s*후|변경\s*필요|기존|이전|이후|현재값?|baseline|before|after|입력\s*값|입력\s*필요|선택\s*값|TBD|N/A|null|undefined|—|값$|값\s*$)", re.I)
    def _is_ph(v):
        if v is None: return True
        if isinstance(v, (int, float)) and not (isinstance(v, float) and (v != v)): return False
        s = str(v).strip()
        if not s: return True
        if PH.search(s): return True
        if not re.search(r"\d", s) and not re.search(r"(OK|NG|PASS|FAIL|✓|✗)", s, re.I): return True
        return False
    cleaned: list[dict] = []
    for b in blocks:
        if b.get("type") == "comparison":
            rows = (b.get("data") or {}).get("rows") or []
            filtered = [r for r in rows if not (_is_ph(r.get("before")) and _is_ph(r.get("after")))]
            if not filtered:
                continue  # placeholder 만 있는 block 자체 제거
            new_b = {**b, "data": {**b.get("data", {}), "rows": filtered}}
            cleaned.append(new_b)
        else:
            cleaned.append(b)
    return cleaned


def compose_dynamic_blocks(*, intent: str, user_query: str, payload: dict) -> list[dict]:
    """LLM 호출로 질문별 최적 UI block plan 생성. 실패 시 ontology 기반 fallback.

    plan 의 sweep_request 가 있고 backend 가 실제 sweep 실행 가능하면 결과 데이터로
    sweep_chart block 의 data 를 실측치로 교체한다.

    2026-05-25: simulate intent 는 LLM 우회 — 가상 주문 5케이스 + 21-step 실제 설계 결과를
    table/metric_grid/step_callout 으로 즉시 합성 (walkthrough.md 형식).
    """
    # simulate intent — 가상 주문 5케이스 + 21-step 설계 결과
    if intent == "simulate":
        try:
            return _build_simulate_blocks(payload, user_query)
        except Exception as e:  # noqa: BLE001
            logger.warning("simulate blocks 합성 실패: %s", e)

    # impact intent — 변경 대상 추출 가능하면 가상 주문 1건 + 변경 전/후 21-step 비교
    if intent == "impact":
        try:
            impact_blocks = _build_impact_blocks(payload, user_query)
            if impact_blocks:
                return impact_blocks
        except Exception as e:  # noqa: BLE001
            logger.warning("impact blocks 합성 실패: %s", e)

    # 신규 기준 추가 시나리오 — explain 으로 demote 된 hypothesis 포함, "신규" 키워드만 보고 판단
    if any(kw in user_query for kw in (
        "신규 고객사", "신규 강종", "신규 품종", "신규 EDGING", "신규 엣징",
        "새 고객사", "새 강종", "새 품종", "고객사 추가", "강종 추가", "품종 추가", "EDGING 추가",
    )):
        try:
            ns_blocks = _build_new_standard_blocks(payload, user_query)
            if ns_blocks:
                return ns_blocks
        except Exception as e:  # noqa: BLE001
            logger.warning("new_standard blocks 합성 실패: %s", e)

    try:
        from backend.section3.llm.openai_client import get_llm_client
        ctx = _build_ontology_ctx(payload)
        sweep_hint = _try_extract_sweep_params(user_query)
        ctx_str = json.dumps(ctx, ensure_ascii=False, indent=2)
        user_msg = (
            f"사용자 질문:\n{user_query}\n\n"
            f"intent: {intent}\n"
            f"sweep 패턴 정규식 추출: {json.dumps(sweep_hint, ensure_ascii=False) if sweep_hint else 'none'}\n\n"
            f"ontology 컨텍스트:\n{ctx_str}"
        )
        llm = get_llm_client()
        raw = llm.chat_json([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ], temperature=0.3)
        blocks_raw = raw.get("blocks") if isinstance(raw, dict) else None
        if isinstance(blocks_raw, list) and blocks_raw:
            # 정제 — 알려진 type 만 통과
            allowed = {"metric_grid", "table", "sweep_chart", "comparison",
                       "step_callout", "formula", "text"}
            clean: list[dict] = []
            for b in blocks_raw[:7]:
                if not isinstance(b, dict): continue
                bt = b.get("type")
                if bt not in allowed: continue
                data = b.get("data")
                if not isinstance(data, dict): continue
                clean.append({
                    "type": bt,
                    "title": str(b.get("title", ""))[:120],
                    "data": data,
                    "_estimated": bool(b.get("_estimated", False)),
                })
            if clean:
                # sweep_request 가 있으면 실제 sweep 실행 → comparison/sweep_chart 실측 데이터로 교체
                sw_req = raw.get("sweep_request") if isinstance(raw, dict) else None
                if not sw_req and sweep_hint:
                    # LLM 이 sweep_request 안 만들었는데 정규식이 잡았으면 그것 사용
                    sw_req = {
                        "variable": sweep_hint.get("variable"),
                        "step": sweep_hint.get("step"),
                        "count": sweep_hint.get("count"),
                        "direction": sweep_hint.get("direction"),
                    }
                base_for_sweep = _virtual_base_order()
                clean = _fill_sweep_blocks(clean, sw_req, base_for_sweep)
                # placeholder row 제거 (LLM 응답 검증)
                clean = _post_strip_placeholder_rows(clean)
                # 모든 의도에 clarify_form 첫 줄 추가 (form gate 작동 보장)
                if not any(b.get("type") in ("clarify_form", "new_standard_form") for b in clean):
                    clean.insert(0, _build_clarify_form(
                        intent=intent, user_query=user_query,
                        target_key=None, current_val=None,
                    ))
                return clean
    except Exception as e:  # noqa: BLE001
        logger.info("dynamic_blocks LLM 실패 → fallback: %s", e)

    # fallback 도 sweep 가능하면 실측 데이터로 sweep_chart + comparison 합성
    blocks = _make_fallback_blocks(intent, user_query, payload)
    sweep_hint = _try_extract_sweep_params(user_query)
    if sweep_hint:
        base = _virtual_base_order()
        points = _run_quick_sweep(base, "DESIGN_PEND_QTY", float(sweep_hint["step"]), int(sweep_hint["count"]), sweep_hint["direction"])
        if points:
            baseline_point = points[0]
            last_point = points[-1]
            best_idx = max(range(len(points)), key=lambda i: points[i]["slab_wgt"])
            blocks.insert(0, {
                "type": "sweep_chart", "title": "Slab 단중 변화 추이 (실측 sweep)",
                "data": {
                    "x_label": f"step ({sweep_hint['direction']} {sweep_hint['step']}{sweep_hint.get('step_unit','')})",
                    "y_label": "Slab 단중 (kg)",
                    "points": [{"x": f"+{i*float(sweep_hint['step']):.0f}", "y": p["slab_wgt"]} for i, p in enumerate(points)],
                    "best_index": best_idx,
                }, "_estimated": False,
            })
            blocks.insert(1, {
                "type": "comparison", "title": "baseline vs 최종 step",
                "data": {
                    "before_label": f"baseline (i=0)",
                    "after_label": f"after (i={sweep_hint['count']})",
                    "rows": [
                        {"label": "Slab 단중", "before": baseline_point["slab_wgt"], "after": last_point["slab_wgt"],
                         "change_pct": ((last_point["slab_wgt"] - baseline_point["slab_wgt"]) / baseline_point["slab_wgt"] * 100) if baseline_point["slab_wgt"] else None},
                        {"label": "분할수", "before": baseline_point["split_count"], "after": last_point["split_count"]},
                    ],
                }, "_estimated": False,
            })
    return blocks


__all__ = ["compose_dynamic_blocks"]
