"""Anthropic tool_use format schemas for all Slab design simulation tools.

Each tool is declared in the format expected by the Anthropic SDK:
    {"name": str, "description": str, "input_schema": {...JSON Schema...}}

These are consumed by SimulationToolExecutor when constructing the `tools=` parameter
for Anthropic API calls, and also registered into SimulationToolRegistry.
"""

from __future__ import annotations

# ── Scenario A: Width range & order info tools ────────────────────────────────

GET_ORDER_INFO: dict = {
    "name": "get_order_info",
    "description": (
        "주문 ID로 Slab 설계 주문 상세 정보를 조회합니다. "
        "목표폭(target_width), 목표두께(target_thickness), 목표길이(target_length), "
        "배정 열연라인(assigned_rolling), 설계 상태(status), 에러 코드 등을 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "조회할 주문 ID (예: ORD-2024-0042)",
            }
        },
        "required": ["order_id"],
    },
}

SIMULATE_WIDTH_RANGE: dict = {
    "name": "simulate_width_range",
    "description": (
        "주어진 목표폭과 열연라인에 대해 폭 범위 산정 가능 여부를 시뮬레이션합니다. "
        "Edging 기준 테이블과 대조하여 DG320 에러 발생 여부와 산정된 폭 하한/상한을 반환합니다. "
        "edging_override를 지정하면 What-If 분석(Edging 능력 변경 시나리오)에 사용할 수 있습니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_width": {
                "type": "integer",
                "description": "검사할 목표 폭 (mm 단위, 예: 1850)",
            },
            "rolling_line_id": {
                "type": "string",
                "description": "열연라인 ID (예: HR-A, HR-B)",
            },
            "edging_override": {
                "type": "integer",
                "description": (
                    "Edging 최대 능력을 임시로 대체할 값 (mm). "
                    "지정하지 않으면 기준 테이블 값 사용. What-If 시나리오용."
                ),
            },
        },
        "required": ["target_width", "rolling_line_id"],
    },
}

SUGGEST_ADJUSTED_WIDTH: dict = {
    "name": "suggest_adjusted_width",
    "description": (
        "DG320 에러가 발생한 주문에 대해 Edging 기준 내에서 실현 가능한 최대 목표폭을 제안합니다. "
        "현재 목표폭과 조정 폭의 차이, 조정 후 시뮬레이션 결과를 포함한 권장사항을 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "폭 조정이 필요한 주문 ID",
            }
        },
        "required": ["order_id"],
    },
}

# ── Scenario B: Ripple effect tools ──────────────────────────────────────────

SIMULATE_WIDTH_IMPACT: dict = {
    "name": "simulate_width_impact",
    "description": (
        "Edging 최대 능력 변경이 특정 주문의 폭 범위 설계에 미치는 영향을 평가합니다. "
        "변경 전후의 가부 상태와 폭 범위 변화를 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "평가할 주문 ID",
            },
            "new_edging_max": {
                "type": "integer",
                "description": "새로운 Edging 최대 능력 값 (mm, 예: 160)",
            },
        },
        "required": ["order_id", "new_edging_max"],
    },
}

BATCH_SIMULATE_WIDTH_IMPACT: dict = {
    "name": "batch_simulate_width_impact",
    "description": (
        "여러 주문에 대해 Edging 최대 능력 변경 영향을 병렬로 일괄 평가합니다. "
        "파급 효과 분석(시나리오 B)에서 다수 주문을 효율적으로 처리할 때 사용합니다. "
        "각 주문별 impact 결과 리스트와 요약 통계를 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "평가할 주문 ID 목록",
            },
            "new_edging_max": {
                "type": "integer",
                "description": "새로운 Edging 최대 능력 값 (mm)",
            },
        },
        "required": ["order_ids", "new_edging_max"],
    },
}

