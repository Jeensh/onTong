"""Scenario C: Split count optimization for unit-weight/count combination.

User input: "주문 ORD-2024-0055 Slab 설계 결과 분할수 3으로 나왔는데, 단중 만족률이 60%밖에 안 돼. 더 나은 조합 없어?"

Agent flow (LLM 자율 결정):
    1. get_order_info → 현재 설계 상태 조회
    2. simulate_split_combinations → 분할수 1~5 만족률 비교
    3. 최적 분할수 권장 및 시각화 데이터 생성
"""

from __future__ import annotations

import re
from typing import AsyncGenerator

SCENARIO_C_SYSTEM_PROMPT = """당신은 철강 Slab 분할수 최적화 전문 에이전트입니다.

## 역할
- 주문의 단중(unit weight) 만족률을 최대화하는 최적 분할수를 찾습니다
- 분할수별 Slab 단중 범위와 주문 단중 범위의 교집합을 계산하여 만족률을 평가합니다

## 분석 순서
1. get_order_info로 현재 주문의 분할수와 만족률을 확인하세요
2. simulate_split_combinations로 분할수 1~5개 전체 조합의 만족률을 계산하세요
3. 최적 분할수와 현재 분할수를 비교하는 표를 작성하세요
4. 개선 효과와 Slab 단중 범위를 포함한 권장사항을 제시하세요

## 만족률 판단 기준
- 90% 이상: 최적 (초록색)
- 70~90%: 양호 (노란색)
- 70% 미만: 개선 필요 (주황색)
- 0%: 설계불가 (빨간색)

## 출력 형식
- 현재 설계 상태 (주문 ID, 현재 분할수, 현재 만족률)
- 분할수별 만족률 비교 표 (바 차트 포함)
- 최적 분할수 권장 이유
- 개선 전후 만족률 비교 및 단중 범위
"""

SCENARIO_C_TOOL_NAMES = [
    "get_order_info",
    "simulate_split_combinations",
]


async def run_scenario_c(message: str) -> AsyncGenerator[dict, None]:
    """
    Scenario C를 SimulationToolExecutor에 위임하여 실행.
    LLM이 order_info 조회 후 split 최적화를 수행한다.

    Yields:
        {"event": str, "data": dict} — SSE 이벤트
    """
    from backend.simulation.agent.llm_tool_executor import SimulationToolExecutor

    order_id = _extract_order_id(message)
    initial_context = {"extracted_order_id": order_id} if order_id else {}

    executor = SimulationToolExecutor(
        tool_names=SCENARIO_C_TOOL_NAMES,
        system_prompt=SCENARIO_C_SYSTEM_PROMPT,
        scenario="C",
        initial_context=initial_context,
    )

    async for evt in executor.run(message):
        yield evt


def _extract_order_id(text: str) -> str | None:
    match = re.search(r"ORD-\d{4}-\d{4}", text)
    return match.group(0) if match else None
