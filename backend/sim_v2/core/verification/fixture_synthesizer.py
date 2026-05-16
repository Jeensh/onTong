"""W71 — Production fixture synthesizer.

For behavioral verification (W59 BehaviorTwinRunner) to be useful on production,
we need a `BehaviorFixture` per (action, input-case) pair. Hand-authoring these
for 38 production actions is infeasible. This module synthesizes them
automatically from the action's declared `params_json` shape.

Strategies per primitive type:
    string   — ("", "x", "long_text", "0", "-1", "특수문자!@#")
    int      — (0, 1, -1, MAX_INT, MIN_INT)
    long     — (0, 1, -1, MAX_LONG)
    float    — (0.0, 1.0, -1.0, 0.5, MAX_FLOAT)
    double   — (0.0, 1.0, -1.0, 1e100)
    decimal  — (Decimal("0"), Decimal("1"), Decimal("-1"), Decimal("0.5"))
    boolean  — (True, False)

For object_ref params we emit `None` — actual entity instantiation needs a
factory that knows how to populate JPA fields. That belongs to a future
sprint (W74+).

The synthesizer reports `synthesizable_count` (params we can drive) and
`skipped_count` (object_refs we can only null) so the user can see coverage.

Public API:
    - FixtureSynthesisReport      — frozen Pydantic, per-action summary
    - synthesize_fixtures_for_action(session, action, function_name, python_source)
    - synthesize_fixtures_for_repo(session, repo_id, translations)
"""
from __future__ import annotations

import itertools
import json
import sys
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
)
from backend.sim_v2.core.verification.behavior_twin_runner import (
    BehaviorFixture,
)


PRIMITIVE_TYPES: frozenset[str] = frozenset({
    "string", "int", "long", "float", "double", "decimal", "boolean",
})


# ─────────────────────────────────────────────────────────────────────────────
# Per-primitive value generators
# ─────────────────────────────────────────────────────────────────────────────


_VALUE_SEEDS: dict[str, tuple[Any, ...]] = {
    "string":  ("", "x", "y", "0", "-1", "테스트"),
    "int":     (0, 1, -1, sys.maxsize, -sys.maxsize - 1),
    "long":    (0, 1, -1, 2**62, -(2**62)),
    "float":   (0.0, 1.0, -1.0, 0.5, 1e30),
    "double":  (0.0, 1.0, -1.0, 1e100),
    "decimal": (Decimal("0"), Decimal("1"), Decimal("-1"), Decimal("0.5")),
    "boolean": (True, False),
}


def _values_for_type(type_name: str) -> tuple[Any, ...]:
    """Return boundary + typical values for a primitive type, () for non-primitives."""
    return _VALUE_SEEDS.get(type_name, ())


# ─────────────────────────────────────────────────────────────────────────────
# Action.params_json → fixture combinations
# ─────────────────────────────────────────────────────────────────────────────


class FixtureSynthesisReport(BaseModel):
    """Per-action synthesis outcome."""
    model_config = ConfigDict(frozen=True)

    action_fqn:           str
    method_fqn:           str | None
    fixtures:             tuple[BehaviorFixture, ...] = ()
    synthesizable_params: int = 0   # primitive params we can drive
    skipped_params:       int = 0   # object_ref params we can only null
    reason:               str = ""  # if no fixtures synthesized


def _load_action_params(
    session: Session, action_fqn: str, repo_id: str,
) -> list[dict[str, Any]]:
    row = session.execute(
        text(
            "SELECT params_json FROM actions "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": action_fqn, "rid": repo_id},
    ).fetchone()
    if row is None or not row[0]:
        return []
    try:
        parsed = json.loads(row[0])
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _arg_combinations(
    params: list[dict[str, Any]],
    *,
    max_combinations: int = 12,
) -> list[tuple[Any, ...]]:
    """Build the Cartesian product of per-param value sets, capped at max."""
    if not params:
        # Zero-arg method — single empty fixture.
        return [()]

    per_param_values: list[tuple[Any, ...]] = []
    for p in params:
        t = p.get("type", "") if isinstance(p, dict) else ""
        if t in PRIMITIVE_TYPES:
            per_param_values.append(_values_for_type(t))
        else:
            # object_ref / unknown — emit single None placeholder
            per_param_values.append((None,))

    # Cap total combinations: take first `max_combinations` boundary-rich tuples.
    combos = list(itertools.islice(
        itertools.product(*per_param_values), max_combinations,
    ))
    return combos


def synthesize_fixtures_for_action(
    session: Session,
    action: ActionView,
    *,
    function_name: str,
    python_source: str,
    self_value: Any = None,
    max_combinations: int = 12,
) -> FixtureSynthesisReport:
    """Generate fixtures for one action.

    The caller supplies the translated `python_source` (from
    `JavaToPythonTranslator`) and the `function_name` it defines. The
    synthesizer wires self as the first positional arg (since Java instance
    methods become Python methods with `self`).
    """
    params = _load_action_params(session, action.fqn, action.repo_id)

    synthesizable = sum(
        1 for p in params
        if isinstance(p, dict) and p.get("type", "") in PRIMITIVE_TYPES
    )
    skipped = len(params) - synthesizable

    combos = _arg_combinations(params, max_combinations=max_combinations)
    fixtures: list[BehaviorFixture] = []
    for i, combo in enumerate(combos):
        fixtures.append(BehaviorFixture(
            fixture_id=f"{action.fqn}#{i}",
            python_source=python_source,
            function_name=function_name,
            input_args=(self_value,) + tuple(combo),
            input_kwargs={},
            # No Java baseline available yet — caller compares twin runs
            # against each other (W72 invariants) or supplies a real oracle.
            expected_output=None,
        ))

    reason = ""
    if not fixtures:
        reason = "no fixtures produced (unexpected — params malformed?)"
    elif synthesizable == 0 and skipped > 0:
        reason = "all params are object_ref; fixtures use null placeholders only"

    return FixtureSynthesisReport(
        action_fqn=action.fqn,
        method_fqn=action.code_method_fqn,
        fixtures=tuple(fixtures),
        synthesizable_params=synthesizable,
        skipped_params=skipped,
        reason=reason,
    )


__all__ = [
    "PRIMITIVE_TYPES",
    "FixtureSynthesisReport",
    "synthesize_fixtures_for_action",
]
