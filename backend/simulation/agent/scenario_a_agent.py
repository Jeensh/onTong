"""Scenario A: Width range calculation failure (DG320 error) analysis & auto-adjustment.

User input: "주문 ORD-2024-0042가 폭 범위 계산에서 에러났어. 왜 그러는지 찾고, 폭을 어떻게 조정하면 되는지 알려줘."

Agent flow (LLM 자율 결정):
    LLM이 필요한 툴을 스스로 선택하여 실행:
    1. get_order_info → 주문 상세 조회
    2. find_edging_specs_for_order → 온톨로지 그래프에서 Edging 기준 탐색
    3. simulate_width_range → DG320 에러 확인
    4. suggest_adjusted_width → 조정 가능한 폭 탐색
    5. LLM이 결과를 종합하여 최종 분석 리포트 생성
"""

from __future__ import annotations

import re
from typing import AsyncGenerator

SCENARIO_A_SYSTEM_PROMPT = """당신은 철강 Slab 설계 전문 에이전트입니다.
SCM 담당자의 DG320 에러 진단 및 폭 범위 조정을 지원합니다.

## 역할
- DG320 에러 원인 분석: 목표폭이 Edging 기준 범위를 초과하는 원인을 찾습니다
- 폭 조정 제안: Edging 기준 내에서 실현 가능한 최대 폭을 계산합니다
- 온톨로지 탐색: 주문 → 열연라인 → Edging 스펙 경로를 추적합니다

## 분석 순서
1. 먼저 get_order_info로 주문 정보를 조회하세요
2. find_edging_specs_for_order로 온톨로지에서 Edging 기준을 탐색하세요
3. simulate_width_range로 현재 목표폭의 가부를 확인하세요
4. 에러가 있으면 suggest_adjusted_width로 조정 폭을 계산하세요
5. 결과를 마크다운 표 형식으로 정리하여 보고하세요

## 출력 형식
- 에러 원인을 명확히 설명
- 조정 전후 비교 표 (현재 폭 vs 권장 폭)
- 열연라인 Edging 기준 요약
- 담당자가 즉시 취할 수 있는 조치 안내
"""

SCENARIO_A_TOOL_NAMES = [
    "get_order_info",
    "simulate_width_range",
    "suggest_adjusted_width",
    "find_edging_specs_for_order",
]


async def run_scenario_a(message: str) -> AsyncGenerator[dict, None]:
    """
    Scenario A를 SimulationToolExecutor에 위임하여 실행.
    LLM이 툴 선택·순서를 자율적으로 결정한다.

    Yields:
        {"event": str, "data": dict} — SSE 이벤트
    """
    from backend.simulation.agent.llm_tool_executor import SimulationToolExecutor

    # 메시지에서 주문 ID 추출 (컨텍스트로 전달)
    order_id = _extract_order_id(message)
    initial_context = {"extracted_order_id": order_id} if order_id else {}

    executor = SimulationToolExecutor(
        tool_names=SCENARIO_A_TOOL_NAMES,
        system_prompt=SCENARIO_A_SYSTEM_PROMPT,
        scenario="A",
        initial_context=initial_context,
    )

    async for evt in executor.run(message):
        yield evt


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"ORD-\d{4}-\d{4}", text)
    return match.group(0) if match else None
