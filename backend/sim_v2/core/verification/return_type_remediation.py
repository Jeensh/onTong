"""W58 — Return-type drift remediation recommender.

Sister to W55 (param-signature remediation) on the return-type axis. W56/W57
*detect* drift between action output declarations and method return types;
W58 turns each finding into a *concrete fix step* Section 2 can apply.

Same "code is ground truth" principle: when an action declares one thing and
the method actually returns another, we recommend modifying the action.

Strategies (one step per verification, picked by priority):

    IMPLICIT_OUTPUT
        → DECLARE_OUTPUT — action gained no output_json; method returns X.
          Recommend adding `output_json` to match.

    PRIMITIVE_MISMATCH
        → If `method_return` is `List<...>` (or other collection):
            WRAP_AS_LIST — lift action.output to a list-typed object_ref.
        → Else if `method_return` strips to a known *primitive* alias
            (BigDecimal, Integer, Long, …):
            CHANGE_PRIMITIVE_TYPE — adjust the primitive declaration.
        → Else if the term-class index has a term matching the class:
            LIFT_TO_OBJECT_REF — replace primitive output with object_ref.
        → Else:
            PROPOSE_NEW_TERM — no existing term covers this class.

    OBJECT_REF_MISMATCH
        → If `method_return` is `List<X>` and the existing term resolves to X:
            WRAP_AS_LIST — current object_ref is correct as element type,
            but should be list-wrapped.
        → Else if the index has a term for the method's class:
            LIFT_TO_OBJECT_REF — swap the term reference.
        → Else:
            PROPOSE_NEW_TERM.

    VOID_MISMATCH, OBJECT_REF_UNRESOLVED, METHOD_NOT_FOUND, NO_RECOMMENDATION
        → No remediation emitted. These need either a method-side change
          (out of Section 2's scope) or upstream verification gates to close.

Public API:
    - ReturnTypeRemediationKind     — Literal enum
    - ReturnTypeRemediationStep     — frozen Pydantic
    - ReturnTypeRemediationReport   — bundle
    - TermClassIndex                — class simple-name → tuple[term_fqn, ...]
    - generate_return_type_remediation(verifications, term_index=None)
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.sim_v2.core.verification.return_type_verifier import (
    ReturnTypeVerification,
)
from backend.sim_v2.core.verification.term_type_resolver import (
    resolve_term_to_java_type,
    simple_name_of,
)


ReturnTypeRemediationKind = Literal[
    "DECLARE_OUTPUT",        # IMPLICIT_OUTPUT — add an output_json
    "CHANGE_PRIMITIVE_TYPE", # primitive→primitive realignment
    "WRAP_AS_LIST",          # action declares scalar; method returns List<X>
    "LIFT_TO_OBJECT_REF",    # primitive output → existing object_ref term
    "PROPOSE_NEW_TERM",      # method returns a class that no existing term covers
]


class ReturnTypeRemediationStep(BaseModel):
    """One concrete return-type fix Section 2 can apply."""
    model_config = ConfigDict(frozen=True)

    action_fqn:       str
    code_method_fqn:  str
    kind:             ReturnTypeRemediationKind
    current_output:   str | None = None     # raw `action_output` from verifier
    expected_output:  str = ""              # recommended new declaration
    method_return:    str | None = None
    target_term_fqn:  str | None = None     # for LIFT_TO_OBJECT_REF / WRAP_AS_LIST
    proposed_class:   str | None = None     # for PROPOSE_NEW_TERM
    recommendation:   str
    rationale:        str


class ReturnTypeRemediationReport(BaseModel):
    """All return-type fix steps for one repo, plus a one-line summary."""
    model_config = ConfigDict(frozen=True)

    steps:   list[ReturnTypeRemediationStep] = Field(default_factory=list)
    summary: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Class → term index
# ─────────────────────────────────────────────────────────────────────────────


class TermClassIndex(BaseModel):
    """Reverse lookup: Java class simple name → list of term FQNs.

    Built from `business_terms` for a single repo. The same class can map to
    multiple terms (different domains, granularities), so the value is a tuple.
    """
    model_config = ConfigDict(frozen=True)

    class_to_terms: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    def terms_for_class(self, class_simple_name: str) -> tuple[str, ...]:
        return self.class_to_terms.get(class_simple_name, ())

    def has_term_for_class(self, class_simple_name: str) -> bool:
        return class_simple_name in self.class_to_terms

    @classmethod
    def build(cls, session: Session, repo_id: str) -> "TermClassIndex":
        rows = session.execute(
            text("SELECT fqn FROM business_terms WHERE repo_id = :rid"),
            {"rid": repo_id},
        ).fetchall()
        index: dict[str, list[str]] = {}
        for (term_fqn,) in rows:
            resolution = resolve_term_to_java_type(session, term_fqn, repo_id)
            for candidate in resolution.candidates:
                simple = simple_name_of(candidate)
                if not simple:
                    continue
                index.setdefault(simple, []).append(term_fqn)
        return cls(class_to_terms={k: tuple(v) for k, v in index.items()})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


# Common collection wrappers Java return types use. Element type extraction is
# best-effort; only used for human-readable rationale strings.
_LIST_TYPE_RE = re.compile(r"^(List|ArrayList|LinkedList|Collection|Set|HashSet)\s*<")
_OPTIONAL_RE  = re.compile(r"^Optional\s*<")


def _is_list_return(method_return: str) -> bool:
    return bool(_LIST_TYPE_RE.match(method_return.strip()))


def _element_type_of(method_return: str) -> str:
    """`List<SDOrderEntity>` → `SDOrderEntity`. Returns input unchanged if no
    generics can be parsed."""
    m = re.match(r"^[A-Za-z_]\w*\s*<\s*(.+?)\s*>$", method_return.strip())
    return m.group(1) if m else method_return.strip()


# Inverse of W56's _PRIMITIVE_COMPATIBILITY for the cases where the recommendation
# is to *change the action primitive*, not lift to object_ref.
_JAVA_TO_ACTION_PRIMITIVE: dict[str, str] = {
    "BigDecimal":            "decimal",
    "java.math.BigDecimal":  "decimal",
    "Integer":               "int",
    "java.lang.Integer":     "int",
    "Long":                  "long",
    "java.lang.Long":        "long",
    "Boolean":               "boolean",
    "java.lang.Boolean":     "boolean",
    "Double":                "double",
    "java.lang.Double":      "double",
    "Float":                 "float",
    "java.lang.Float":       "float",
    "String":                "string",
    "java.lang.String":      "string",
}


def _strip_generics(s: str) -> str:
    return re.sub(r"<.*>", "", s).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Step constructors
# ─────────────────────────────────────────────────────────────────────────────


def _step_declare_output(v: ReturnTypeVerification) -> ReturnTypeRemediationStep:
    return ReturnTypeRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="DECLARE_OUTPUT",
        current_output=None,
        expected_output=f"declare output matching method return {v.method_return!r}",
        method_return=v.method_return,
        recommendation=(
            f"Add output_json to action — method returns {v.method_return!r} "
            f"but action declares no output."
        ),
        rationale=(
            "Method has a non-void return type; action authoring is missing "
            "the output declaration."
        ),
    )


def _step_change_primitive(
    v: ReturnTypeVerification, new_primitive: str,
) -> ReturnTypeRemediationStep:
    return ReturnTypeRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="CHANGE_PRIMITIVE_TYPE",
        current_output=v.action_output,
        expected_output=f'{{"type":"{new_primitive}"}}',
        method_return=v.method_return,
        recommendation=(
            f"Change action.output.type {v.action_output!r} → {new_primitive!r}"
        ),
        rationale=(
            f"Method returns {v.method_return!r} which maps to "
            f"action primitive {new_primitive!r}."
        ),
    )


def _step_wrap_as_list(
    v: ReturnTypeVerification, element_term_fqn: str | None,
    element_class: str,
) -> ReturnTypeRemediationStep:
    target = (
        element_term_fqn if element_term_fqn
        else f"(no existing term — propose one for {element_class!r})"
    )
    return ReturnTypeRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="WRAP_AS_LIST",
        current_output=v.action_output,
        expected_output=f'{{"type":"object_ref","object_ref_term":"{target}","cardinality":"many"}}',
        method_return=v.method_return,
        target_term_fqn=element_term_fqn,
        proposed_class=None if element_term_fqn else element_class,
        recommendation=(
            f"Wrap action output as list of {element_class!r}. "
            f"Method returns {v.method_return!r}."
        ),
        rationale=(
            f"Method returns a collection; action declares a scalar. "
            f"Lift action.output to list-typed object_ref."
        ),
    )


def _step_lift_to_object_ref(
    v: ReturnTypeVerification, term_fqn: str, class_name: str,
) -> ReturnTypeRemediationStep:
    return ReturnTypeRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="LIFT_TO_OBJECT_REF",
        current_output=v.action_output,
        expected_output=f'{{"type":"object_ref","object_ref_term":"{term_fqn}"}}',
        method_return=v.method_return,
        target_term_fqn=term_fqn,
        recommendation=(
            f"Lift action.output from primitive {v.action_output!r} to "
            f"object_ref pointing to {term_fqn!r}."
        ),
        rationale=(
            f"Method returns {class_name!r}; an existing term resolves to "
            f"that class. Replace the primitive declaration with an "
            f"object_ref reference."
        ),
    )


def _step_propose_new_term(
    v: ReturnTypeVerification, class_name: str,
) -> ReturnTypeRemediationStep:
    return ReturnTypeRemediationStep(
        action_fqn=v.action_fqn,
        code_method_fqn=v.code_method_fqn or "",
        kind="PROPOSE_NEW_TERM",
        current_output=v.action_output,
        expected_output=f"(new term for class {class_name!r})",
        method_return=v.method_return,
        proposed_class=class_name,
        recommendation=(
            f"Propose a new business_term for {class_name!r}, then re-author "
            f"action.output as object_ref pointing to it."
        ),
        rationale=(
            f"Method returns {class_name!r}, but no existing term maps to it. "
            f"A new term needs to be authored before this action's output can "
            f"be lifted."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main generator
# ─────────────────────────────────────────────────────────────────────────────


def _decide_step(
    v: ReturnTypeVerification,
    term_index: TermClassIndex | None,
) -> ReturnTypeRemediationStep | None:
    if v.status == "IMPLICIT_OUTPUT":
        return _step_declare_output(v)

    if v.status == "PRIMITIVE_MISMATCH":
        method_return = (v.method_return or "").strip()

        if _is_list_return(method_return):
            element_class = simple_name_of(_element_type_of(method_return))
            terms = (
                term_index.terms_for_class(element_class)
                if term_index else ()
            )
            return _step_wrap_as_list(
                v, terms[0] if terms else None, element_class,
            )

        stripped = _strip_generics(method_return)
        new_primitive = _JAVA_TO_ACTION_PRIMITIVE.get(stripped)
        if new_primitive and new_primitive != v.action_output:
            return _step_change_primitive(v, new_primitive)

        class_simple = simple_name_of(stripped)
        if term_index and term_index.has_term_for_class(class_simple):
            term_fqn = term_index.terms_for_class(class_simple)[0]
            return _step_lift_to_object_ref(v, term_fqn, class_simple)

        return _step_propose_new_term(v, class_simple)

    if v.status == "OBJECT_REF_MISMATCH":
        method_return = (v.method_return or "").strip()

        if _is_list_return(method_return):
            element_class = simple_name_of(_element_type_of(method_return))
            terms = (
                term_index.terms_for_class(element_class)
                if term_index else ()
            )
            return _step_wrap_as_list(
                v, terms[0] if terms else None, element_class,
            )

        class_simple = simple_name_of(_strip_generics(method_return))
        if term_index and term_index.has_term_for_class(class_simple):
            term_fqn = term_index.terms_for_class(class_simple)[0]
            return _step_lift_to_object_ref(v, term_fqn, class_simple)

        return _step_propose_new_term(v, class_simple)

    return None


def generate_return_type_remediation(
    verifications: list[ReturnTypeVerification],
    term_index: TermClassIndex | None = None,
) -> ReturnTypeRemediationReport:
    """Produce remediation steps for verifications in a fixable state.

    Order-preserving over input.
    """
    steps: list[ReturnTypeRemediationStep] = []
    for v in verifications:
        step = _decide_step(v, term_index)
        if step is not None:
            steps.append(step)
    return ReturnTypeRemediationReport(
        steps=steps,
        summary=_summarize(steps),
    )


def _summarize(steps: list[ReturnTypeRemediationStep]) -> str:
    if not steps:
        return "No return-type drift to remediate."
    parts: dict[str, int] = {}
    for s in steps:
        parts[s.kind] = parts.get(s.kind, 0) + 1
    return "Remediation: " + ", ".join(
        f"{n} {k}" for k, n in parts.items()
    )


__all__ = [
    "ReturnTypeRemediationKind",
    "ReturnTypeRemediationReport",
    "ReturnTypeRemediationStep",
    "TermClassIndex",
    "generate_return_type_remediation",
]