ANALYZE_EDGING_CHANGE_RIPPLE: dict = {
    "name": "analyze_edging_change_ripple",
    "description": (
        "특정 열연라인의 Edging 능력 변경이 해당 라인 전체 주문에 미치는 파급 효과를 분석합니다. "
        "영향받는 주문 수, 영향률, 주문별 상세 impact 결과를 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rolling_line_id": {
                "type": "string",
                "description": "분석할 열연라인 ID (예: HR-A)",
            },
            "new_edging_max": {
                "type": "integer",
                "description": "새로운 Edging 최대 능력 값 (mm)",
            },
        },
        "required": ["rolling_line_id", "new_edging_max"],
    },
}

# ── Scenario C: Split optimization tools ─────────────────────────────────────

SIMULATE_SPLIT_COMBINATIONS: dict = {
    "name": "simulate_split_combinations",
    "description": (
        "주문의 분할수(1~max_splits)별 단중 만족률을 계산하고 최적 분할수를 추천합니다. "
        "각 분할수에 대한 Slab 단중 범위, 만족률, 최적 조합 요약을 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "최적화할 주문 ID",
            },
            "target_capacity": {
                "type": "integer",
                "description": "총 Slab 중량 (kg). 미지정 시 주문 데이터의 slab_weight 사용.",
            },
            "max_splits": {
                "type": "integer",
                "description": "평가할 최대 분할수 (기본값 5)",
                "default": 5,
            },
        },
        "required": ["order_id"],
    },
}

# ── Equipment & ontology tools ────────────────────────────────────────────────

GET_EQUIPMENT_SPEC: dict = {
    "name": "get_equipment_spec",
    "description": (
        "연주기(Caster)와 열연(Hot Rolling Mill) 설비의 기준 데이터를 조회합니다. "
        "폭/길이/두께 범위, Edging 능력 등 설비 제약 조건을 포함합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

FIND_ORDERS_BY_ROLLING_LINE: dict = {
    "name": "find_orders_by_rolling_line",
    "description": (
        "온톨로지 그래프를 탐색하여 특정 열연라인에 배정된 주문 목록을 반환합니다. "
        "그래프 순회 경로와 강조 표시할 엣지 정보도 함께 반환합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "rolling_line_id": {
                "type": "string",
                "description": "조회할 열연라인 ID (예: HR-A)",
            }
        },
        "required": ["rolling_line_id"],
    },
}

FIND_EDGING_SPECS_FOR_ORDER: dict = {
    "name": "find_edging_specs_for_order",
    "description": (
        "온톨로지 그래프를 탐색하여 특정 주문의 배정 열연라인 Edging 기준을 찾습니다. "
        "Order → ROLLED_BY → HotRollingMill → HAS_EDGING_SPEC → EdgeSpec 경로를 순회합니다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Edging 기준을 조회할 주문 ID",
            }
        },
        "required": ["order_id"],
    },
}

# ── Tool sets per scenario ────────────────────────────────────────────────────

SCENARIO_A_TOOLS: list[dict] = [
    GET_ORDER_INFO,
    SIMULATE_WIDTH_RANGE,
    SUGGEST_ADJUSTED_WIDTH,
    FIND_EDGING_SPECS_FOR_ORDER,
]

SCENARIO_B_TOOLS: list[dict] = [
    FIND_ORDERS_BY_ROLLING_LINE,
    SIMULATE_WIDTH_IMPACT,
    BATCH_SIMULATE_WIDTH_IMPACT,
    ANALYZE_EDGING_CHANGE_RIPPLE,
    GET_ORDER_INFO,
]

SCENARIO_C_TOOLS: list[dict] = [
    GET_ORDER_INFO,
    SIMULATE_SPLIT_COMBINATIONS,
]

ALL_TOOLS: list[dict] = [
    GET_ORDER_INFO,
    SIMULATE_WIDTH_RANGE,
    SUGGEST_ADJUSTED_WIDTH,
    SIMULATE_WIDTH_IMPACT,
    BATCH_SIMULATE_WIDTH_IMPACT,
    ANALYZE_EDGING_CHANGE_RIPPLE,
    SIMULATE_SPLIT_COMBINATIONS,
    GET_EQUIPMENT_SPEC,
    FIND_ORDERS_BY_ROLLING_LINE,
    FIND_EDGING_SPECS_FOR_ORDER,
]
