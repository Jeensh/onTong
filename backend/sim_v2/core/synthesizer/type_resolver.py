"""Type resolver — Java type info source for type-aware translator.

W8.1. Decouples translator from any specific ontology backend via Protocol.

Public API:
  - TypeResolver (Protocol) — resolve_method_return_type / resolve_field_type
  - NullTypeResolver — default no-op (W7 의 untyped behavior 와 동일)
  - BigDecimalAwareResolver — hardcoded BigDecimal-family knowledge, NO ontology dependency
"""
from __future__ import annotations

from typing import Protocol


class TypeResolver(Protocol):
    """Type info source. Translator calls during method invocation dispatch.

    Implementations may consult ontology, AST attributes, or hardcoded knowledge.
    Returning None signals "unknown" — caller falls back to syntactic heuristic.
    """

    def resolve_method_return_type(
        self,
        receiver_type_fqn: str | None,
        method_name: str,
    ) -> str | None:
        """`receiver_type_fqn.method_name()` 의 return type FQN.

        receiver_type_fqn is None when receiver type is unknown (static or untracked).
        """
        ...

    def resolve_field_type(
        self,
        owner_type_fqn: str | None,
        field_name: str,
    ) -> str | None:
        """`owner_type_fqn.field_name` 의 type FQN."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Default no-op
# ─────────────────────────────────────────────────────────────────────────────


class NullTypeResolver:
    """No-op default — matches W7 untyped translator behavior."""

    def resolve_method_return_type(
        self,
        receiver_type_fqn: str | None,
        method_name: str,
    ) -> str | None:
        return None

    def resolve_field_type(
        self,
        owner_type_fqn: str | None,
        field_name: str,
    ) -> str | None:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BigDecimal-aware default — hardcoded, no ontology
# ─────────────────────────────────────────────────────────────────────────────


# BigDecimal methods that return BigDecimal (fluent chain).
# Source: java.math.BigDecimal Javadoc.
_BIGDECIMAL_RETURNS_BIGDECIMAL: frozenset[str] = frozenset({
    "add", "subtract", "multiply", "divide", "remainder",
    "abs", "negate", "plus", "pow",
    "round", "setScale",
    "min", "max",
    "movePointLeft", "movePointRight",
    "scaleByPowerOfTen", "stripTrailingZeros",
    "ulp", "valueOf",  # static factory
})

# BigDecimal methods that return primitives.
_BIGDECIMAL_RETURNS_INT: frozenset[str] = frozenset({
    "compareTo", "signum", "scale", "precision",
    "intValue", "intValueExact",
    "byteValue", "byteValueExact",
    "shortValue", "shortValueExact",
})

_BIGDECIMAL_RETURNS_LONG: frozenset[str] = frozenset({
    "longValue", "longValueExact",
})

_BIGDECIMAL_RETURNS_DOUBLE: frozenset[str] = frozenset({
    "doubleValue", "floatValue",
})

_BIGDECIMAL_RETURNS_BOOLEAN: frozenset[str] = frozenset({"equals"})

_BIGDECIMAL_RETURNS_STRING: frozenset[str] = frozenset({
    "toString", "toPlainString", "toEngineeringString",
})


_BIGDECIMAL_FQN_VARIANTS: frozenset[str] = frozenset({
    "java.math.BigDecimal",
    "BigDecimal",
})


class BigDecimalAwareResolver:
    """Hardcoded BigDecimal-family knowledge — no ontology dependency.

    Sufficient for v2 (slab-design) use cases: covers all BigDecimal methods
    used in `sample-repos/slab-design-real_v2/` 산술.

    Plugin-specific receiver types (e.g., SDOrderEntity.getOrderWgtHigh() → BigDecimal)
    are NOT in this resolver. Compose with an OntologyTypeResolver (W9+) for those.
    """

    def resolve_method_return_type(
        self,
        receiver_type_fqn: str | None,
        method_name: str,
    ) -> str | None:
        if receiver_type_fqn not in _BIGDECIMAL_FQN_VARIANTS:
            return None
        if method_name in _BIGDECIMAL_RETURNS_BIGDECIMAL:
            return "java.math.BigDecimal"
        if method_name in _BIGDECIMAL_RETURNS_INT:
            return "int"
        if method_name in _BIGDECIMAL_RETURNS_LONG:
            return "long"
        if method_name in _BIGDECIMAL_RETURNS_DOUBLE:
            return "double"
        if method_name in _BIGDECIMAL_RETURNS_BOOLEAN:
            return "boolean"
        if method_name in _BIGDECIMAL_RETURNS_STRING:
            return "java.lang.String"
        return None

    def resolve_field_type(
        self,
        owner_type_fqn: str | None,
        field_name: str,
    ) -> str | None:
        if owner_type_fqn not in _BIGDECIMAL_FQN_VARIANTS:
            return None
        # Static fields — all BigDecimal type
        if field_name in {"ZERO", "ONE", "TEN"}:
            return "java.math.BigDecimal"
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Composite — chain multiple resolvers, first non-None wins
# ─────────────────────────────────────────────────────────────────────────────


class CompositeTypeResolver:
    """Try resolvers in order, return first non-None result.

    Usage:
        resolver = CompositeTypeResolver([
            OntologyTypeResolver(session, repo_id),  # plugin-specific (W9+)
            BigDecimalAwareResolver(),                # std library
        ])
    """

    def __init__(self, resolvers: list[TypeResolver]) -> None:
        self.resolvers = resolvers

    def resolve_method_return_type(
        self,
        receiver_type_fqn: str | None,
        method_name: str,
    ) -> str | None:
        for r in self.resolvers:
            t = r.resolve_method_return_type(receiver_type_fqn, method_name)
            if t is not None:
                return t
        return None

    def resolve_field_type(
        self,
        owner_type_fqn: str | None,
        field_name: str,
    ) -> str | None:
        for r in self.resolvers:
            t = r.resolve_field_type(owner_type_fqn, field_name)
            if t is not None:
                return t
        return None


def is_bigdecimal_type(type_fqn: str | None) -> bool:
    """Helper — check if a type FQN refers to BigDecimal."""
    return type_fqn in _BIGDECIMAL_FQN_VARIANTS


__all__ = [
    "BigDecimalAwareResolver",
    "CompositeTypeResolver",
    "NullTypeResolver",
    "TypeResolver",
    "is_bigdecimal_type",
]
