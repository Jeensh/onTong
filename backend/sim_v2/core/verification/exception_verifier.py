"""W63 — Exception agreement verifier (7th verification dimension).

Layered verification stack so far:
    W47 — method exists                 (existence)
    W52 — param signature                (param shape)
    W56 — primitive return type          (return shape)
    W57 — object_ref return type         (return shape resolved)
    W59 — behavior twin                  (execution)
    W60 — trace twin                     (execution path)
    W63 — exception agreement            ← here

For each action with a code_method_fqn, compare:
  - what the action *declares* it can raise (encoded in `effects_json`
    entries of the form `{"kind":"raises", "exception":"…"}`)
  - what the Java method *actually* throws (scraped from `body_text` —
    `throw new SomethingException(...)` statements; the simple class
    name is recorded).

If the framework is healthy, those sets must match. In production they
rarely do — Section 2's authoring pipeline omits exception documentation
in most cases, so almost every throwing method surfaces UNDECLARED_THROWS
(a precise actionable signal for the next authoring iteration).

Public API:
    - ExceptionStatus              — Literal of 6 outcomes
    - ExceptionVerification        — frozen Pydantic per-action record
    - extract_thrown_exceptions(body_text)
    - extract_declared_exceptions(effects_json)
    - verify_action_exceptions(session, action)
    - verify_action_exceptions_batch(session, actions)
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
)


ExceptionStatus = Literal[
    "VERIFIED",              # action declares exactly what method throws (or both empty)
    "UNDECLARED_THROWS",     # method throws X, action does not declare it
    "MISSING_THROWS",        # action declares X, method does not throw it
    "DIVERGENT_THROWS",      # both non-empty AND sets differ on both sides
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",     # action has no parsed code_method_fqn
]


class ExceptionVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_fqn:        str
    code_method_fqn:   str | None
    status:            ExceptionStatus
    declared:          tuple[str, ...] = ()    # action's effects_json
    thrown:            tuple[str, ...] = ()    # method body's throws
    undeclared_only:   tuple[str, ...] = ()    # thrown - declared
    missing_only:      tuple[str, ...] = ()    # declared - thrown
    details:           str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Extractors
# ─────────────────────────────────────────────────────────────────────────────


# Matches `throw new <ExceptionTypeName>(…)` — captures the type name only.
# The type name may be a simple class name (`AlgorithmException`) or a dotted
# inner class (`Foo.BarException`). The captured group is normalized to the
# simple class name for set comparison.
_THROW_NEW_RE = re.compile(r"throw\s+new\s+([A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)*)\s*\(")


def _simple_name(qualified: str) -> str:
    """`com.x.Foo$Bar` / `Foo.Bar` / `Bar` → `Bar`."""
    if not qualified:
        return ""
    last_dot = qualified.rsplit(".", 1)[-1]
    last_dollar = last_dot.rsplit("$", 1)[-1]
    return last_dollar


def extract_thrown_exceptions(body_text: str | None) -> tuple[str, ...]:
    """Return the sorted set of exception simple-names a method throws.

    Scans `body_text` for `throw new XException(...)` patterns. Returns
    `()` if body is empty/None or no throws found. Duplicates are removed.
    """
    if not body_text:
        return ()
    seen: set[str] = set()
    for m in _THROW_NEW_RE.finditer(body_text):
        simple = _simple_name(m.group(1))
        if simple:
            seen.add(simple)
    return tuple(sorted(seen))


def extract_declared_exceptions(effects_json: str | None) -> tuple[str, ...]:
    """Return the sorted set of exception simple-names an action declares.

    Looks for effects entries of the form:
        {"kind": "raises", "exception": "AlgorithmException"}
        {"kind": "throws", "exception": "..."}
        {"type": "raises", "exception": "..."}      (lenient alt key)

    Returns `()` if effects_json is missing/empty/malformed or no raises
    entries are present.
    """
    if not effects_json:
        return ()
    try:
        parsed = json.loads(effects_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()
    seen: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind") or entry.get("type") or ""
        if kind not in {"raises", "throws", "raise"}:
            continue
        exc = entry.get("exception") or entry.get("error") or ""
        if isinstance(exc, str) and exc.strip():
            seen.add(_simple_name(exc.strip()))
    return tuple(sorted(seen))


# ─────────────────────────────────────────────────────────────────────────────
# Verifier
# ─────────────────────────────────────────────────────────────────────────────


def _method_row(
    session: Session, method_fqn: str, repo_id: str,
) -> tuple[str | None, str | None] | None:
    """Return (body_text, repo_id) of the matching code_methods row, or None."""
    row = session.execute(
        text(
            "SELECT body_text FROM code_methods "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": method_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return None
    return (row[0] or "", repo_id)


def _action_effects_json(
    session: Session, action_fqn: str, repo_id: str,
) -> str | None:
    row = session.execute(
        text(
            "SELECT effects_json FROM actions "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": action_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return None
    return row[0]


def _classify(
    declared: tuple[str, ...], thrown: tuple[str, ...],
) -> tuple[ExceptionStatus, str]:
    decl_set = set(declared)
    thr_set  = set(thrown)
    if decl_set == thr_set:
        return "VERIFIED", "exception sets agree"
    if not decl_set and thr_set:
        return ("UNDECLARED_THROWS",
                f"method throws {sorted(thr_set)} but action declares none")
    if decl_set and not thr_set:
        return ("MISSING_THROWS",
                f"action declares {sorted(decl_set)} but method throws none")
    return ("DIVERGENT_THROWS",
            f"declared={sorted(decl_set)} vs thrown={sorted(thr_set)}")


def verify_action_exceptions(
    session: Session, action: ActionView,
) -> ExceptionVerification:
    if not action.code_method_fqn:
        return ExceptionVerification(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_RECOMMENDATION",
        )
    row = _method_row(session, action.code_method_fqn, action.repo_id)
    if row is None:
        return ExceptionVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="METHOD_NOT_FOUND",
        )

    body, _rid = row
    thrown = extract_thrown_exceptions(body)
    declared = extract_declared_exceptions(
        _action_effects_json(session, action.fqn, action.repo_id),
    )
    status, details = _classify(declared, thrown)

    decl_set = set(declared)
    thr_set  = set(thrown)
    return ExceptionVerification(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status=status,
        declared=declared,
        thrown=thrown,
        undeclared_only=tuple(sorted(thr_set - decl_set)),
        missing_only=tuple(sorted(decl_set - thr_set)),
        details=details,
    )


def verify_action_exceptions_batch(
    session: Session, actions: list[ActionView],
) -> list[ExceptionVerification]:
    return [verify_action_exceptions(session, a) for a in actions]


__all__ = [
    "ExceptionStatus",
    "ExceptionVerification",
    "extract_thrown_exceptions",
    "extract_declared_exceptions",
    "verify_action_exceptions",
    "verify_action_exceptions_batch",
]
