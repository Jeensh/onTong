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
            "시뮬레이션 기능은 아직 준비 중입니다. "
            "현재는 위키 기반 질의응답만 지원하니, 문서 내용을 묻는 형태로 질문해 주세요."
        )
        yield f"event: content_delta\ndata: {ContentDelta(delta=msg).model_dump_json()}\n\n"
        yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"
