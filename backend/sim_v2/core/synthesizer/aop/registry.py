"""Aspect base + registry — ADR-008 + ADR-013 §2.

@Aspect weaving — Spring AOP / AspectJ pattern.

Public API:
    - AspectBase
    - AspectContext / AspectOutput
    - AspectRegistry + register_aspect / get_aspect
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

AdviceKind = Literal["before", "after", "around", "after_returning", "after_throwing"]


@dataclass(frozen=True)
class AspectContext:
    aspect_name:       str
    advice_kind:       AdviceKind
    pointcut:          str = ""        # @Around("@within(...)") expression
    target_method:     dict[str, Any] = field(default_factory=dict)
    aspect_args:       dict[str, Any] = field(default_factory=dict)
    plugin_name:       str = ""
    plugin_contract:   Any | None = None


@dataclass(frozen=True)
class AspectOutput:
    python_source:     str            # decorator / wrapper
    imports_needed:    tuple[str, ...] = ()
    signature_locked:  bool = False
    notes:             tuple[str, ...] = ()


class AspectBase(ABC):
    name:        str = ""
    aspect_kind: str = ""   # registry identifier ("banking.tenant_context")

    @abstractmethod
    def weave(self, context: AspectContext) -> AspectOutput:
        ...


class _SignatureLockedAspect:
    name = "core.signature_locked_aspect"
    aspect_kind = ""

    def weave(self, context: AspectContext) -> AspectOutput:
        return AspectOutput(
            python_source=(
                f"# UNCLEAR: aspect {context.aspect_name!r} not handled.\n"
                f"# SIGNATURE_LOCKED. Add plugins/{context.plugin_name or '<sys>'}/aop/ extension."
            ),
            signature_locked=True,
            notes=(f"SIGNATURE_LOCKED for aspect={context.aspect_name!r}",),
        )


class AspectRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, AspectBase] = {}
        self._by_kind: dict[str, AspectBase] = {}
        self._fallback: Any = _SignatureLockedAspect()

    def register(self, aspect: AspectBase, *, override: bool = False) -> None:
        if not aspect.name:
            raise ValueError("aspect must define .name")
        if not aspect.aspect_kind:
            raise ValueError(f"aspect {aspect.name!r} must define .aspect_kind")
        if aspect.name in self._by_name and not override:
            raise ValueError(f"aspect name conflict: {aspect.name!r}")
        if aspect.aspect_kind in self._by_kind and not override:
            raise ValueError(
                f"aspect_kind conflict: {aspect.aspect_kind!r} "
                f"already handled by {self._by_kind[aspect.aspect_kind].name!r}"
            )
        self._by_name[aspect.name] = aspect
        self._by_kind[aspect.aspect_kind] = aspect

    def get(self, aspect_kind: str) -> AspectBase:
        return self._by_kind.get(aspect_kind, self._fallback)  # type: ignore[return-value]

    def get_by_name(self, name: str) -> AspectBase | None:
        return self._by_name.get(name)

    def weave(self, context: AspectContext) -> AspectOutput:
        # context.aspect_name doubles as aspect_kind for lookup
        return self.get(context.aspect_name).weave(context)

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())

    def count(self) -> int:
        return len(self._by_name)


_default_registry: AspectRegistry | None = None


def get_default_registry() -> AspectRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = AspectRegistry()
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None


def register_aspect(aspect: AspectBase, *, override: bool = False) -> None:
    get_default_registry().register(aspect, override=override)


def get_aspect(aspect_kind: str) -> AspectBase:
    return get_default_registry().get(aspect_kind)


__all__ = [
    "AdviceKind",
    "AspectBase",
    "AspectContext",
    "AspectOutput",
    "AspectRegistry",
    "get_aspect",
    "get_default_registry",
    "register_aspect",
    "reset_default_registry",
]
