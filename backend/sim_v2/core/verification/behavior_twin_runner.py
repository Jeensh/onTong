"""W59 — Behavior-level twin verifier (FixtureRunner impl).

Fifth gate in the verification stack, and the strongest form: instead of
comparing static surfaces (existence / param / return type), we *actually run*
the Python twin against pre-authored input fixtures and compare the produced
output to a Java baseline output that the fixture carries.

This closes the loop on ADR-001's "Python = Java's execution-infra-free twin"
claim — for any method whose translation we believe is faithful, the twin's
output on any fixture must equal the Java baseline output (to a tolerance).

Public API:
    - BehaviorFixture            — pre-authored test case (input + baseline)
    - BehaviorFixtureStore       — fixture_id → BehaviorFixture lookup
    - BehaviorTwinRunner         — implements FixtureRunner Protocol
    - compare_outputs(...)       — diffing helper with tolerance

Status mapping (FixtureStatus from oracle.py):
    PASS         — twin output equivalent to baseline (within tolerance)
    FAIL_OUTPUT  — twin output diverges from baseline (contract violation)
    FAIL_TRACE   — output equivalent BUT trace would diverge (R4 — reserved for
                   future trace-instrumented runs; current impl returns PASS)
    ERROR        — twin failed to compile or threw at runtime

The runner is intentionally conservative: any exception in the twin yields
ERROR, never FAIL_OUTPUT. Section 2 should fix the translation, not the test.
"""
from __future__ import annotations

