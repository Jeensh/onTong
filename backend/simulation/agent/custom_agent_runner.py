"""Custom Agent Runner — 등록된 커스텀 에이전트를 SimulationToolExecutor로 실행.

기존 패턴 매칭 기반 툴 선택을 완전히 제거하고,
LLM(Anthropic claude-sonnet-4-6)이 agent_def의 available_tools 중에서
적합한 툴을 자율적으로 선택·실행하도록 변경한다.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


async def run_custom_agent(
    agent_def: dict,
    message: str,
) -> AsyncGenerator[dict, None]:
    """
    커스텀 에이전트 정의를 바탕으로 SimulationToolExecutor를 구성하여 실행.

    Args:
        agent_def: {name, system_prompt, available_tools, goal, ...}
        message: 사용자 입력 메시지

    Yields:
        {"event": str, "data": dict} — SSE 이벤트
    """
    from backend.simulation.agent.llm_tool_executor import SimulationToolExecutor
    from backend.simulation.tools.tool_registry import get_registry

    agent_name = agent_def.get("name", "Custom Agent")
    system_prompt = agent_def.get("system_prompt", "")
    available_tools = agent_def.get("available_tools", [])

    # system_prompt가 없으면 goal에서 생성
    if not system_prompt:
        goal = agent_def.get("goal", "Slab 설계 분석")
        system_prompt = _build_system_prompt(agent_name, goal, available_tools)

    # 레지스트리에 실제 등록된 툴만 필터링
    registry = get_registry()
    valid_tools = [t for t in available_tools if registry.get(t) is not None]

    if not valid_tools:
        logger.warning(f"커스텀 에이전트 '{agent_name}': 유효한 툴이 없습니다. 전체 툴 목록 사용.")
        valid_tools = registry.all_tool_names()

    executor = SimulationToolExecutor(
        tool_names=valid_tools,
        system_prompt=system_prompt,
        scenario="custom",
    )

    async for evt in executor.run(message):
        yield evt


def _build_system_prompt(agent_name: str, goal: str, available_tools: list[str]) -> str:
    """agent_def의 goal과 available_tools로 기본 시스템 프롬프트 생성."""
    tool_list = "\n".join(f"- {t}" for t in available_tools) if available_tools else "- (모든 Slab 설계 툴)"
    return f"""당신은 '{agent_name}' 에이전트입니다.

## 목표
{goal}

## 사용 가능한 도구
{tool_list}

## 지침
- 사용자 질문을 분석하고 위 도구 중 적합한 것을 선택하여 실행하세요
- 도구 결과를 종합하여 한국어로 명확하게 답변하세요
- 마크다운 표 형식을 활용하여 결과를 구조화하세요
- 분석 근거와 권장 조치를 포함하세요
"""
