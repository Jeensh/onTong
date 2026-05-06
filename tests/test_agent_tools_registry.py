"""agent_tools — registry + tracker unit tests.

Covers:
- all_tool_names() reports the expected 23-tool inventory
- validate_allowlist() raises on unknown names
- RunTracker enforces max_calls (returns sentinel marker)
- RunTracker dedup caches identical calls
- register_tools() wires only the requested subset
- PRESETS map is consistent with all_tool_names()
"""

from __future__ import annotations

import pytest
from pydantic_ai import Agent

from backend.application.agent_tools import RunTracker, ToolCallRecord, register_tools
from backend.application.agent_tools.registry import (
    PRESETS,
    all_tool_names,
    validate_allowlist,
)
from backend.application.agent_tools.tracking import make_tracked


def test_inventory_reports_23_tools() -> None:
    names = all_tool_names()
    assert len(names) == 23
    # Spot check from each module
    assert "code_lookup" in names
    assert "domain_search" in names
    assert "find_existing_mapping" in names
    assert "note_observation" in names
    assert "request_user_input" in names


def test_validate_allowlist_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown agent tool"):
        validate_allowlist({"this_does_not_exist"})


def test_validate_allowlist_known_passes() -> None:
    validate_allowlist({"code_lookup", "domain_search"})


def test_presets_subset_of_all_names() -> None:
    all_names = all_tool_names()
    for preset_name, names in PRESETS.items():
        unknown = names - all_names
        assert not unknown, f"PRESET '{preset_name}' has unknown tools: {unknown}"


def test_run_tracker_dedup_caches_repeat_calls() -> None:
    calls = []

    def fn(*, x: int) -> int:
        calls.append(x)
        return x * 2

    tracker = RunTracker(max_calls=10)
    wrapped = make_tracked(fn, tool_name="double", tracker=tracker)

    assert wrapped(x=3) == 6
    assert wrapped(x=3) == 6  # cache hit — fn not called again
    assert wrapped(x=4) == 8

    assert calls == [3, 4]
    assert tracker.calls == 3
    # Second call recorded as cached
    assert tracker.records[1].cached is True
    assert tracker.records[0].cached is False


def test_run_tracker_max_calls_returns_sentinel() -> None:
    def fn(**kwargs):
        return "ok"

    tracker = RunTracker(max_calls=2, dedup=False)
    wrapped = make_tracked(fn, tool_name="t", tracker=tracker)

    assert wrapped() == "ok"
    assert wrapped() == "ok"
    out = wrapped()
    # New marker is imperative ("⛔ TOOL_BUDGET_EXCEEDED ...")
    assert "TOOL_BUDGET_EXCEEDED" in out
    # Sentinel call still recorded so the host sees the attempt
    assert tracker.calls == 3


def test_run_tracker_logger_called() -> None:
    captured: list[ToolCallRecord] = []

    def fn(**kwargs):
        return {"ok": True}

    tracker = RunTracker(max_calls=5, logger_fn=captured.append)
    wrapped = make_tracked(fn, tool_name="logme", tracker=tracker)
    wrapped(x=1)
    wrapped(x=1)  # cache hit

    assert len(captured) == 2
    assert captured[0].tool_name == "logme"
    assert captured[0].cached is False
    assert captured[1].cached is True


def test_run_tracker_swallows_tool_exceptions_as_observations() -> None:
    def boom(**kwargs):
        raise ValueError("intentional")

    tracker = RunTracker(max_calls=5)
    wrapped = make_tracked(boom, tool_name="boom", tracker=tracker)

    out = wrapped()
    assert isinstance(out, str)
    assert out.startswith("[TOOL_ERROR boom]")
    assert tracker.records[0].error == "intentional"


def test_register_tools_wires_only_allowed_subset() -> None:
    agent = Agent("test:test", output_type=str, defer_model_check=True)
    tracker = RunTracker(max_calls=3)
    registered = register_tools(
        agent,
        allowed={"code_lookup", "domain_search"},
        tracker=tracker,
    )
    assert sorted(registered) == ["code_lookup", "domain_search"]


def test_register_tools_operational_uses_null_session_when_omitted() -> None:
    agent = Agent("test:test", output_type=str, defer_model_check=True)
    tracker = RunTracker(max_calls=3)
    registered = register_tools(
        agent,
        allowed={"note_observation"},
        tracker=tracker,
        operational_session=None,
    )
    assert "note_observation" in registered


