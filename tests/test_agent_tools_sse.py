"""ToolEventPump SSE bridge tests.

Verifies that:
- start callbacks emit `tool_call_start` events
- end callbacks emit `tool_call_end` events
- bridge() interleaves events with the agent run and surfaces a `done` final
- bridge() yields `error` on agent exception (does not raise upward)
- sse_format produces a well-formed SSE frame
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.application.agent_tools import RunTracker, ToolEventPump, sse_format
from backend.application.agent_tools.tracking import make_tracked


def test_sse_format_writes_data_frame() -> None:
    out = sse_format({"type": "x", "n": 1})
    assert out.startswith("data: ")
    assert out.endswith("\n\n")
    body = out[len("data: "): -2]
    assert json.loads(body) == {"type": "x", "n": 1}


@pytest.mark.asyncio
async def test_pump_start_and_end_events() -> None:
    pump = ToolEventPump()

    def fn(*, x: int) -> int:
        return x * 2

    tracker = RunTracker(
        max_calls=5,
        start_logger_fn=pump.start,
        logger_fn=pump.end,
        dedup=False,
    )
    wrapped = make_tracked(fn, tool_name="dbl", tracker=tracker)
    wrapped(x=3)
    wrapped(x=4)

    # 4 events queued (2 start + 2 end)
    drained = []
    while not pump.queue.empty():
        drained.append(pump.queue.get_nowait())
    types = [e["type"] for e in drained]
    assert types == ["tool_call_start", "tool_call_end", "tool_call_start", "tool_call_end"]
    # seq numbers monotonic
    assert drained[0]["seq"] == 1
    assert drained[2]["seq"] == 2
    # tool name preserved
    assert all(e["tool_name"] == "dbl" for e in drained)


@pytest.mark.asyncio
async def test_pump_bridge_interleaves_with_agent_run() -> None:
    pump = ToolEventPump()

    def fn(*, x: int) -> int:
        return x

    tracker = RunTracker(
        max_calls=5,
        start_logger_fn=pump.start,
        logger_fn=pump.end,
        dedup=False,
    )
    wrapped = make_tracked(fn, tool_name="t", tracker=tracker)

    async def fake_agent_run() -> object:
        # Tool calls happen mid-run
        await asyncio.sleep(0.01)
        wrapped(x=1)
        await asyncio.sleep(0.01)
        wrapped(x=2)
        await asyncio.sleep(0.01)

        class _Result:
            output = {"final": True}

        return _Result()

    events = []
    async for ev in pump.bridge(fake_agent_run(), poll_interval=0.005):
        events.append(ev)

    types = [e["type"] for e in events]
    assert types[0] == "stream_open"
    assert "tool_call_start" in types
    assert "tool_call_end" in types
    assert types[-1] == "done"
    done = events[-1]
    assert done["output"] == {"final": True}
    assert done["tool_call_count"] == 2


@pytest.mark.asyncio
async def test_pump_bridge_surfaces_agent_error() -> None:
    pump = ToolEventPump()

    async def boom() -> object:
        raise RuntimeError("intentional")

    events = []
    async for ev in pump.bridge(boom(), poll_interval=0.005):
        events.append(ev)

    types = [e["type"] for e in events]
    assert "error" in types
    err = next(e for e in events if e["type"] == "error")
    assert "intentional" in err["message"]
