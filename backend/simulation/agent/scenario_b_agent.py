"""Scenario B: Edging spec change ripple effect (What-If simulation).

User input: "열연 A라인 Edging 최대 능력을 180mm에서 160mm로 줄이면, 현재 설계 중인 주문들 중 몇 개나 폭 범위가 깨져?"

Agent flow (LLM 자율 결정):
    1. find_orders_by_rolling_line → 해당 라인 주문 목록 조회
    2. batch_simulate_width_impact → 병렬로 전체 주문 영향 분석
    3. 영향 요약 및 파급 효과 리포트 생성
"""

from __future__ import annotations

import re
from typing import AsyncGenerator

SCENARIO_B_SYSTEM_PROMPT = """당신은 철강 SCM Edging 기준 변경 파급효과 분석 전문 에이전트입니다.

## 역할
- 열연라인의 Edging 최대 능력이 변경될 경우, 해당 라인에 배정된 주문들의 폭 범위 설계에 미치는 영향을 분석합니다
- 영향받는 주문(설계불가 전환)과 안전한 주문을 구분하여 파급효과 보고서를 작성합니다

## 분석 순서
1. find_orders_by_rolling_line으로 대상 열연라인의 주문 목록을 조회하세요
2. batch_simulate_width_impact로 전체 주문의 영향을 한 번에 병렬 분석하세요
   (또는 analyze_edging_change_ripple로 전체 분석을 한 번에 수행할 수 있습니다)
3. 영향받는 주문과 안전한 주문을 표로 정리하세요
4. 전체 영향률과 권장 조치를 제시하세요

## 주요 판단 기준
- 영향받는 주문: 기존에 가능(feasible=true)했으나 변경 후 불가(feasible=false)로 전환
- 폭 범위 축소: 가능하지만 허용 범위가 줄어드는 경우
- 안전한 주문: 변경 후에도 설계 가부에 변화 없음

## 출력 형식
- 변경 요약 (열연라인, 기존 Edging → 변경 Edging)
- 영향 현황 요약 표 (전체/영향/안전 건수, 영향률)
- 영향받는 주문 상세 목록
- 권장 조치 (폭 조정 또는 라인 재배정 안내)
"""

SCENARIO_B_TOOL_NAMES = [
    "find_orders_by_rolling_line",
    "simulate_width_impact",
    "batch_simulate_width_impact",
    "analyze_edging_change_ripple",
    "get_order_info",
]


async def run_scenario_b(message: str) -> AsyncGenerator[dict, None]:
    """
    Scenario B를 SimulationToolExecutor에 위임하여 실행.
    LLM이 툴을 선택하고, batch_simulate_width_impact로 병렬 분석을 수행한다.

    Yields:
        {"event": str, "data": dict} — SSE 이벤트
    """
    from backend.simulation.agent.llm_tool_executor import SimulationToolExecutor

    # 메시지에서 파라미터 추출 (초기 컨텍스트로 전달)
    rolling_line = _extract_rolling_line(message)
    new_edging_max = _extract_edging_max(message)

    initial_context: dict = {}
    if rolling_line:
        initial_context["extracted_rolling_line"] = rolling_line
    if new_edging_max:
        initial_context["extracted_new_edging_max"] = new_edging_max

    executor = SimulationToolExecutor(
        tool_names=SCENARIO_B_TOOL_NAMES,
        system_prompt=SCENARIO_B_SYSTEM_PROMPT,
        scenario="B",
        initial_context=initial_context,
    )

    async for evt in executor.run(message):
        yield evt


def _extract_rolling_line(text: str) -> str | None:
    if "A라인" in text or "HR-A" in text:
        return "HR-A"
    if "B라인" in text or "HR-B" in text:
        return "HR-B"
    return None


def _extract_edging_max(text: str) -> int | None:
    match = re.search(r"(\d{2,3})\s*mm", text)
    if match:
        return int(match.group(1))
    return None
