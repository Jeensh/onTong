"""Slab Size 설계 시뮬레이터 — Mock 계산 로직.

SEQ 2~16 기준의 Slab 설계 프로세스를 Mock 데이터로 계산한다.
모든 수치는 Mock 기반이며 실제 설비 수치와 무관하다.
"""

from __future__ import annotations

import math

from backend.shared.contracts.simulation import (
    SlabDesignResult,
    SlabDesignStep,
    SlabDesignSummary,
    SlabSizeParams,
)

# ── 설비 제약 기준 (Mock) ─────────────────────────────────────────────

EQUIPMENT_CONSTRAINTS: dict = {
    "CC-01": {           # 연주설비
        "thickness": 250,
        "width_min": 900, "width_max": 1600,
        "length_min": 4500, "length_max": 12000,
    },
    "HR-A": {            # 열연설비
        "width_min": 900, "width_max": 1570,
        "length_min": 4500, "length_max": 12000,
    },
    "EDGING_HR_A": [
        {"target_width_min": 900,  "target_width_max": 1200, "edging_max": 180},
        {"target_width_min": 1201, "target_width_max": 1570, "edging_max": 120},
    ],
}

DENSITY = 7.82          # 철강 비중 (g/cm³)
MIN_COIL_LENGTH = 2750  # 분할 후 최소 코일 길이 (mm)
MIN_SLAB_WEIGHT = 8000  # 최소 슬라브 단중 (kg)


def _weight(width_mm: int, thickness_mm: int, length_mm: int) -> float:
    """치수로부터 단중(kg) 계산."""
    return DENSITY * width_mm * thickness_mm * length_mm / 1_000_000


def _find_edging_max(target_width: int, rolling: str) -> int:
    """목표폭에 해당하는 Edging 최대 능력 반환."""
    # "HR-A" → "EDGING_HR_A" 형태로 키 변환
    key = f"EDGING_{rolling.replace('-', '_')}"
    for spec in EQUIPMENT_CONSTRAINTS.get(key, []):
        if spec["target_width_min"] <= target_width <= spec["target_width_max"]:
            return spec["edging_max"]
    return 120  # 기본값


def _status_from_range(value: float, lower: float, upper: float, warn_pct: float = 0.05) -> str:
    """값이 [lower, upper] 범위에서 어느 상태인지 반환."""
    if value < lower or value > upper:
        return "error"
    warn_lower = lower + (upper - lower) * warn_pct
    warn_upper = upper - (upper - lower) * warn_pct
    if value < warn_lower or value > warn_upper:
        return "warning"
    return "ok"


