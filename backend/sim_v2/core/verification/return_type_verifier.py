"""W56 / W57 — Action ↔ Method return-type agreement verification.

Third in the layered verification stack:
  W47 — method exists + translates clean
  W52 — param signature agreement
  W56 — return-type agreement   ← here
  W57 — closes the OBJECT_REF gap with a term→Java type resolver

For each action with `output_json`, compare the declared output to the actual
Java method's `return_type`. Both `void` ⇒ MATCH; primitive↔Java mapping
(string→String, int→int|Integer, decimal→BigDecimal, …) covers primitives.
`object_ref` outputs (term-typed) resolve the term to a Java class FQN via
`term_type_resolver` and compare candidate simple-names to `return_type`.

Outcomes:
    VERIFIED              — both void OR primitive compatible OR object_ref candidate match
    VOID_MISMATCH         — one side void, the other not
    IMPLICIT_OUTPUT       — action declares no output, method returns something
    PRIMITIVE_MISMATCH    — both non-void primitives but incompatible
    OBJECT_REF_MISMATCH   — term resolved but method returns a different class
    OBJECT_REF_UNRESOLVED — term has no description/alias → cannot decide
    METHOD_NOT_FOUND      — code_methods row missing
    NO_RECOMMENDATION     — action lacks parsed code_method_fqn
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
from backend.sim_v2.core.verification.term_type_resolver import (
    resolve_term_to_java_type,
    simple_name_of,
)


ReturnTypeStatus = Literal[
    "VERIFIED",
    "VOID_MISMATCH",          # action declares non-void output, method is void
    "IMPLICIT_OUTPUT",        # action declares no output, method returns something
    "PRIMITIVE_MISMATCH",     # both non-void primitives but incompatible
    "OBJECT_REF_MISMATCH",    # term resolved → expected class but method returns another
    "OBJECT_REF_UNRESOLVED",  # term has no resolvable description/aliases
    "METHOD_NOT_FOUND",
    "NO_RECOMMENDATION",      # action has no parsed code_method_fqn
]


class ReturnTypeVerification(BaseModel):
    model_config = ConfigDict(frozen=True)

    action_fqn:        str
    code_method_fqn:   str | None
    status:            ReturnTypeStatus
    action_output:     str | None = None   # e.g. 'string' / 'int' / 'object_ref:term.scm.x' / None for void
    method_return:     str | None = None   # raw code_methods.return_type value
    details:           str = ""


# Action primitive type → set of compatible Java return types (case-sensitive).
# `object_ref` is intentionally absent — handled by OBJECT_REF_SKIPPED.
_PRIMITIVE_COMPATIBILITY: dict[str, frozenset[str]] = {
    "string":  frozenset({"String", "java.lang.String"}),
    "int":     frozenset({"int", "Integer", "java.lang.Integer"}),
    "long":    frozenset({"long", "Long", "java.lang.Long",
                          "int", "Integer"}),   # long can absorb int
    "float":   frozenset({"float", "double", "Float", "Double",
                          "java.lang.Float", "java.lang.Double"}),
    "double":  frozenset({"double", "Double", "java.lang.Double",
                          "float", "Float"}),
    "boolean": frozenset({"boolean", "Boolean", "java.lang.Boolean"}),
    "decimal": frozenset({"BigDecimal", "java.math.BigDecimal"}),
}


def _parse_action_output(session: Session, action: ActionView) -> dict | None:
    """Read action.output_json and parse. Returns None for missing/null/empty."""
    row = session.execute(
        text(
            "SELECT output_json FROM actions WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": action.fqn, "rid": action.repo_id},
    ).fetchone()
    if row is None or not row[0]:
        return None
    raw = row[0].strip()
    if not raw or raw.lower() == "null":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _method_return_type(
    session: Session, method_fqn: str, repo_id: str,
) -> str | None:
    """Return code_methods.return_type, or None if the method isn't found."""
    row = session.execute(
        text(
            "SELECT return_type FROM code_methods "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": method_fqn, "rid": repo_id},
    ).fetchone()
    if row is None:
        return None
    return row[0] or ""


def _is_void(return_type: str) -> bool:
    return return_type.strip() in {"void", ""}


def _strip_generics(return_type: str) -> str:
    """`List<String>` → `List`, `Map<K,V>` → `Map`, `Foo` → `Foo`."""
    if not return_type:
        return ""
    return re.sub(r"<.*>", "", return_type).strip()


def verify_action_return_type(
    session: Session, action: ActionView,
) -> ReturnTypeVerification:
    if not action.code_method_fqn:
        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_RECOMMENDATION",
        )

    method_return = _method_return_type(
        session, action.code_method_fqn, action.repo_id,
    )
    if method_return is None:
        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="METHOD_NOT_FOUND",
        )

    method_is_void = _is_void(method_return)
    action_output = _parse_action_output(session, action)

    if action_output is None:
        # Action declares no output. Both-void ⇒ VERIFIED; otherwise the method
        # secretly returns something the action doesn't mention ⇒ IMPLICIT_OUTPUT.
        if method_is_void:
            return ReturnTypeVerification(
                action_fqn=action.fqn,
                code_method_fqn=action.code_method_fqn,
                status="VERIFIED",
                action_output=None,
                method_return=method_return,
            )
        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="IMPLICIT_OUTPUT",
            action_output=None,
            method_return=method_return,
            details=f"action declares no output, but method returns {method_return!r}",
        )

    output_type = action_output.get("type", "")

    if output_type == "object_ref":
        term_fqn = action_output.get("object_ref_term", "")
        action_output_str = f"object_ref:{term_fqn or '?'}"

        if method_is_void:
            return ReturnTypeVerification(
                action_fqn=action.fqn,
                code_method_fqn=action.code_method_fqn,
                status="VOID_MISMATCH",
                action_output=action_output_str,
                method_return=method_return,
                details=(
                    f"action declares object_ref {term_fqn!r} output, "
                    f"but method is void"
                ),
            )

        if not term_fqn:
            return ReturnTypeVerification(
                action_fqn=action.fqn,
                code_method_fqn=action.code_method_fqn,
                status="OBJECT_REF_UNRESOLVED",
                action_output=action_output_str,
                method_return=method_return,
                details="action.output_json.object_ref_term is empty",
            )

        resolution = resolve_term_to_java_type(session, term_fqn, action.repo_id)
        if not resolution.is_resolved:
            return ReturnTypeVerification(
                action_fqn=action.fqn,
                code_method_fqn=action.code_method_fqn,
                status="OBJECT_REF_UNRESOLVED",
                action_output=action_output_str,
                method_return=method_return,
                details=(
                    f"term {term_fqn!r} has no resolvable description/aliases"
                ),
            )

        method_return_simple = simple_name_of(_strip_generics(method_return))
        candidates_simple = {simple_name_of(c) for c in resolution.candidates}
        if method_return_simple in candidates_simple:
            return ReturnTypeVerification(
                action_fqn=action.fqn,
                code_method_fqn=action.code_method_fqn,
                status="VERIFIED",
                action_output=action_output_str,
                method_return=method_return,
                details=f"matched candidate {method_return_simple!r}",
            )

        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="OBJECT_REF_MISMATCH",
            action_output=action_output_str,
            method_return=method_return,
            details=(
                f"term {term_fqn!r} resolves to {resolution.candidates!r}, "
                f"method returns {method_return!r}"
            ),
        )

    if method_is_void:
        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="VOID_MISMATCH",
            action_output=output_type,
            method_return=method_return,
            details=f"action declares {output_type!r} output, but method is void",
        )

    compatible_types = _PRIMITIVE_COMPATIBILITY.get(output_type)
    if compatible_types and method_return.strip() in compatible_types:
        return ReturnTypeVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="VERIFIED",
            action_output=output_type,
            method_return=method_return,
        )

    return ReturnTypeVerification(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status="PRIMITIVE_MISMATCH",
        action_output=output_type,
        method_return=method_return,
        details=(
            f"action declares {output_type!r}, method returns {method_return!r}"
        ),
    )


def verify_action_return_types(
    session: Session, actions: list[ActionView],
) -> list[ReturnTypeVerification]:
    return [verify_action_return_type(session, a) for a in actions]


__all__ = [
    "ReturnTypeStatus",
    "ReturnTypeVerification",
    "verify_action_return_type",
    "verify_action_return_types",
]