def test_registered_tools_have_real_json_schema() -> None:
    """The wrapper must preserve fn signature so pydantic_ai derives a
    proper schema (LLM needs to know parameter names + types)."""
    agent = Agent("test:test", output_type=str, defer_model_check=True)
    tracker = RunTracker(max_calls=3)
    register_tools(
        agent,
        allowed={"code_lookup", "find_callers"},
        tracker=tracker,
    )
    toolset = agent._function_toolset  # type: ignore[attr-defined]
    schemas = {t.name: t.tool_def.parameters_json_schema for t in toolset.tools.values()}
    # Required params surface in schema
    assert schemas["code_lookup"]["required"] == ["fqn"]
    assert schemas["code_lookup"]["properties"]["fqn"]["type"] == "string"
    assert schemas["find_callers"]["required"] == ["method_fqn"]
    assert schemas["find_callers"]["properties"]["limit"]["default"] == 20


def test_run_tracker_forced_reflection_wraps_result() -> None:
    """At every reflect_every-th call, the wrapper returns {result, _system_note}."""
    def fn(*, x: int) -> int:
        return x * 2

    tracker = RunTracker(max_calls=20, reflect_every=3, dedup=False)
    wrapped = make_tracked(fn, tool_name="dbl", tracker=tracker)

    assert wrapped(x=1) == 2  # call 1 — plain
    assert wrapped(x=2) == 4  # call 2 — plain
    out = wrapped(x=3)        # call 3 — reflection boundary
    assert isinstance(out, dict) and out["result"] == 6
    assert "_system_note" in out
    assert "3 tool calls" in out["_system_note"]
    assert wrapped(x=4) == 8  # call 4 — plain


def test_run_tracker_reflect_disabled_when_zero_or_none() -> None:
    def fn(*, x: int) -> int:
        return x

    tracker = RunTracker(max_calls=10, reflect_every=None)
    wrapped = make_tracked(fn, tool_name="t", tracker=tracker)
    for i in range(6):
        out = wrapped(x=i)
        assert isinstance(out, int)


def test_run_tracker_start_logger_fires_before_end() -> None:
    """SSE pattern: start fires synchronously before the tool body runs."""
    events: list[str] = []

    def fn(*, x: int) -> int:
        events.append("body")
        return x

    def start_log(*, tool_name: str, args: dict) -> None:
        events.append("start")

    def end_log(record) -> None:
        events.append("end")

    tracker = RunTracker(
        max_calls=5,
        logger_fn=end_log,
        start_logger_fn=start_log,
        dedup=False,
    )
    wrapped = make_tracked(fn, tool_name="t", tracker=tracker)
    wrapped(x=1)
    assert events == ["start", "body", "end"]


# Required so the new test_run_tracker_forced_reflection_wraps_result test
# can `make_tracked` directly.
from backend.application.agent_tools.tracking import make_tracked, usage_limits_for  # noqa: E402


def test_usage_limits_for_adds_cushion_default_2() -> None:
    """Hard cap = max_calls + cushion (default 2). Cushion gives the LLM
    a chance to see the BUDGET_EXCEEDED marker and stop voluntarily before
    pydantic_ai raises UsageLimitExceeded."""
    ul = usage_limits_for(8)
    assert ul.tool_calls_limit == 10  # 8 + 2 cushion
    assert ul.request_limit == 50

    # Custom cushion respected
    ul = usage_limits_for(10, cushion=4)
    assert ul.tool_calls_limit == 14

    # cushion=0 → tight (back to original behaviour)
    ul = usage_limits_for(5, cushion=0)
    assert ul.tool_calls_limit == 5


def test_budget_exceeded_marker_is_aggressive() -> None:
    """The soft marker should be unambiguous about stopping. Validation
    showed the LLM ignored a passive nudge — the new copy is imperative
    and tells it the next call will throw."""
    from backend.application.agent_tools.tracking import RunTracker

    marker = RunTracker.BUDGET_EXCEEDED_MARKER
    assert "DO NOT" in marker
    assert "abort" in marker.lower()
    assert "IMMEDIATELY" in marker
