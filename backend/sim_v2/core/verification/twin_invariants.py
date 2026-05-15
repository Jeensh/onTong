"""W72 — Twin invariant runner (baseline-free behavioral checks).

W59's `BehaviorTwinRunner` answers "does the twin output match the Java
baseline?" — but pre-authored baselines don't exist for every production
method. W72 fills that gap with three baseline-free invariants that any
well-translated twin should satisfy:

    1. DETERMINISM       — calling the twin twice with the same args
                           produces the same output.
    2. NO_UNEXPECTED_THROW — the twin completes (raises only declared exceptions
                             or none at all).
    3. RETURN_TYPE_OK    — the runtime type of the output matches the action's
                           declared return type. `None` is always allowed for
                           non-`void` returns (sentinel for "not applicable").

Status taxonomy:
    PASS                  — every invariant satisfied
    FAIL_NONDETERMINISTIC — two runs disagreed
    FAIL_UNEXPECTED_THROW — twin raised an exception (vs allowed list)
    FAIL_RETURN_TYPE      — output type didn't match declared return
    ERROR                 — twin source failed to compile / exec setup

The runner consumes a `BehaviorFixture` (so it composes with the W71
synthesizer output) but ignores `expected_output` — that's W59's job.

Public API:
    - InvariantCheckResult   — per-fixture report
    - TwinInvariantRunner    — invariant-only checker
    - run_invariants_for_fixtures(...)  — convenience aggregate
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
    _compile_and_extract_callable,
)


# ─────────────────────────────────────────────────────────────────────────────
# Declared-return → expected Python type mapping
# ─────────────────────────────────────────────────────────────────────────────


_PY_TYPE_FOR_DECLARED: dict[str, tuple[type, ...]] = {
    "string":  (str,),
    "int":     (int,),
    "long":    (int,),
    "float":   (float, int),                # Java float widens; allow int
    "double":  (float, int),
    "decimal": (Decimal, int, float),
    "boolean": (bool,),
    "void":    (type(None),),
    # object_ref / unknown → anything (skip the type check)
}


def _output_type_ok(declared_return: str, output: Any) -> tuple[bool, str]:
    """Return (ok, reason). Unknown / object_ref declared returns always pass."""
    if output is None:
        # Conservative: None is allowed for any non-void declared return —
        # production methods commonly short-circuit with null.
        return True, ""
    expected = _PY_TYPE_FOR_DECLARED.get(declared_return)
    if expected is None:
        # Unknown / object_ref / domain type → no shape check possible
        return True, ""
    # bool is a subclass of int in Python — guard against silently passing
    # bool where int was declared.
    if declared_return in ("int", "long") and isinstance(output, bool):
        return False, "got bool, declared int/long"
    if isinstance(output, expected):
        return True, ""
    return False, (
        f"got {type(output).__name__}, declared {declared_return} "
        f"(expected {[t.__name__ for t in expected]})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-fixture result
# ─────────────────────────────────────────────────────────────────────────────


class InvariantCheckResult(BaseModel):
    """Per-fixture invariant report."""
    model_config = ConfigDict(frozen=True)

    fixture_id:            str
    status:                str   # PASS / FAIL_* / ERROR
    deterministic:         bool = True
    threw:                 bool = False
    return_type_ok:        bool = True
    first_output_repr:     str = ""
    second_output_repr:    str = ""
    error:                 str = ""

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass(frozen=True)
class InvariantAggregate:
    fixture_id_to_result: dict[str, InvariantCheckResult]

    @property
    def total(self) -> int:
        return len(self.fixture_id_to_result)

    @property
    def passing(self) -> int:
        return sum(1 for r in self.fixture_id_to_result.values() if r.passed)

    @property
    def aggregate_status(self) -> str:
        if not self.fixture_id_to_result:
            return "INCONCLUSIVE"
        statuses = {r.status for r in self.fixture_id_to_result.values()}
        if statuses == {"PASS"}:
            return "PASS"
        if "FAIL_NONDETERMINISTIC" in statuses:
            return "FAIL_NONDETERMINISTIC"
        if "FAIL_UNEXPECTED_THROW" in statuses:
            return "FAIL_UNEXPECTED_THROW"
        if "FAIL_RETURN_TYPE" in statuses:
            return "FAIL_RETURN_TYPE"
        return "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────


def _equivalent_outputs(a: Any, b: Any) -> bool:
    """Determinism uses strict equality — twin should be deterministic up to
    value, not "within tolerance".
    """
    if type(a) is not type(b):
        return False
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_equivalent_outputs(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(_equivalent_outputs(a[k], b[k]) for k in a)
    try:
        return a == b
    except Exception:
        return False


class TwinInvariantRunner:
    """Baseline-free twin invariant checker.

    Each `check(fixture, ...)` call performs:
      • two consecutive runs with identical args (determinism)
      • exception trap (no_unexpected_throw)
      • runtime-type check against `declared_return` (return_type_ok)
    """

    def __init__(
        self,
        *,
        declared_return: str = "void",
        allowed_exceptions: tuple[str, ...] = (),
        stub_namespace: dict | None = None,
    ) -> None:
        self._declared_return = declared_return
        self._allowed = frozenset(allowed_exceptions)
        self._stub_namespace = dict(stub_namespace) if stub_namespace else None

    def check(self, fixture: BehaviorFixture) -> InvariantCheckResult:
        try:
            fn, _ = _compile_and_extract_callable(
                fixture.python_source, fixture.function_name,
                stub_namespace=self._stub_namespace,
            )
        except RuntimeError as e:
            return InvariantCheckResult(
                fixture_id=fixture.fixture_id,
                status="ERROR",
                error=str(e),
            )

        args = fixture.input_args
        kwargs = dict(fixture.input_kwargs)

        # Run 1
        try:
            out1 = fn(*args, **kwargs)
        except Exception as e:
            cls_name = type(e).__name__
            if cls_name in self._allowed:
                # Declared exception — still need determinism: second run must
                # raise the same class.
                try:
                    fn(*args, **kwargs)
                    # Inconsistent: first threw, second didn't
                    return InvariantCheckResult(
                        fixture_id=fixture.fixture_id,
                        status="FAIL_NONDETERMINISTIC",
                        deterministic=False,
                        threw=True,
                        error=f"first threw {cls_name}; second did not",
                    )
                except Exception as e2:
                    if type(e2).__name__ != cls_name:
                        return InvariantCheckResult(
                            fixture_id=fixture.fixture_id,
                            status="FAIL_NONDETERMINISTIC",
                            deterministic=False,
                            threw=True,
                            error=(
                                f"first threw {cls_name}; "
                                f"second threw {type(e2).__name__}"
                            ),
                        )
                return InvariantCheckResult(
                    fixture_id=fixture.fixture_id,
                    status="PASS",
                    threw=True,
                    first_output_repr=f"raised {cls_name}",
                    second_output_repr=f"raised {cls_name}",
                )
            return InvariantCheckResult(
                fixture_id=fixture.fixture_id,
                status="FAIL_UNEXPECTED_THROW",
                threw=True,
                error=f"{cls_name}: {e}",
            )

        # Run 2 (fresh callable to avoid carrying mutable state across runs)
        try:
            fn2, _ = _compile_and_extract_callable(
                fixture.python_source, fixture.function_name,
                stub_namespace=self._stub_namespace,
            )
            out2 = fn2(*args, **kwargs)
        except Exception as e:
            return InvariantCheckResult(
                fixture_id=fixture.fixture_id,
                status="FAIL_NONDETERMINISTIC",
                deterministic=False,
                threw=True,
                first_output_repr=repr(out1),
                error=f"second run threw: {type(e).__name__}: {e}",
            )

        if not _equivalent_outputs(out1, out2):
            return InvariantCheckResult(
                fixture_id=fixture.fixture_id,
                status="FAIL_NONDETERMINISTIC",
                deterministic=False,
                first_output_repr=repr(out1),
                second_output_repr=repr(out2),
                error="determinism violated",
            )

        ok, why = _output_type_ok(self._declared_return, out1)
        if not ok:
            return InvariantCheckResult(
                fixture_id=fixture.fixture_id,
                status="FAIL_RETURN_TYPE",
                return_type_ok=False,
                first_output_repr=repr(out1),
                second_output_repr=repr(out2),
                error=why,
            )

        return InvariantCheckResult(
            fixture_id=fixture.fixture_id,
            status="PASS",
            first_output_repr=repr(out1),
            second_output_repr=repr(out2),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience
# ─────────────────────────────────────────────────────────────────────────────


def run_invariants_for_fixtures(
    fixtures: tuple[BehaviorFixture, ...],
    *,
    declared_return: str = "void",
    allowed_exceptions: tuple[str, ...] = (),
) -> InvariantAggregate:
    runner = TwinInvariantRunner(
        declared_return=declared_return,
        allowed_exceptions=allowed_exceptions,
    )
    results: dict[str, InvariantCheckResult] = {}
    for f in fixtures:
        results[f.fixture_id] = runner.check(f)
    return InvariantAggregate(fixture_id_to_result=results)


__all__ = [
    "InvariantAggregate",
    "InvariantCheckResult",
    "TwinInvariantRunner",
    "run_invariants_for_fixtures",
]
