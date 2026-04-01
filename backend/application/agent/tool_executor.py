"""Tool executor — Pydantic AI-based ReAct loop for LLM tool-use agents.

Replaces the manual litellm tool-calling loop with Pydantic AI's built-in
agent loop while preserving the same SSE event interface.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
)

from backend.core.schemas import ContentDelta, DoneEvent, TokenUsage
from backend.application.agent.context import AgentContext

logger = logging.getLogger(__name__)


async def execute_tool_call(ctx: AgentContext, tool_call: Any) -> str:
    """Execute a single LLM tool call against the skill registry.

    Kept for backward compatibility with any code calling it directly.
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
    *,
    agent: Agent[AgentContext, str] | None = None,
) -> AsyncGenerator[str, None]:
    """Pydantic AI-based ReAct loop: agent decides tools, executes them, streams answer.

    Yields SSE event strings throughout the process.
    Signature preserved for backward compatibility.

    Args:
        ctx: Agent context with skill access.
        messages: Initial conversation messages (system + user). Used to extract
                  the user prompt; Pydantic AI manages the conversation internally.
        tools: Tool schemas (ignored — Pydantic AI uses registered @agent.tool).
        max_iterations: Safety limit on tool call rounds.
        stream_final: If True, stream the final answer chunk by chunk.
        agent: Optional pre-configured Pydantic AI agent. If None, creates one.
    """
    if agent is None:
        from backend.application.agent.react_agent import create_react_agent

        system_msgs = [m["content"] for m in messages if m.get("role") == "system"]
        system_prompt = "\n\n".join(system_msgs) if system_msgs else ""
        agent = create_react_agent(system_prompt)

    # Extract user prompt from messages
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    user_prompt = user_msgs[-1] if user_msgs else ""

    # Collect SSE events from tool calls via event_stream_handler
    sse_queue: list[str] = []

    async def handle_events(run_ctx: Any, events: Any) -> None:
        """Capture tool call/result events and convert to SSE thinking steps."""
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                tool_name = event.part.tool_name
                sse_queue.append(
                    ctx.emit_thinking(
                        f"skill:{tool_name}", "start",
                        f"스킬 실행: {tool_name}",
                    )
                )
            elif isinstance(event, FunctionToolResultEvent):
                tool_name = event.result.tool_name
                content_str = str(event.content) if event.content else ""
                preview = content_str[:100] + ("..." if len(content_str) > 100 else "")
                sse_queue.append(
                    ctx.emit_thinking(
                        f"skill:{tool_name}", "done",
                        f"스킬 완료: {tool_name}",
                        preview,
                    )
                )

    try:
        async with agent.run_stream(
            user_prompt,
            deps=ctx,
            usage_limits=UsageLimits(request_limit=max_iterations),
            event_stream_handler=handle_events,
        ) as stream:
            # Yield any tool-related SSE events that accumulated
            while sse_queue:
                yield sse_queue.pop(0)

            # Stream the final text answer
            async for text_delta in stream.stream_text(delta=True):
                # Flush any queued tool events first
                while sse_queue:
                    yield sse_queue.pop(0)

                if text_delta and stream_final:
                    yield ctx.sse(
                        "content_delta",
                        ContentDelta(delta=text_delta).model_dump_json(),
                    )

            # Flush remaining tool events
            while sse_queue:
                yield sse_queue.pop(0)

            # Emit done with usage info
            usage = stream.usage()
            token_usage = TokenUsage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
            )
            yield ctx.sse("done", DoneEvent(usage=token_usage).model_dump_json())

    except Exception as e:
        logger.error(f"ReAct loop error: {e}", exc_info=True)
        yield ctx.sse(
            "content_delta",
            ContentDelta(delta=f"처리 중 오류가 발생했습니다: {e}").model_dump_json(),
        )
        yield ctx.sse("done", DoneEvent().model_dump_json())
