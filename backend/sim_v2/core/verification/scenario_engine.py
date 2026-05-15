"""Scenario-based VerificationEngine — W15.1 + W16 trace capture.

A concrete `VerificationEngine` impl that adapts in-process scenario tests to
the Integrator's OracleRequest/OracleResult protocol.

Given:
  - A translated Python callable (the proposal's "twin")
  - A baseline Python callable (ground truth)
  - A fixture dict (id → scenario inputs + expected output)

Runs each requested fixture through both callables, compares outputs, builds
FixtureOracleResult per fixture, and aggregates to OracleResult.

W16: optional `with_trace=True` — translator emit instrumented Python that
calls `_trace.step(...)` after each statement. ScenarioEngine injects a fresh
TraceCollector into translated_fn's globals per fixture run and captures the
events for TraceDiff. Cross-side comparison (translated vs Java baseline) is
deferred to W17 — for now TraceDiff summary records `N events captured`.

Public API:
  - Scenario — input dict + expected output (or expected exception)
  - ScenarioVerificationEngine — implements VerificationEngine Protocol
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)
from backend.sim_v2.core.verification.trace import (
    TraceCollector,
    TraceEvent,
    diff_traces,
)


@dataclass
class Scenario:
    """Single fixture input + expected output (or expected exception type)."""
    fixture_id: str
    inputs: dict[str, Any]
    expected_output: Any = None
    expected_exception: type | None = None
    tolerance: dict[str, float] = field(default_factory=dict)


class ScenarioVerificationEngine:
    """In-process VerificationEngine — runs translated_fn vs baseline_fn per scenario.

    Implements the `VerificationEngine` Protocol from `core.integrator.integrator`.
    Lesson 5 §4.1 metadata (tolerance, scenario_intent) is partially honored via
    Scenario.tolerance (used in OutputDiff.tolerance).
    """

    def __init__(
        self,
        translated_fn: Callable[..., Any],
        baseline_fn: Callable[..., Any],
        fixtures: dict[str, Scenario],
        with_trace: bool = False,
        trace_tolerance: float = 0.0,
    ) -> None:
        self.translated_fn = translated_fn
        self.baseline_fn = baseline_fn
        self.fixtures = fixtures
        self.with_trace = with_trace
        self.trace_tolerance = trace_tolerance
        # captured per-fixture trace events (W16/W17, accessible after run_oracle)
        self.last_traces: dict[str, list[TraceEvent]] = {}
        self.last_baseline_traces: dict[str, list[TraceEvent]] = {}

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        results: dict[str, FixtureOracleResult] = {}
        self.last_traces = {}
        self.last_baseline_traces = {}
        for fid in request.fixture_subset:
            scenario = self.fixtures.get(fid)
            if scenario is None:
                results[fid] = _missing_fixture_result(fid)
                continue
            results[fid] = self._run_one(scenario)

        aggregate = aggregate_status_from_fixtures(results)
        summary = self._summarize(results)
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=results,
            aggregate_status=aggregate,
            summary=summary,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Per-fixture run
    # ─────────────────────────────────────────────────────────────────────

    def _run_one(self, scenario: Scenario) -> FixtureOracleResult:
        translated_trace: list[TraceEvent] = []
        baseline_trace: list[TraceEvent] = []

        if self.with_trace:
            translated_collector = TraceCollector()
            baseline_collector = TraceCollector()
            if hasattr(self.translated_fn, "__globals__"):
                self.translated_fn.__globals__["_trace"] = translated_collector
            if hasattr(self.baseline_fn, "__globals__"):
                self.baseline_fn.__globals__["_trace"] = baseline_collector

            translated_out, translated_exc = _safe_call(self.translated_fn, scenario.inputs)
            baseline_out, baseline_exc = _safe_call(self.baseline_fn, scenario.inputs)

            translated_trace = translated_collector.events
            baseline_trace = baseline_collector.events
            self.last_traces[scenario.fixture_id] = translated_trace
            self.last_baseline_traces[scenario.fixture_id] = baseline_trace
        else:
            translated_out, translated_exc = _safe_call(self.translated_fn, scenario.inputs)
            baseline_out, baseline_exc = _safe_call(self.baseline_fn, scenario.inputs)

        return self._build_fixture_result(
            scenario=scenario,
            translated_out=translated_out,
            translated_exc=translated_exc,
            baseline_out=baseline_out,
            baseline_exc=baseline_exc,
            translated_trace=translated_trace,
            baseline_trace=baseline_trace,
        )

    def _build_fixture_result(
        self,
        *,
        scenario: Scenario,
        translated_out: Any,
        translated_exc: Exception | None,
        baseline_out: Any,
        baseline_exc: Exception | None,
        translated_trace: list[TraceEvent],
        baseline_trace: list[TraceEvent],
    ) -> FixtureOracleResult:
        is_equivalent, diff_summary = _compare_outputs(
            translated_out, translated_exc,
            baseline_out, baseline_exc,
            scenario,
        )

        output_diff = OutputDiff(
            is_equivalent=is_equivalent,
            baseline_value=_serializable(baseline_out, baseline_exc),
            proposal_value=_serializable(translated_out, translated_exc),
            tolerance=scenario.tolerance,
            summary=diff_summary,
        )

        # Trace diff (W17) — cross-side comparison when with_trace=True.
        if self.with_trace and (translated_trace or baseline_trace):
            tr = diff_traces(
                baseline_trace, translated_trace,
                numeric_tolerance=self.trace_tolerance,
            )
            trace_diff = TraceDiff(
                is_equivalent=tr.is_equivalent,
                diverging_step_no=tr.diverging_step_no,
                expected_event=_event_to_dict(tr.expected_event),
                actual_event=_event_to_dict(tr.actual_event),
                summary=tr.summary,
            )
        elif self.with_trace:
            trace_diff = TraceDiff(
                is_equivalent=True,
                summary="trace enabled but no events captured",
            )
        else:
            trace_diff = TraceDiff(
                is_equivalent=True,
                summary="trace capture disabled",
            )

        # Status determination — output first, then trace (W17 enables FAIL_TRACE)
        if not is_equivalent:
            status = "FAIL_OUTPUT"
        elif translated_exc is not None and not _matches_expected(scenario, translated_exc):
            status = "FAIL_OUTPUT"
        elif not trace_diff.is_equivalent:
            status = "FAIL_TRACE"
        else:
            status = "PASS"

        return FixtureOracleResult(
            fixture_id=scenario.fixture_id,
            java_baseline_output=_serializable(baseline_out, baseline_exc),
            python_proposal_output=_serializable(translated_out, translated_exc),
            output_diff=output_diff,
            trace_diff=trace_diff,
            status=status,
            error=str(translated_exc) if translated_exc is not None and status == "FAIL_OUTPUT" else None,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _summarize(self, results: dict[str, FixtureOracleResult]) -> str:
        counts: dict[str, int] = {}
        for r in results.values():
            counts[r.status] = counts.get(r.status, 0) + 1
        parts = [f"{k}={v}" for k, v in sorted(counts.items())]
        return f"{len(results)} fixture(s): " + ", ".join(parts)


def _event_to_dict(event: TraceEvent | None) -> dict[str, Any] | None:
    """Convert TraceEvent to serializable dict for TraceDiff.expected_event/actual_event."""
    if event is None:
        return None
    return {
        "anchor_id": event.anchor_id,
        "kind":      event.kind,
        "vars":      {k: _stringify(v) for k, v in event.vars},
    }


def _stringify(v: Any) -> Any:
    """Best-effort serialization — Decimal → str, others kept."""
    if hasattr(v, "__class__") and v.__class__.__name__ == "Decimal":
        return str(v)
    return v


def _safe_call(fn: Callable[..., Any], inputs: dict[str, Any]) -> tuple[Any, Exception | None]:
    try:
        return fn(**inputs), None
    except Exception as e:
        return None, e


def _compare_outputs(
    translated_out: Any,
    translated_exc: Exception | None,
    baseline_out: Any,
    baseline_exc: Exception | None,
    scenario: Scenario,
) -> tuple[bool, str]:
    """Compare translated vs baseline. Returns (is_equivalent, summary)."""
    # Both raised exception
    if translated_exc is not None and baseline_exc is not None:
        if type(translated_exc) is type(baseline_exc):
            return True, f"both raised {type(translated_exc).__name__}"
        return False, (
            f"exception mismatch: translated={type(translated_exc).__name__}, "
            f"baseline={type(baseline_exc).__name__}"
        )
    # One raised, the other returned
    if translated_exc is not None or baseline_exc is not None:
        return False, (
            f"raise mismatch: translated_exc={type(translated_exc).__name__ if translated_exc else None}, "
            f"baseline_exc={type(baseline_exc).__name__ if baseline_exc else None}"
        )
    # Both returned — compare values
    if translated_out == baseline_out:
        return True, f"both returned {translated_out!r}"
    return False, f"value mismatch: translated={translated_out!r}, baseline={baseline_out!r}"


def _matches_expected(scenario: Scenario, exc: Exception) -> bool:
    if scenario.expected_exception is None:
        return False
    return isinstance(exc, scenario.expected_exception)


def _serializable(value: Any, exc: Exception | None) -> Any:
    """Pydantic frozen model fields accept Any but we keep it JSON-friendly."""
    if exc is not None:
        return {"_exception": type(exc).__name__, "message": str(exc)}
    if hasattr(value, "__class__") and value.__class__.__name__ in {"Decimal"}:
        return str(value)
    return value


def _missing_fixture_result(fid: str) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fid,
        java_baseline_output=None,
        python_proposal_output=None,
        output_diff=OutputDiff(
            is_equivalent=False,
            summary=f"fixture {fid!r} not found in engine fixture map",
        ),
        trace_diff=TraceDiff(is_equivalent=False, summary="fixture missing"),
        status="ERROR",
        error=f"fixture {fid!r} missing",
    )


__all__ = ["Scenario", "ScenarioVerificationEngine"]