import math
import traceback
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OutputDiff,
    TraceDiff,
)
from backend.sim_v2.core.verification.trace import (
    TraceCollector,
    TraceEvent,
    diff_traces,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BehaviorFixture:
    """One pre-authored input → expected-output test case.

    `python_source` is the full Python translation of the Java method
    (typically obtained by running `JavaToPythonTranslator.translate(...)` on
    the method's tree-sitter node). It must define a single top-level callable
    whose name matches `function_name`.

    `expected_trace_events` (optional, W60): when present, the runner injects a
    fresh `TraceCollector` as `_trace` in twin globals and compares the captured
    trace against this expected sequence. Output mismatch dominates trace
    mismatch in classification — FAIL_OUTPUT takes precedence over FAIL_TRACE.
    Requires the twin to be translated with `with_trace=True`.
    """
    fixture_id:             str
    python_source:          str
    function_name:          str
    input_args:             tuple[Any, ...]
    input_kwargs:           Mapping[str, Any]
    expected_output:        Any
    tolerance:              float = 0.0
    # 0.0 → exact equality; positive → abs(a-b) <= tolerance for numeric leaves.
    expected_trace_events:  tuple[TraceEvent, ...] | None = None
    trace_numeric_tolerance: float = 0.0


class BehaviorFixtureStore:
    """Plug-in's fixture catalog — fixture_id → BehaviorFixture lookup."""

    def __init__(self, fixtures: list[BehaviorFixture] | None = None) -> None:
        self._by_id: dict[str, BehaviorFixture] = {}
        for f in fixtures or ():
            self.add(f)

    def add(self, fixture: BehaviorFixture) -> None:
        if fixture.fixture_id in self._by_id:
            raise ValueError(f"duplicate fixture_id: {fixture.fixture_id!r}")
        self._by_id[fixture.fixture_id] = fixture

    def get(self, fixture_id: str) -> BehaviorFixture | None:
        return self._by_id.get(fixture_id)

    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Output comparison
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_numeric(value: Any) -> Any:
    """Decimal ↔ float ↔ int 의 cross-type 비교를 통일된 numeric 으로."""
    if isinstance(value, Decimal):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def _values_equivalent(
    a: Any, b: Any, tolerance: float,
) -> tuple[bool, str]:
    """Recursive structural equality with numeric tolerance. Returns (ok, why)."""
    # Numeric short-circuit: int/float/Decimal all compare numerically regardless
    # of concrete type. `bool` is excluded — `isinstance(True, int)` is True in
    # Python but `True == 1` is misleading for behavior diffs.
    a_num = _coerce_numeric(a)
    b_num = _coerce_numeric(b)
    a_is_num = isinstance(a_num, (int, float)) and not isinstance(a_num, bool)
    b_is_num = isinstance(b_num, (int, float)) and not isinstance(b_num, bool)
    if a_is_num and b_is_num:
        if isinstance(a_num, float) and math.isnan(a_num) \
                and isinstance(b_num, float) and math.isnan(b_num):
            return True, ""
        diff = abs(a_num - b_num)
        if diff <= tolerance:
            return True, ""
        return False, f"numeric diff {diff} > tolerance {tolerance}"

    if type(a) is not type(b):
        return False, f"type mismatch: {type(a).__name__} vs {type(b).__name__}"

    if isinstance(a, str) or isinstance(a, bytes) or isinstance(a, bool):
        return (a == b, "" if a == b else f"{a!r} != {b!r}")

    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False, f"length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            ok, why = _values_equivalent(x, y, tolerance)
            if not ok:
                return False, f"[{i}]: {why}"
        return True, ""

    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False, f"key set diff: {set(a)} vs {set(b)}"
        for k in a:
            ok, why = _values_equivalent(a[k], b[k], tolerance)
            if not ok:
                return False, f"[{k!r}]: {why}"
        return True, ""

    return (a == b, "" if a == b else f"{a!r} != {b!r}")


def compare_outputs(
    baseline: Any, proposal: Any, tolerance: float = 0.0,
) -> OutputDiff:
    """Build an OutputDiff describing whether `proposal` matches `baseline`."""
    ok, why = _values_equivalent(baseline, proposal, tolerance)
    return OutputDiff(
        is_equivalent=ok,
        baseline_value=baseline,
        proposal_value=proposal,
        tolerance={"epsilon": tolerance} if tolerance else {},
        summary="match" if ok else f"diverge: {why}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox exec
# ─────────────────────────────────────────────────────────────────────────────


def _safe_globals(extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Minimal globals for twin exec — Decimal + math + standard builtins.

    `extra` (optional) lets the caller inject additional names into the globals
    — used by W74 stub injection so production methods can reference
    `DEFAULT_PRODUCTIVITY`, `ValidationResult`, `orderRepository`, etc.
    without NameError.
    """
    import math as _math
    from decimal import Decimal as _Decimal, getcontext as _getcontext
    g: dict[str, Any] = {
        "__builtins__": {
            # safe-ish subset of builtins
            "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
            "range": range, "round": round, "sorted": sorted, "reversed": reversed,
            "any": any, "all": all, "map": map, "filter": filter, "zip": zip,
            "enumerate": enumerate, "list": list, "tuple": tuple, "set": set,
            "dict": dict, "str": str, "int": int, "float": float, "bool": bool,
            "isinstance": isinstance, "issubclass": issubclass, "type": type,
            "True": True, "False": False, "None": None,
            "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "RuntimeError": RuntimeError,
            "ArithmeticError": ArithmeticError,
            "print": lambda *a, **kw: None,  # silence prints
        },
        "Decimal": _Decimal,
        "getcontext": _getcontext,
        "math": _math,
    }
    if extra:
        g.update(extra)
    return g


def _compile_and_extract_callable(
    python_source: str, function_name: str,
    *, stub_namespace: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Exec the source in a sandboxed namespace, return (callable, namespace).

    `stub_namespace` (W74) — extra names injected into the sandbox globals.
    Raises RuntimeError if compilation or extraction fails.
    """
    namespace: dict[str, Any] = {}
    try:
        code_obj = compile(python_source, f"<twin:{function_name}>", "exec")
    except SyntaxError as e:
        raise RuntimeError(f"twin source did not compile: {e}") from e
    try:
        exec(code_obj, _safe_globals(stub_namespace), namespace)
    except Exception as e:
        raise RuntimeError(
            f"twin module-level exec failed: {type(e).__name__}: {e}"
        ) from e
    fn = namespace.get(function_name)
    if not callable(fn):
        raise RuntimeError(
            f"twin source does not define a callable named {function_name!r}; "
            f"defined names: {sorted(namespace)}"
        )
    return fn, namespace


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────


class BehaviorTwinRunner:
    """FixtureRunner impl — runs a Python twin against fixtures.

    Implements the `FixtureRunner` Protocol from `oracle.py` so it can plug
    straight into `VerificationEngine.run_oracle(...)`.
    """

    def __init__(
        self,
        store: BehaviorFixtureStore,
        *,
        stub_namespace: Mapping[str, Any] | None = None,
    ) -> None:
        self._store = store
        self._stub_namespace = dict(stub_namespace) if stub_namespace else None

    def run_fixture(
        self,
        fixture_id: str,
        plugin: str,
        apply_diffs: dict[str, Any],
    ) -> FixtureOracleResult:
        fixture = self._store.get(fixture_id)
        if fixture is None:
            return FixtureOracleResult(
                fixture_id=fixture_id,
                java_baseline_output=None,
                python_proposal_output=None,
                output_diff=OutputDiff(is_equivalent=False, summary="fixture not found"),
                trace_diff=TraceDiff(is_equivalent=False),
                status="ERROR",
                error=f"unknown fixture_id: {fixture_id!r}",
            )

        try:
            fn, namespace = _compile_and_extract_callable(
                fixture.python_source, fixture.function_name,
                stub_namespace=self._stub_namespace,
            )
        except RuntimeError as e:
            return FixtureOracleResult(
                fixture_id=fixture_id,
                java_baseline_output=fixture.expected_output,
                python_proposal_output=None,
                output_diff=OutputDiff(is_equivalent=False, summary=str(e)),
                trace_diff=TraceDiff(is_equivalent=False),
                status="ERROR",
                error=str(e),
            )

        # W60: inject TraceCollector into both module-namespace and the
        # function's __globals__ so emitted `_trace.step(...)` resolves.
        collector: TraceCollector | None = None
        if fixture.expected_trace_events is not None:
            collector = TraceCollector()
            namespace["_trace"] = collector
            if hasattr(fn, "__globals__"):
                fn.__globals__["_trace"] = collector

        try:
            actual = fn(*fixture.input_args, **dict(fixture.input_kwargs))
        except Exception as e:
            tb = traceback.format_exc(limit=2)
            return FixtureOracleResult(
                fixture_id=fixture_id,
                java_baseline_output=fixture.expected_output,
                python_proposal_output=None,
                output_diff=OutputDiff(
                    is_equivalent=False,
                    summary=f"runtime error: {type(e).__name__}: {e}",
                ),
                trace_diff=TraceDiff(is_equivalent=False),
                status="ERROR",
                error=f"{type(e).__name__}: {e}\n{tb}",
            )

        output_diff = compare_outputs(
            fixture.expected_output, actual, tolerance=fixture.tolerance,
        )

        trace_diff_payload = TraceDiff(is_equivalent=True)
        trace_ok = True
        if collector is not None:
            actual_events = collector.events
            tdr = diff_traces(
                list(fixture.expected_trace_events or ()),
                actual_events,
                numeric_tolerance=fixture.trace_numeric_tolerance,
            )
            trace_ok = tdr.is_equivalent
            trace_diff_payload = TraceDiff(
                is_equivalent=tdr.is_equivalent,
                diverging_step_no=tdr.diverging_step_no,
                expected_event=(
                    _event_to_dict(tdr.expected_event)
                    if tdr.expected_event else None
                ),
                actual_event=(
                    _event_to_dict(tdr.actual_event)
                    if tdr.actual_event else None
                ),
                summary=tdr.summary,
            )

        # Classification: FAIL_OUTPUT dominates FAIL_TRACE (contract violation
        # is strictly worse than process drift).
        if not output_diff.is_equivalent:
            status = "FAIL_OUTPUT"
        elif not trace_ok:
            status = "FAIL_TRACE"
        else:
            status = "PASS"

        return FixtureOracleResult(
            fixture_id=fixture_id,
            java_baseline_output=fixture.expected_output,
            python_proposal_output=actual,
            output_diff=output_diff,
            trace_diff=trace_diff_payload,
            status=status,
            error=None,
        )


def _event_to_dict(event: TraceEvent) -> dict[str, Any]:
    return {
        "anchor_id": event.anchor_id,
        "kind":      event.kind,
        "vars":      dict(event.vars),
    }


__all__ = [
    "BehaviorFixture",
    "BehaviorFixtureStore",
    "BehaviorTwinRunner",
    "compare_outputs",
]
