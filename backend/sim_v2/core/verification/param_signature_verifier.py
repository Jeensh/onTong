"""W52 — Action ↔ Method parameter-signature agreement verification.

W47 verified that an action's `code_method_fqn` translates cleanly. W52 goes
deeper: do the action's *declared* parameters (Section 2's `action.params_json`
with `object_ref_term`-bound types) agree with the Java method's actual
parameter list (`code_methods.params_json`)?

Per-action outcomes:
    VERIFIED          — same arity, same param names, same order
    ARITY_MISMATCH    — action declares N params, method has M
    NAME_MISMATCH     — same count but parameter names diverge
    METHOD_NOT_FOUND  — action.code_method_fqn doesn't resolve in code_methods
    NO_ACTION_PARAMS  — action.params_json is empty or missing
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
)


ParamStatus = Literal[
    "VERIFIED",
    "ARITY_MISMATCH",
    "NAME_MISMATCH",
    "METHOD_NOT_FOUND",
    "NO_ACTION_PARAMS",
    "NO_RECOMMENDATION",   # action lacks parsed code_method_fqn
]


class ParamVerification(BaseModel):
    """Per-action signature-agreement outcome."""
    model_config = ConfigDict(frozen=True)

    action_fqn:        str
    code_method_fqn:   str | None
    status:            ParamStatus
    action_params:     tuple[str, ...] = ()
    method_params:     tuple[str, ...] = ()
    details:           str = ""


def _action_param_names(action: ActionView, session: Session) -> tuple[str, ...]:
    """Pull declared param names for `action`. Returns () when unparseable or
    missing — caller maps to NO_ACTION_PARAMS."""
    row = session.execute(
        text("SELECT params_json FROM actions WHERE fqn = :fqn AND repo_id = :rid"),
        {"fqn": action.fqn, "rid": action.repo_id},
    ).fetchone()
    if row is None or not row[0]:
        return ()
    try:
        parsed = json.loads(row[0])
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    names: list[str] = []
    for p in parsed:
        if isinstance(p, dict) and isinstance(p.get("name"), str):
            names.append(p["name"])
    return tuple(names)


def _method_param_names(
    session: Session, method_fqn: str, repo_id: str,
) -> tuple[str, ...] | None:
    """Look up `code_methods.params_json` for `method_fqn` and return parameter
    names. Returns None when the method isn't found at all; () when present but
    parameter list is empty."""
    row = session.execute(
        text(
            "SELECT params_json FROM code_methods "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": method_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return None
    if not row[0]:
        return ()
    try:
        parsed = json.loads(row[0])
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    names: list[str] = []
    for p in parsed:
        if isinstance(p, dict) and isinstance(p.get("name"), str):
            names.append(p["name"])
    return tuple(names)


def verify_action_param_signature(
    session: Session, action: ActionView,
) -> ParamVerification:
    """Compare action's declared params to its referenced method's actual params.

    Order matters — `(order, slab)` and `(slab, order)` count as NAME_MISMATCH.
    """
    if not action.code_method_fqn:
        return ParamVerification(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_RECOMMENDATION",
        )

    action_params = _action_param_names(action, session)
    if not action_params:
        return ParamVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="NO_ACTION_PARAMS",
        )

    method_params = _method_param_names(
        session, action.code_method_fqn, action.repo_id,
    )
    if method_params is None:
        return ParamVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="METHOD_NOT_FOUND",
            action_params=action_params,
        )

    if len(action_params) != len(method_params):
        return ParamVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="ARITY_MISMATCH",
            action_params=action_params,
            method_params=method_params,
            details=(
                f"action declares {len(action_params)} params, "
                f"method has {len(method_params)}"
            ),
        )

    if action_params != method_params:
        return ParamVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="NAME_MISMATCH",
            action_params=action_params,
            method_params=method_params,
            details=(
                f"names differ: action={list(action_params)}, "
                f"method={list(method_params)}"
            ),
        )

    return ParamVerification(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status="VERIFIED",
        action_params=action_params,
        method_params=method_params,
    )


def verify_action_param_signatures(
    session: Session, actions: list[ActionView],
) -> list[ParamVerification]:
    """Bulk variant — order-preserving."""
    return [verify_action_param_signature(session, a) for a in actions]


__all__ = [
    "ParamStatus",
    "ParamVerification",
    "verify_action_param_signature",
    "verify_action_param_signatures",
]
