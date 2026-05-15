"""W73 — Java oracle adapter.

Bridge between W71's synthesized fixtures (no baseline) and W59's
`BehaviorTwinRunner` (needs `expected_output` to render PASS/FAIL_OUTPUT).

Why an adapter at all? The Java baseline can come from three sources:

    a. Manual annotation     — the user authors `(args → expected)` tuples for
                               a known production method.
    b. Recorded run          — JSON dump from running the real Java code.
    c. Computed reference    — a Python re-implementation acting as oracle.

W73 unifies all three under a single `JavaBaselineMap` that synthesized
fixtures opt into. When a fixture's argument tuple matches a key in the map,
the adapter replaces the fixture's `expected_output=None` placeholder with
the recorded value. Fixtures with no baseline match are surfaced as
`unmatched` so the caller can see coverage at a glance.

This decouples *fixture generation* (W71) from *baseline acquisition* (W73),
letting both evolve independently — and supports incremental B-level
coverage: any single annotated (args, expected) pair makes one synthesized
fixture promotable from invariant-only (W72) to behavioral (W59).

Public API:
    - JavaBaselineEntry         — single (args, expected) annotation
    - JavaBaselineMap           — per-action lookup of baselines
    - attach_baselines(...)     — produce promoted BehaviorFixtures
    - BaselineAttachmentReport  — coverage of attachment pass
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
)


# ─────────────────────────────────────────────────────────────────────────────
# Baseline entries + map
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JavaBaselineEntry:
    """One annotated Java-side output for an action+args combination."""
    action_fqn:      str
    input_args:      tuple[Any, ...]
    expected_output: Any
    note:            str = ""        # optional provenance (e.g. "manual", "rec.2026-05-15")


def _key(args: tuple[Any, ...]) -> tuple[Any, ...]:
    """Normalize args into a hashable key.

    Lists become tuples, dicts become sorted-key tuples. The same args from
    W71 will always produce the same key, so map lookups are exact.
    """
    out: list[Any] = []
    for a in args:
        if isinstance(a, list):
            out.append(("__list__", _key(tuple(a))))
        elif isinstance(a, dict):
            out.append((
                "__dict__",
                tuple(sorted((k, _key((v,))[0]) for k, v in a.items())),
            ))
        elif isinstance(a, tuple):
            out.append(_key(a))
        else:
            out.append(a)
    return tuple(out)


class JavaBaselineMap:
    """Catalog: (action_fqn, args_key) → baseline entry."""

    def __init__(self, entries: Iterable[JavaBaselineEntry] = ()) -> None:
        self._by_key: dict[tuple[str, tuple[Any, ...]], JavaBaselineEntry] = {}
        for e in entries:
            self.add(e)

    def add(self, entry: JavaBaselineEntry) -> None:
        k = (entry.action_fqn, _key(entry.input_args))
        # Last writer wins. Re-recording the same args is allowed (idempotent
        # for fresh runs from a known good state).
        self._by_key[k] = entry

    def lookup(
        self, action_fqn: str, input_args: tuple[Any, ...],
    ) -> JavaBaselineEntry | None:
        return self._by_key.get((action_fqn, _key(input_args)))

    def __len__(self) -> int:
        return len(self._by_key)

    def keys_for(self, action_fqn: str) -> tuple[tuple[Any, ...], ...]:
        return tuple(
            args for (fqn, args) in self._by_key.keys() if fqn == action_fqn
        )


# ─────────────────────────────────────────────────────────────────────────────
# Attachment
# ─────────────────────────────────────────────────────────────────────────────


class BaselineAttachmentReport(BaseModel):
    """Coverage summary from a single attach_baselines call."""
    model_config = ConfigDict(frozen=True)

    action_fqn:        str
    total_fixtures:    int
    matched_fixtures:  tuple[BehaviorFixture, ...]
    unmatched_count:   int

    @property
    def match_rate(self) -> float:
        if self.total_fixtures == 0:
            return 0.0
        return len(self.matched_fixtures) / self.total_fixtures


def attach_baselines(
    action_fqn: str,
    fixtures: tuple[BehaviorFixture, ...],
    baseline_map: JavaBaselineMap,
) -> BaselineAttachmentReport:
    """Return new fixtures whose `expected_output` is the recorded Java output.

    Synthesized fixtures (from W71) carry `expected_output=None` — the runner
    treats those as "no baseline available". This function rewrites the
    `expected_output` field for every fixture whose `(action_fqn, input_args)`
    matches an entry in `baseline_map`.

    Fixtures with no matching entry are *dropped* from the result so the
    caller doesn't accidentally feed null-baseline fixtures to W59 (which
    would otherwise classify any output as `FAIL_OUTPUT`).
    """
    matched: list[BehaviorFixture] = []
    unmatched = 0
    for f in fixtures:
        entry = baseline_map.lookup(action_fqn, f.input_args)
        if entry is None:
            unmatched += 1
            continue
        matched.append(BehaviorFixture(
            fixture_id=f.fixture_id,
            python_source=f.python_source,
            function_name=f.function_name,
            input_args=f.input_args,
            input_kwargs=f.input_kwargs,
            expected_output=entry.expected_output,
            tolerance=f.tolerance,
            expected_trace_events=f.expected_trace_events,
            trace_numeric_tolerance=f.trace_numeric_tolerance,
        ))
    return BaselineAttachmentReport(
        action_fqn=action_fqn,
        total_fixtures=len(fixtures),
        matched_fixtures=tuple(matched),
        unmatched_count=unmatched,
    )


__all__ = [
    "BaselineAttachmentReport",
    "JavaBaselineEntry",
    "JavaBaselineMap",
    "attach_baselines",
]
