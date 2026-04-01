"""Tracer Agent — Phase 2 stub with Pydantic AI scaffolding.

When fully implemented, this agent will use the ReAct loop with wiki tools
and code analysis tools to trace root causes of issues.

Usage pattern (Phase 2):
    from backend.application.agent.react_agent import create_react_agent
    from backend.application.agent.tool_executor import react_loop

    agent = create_react_agent(DEBUG_TRACE_SYSTEM_PROMPT)
    async for event in react_loop(ctx, messages, tools=[], agent=agent):
        yield event
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from backend.core.schemas import ChatRequest, ContentDelta, DoneEvent


class TracerAgent:
    name = "DEBUG_TRACE"

    async def execute(
        self, request: ChatRequest, **kwargs
    ) -> AsyncGenerator[str, None]:
        msg = (
            "디버그 추적 에이전트는 현재 Phase 2에서 개발 예정입니다.\n\n"
            "이 에이전트가 완성되면 다음을 수행합니다:\n"
            "- Git 커밋 히스토리 파싱\n"
            "- Pydantic AI ReAct 루프로 코드 의존성 추적\n"
            "- DB 유효성 검사로 데이터 불일치 경계 파악"
        )
        yield f"event: content_delta\ndata: {ContentDelta(delta=msg).model_dump_json()}\n\n"
        yield f"event: done\ndata: {DoneEvent().model_dump_json()}\n\n"
