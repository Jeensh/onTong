"""SSE event pump — bridges agent tool calls to a streaming endpoint.

Usage in a FastAPI SSE endpoint:

    pump = ToolEventPump()
    tracker = RunTracker(
        max_calls=10,
        start_logger_fn=pump.start,   # → tool_call_start
        logger_fn=pump.end,           # → tool_call_end
    )
    register_tools(agent, allowed=..., tracker=tracker, ...)

    async def stream():
        async for ev in pump.bridge(agent.run(prompt, ...)):
            yield f"data: {json.dumps(ev)}\\n\\n"

The pump puts events on an asyncio.Queue. `bridge()` interleaves events
with the running agent task and yields a final `done` event with the
agent's structured output.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from backend.application.agent_tools.tracking import ToolCallRecord, summarize

logger = logging.getLogger(__name__)


class ToolEventPump:
    """Asyncio queue + start/end loggers tailored for SSE."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._call_seq = 0

    # ── Logger callbacks (sync, called from inside tool wrappers) ────

    def start(self, *, tool_name: str, args: dict[str, Any]) -> None:
        self._call_seq += 1
        ev = {
            "type": "tool_call_start",
            "seq": self._call_seq,
            "tool_name": tool_name,
            "args_summary": summarize(args, max_len=120),
        }
        try:
            self.queue.put_nowait(ev)
        except asyncio.QueueFull:
            logger.warning("agent_tools SSE queue full; dropping start event")

    def end(self, record: ToolCallRecord) -> None:
        ev = {
            "type": "tool_call_end",
            "tool_name": record.tool_name,
            "result_summary": record.result_summary,
            "duration_ms": record.duration_ms,
            "cached": record.cached,
            "error": record.error,
        }
        try:
            self.queue.put_nowait(ev)
        except asyncio.QueueFull:
            logger.warning("agent_tools SSE queue full; dropping end event")

    # ── Bridge ───────────────────────────────────────────────────────

    async def bridge(
        self, agent_run_coro, *, poll_interval: float = 0.2, idle_timeout_s: float = 300.0
    ):
        """Run `agent_run_coro` concurrently and yield events as they arrive.

        Final yield is `{"type": "done", "output": <structured>, "tool_call_count": N}`.
        On agent error, yields `{"type": "error", "message": ...}` and re-raises
        only AFTER closing — caller must catch in surrounding `try` if it wants
        to.

        `idle_timeout_s` guards against a stuck task; if no events fire and
        the agent hasn't completed within this window we yield a heartbeat.
        """
        agent_task = asyncio.create_task(agent_run_coro)

        # Initial event so clients confirm stream is open.
        yield {"type": "stream_open"}

        last_event_time = asyncio.get_event_loop().time()
        try:
            while not agent_task.done():
                try:
                    ev = await asyncio.wait_for(
                        self.queue.get(), timeout=poll_interval
                    )
                    last_event_time = asyncio.get_event_loop().time()
                    yield ev
                except asyncio.TimeoutError:
                    now = asyncio.get_event_loop().time()
                    if now - last_event_time > idle_timeout_s:
                        yield {"type": "heartbeat", "stale_for_s": int(now - last_event_time)}
                        last_event_time = now

            # Drain anything left in the queue.
            while True:
                try:
                    ev = self.queue.get_nowait()
                    yield ev
                except asyncio.QueueEmpty:
                    break

            # Surface the agent's final output.
            try:
                result = agent_task.result()
                output = getattr(result, "output", result)
                # If structured output is a Pydantic model, dump to dict.
                if hasattr(output, "model_dump"):
                    output = output.model_dump()
                yield {
                    "type": "done",
                    "output": output,
                    "tool_call_count": self._call_seq,
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("agent run errored inside pump.bridge")
                yield {"type": "error", "message": str(exc)}
        finally:
            if not agent_task.done():
                agent_task.cancel()


def sse_format(event: dict[str, Any]) -> str:
    """Encode an event dict as an SSE `data:` frame."""
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


__all__ = ["ToolEventPump", "sse_format"]
