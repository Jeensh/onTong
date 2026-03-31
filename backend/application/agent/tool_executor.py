"""Tool executor — ReAct loop for LLM tool-use agents.

Provides a generic execute_tool_call() + react_loop() that any agent can use.
The LLM decides which skills to call, this module executes them and feeds results back.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Any

from backend.core.schemas import ContentDelta, DoneEvent, ThinkingStepEvent, TokenUsage
from backend.application.agent.context import AgentContext

logger = logging.getLogger(__name__)


async def execute_tool_call(ctx: AgentContext, tool_call: Any) -> str:
    """Execute a single LLM tool call against the skill registry.

    Returns JSON string of the skill result for feeding back to the LLM.
    """
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return json.dumps({"error": f"Invalid JSON arguments for {name}"}, ensure_ascii=False)

    result = await ctx.run_skill(name, **args)

    if not result.success:
        return json.dumps({"error": result.error}, ensure_ascii=False)

    return json.dumps(result.data, ensure_ascii=False, default=str)


async def react_loop(
    ctx: AgentContext,
    messages: list[dict],
    tools: list[dict],
    max_iterations: int = 5,
    stream_final: bool = True,
) -> AsyncGenerator[str, None]:
    """Generic ReAct loop: LLM decides which tools to call, we execute them, repeat.

    Yields SSE event strings throughout the process.

    Args:
        ctx: Agent context with skill access.
        messages: Initial conversation messages (system + user).
        tools: Tool schemas from skill_registry.to_tool_schemas() or a subset.
        max_iterations: Safety limit on tool call rounds.
        stream_final: If True, stream the final answer chunk by chunk.
    """
    for iteration in range(max_iterations):
        # Call LLM with tools
        gen_result = await ctx.run_skill(
            "llm_generate",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
            temperature=0.3,
        )

        if not gen_result.success:
            yield ctx.sse(
                "content_delta",
                ContentDelta(delta=f"LLM 호출 실패: {gen_result.error}").model_dump_json(),
            )
            yield ctx.sse("done", DoneEvent().model_dump_json())
            return

        data = gen_result.data
        tool_calls = data.get("tool_calls")

        if not tool_calls:
            # LLM is done reasoning — emit final content
            content = data.get("content", "")
            if content:
                if stream_final:
                    # For non-streaming final response, emit as single delta
                    yield ctx.sse("content_delta", ContentDelta(delta=content).model_dump_json())
                else:
                    yield ctx.sse("content_delta", ContentDelta(delta=content).model_dump_json())

            yield ctx.sse("done", DoneEvent(usage=data.get("usage")).model_dump_json())
            return

        # Execute each tool call
        llm_message = data.get("message")
        if llm_message:
            messages.append(llm_message.model_dump())

        for tc in tool_calls:
            skill_name = tc.function.name
            yield ctx.emit_thinking(
                f"skill:{skill_name}", "start",
                f"스킬 실행: {skill_name}",
            )

            result_str = await execute_tool_call(ctx, tc)

            yield ctx.emit_thinking(
                f"skill:{skill_name}", "done",
                f"스킬 완료: {skill_name}",
                result_str[:100] + ("..." if len(result_str) > 100 else ""),
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    # Safety: max iterations reached
    yield ctx.sse(
        "content_delta",
        ContentDelta(delta="최대 반복 횟수에 도달했습니다. 결과를 정리합니다.").model_dump_json(),
    )
    yield ctx.sse("done", DoneEvent().model_dump_json())
