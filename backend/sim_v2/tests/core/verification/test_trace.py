"""Trace infrastructure tests — W16.1."""
from __future__ import annotations

from decimal import Decimal

from backend.sim_v2.core.verification.trace import (
    TraceCollector,
    TraceEvent,
    diff_traces,
    traces_equivalent,
)


# ─────────────────────────────────────────────────────────────────────────────
# TraceCollector
# ─────────────────────────────────────────────────────────────────────────────


def test_collector_starts_empty():
    c = TraceCollector()
    assert c.events == []


def test_collector_step_appends():
    c = TraceCollector()
    c.step("a1", {"x": 1})
    c.step("a2", {"y": 2})
    assert len(c.events) == 2
    assert c.events[0].anchor_id == "a1"
    assert c.events[0].vars == (("x", 1),)


def test_collector_branch():
    c = TraceCollector()
    c.branch("b1", True)
    assert c.events[0].kind == "branch"
    assert c.events[0].vars == (("cond", True),)


def test_collector_exception():
    c = TraceCollector()
    c.exception("e1", "RuntimeError", "boom")
    assert c.events[0].kind == "exception"
    assert dict(c.events[0].vars) == {"type": "RuntimeError", "message": "boom"}


def test_collector_reset():
    c = TraceCollector()
    c.step("a1", {})
    c.reset()
    assert c.events == []


def test_collector_events_is_copy():
    """Mutating the returned events list does not affect collector."""
    c = TraceCollector()
    c.step("a1", {})
    snapshot = c.events
    snapshot.append("garbage")
    assert len(c.events) == 1


def test_event_vars_sorted_by_key():
    c = TraceCollector()
    c.step("a1", {"z": 1, "a": 2, "m": 3})
    assert c.events[0].vars == (("a", 2), ("m", 3), ("z", 1))


def test_event_is_frozen():
    import pytest
    from dataclasses import FrozenInstanceError
    e = TraceEvent(anchor_id="a", kind="step", vars=(("x", 1),))
    with pytest.raises(FrozenInstanceError):
        e.anchor_id = "b"  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# diff_traces
# ─────────────────────────────────────────────────────────────────────────────


def test_diff_identical_traces():
    a = [TraceEvent("1", "step", (("x", 1),))]
    b = [TraceEvent("1", "step", (("x", 1),))]
    r = diff_traces(a, b)
    assert r.is_equivalent
    assert "1 steps matched" in r.summary


def test_diff_value_mismatch():
    a = [TraceEvent("1", "step", (("x", 1),))]
    b = [TraceEvent("1", "step", (("x", 2),))]
    r = diff_traces(a, b)
    assert not r.is_equivalent
    assert r.diverging_step_no == 0
    assert "var values differ" in r.summary


def test_diff_anchor_mismatch():
    a = [TraceEvent("a", "step", ())]
    b = [TraceEvent("b", "step", ())]
    r = diff_traces(a, b)
    assert not r.is_equivalent
    assert "anchor/kind mismatch" in r.summary


def test_diff_length_mismatch():
    a = [TraceEvent("1", "step", ()), TraceEvent("2", "step", ())]
    b = [TraceEvent("1", "step", ())]
    r = diff_traces(a, b)
    assert not r.is_equivalent
    assert r.diverging_step_no == 1
    assert "length mismatch" in r.summary


def test_diff_numeric_tolerance_within():
    a = [TraceEvent("1", "step", (("x", Decimal("1.0")),))]
    b = [TraceEvent("1", "step", (("x", Decimal("1.001")),))]
    r = diff_traces(a, b, numeric_tolerance=0.01)
    assert r.is_equivalent


def test_diff_numeric_tolerance_exceeded():
    a = [TraceEvent("1", "step", (("x", Decimal("1.0")),))]
    b = [TraceEvent("1", "step", (("x", Decimal("2.0")),))]
    r = diff_traces(a, b, numeric_tolerance=0.5)
    assert not r.is_equivalent


def test_traces_equivalent_boolean_alias():
    a = [TraceEvent("1", "step", ())]
    b = [TraceEvent("1", "step", ())]
    assert traces_equivalent(a, b)
    assert not traces_equivalent(a, [TraceEvent("1", "step", (("z", 1),))])
