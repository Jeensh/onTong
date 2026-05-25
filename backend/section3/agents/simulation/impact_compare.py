"""impact intent — 선택 주문 기반 변경 전/후 slab 결과 비교.

흐름:
  1) order_no 로 Java :8080 호출 → baseline slab + trace
  2) 변경 대상 (table.column · before → after) 을 baseline 에 직접 적용 가능한지 판정.
     - CAST_SPEC.SLAB_THICKNESS → baseline.slabThickness 에 after 대입
     - HR_MIN_WGT/HR_MAX_WGT.MIN_WGT/MAX_WGT → baseline.secondWgtLow/secondWgtHigh
     - SD_PRODUCTIVITY_STD.PRODUCTIVITY → 단중 계열 비율 (hypothesis_workflow 와 동일)
     - 그 외 → 변경 없음 (heuristic)
  3) projected slab + 변경 전·후 field-level diff 반환

H2 dynamic UPDATE 불가능 (in-memory same-JVM) 이므로 추론 모델 사용.
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from backend.section3.agents.simulation.slab_design_runner import run_full_design

logger = logging.getLogger(__name__)


# (table, column) → baseline slab 의 어떤 필드를 어떻게 바꿀지 (직접 대입)
DIRECT_MAP: dict[tuple[str, str], list[str]] = {
    ("CAST_SPEC", "SLAB_THICKNESS"): ["slabThickness"],
    ("CAST_SPEC", "WIDTH_LOW"): ["slabWidthLow", "slabWidthLow1"],
    ("CAST_SPEC", "WIDTH_HIGH"): ["slabWidthHigh", "slabWidthHigh1"],
    ("CAST_SPEC", "LENGTH_LOW"): ["slabLengthLow", "slabLengthLow1"],
    ("CAST_SPEC", "LENGTH_HIGH"): ["slabLengthHigh", "slabLengthHigh1"],
    ("CAST_SPEC", "WGT_LOW"): ["slabWgtLow"],
    ("CAST_SPEC", "WGT_HIGH"): ["slabWgtHigh"],
    ("HR_SPEC", "WIDTH_LOW"): ["firstWidthLow"],
    ("HR_SPEC", "WIDTH_HIGH"): ["firstWidthHigh"],
    ("HR_SPEC", "LENGTH_LOW"): ["firstLengthLow"],
    ("HR_SPEC", "LENGTH_HIGH"): ["firstLengthHigh"],
    ("HR_MIN_WGT", "MIN_WGT"): ["secondWgtLow"],
    ("HR_MAX_WGT", "MAX_WGT"): ["secondWgtHigh", "slabWgtHigh"],
}

# (table, column) → ratio 적용 (변경된 비율을 다운스트림 필드들에 비례 전파)
# 도메인 지식: slab-design 21-step 알고리즘에서 weight = thickness × width × length × density × adjust.
# 즉 thickness ↑ → 단중 계열 비례 ↑ · width ↑ → 단중·길이 영향 등.
PROPAGATION_RULES: dict[tuple[str, str], dict[str, str]] = {
    # SLAB_THICKNESS 변경 → 단중 계열 비례 (두께 변화율만큼 무게 증가)
    ("CAST_SPEC", "SLAB_THICKNESS"): {
        "slabWgt": "ratio", "slabWgtLow": "ratio", "slabWgtHigh": "ratio",
        "slabWgt1": "ratio", "slabWgtLow1": "ratio", "slabWgtHigh1": "ratio",
        "firstWgtLow": "ratio", "firstWgtHigh": "ratio",
        "secondWgtLow": "ratio", "secondWgtHigh": "ratio",
        "splitWgtLow": "ratio", "splitWgtHigh": "ratio",
        "slabWgtInProgress": "ratio",
    },
    # 폭 변경 → 단중·길이 일부 영향 (slab volume = w × l × t)
    ("CAST_SPEC", "WIDTH_LOW"): {"slabWgtLow": "ratio", "firstWgtLow": "ratio"},
    ("CAST_SPEC", "WIDTH_HIGH"): {"slabWgtHigh": "ratio", "firstWgtHigh": "ratio"},
    # productivity 변경 → 단중 계열 비례 (hypothesis_workflow 모델과 동일)
    ("SD_PRODUCTIVITY_STD", "PRODUCTIVITY"): {
        "slabWgt": "ratio", "slabWgtLow": "ratio", "slabWgtHigh": "ratio",
        "slabWgt1": "ratio", "slabWgtLow1": "ratio", "slabWgtHigh1": "ratio",
        "firstWgtLow": "ratio", "firstWgtHigh": "ratio",
        "secondWgtLow": "ratio", "secondWgtHigh": "ratio",
        "splitWgtLow": "ratio", "splitWgtHigh": "ratio",
        "slabWgtInProgress": "ratio",
    },
}


def _coerce_num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


async def transpile_methods(method_fqns: list[str], repo_id: str = "slab-design-real-v2") -> list[dict[str, Any]]:
    """affected method 의 Java body → Python 변환 (병렬). impact/hypothesis 결과 surface 용."""
    from sqlalchemy import select
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow
    from backend.section3.agents.multiturn.tools import call_sim_v2_translate

    out: list[dict[str, Any]] = []
    with session_scope() as s:
        for fqn in method_fqns[:5]:  # 최대 5개
            row = s.execute(
                select(CodeMethodRow).where(
                    CodeMethodRow.fqn == fqn,
                    CodeMethodRow.repo_id == repo_id,
                )
            ).scalar_one_or_none()
            if not row or not row.body_text:
                out.append({"fqn": fqn, "java": "", "python": "", "error": "본문 없음"})
                continue
            try:
                tr = await call_sim_v2_translate(body_text=row.body_text)
                # translated 가 tuple 또는 (python_source, function_name, idiom_rewrites)
                python_source = ""
                idiom_diffs: list[Any] = []
                if tr.data:
                    if isinstance(tr.data, (list, tuple)) and len(tr.data) >= 1:
                        python_source = str(tr.data[0])
                        if len(tr.data) >= 3:
                            idiom_diffs = list(tr.data[2] or [])
                    elif isinstance(tr.data, str):
                        python_source = tr.data
                out.append({
                    "fqn": fqn,
                    "class_name": fqn.split("(")[0].rsplit(".", 1)[0].split(".")[-1],
                    "method_name": fqn.split("(")[0].rsplit(".", 1)[-1],
                    "java": row.body_text[:1500],
                    "java_truncated": len(row.body_text) > 1500,
                    "python": python_source[:1500] if python_source else "",
                    "python_truncated": len(python_source) > 1500 if python_source else False,
                    "idiom_diffs": idiom_diffs[:5],
                    "line_start": row.line_start,
                    "line_end": row.line_end,
                })
            except Exception as e:  # noqa: BLE001
                out.append({"fqn": fqn, "java": row.body_text[:800], "python": "", "error": f"transpile 실패: {e}"})
    return out


async def compare_impact_slab(
    *, table: str, column: str,
    before: str | None, after: str | None,
    order_no: str,
    cmp_cd: str = "K", org_cd: str = "1",
    affected_method_fqns: list[str] | None = None,
) -> dict[str, Any]:
    """선택 주문 baseline + 변경 적용 projected + diff."""
    # 1) baseline
    baseline = await run_full_design(order_no=order_no, cmp_cd=cmp_cd, org_cd=org_cd)
    slabs = baseline.get("slab_results") or []
    if not slabs:
        return {
            "ok": False, "order_no": order_no,
            "error": baseline.get("error_message") or "baseline slab 결과 없음",
            "error_code": baseline.get("error_code"),
            "baseline_slab": None, "projected_slab": None, "diff": [],
        }
    base = slabs[0]
    projected = copy.deepcopy(base)
    notes: list[str] = []

    after_num = _coerce_num(after)
    before_num = _coerce_num(before)
    key = (table.upper(), column.upper())

    # 2-A) 직접 대입 — 변경 대상 자체 필드
    if key in DIRECT_MAP and after_num is not None:
        for field in DIRECT_MAP[key]:
            if field in projected:
                old = projected[field]
                projected[field] = after_num
                notes.append(f"[직접] {field} {old} → {after_num}")

    # 2-B) propagation — 변경 비율로 downstream 필드 비례 전파
    ratio: float | None = None
    if after_num is not None and before_num and before_num != 0:
        ratio = after_num / before_num

    if key in PROPAGATION_RULES and ratio is not None and abs(ratio - 1.0) > 1e-9:
        rules = PROPAGATION_RULES[key]
        for field, mode in rules.items():
            if field in DIRECT_MAP.get(key, []):
                continue  # 이미 직접 대입한 필드는 skip
            if field not in projected or projected[field] is None:
                continue
            try:
                old = float(projected[field])
                if mode == "ratio":
                    new = round(old * ratio, 3)
                    projected[field] = new
                    notes.append(f"[전파] {field} {old} → {new} (×{ratio:.4f})")
            except Exception:
                continue
        notes.append(
            f"※ propagation 모델 — 도메인 지식(weight ∝ thickness × width × length × density) 기반 "
            f"비례 추정. 실제 21-step 알고리즘은 guard·rule 영향으로 차이가 있을 수 있습니다."
        )

    if key not in DIRECT_MAP and key not in PROPAGATION_RULES:
        notes.append(
            f"{table}.{column} 의 매핑 룰이 없습니다. baseline 그대로. "
            "DIRECT_MAP / PROPAGATION_RULES 에 추가하면 추론 가능."
        )

    # 3) diff
    diff: list[dict[str, Any]] = []
    for k in base:
        b = base[k]
        a = projected.get(k)
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            if abs(float(b) - float(a)) > 0.001:
                diff.append({
                    "field": k, "before": b, "after": a,
                    "delta": round(float(a) - float(b), 3),
                    "delta_pct": round((float(a) - float(b)) / float(b) * 100, 2) if float(b) else 0,
                })
        elif b != a:
            diff.append({"field": k, "before": b, "after": a, "delta": None, "delta_pct": None})

    # 4) affected method Java → Python 변환 (있으면)
    transpiled: list[dict[str, Any]] = []
    if affected_method_fqns:
        try:
            transpiled = await transpile_methods(affected_method_fqns)
        except Exception as e:  # noqa: BLE001
            logger.warning("transpile 실패: %s", e)

    return {
        "ok": True, "order_no": order_no,
        "baseline_slab": base, "projected_slab": projected,
        "diff": diff, "notes": notes,
        "target": {"table": table, "column": column, "before": before, "after": after},
        "transpiled_methods": transpiled,
    }
