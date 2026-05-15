"""Trace collector + comparison — W16.

Per-anchor execution trace. Emitter (when instrumented via translator's
with_trace=True option) inserts `_trace.step(anchor_id, vars)` after each
statement. Verification engine compares two traces (translated vs baseline)
to produce TraceDiff for R4 strong verification.

Public API:
  - TraceEvent — frozen dataclass per step
  - TraceCollector — mutable append-only collector, exposes step() to emitted code
  - traces_equivalent — comparison helper with tolerance
  - diff_traces — detailed first-divergence report
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal


TraceKind = Literal["step", "branch", "loop_iter", "exception"]


@dataclass(frozen=True)
class TraceEvent:
    """One immutable trace entry. step() appends; never mutated after creation."""
    anchor_id: str
    kind:      TraceKind = "step"
    vars:      tuple[tuple[str, Any], ...] = ()
    # frozen — converted from dict at construction time


class TraceCollector:
    """Mutable append-only trace recorder. emitted code calls `step(anchor, vars)`."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def step(self, anchor_id: str, vars: dict[str, Any] | None = None) -> None:
        """Append a 'step' event. vars dict is frozen into tuple-of-pairs."""
        self._events.append(TraceEvent(
            anchor_id=str(anchor_id),
            kind="step",
            vars=tuple(sorted((vars or {}).items())),
        ))

    def branch(self, anchor_id: str, cond: bool) -> None:
        self._events.append(TraceEvent(
            anchor_id=str(anchor_id),
            kind="branch",
            vars=(("cond", cond),),
        ))

    def exception(self, anchor_id: str, exc_type: str, message: str) -> None:
        self._events.append(TraceEvent(
            anchor_id=str(anchor_id),
            kind="exception",
            vars=(("type", exc_type), ("message", message)),
        ))

    @property
    def events(self) -> list[TraceEvent]:
        """Read-only view (list is a copy)."""
        return list(self._events)

    def reset(self) -> None:
        self._events = []


# ─────────────────────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TraceDiffResult:
    """Output of diff_traces — used to populate Oracle's TraceDiff."""
    is_equivalent:     bool
    diverging_step_no: int | None = None
    expected_event:    TraceEvent | None = None
    actual_event:      TraceEvent | None = None
    summary:           str = ""


def diff_traces(
    expected: list[TraceEvent],
    actual:   list[TraceEvent],
    *,
    numeric_tolerance: float = 0.0,
) -> TraceDiffResult:
    """Diff two trace event lists. First divergence wins.

    A divergence is:
      - anchor_id mismatch
      - kind mismatch
      - vars set differs (key names or values past tolerance)

    Length mismatch — first absent event is the divergence point.
    """
    for i in range(max(len(expected), len(actual))):
        e = expected[i] if i < len(expected) else None
        a = actual[i] if i < len(actual) else None
        if e is None or a is None:
            return TraceDiffResult(
                is_equivalent=False,
                diverging_step_no=i,
                expected_event=e,
                actual_event=a,
                summary=(
                    "length mismatch: "
                    f"expected={len(expected)}, actual={len(actual)}"
                ),
            )
        if e.anchor_id != a.anchor_id or e.kind != a.kind:
            return TraceDiffResult(
                is_equivalent=False,
                diverging_step_no=i,
                expected_event=e,
                actual_event=a,
                summary=f"anchor/kind mismatch at step {i}",
            )
        if not _vars_equivalent(e.vars, a.vars, tolerance=numeric_tolerance):
            return TraceDiffResult(
                is_equivalent=False,
                diverging_step_no=i,
                expected_event=e,
                actual_event=a,
                summary=f"var values differ at step {i}",
            )
    return TraceDiffResult(
        is_equivalent=True,
        summary=f"{len(expected)} steps matched",
    )


def traces_equivalent(
    expected: list[TraceEvent],
    actual:   list[TraceEvent],
    *,
    numeric_tolerance: float = 0.0,
) -> bool:
    """Convenience boolean alias of diff_traces(...).is_equivalent."""
    return diff_traces(expected, actual, numeric_tolerance=numeric_tolerance).is_equivalent


def _vars_equivalent(
    a: tuple[tuple[str, Any], ...],
    b: tuple[tuple[str, Any], ...],
    *,
    tolerance: float,
) -> bool:
    """Compare two sorted var tuples. Numeric tolerance applies to Decimal/float."""
    if len(a) != len(b):
        return False
    for (ka, va), (kb, vb) in zip(a, b):
        if ka != kb:
            return False
        if not _value_equivalent(va, vb, tolerance=tolerance):
            return False
    return True


def _value_equivalent(va: Any, vb: Any, *, tolerance: float) -> bool:
    """Tolerance-aware equality for numeric values (Decimal/int/float)."""
    if isinstance(va, (Decimal, int, float)) and isinstance(vb, (Decimal, int, float)):
        try:
            return abs(Decimal(va) - Decimal(vb)) <= Decimal(str(tolerance))
        except Exception:
            return va == vb
    return va == vb


__all__ = [
    "TraceCollector",
    "TraceDiffResult",
    "TraceEvent",
    "TraceKind",
    "diff_traces",
    "traces_equivalent",
]
