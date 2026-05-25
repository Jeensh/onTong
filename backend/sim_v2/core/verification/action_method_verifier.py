"""W47 — Action ↔ Code agreement verification.

Section 2's authoring pipeline records each auto-recommended action with a
description like `자동 추천 — <code_method_fqn>`. Section 4 verifies the
claim: does that method exist in `code_methods`, and does its body translate
cleanly through the Java→Python translator? Mismatches surface as actionable
findings the framework can flag for review.

Public API:
    - VerificationStatus           — enum of possible outcomes
    - ActionVerification           — frozen Pydantic record
    - verify_action(session, action) — single-action check
    - verify_actions(session, actions) — bulk; returns list aligned to input
"""
from __future__ import annotations

from typing import Literal

import tree_sitter_java as tsjava
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    ActionView,
)
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator


VerificationStatus = Literal[
    "VERIFIED",
    "NO_RECOMMENDATION",   # action has no parsed code_method_fqn
    "METHOD_NOT_FOUND",    # code_method_fqn doesn't resolve in code_methods
    "EMPTY",               # method exists but body_text empty/whitespace
    "PARSE_ERROR",         # body_text didn't parse as a Java method
    "SIGNATURE_LOCKED",    # translator hit an unsupported construct
]


class ActionVerification(BaseModel):
    """Per-action verification outcome.

    `notes` carries SIGNATURE_LOCKED reasons or other diagnostic context.
    Empty for the VERIFIED path.
    """
    model_config = ConfigDict(frozen=True)

    action_fqn:       str
    code_method_fqn:  str | None
    status:           VerificationStatus
    notes:            tuple[str, ...] = ()


_JAVA_LANGUAGE = Language(tsjava.language())


def _load_class_field_scope(
    session: Session, code_method_fqn: str, repo_id: str,
) -> dict[str, str]:
    """Fetch `{field_name: field_type}` for the class owning this method.

    Used to teach the translator that bare identifiers may be implicit-this
    field refs (Java) so it can emit `self.X` in Python. Returns empty dict
    when class is unknown or has no fields — safe no-op for the caller.
    """
    # Enclosing class FQN = method_fqn without the .method(...) suffix
    base = code_method_fqn.split("(", 1)[0]
    if "." not in base:
        return {}
    class_fqn = base.rsplit(".", 1)[0]
    rows = session.execute(
        text(
            "SELECT name, type FROM code_fields "
            "WHERE type_fqn = :cfqn"
        ),
        {"cfqn": class_fqn},
    ).fetchall()
    return {r[0]: (r[1] or "") for r in rows if r[0]}


def _parse_method_declaration(body_text: str):
    """Wrap a body in a synthetic class+method and extract the method_declaration.
    Returns None if no method_declaration is found.
    """
    full = "class _T { " + body_text + " }"
    parser = Parser(_JAVA_LANGUAGE)
    tree = parser.parse(full.encode())
    for cls in tree.root_node.children:
        if cls.type == "class_declaration":
            for ch in cls.children:
                if ch.type == "class_body":
                    for member in ch.named_children:
                        if member.type == "method_declaration":
                            return member
    return None


def verify_action(session: Session, action: ActionView) -> ActionVerification:
    """Translate the method backing `action` (via action.code_method_fqn) and
    classify the outcome. Caller is responsible for the session lifecycle.
    """
    if not action.code_method_fqn:
        return ActionVerification(
            action_fqn=action.fqn,
            code_method_fqn=None,
            status="NO_RECOMMENDATION",
        )

    row = session.execute(
        text(
            "SELECT body_text FROM code_methods "
            "WHERE fqn = :fqn AND repo_id = :rid"
        ),
        {"fqn": action.code_method_fqn, "rid": action.repo_id},
    ).fetchone()

    if row is None:
        return ActionVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="METHOD_NOT_FOUND",
        )

    body_text = row[0] or ""
    if not body_text.strip():
        return ActionVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="EMPTY",
        )

    method_node = _parse_method_declaration(body_text)
    if method_node is None:
        return ActionVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="PARSE_ERROR",
        )

    # Risk 1 fix — load class field scope so translator emits `self.X` for
    # Java implicit-this field refs (e.g. `traces` inside `traces()` resolves
    # to the function in Python, masking the field. `self.traces` is correct).
    class_field_scope = _load_class_field_scope(session, action.code_method_fqn, action.repo_id)
    result = JavaToPythonTranslator(class_field_scope=class_field_scope).translate(method_node, indent=0)
    if result.signature_locked:
        return ActionVerification(
            action_fqn=action.fqn,
            code_method_fqn=action.code_method_fqn,
            status="SIGNATURE_LOCKED",
            notes=tuple(result.notes),
        )

    return ActionVerification(
        action_fqn=action.fqn,
        code_method_fqn=action.code_method_fqn,
        status="VERIFIED",
    )


def verify_actions(
    session: Session, actions: list[ActionView],
) -> list[ActionVerification]:
    """Bulk variant. Order-preserving."""
    return [verify_action(session, a) for a in actions]


__all__ = [
    "ActionVerification",
    "VerificationStatus",
    "verify_action",
    "verify_actions",
]