def calculate_slab_design(params: SlabSizeParams) -> SlabDesignResult:
    """
    입력된 Slab Size 파라미터로 설계 프로세스 전체를 계산한다.
    SEQ별 결과와 최종 설계 가부를 반환한다.
    """
    caster = EQUIPMENT_CONSTRAINTS.get(params.assigned_caster, EQUIPMENT_CONSTRAINTS["CC-01"])
    rolling = EQUIPMENT_CONSTRAINTS.get(params.assigned_rolling, EQUIPMENT_CONSTRAINTS["HR-A"])

    steps: list[SlabDesignStep] = []
    feasible = True
    overall_status = "ok"

    def _add(seq, name, result, status, message, details=None):
        nonlocal feasible, overall_status
        if status == "error":
            feasible = False
            overall_status = "error"
        elif status == "warning" and overall_status == "ok":
            overall_status = "warning"
        steps.append(SlabDesignStep(
            seq=seq, name=name, result=result,
            status=status, message=message, details=details,
        ))

    # ── SEQ 2: 두께 결정 ────────────────────────────────────────────
    expected_thickness = caster["thickness"]
    if params.thickness == expected_thickness:
        _add(2, "두께 결정",
             {"thickness": params.thickness},
             "ok",
             f"연주설비({params.assigned_caster}) mold 두께 {expected_thickness}mm — 일치")
    elif abs(params.thickness - expected_thickness) / expected_thickness < 0.05:
        _add(2, "두께 결정",
             {"thickness": params.thickness, "expected": expected_thickness},
             "warning",
             f"두께 {params.thickness}mm — 기준 {expected_thickness}mm 근접 (±5% 이내)")
    else:
        _add(2, "두께 결정",
             {"thickness": params.thickness, "expected": expected_thickness},
             "error",
             f"두께 {params.thickness}mm — 연주설비 mold {expected_thickness}mm와 불일치",
             {"suggested": expected_thickness})

    # ── SEQ 3: 1차 폭범위 산정 ──────────────────────────────────────
    edging_max = _find_edging_max(params.target_width, params.assigned_rolling)
    width_lower = max(rolling["width_min"], int(params.target_width - edging_max * 0.444))
    width_upper = min(rolling["width_max"], int(params.target_width + edging_max * 0.389))

    if params.target_width < rolling["width_min"]:
        _add(3, "1차 폭범위 산정",
             {"width_range": {"lower": width_lower, "upper": width_upper}},
             "error",
             f"목표폭 {params.target_width}mm — {params.assigned_rolling} 최소폭 {rolling['width_min']}mm 미달",
             {"min_allowed": rolling["width_min"], "over_by": rolling["width_min"] - params.target_width})
    elif params.target_width > rolling["width_max"]:
        _add(3, "1차 폭범위 산정",
             {"width_range": {"lower": width_lower, "upper": width_upper}},
             "error",
             f"목표폭 {params.target_width}mm — {params.assigned_rolling} 최대폭 {rolling['width_max']}mm 초과",
             {"max_allowed": rolling["width_max"], "over_by": params.target_width - rolling["width_max"]})
    else:
        _add(3, "1차 폭범위 산정",
             {"width_range": {"lower": width_lower, "upper": width_upper}},
             "ok",
             f"목표폭 {params.target_width}mm → 1차 폭범위 {width_lower}~{width_upper}mm",
             {"edging_max": edging_max})

    # ── SEQ 4: 1차 길이범위 산정 ────────────────────────────────────
    length_lower = max(
        caster["length_min"],
        rolling["length_min"],
        MIN_COIL_LENGTH * params.split_count,
    )
    length_upper = min(caster["length_max"], rolling["length_max"])

    if params.target_length < length_lower:
        _add(4, "1차 길이범위 산정",
             {"length_range": {"lower": length_lower, "upper": length_upper}},
             "error",
             f"목표길이 {params.target_length}mm — 최소 {length_lower}mm 미달",
             {"min_required": length_lower})
    elif params.target_length > length_upper:
        _add(4, "1차 길이범위 산정",
             {"length_range": {"lower": length_lower, "upper": length_upper}},
             "error",
             f"목표길이 {params.target_length}mm — 최대 {length_upper}mm 초과",
             {"max_allowed": length_upper})
    else:
        _add(4, "1차 길이범위 산정",
             {"length_range": {"lower": length_lower, "upper": length_upper}},
             "ok",
             f"목표길이 {params.target_length}mm → 1차 길이범위 {length_lower}~{length_upper}mm")

    # ── SEQ 5: 1차 단중범위 산정 ────────────────────────────────────
    weight_lower = int(_weight(width_lower, params.thickness, length_lower))
    weight_upper = int(_weight(width_upper, params.thickness, length_upper))

    weight_status = _status_from_range(params.unit_weight, weight_lower, weight_upper)
    if params.unit_weight < weight_lower:
        _add(5, "1차 단중범위 산정",
             {"weight_range": {"lower": weight_lower, "upper": weight_upper}},
             "error",
             f"단중 {params.unit_weight:,}kg — 최소 {weight_lower:,}kg 미달",
             {"deficit": weight_lower - params.unit_weight})
    elif params.unit_weight > weight_upper:
        _add(5, "1차 단중범위 산정",
             {"weight_range": {"lower": weight_lower, "upper": weight_upper}},
             "error",
             f"단중 {params.unit_weight:,}kg — 최대 {weight_upper:,}kg 초과",
             {"excess": params.unit_weight - weight_upper})
    else:
        _add(5, "1차 단중범위 산정",
             {"weight_range": {"lower": weight_lower, "upper": weight_upper}},
             weight_status,
             f"단중 {params.unit_weight:,}kg → 1차 단중범위 {weight_lower:,}~{weight_upper:,}kg 내 포함")

    # ── SEQ 8: 분할수 결정 ──────────────────────────────────────────
    # 최대 분할수: 단중을 최소 코일 단중으로 나눈 몫
    min_piece_weight = _weight(params.target_width, params.thickness, MIN_COIL_LENGTH)
    max_split = max(1, math.floor(params.unit_weight / min_piece_weight))

    if params.split_count > max_split:
        _add(8, "분할수 결정",
             {"split_count": params.split_count, "max_split": max_split},
             "error",
             f"분할수 {params.split_count} — 최대 분할수 {max_split} 초과",
             {"max_allowed": max_split})
    elif params.split_count == max_split:
        _add(8, "분할수 결정",
             {"split_count": params.split_count, "max_split": max_split},
             "warning",
             f"분할수 {params.split_count} = 최대 분할수 {max_split} (경계값)")
    else:
        _add(8, "분할수 결정",
             {"split_count": params.split_count, "max_split": max_split},
             "ok",
             f"분할수 {params.split_count} — 최대 분할수 {max_split} 이하")

    # ── SEQ 9: 매수 산정 ────────────────────────────────────────────
    # 매수 = ceil(필요 중량 / (단중 × 실수율))
    # 단순 Mock: 목표 단중과 실수율로 산정
    required_per_slab = params.unit_weight * params.yield_rate
    slab_count = max(1, math.ceil(params.unit_weight / (required_per_slab * 0.9)))
    # Mock 고정: 기본값 3매 (단중 / 8000 반올림)
    slab_count = max(1, math.ceil(params.unit_weight / 8000))

    _add(9, "매수 산정",
         {"slab_count": slab_count, "yield_rate": params.yield_rate},
         "ok",
         f"산정 매수: {slab_count}매 (실수율 {params.yield_rate:.1%})")

    # ── SEQ 12: 2차 폭범위 산정 ─────────────────────────────────────
    width2_lower = max(rolling["width_min"], params.target_width - int(edging_max * 0.1))
    width2_upper = min(rolling["width_max"], params.target_width + int(edging_max * 0.067))

    if params.target_width < width2_lower or params.target_width > width2_upper:
        _add(12, "2차 폭범위 산정",
             {"width_range_2": {"lower": width2_lower, "upper": width2_upper}},
             "error",
             f"목표폭 {params.target_width}mm — 2차 폭범위 {width2_lower}~{width2_upper}mm 이탈")
    else:
        _add(12, "2차 폭범위 산정",
             {"width_range_2": {"lower": width2_lower, "upper": width2_upper}},
             "ok",
             f"2차 폭범위 {width2_lower}~{width2_upper}mm — 목표폭 {params.target_width}mm 포함")

    # ── SEQ 14: Target 폭 확정 ──────────────────────────────────────
    if width2_lower <= params.target_width <= width2_upper:
        _add(14, "Target 폭 확정",
             {"target_width": params.target_width},
             "ok",
             f"Target 폭 {params.target_width}mm 확정")
    else:
        suggested_w = max(width2_lower, min(width2_upper, params.target_width))
        _add(14, "Target 폭 확정",
             {"target_width": params.target_width, "suggested": suggested_w},
             "error",
             f"Target 폭 {params.target_width}mm 확정 불가 → {suggested_w}mm 권장")

    # ── SEQ 16: Target 길이 확정 ────────────────────────────────────
    if length_lower <= params.target_length <= length_upper:
        _add(16, "Target 길이 확정",
             {"target_length": params.target_length},
             "ok",
             f"Target 길이 {params.target_length}mm 확정")
    else:
        suggested_l = max(length_lower, min(length_upper, params.target_length))
        _add(16, "Target 길이 확정",
             {"target_length": params.target_length, "suggested": suggested_l},
             "error",
             f"Target 길이 {params.target_length}mm 확정 불가 → {suggested_l}mm 권장")

    # ── 요약 ────────────────────────────────────────────────────────
    unit_weight_per_split = round(params.unit_weight / params.split_count, 1)
    summary = SlabDesignSummary(
        width_range={"lower": width_lower, "upper": width_upper},
        length_range={"lower": length_lower, "upper": length_upper},
        weight_range={"lower": weight_lower, "upper": weight_upper},
        target_width=params.target_width,
        target_length=params.target_length,
        split_count=params.split_count,
        slab_count=slab_count,
        unit_weight_per_split=unit_weight_per_split,
    )

    return SlabDesignResult(
        feasible=feasible,
        steps=steps,
        summary=summary,
        overall_status=overall_status,
    )


def get_equipment_constraints() -> dict:
    """슬라이더 min/max 설정용 설비 제약 기준 반환."""
    return {
        "target_width": {"min": 900, "max": 1570, "default": 1040, "unit": "mm"},
        "thickness": {"min": 200, "max": 300, "default": 250, "unit": "mm"},
        "target_length": {"min": 4500, "max": 12000, "default": 11700, "unit": "mm"},
        "unit_weight": {"min": 8000, "max": 30000, "default": 23800, "unit": "kg"},
        "split_count": {"min": 1, "max": 5, "default": 2, "unit": "개"},
        "yield_rate": {"min": 0.85, "max": 0.99, "default": 0.943, "unit": ""},
        "equipment": EQUIPMENT_CONSTRAINTS,
    }
