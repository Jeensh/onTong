"""W66 — Annotation parity verifier (8th verification dimension).

Layered verification stack:
    W47 — method exists                          (existence)
    W52 — param signature                         (param shape)
    W56 — primitive return                        (return shape)
    W57 — object_ref return                       (return shape resolved)
    W59 — behavior twin                           (execution)
    W60 — trace twin                              (execution path)
    W63 — exception agreement                     (exception flows)
    W66 — annotation parity                       ← here  (cross-cutting concerns)

Cross-cutting concerns — transaction boundaries, override relationships, REST
endpoint exposure — are encoded in Java as method-level annotations
(`@Transactional`, `@Override`, `@PostMapping`, …). They are not part of the
method signature but they materially affect the action contract.

This module surfaces drift when:
  - the Java method has `@Transactional` but the action never declares the
    transactional effect → UNDECLARED_ANNOTATION
  - the action declares `{"kind": "rest_endpoint", ...}` but the method has
    no `@PostMapping`/`@GetMapping`/etc → MISSING_ANNOTATION
  - both sides non-empty but disagree on which annotations are present

Only annotations with *contract* implications are checked. Pure
implementation-detail annotations (`@Autowired`, `@Query`, `@Component`) are
filtered out — they don't affect action semantics.

Public API:
    - AnnotationStatus         — Literal of 6 outcomes
    - AnnotationVerification   — frozen Pydantic
    - extract_contract_annotations(modifiers_json) → tuple[str, ...]
    - extract_declared_annotations(effects_json)   → tuple[str, ...]
    - verify_action_annotations(session, action)
    - verify_action_annotations_batch(session, actions)
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


AnnotationStatus = Literal[
    "VERIFIED",                # declared and present sets match (or both empty)
    "UNDECLARED_ANNOTATION",   # method has @X, action doesn't declare it
    "MISSING_ANNOTATION",      # action declares X, method has no matching @X
    "DIVERGENT_ANNOTATIONS",   # both non-empty, sets differ on both sides
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",
]


class AnnotationVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_fqn:        str
    code_method_fqn:   str | None
    status:            AnnotationStatus
    declared:          tuple[str, ...] = ()    # from action.effects_json
    present:           tuple[str, ...] = ()    # from method modifiers_json
    undeclared_only:   tuple[str, ...] = ()    # present - declared
    missing_only:      tuple[str, ...] = ()    # declared - present
    details:           str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Annotation → contract kind mapping
# ─────────────────────────────────────────────────────────────────────────────


# Java annotation simple name → contract kind we normalise it into.
# Only contract-bearing annotations are listed; everything else is filtered.
_CONTRACT_ANNOTATIONS: dict[str, str] = {
    "Transactional":     "transactional",
    "Override":          "overrides",
    "PostMapping":       "rest_endpoint",
    "GetMapping":        "rest_endpoint",
    "PutMapping":        "rest_endpoint",
    "DeleteMapping":     "rest_endpoint",
    "PatchMapping":      "rest_endpoint",
    "RequestMapping":    "rest_endpoint",
    "Async":             "asynchronous",
    "Scheduled":         "scheduled",
    "Cacheable":         "cacheable",
    "CacheEvict":        "cache_evicting",
    "EventListener":     "event_handler",
}


# Annotation simple-name parsing — `@Transactional(readOnly = true)` → `Transactional`.
_ANNOTATION_NAME_RE = re.compile(r"^@(\w+)")


# ─────────────────────────────────────────────────────────────────────────────
# Extractors
# ─────────────────────────────────────────────────────────────────────────────


def _annotation_simple_name(modifier: str) -> str | None:
    """`@Transactional(...)` → `Transactional`; non-annotation → None."""
    if not modifier or not isinstance(modifier, str):
        return None
    if not modifier.startswith("@"):
        return None
    match = _ANNOTATION_NAME_RE.match(modifier)
    return match.group(1) if match else None


def extract_contract_annotations(modifiers_json: str | None) -> tuple[str, ...]:
    """Parse modifiers_json and return the sorted, deduped set of *contract*
    annotations mapped to their normalized kind names.

    Filters out non-contract annotations (`@Autowired`, `@Query`, etc.).
    """
    if not modifiers_json:
        return ()
    try:
        mods = json.loads(modifiers_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(mods, list):
        return ()

    kinds: set[str] = set()
    for m in mods:
        name = _annotation_simple_name(m)
        if name is None:
            continue
        kind = _CONTRACT_ANNOTATIONS.get(name)
        if kind:
            kinds.add(kind)
    return tuple(sorted(kinds))


def extract_declared_annotations(effects_json: str | None) -> tuple[str, ...]:
    """Parse action.effects_json and return the contract-annotation kinds the
    action explicitly declares.

    Recognized entry shapes (all optional, lenient):
        {"kind": "transactional"}
        {"kind": "overrides", "parent_method_fqn": "..."}
        {"kind": "rest_endpoint", "http_method": "POST", "path": "..."}
        {"kind": "asynchronous"}
        ...

    Any entry whose `kind` is in the contract-kind universe (mapped values of
    `_CONTRACT_ANNOTATIONS`) is recorded. Other kinds (raises/writes_table/
    reads_table/etc) are ignored.
    """
    if not effects_json:
        return ()
    try:
        parsed = json.loads(effects_json)
    except json.JSONDecodeError:
        return ()
    if not isinstance(parsed, list):
        return ()

    contract_kinds = set(_CONTRACT_ANNOTATIONS.values())
    kinds: set[str] = set()
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind") or entry.get("type") or ""
        if isinstance(kind, str) and kind in contract_kinds:
            kinds.add(kind)
    return tuple(sorted(kinds))


# ─────────────────────────────────────────────────────────────────────────────
# Database access
# ─────────────────────────────────────────────────────────────────────────────


def _method_modifiers_json(
    session: Session, method_fqn: str, repo_id: str,
) -> str | None:
    row = session.execute(
        text(
            "SELECT modifiers_json FROM code_methods "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": method_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return None
    return row[0]


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


# ─────────────────────────────────────────────────────────────────────────────
# Verifier
# ─────────────────────────────────────────────────────────────────────────────


def _classify(
    declared: tuple[str, ...], present: tuple[str, ...],
) -> tuple[AnnotationStatus, str]:
    decl = set(declared)
    pres = set(present)
    if decl == pres:
        return "VERIFIED", "annotation sets agree"
    if not decl and pres:
        return ("UNDECLARED_ANNOTATION",
                f"method has {sorted(pres)} but action declares none")
    if decl and not pres:
        return ("MISSING_ANNOTATION",
                f"action declares {sorted(decl)} but method has none")
    return ("DIVERGENT_ANNOTATIONS",
            f"declared={sorted(decl)} vs present={sorted(pres)}")


def verify_action_annotations(
    session: Session, action: ActionView,
) -> AnnotationVerification:
    if not action.code_method_fqn:
        return AnnotationVerification(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_RECOMMENDATION",
        )

    modifiers_json = _method_modifiers_json(
        session, action.code_method_fqn, action.repo_id,
    )
    if modifiers_json is None:
        return AnnotationVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="METHOD_NOT_FOUND",
        )

    present  = extract_contract_annotations(modifiers_json)
    declared = extract_declared_annotations(
        _action_effects_json(session, action.fqn, action.repo_id),
    )
    status, details = _classify(declared, present)

    decl_set = set(declared)
    pres_set = set(present)
    return AnnotationVerification(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status=status,
        declared=declared,
        present=present,
        undeclared_only=tuple(sorted(pres_set - decl_set)),
        missing_only=tuple(sorted(decl_set - pres_set)),
        details=details,
    )


def verify_action_annotations_batch(
    session: Session, actions: list[ActionView],
) -> list[AnnotationVerification]:
    return [verify_action_annotations(session, a) for a in actions]


__all__ = [
    "AnnotationStatus",
    "AnnotationVerification",
    "extract_contract_annotations",
    "extract_declared_annotations",
    "verify_action_annotations",
    "verify_action_annotations_batch",
]
