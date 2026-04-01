"""Simulator Agent — Phase 2 stub with Pydantic AI scaffolding.

When fully implemented, this agent will use the ReAct loop with wiki tools
to perform parameter simulation based on wiki rules.

Usage pattern (Phase 2):
    from backend.application.agent.react_agent import create_react_agent
    from backend.application.agent.tool_executor import react_loop

    agent = create_react_agent(SIMULATION_SYSTEM_PROMPT)
    async for event in react_loop(ctx, messages, tools=[], agent=agent):
        yield event
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from backend.core.schemas import ChatRequest, ContentDelta, DoneEvent


class SimulatorAgent:
    name = "SIMULATION"

    async def execute(
        self, request: ChatRequest, **kwargs
    ) -> AsyncGenerator[str, None]:
        msg = (
            "시뮬레이션 에이전트는 현재 Phase 2에서 개발 예정입니다.\n\n"
            "이 에이전트가 완성되면 다음을 수행합니다:\n"
            "- Wiki 규칙 기반 파라미터 시뮬레이션\n"
            "- Pydantic AI ReAct 루프로 오류 감지 시 자동 재조정\n"
            "- 최적 결과 반환"
        )
        yield f"event: content_delta\ndata: {ContentDelta(delta=msg).model_dump_json()}\n\n"
        yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"
