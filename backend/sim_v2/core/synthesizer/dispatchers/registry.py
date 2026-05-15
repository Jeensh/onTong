"""Dispatcher base + registry — ADR-006 + ADR-013 §2.

Polymorphic dispatch (8 dispatch_kind in ADR-006) + plugin extension entry point.

Public API:
    - DispatcherBase — abstract
    - DispatchContext — emit input
    - DispatchOutput — emit output
    - DispatcherRegistry — name → Dispatcher
    - register_dispatcher / get_dispatcher / get_default_registry
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DispatchContext:
    dispatch_kind:  str
    call_site:      dict[str, Any] = field(default_factory=dict)
    plugin_name:    str = ""
    plugin_contract: Any | None = None


@dataclass(frozen=True)
class DispatchOutput:
    python_source:    str
    signature_locked: bool = False
    notes:            tuple[str, ...] = ()


class DispatcherBase(ABC):
    """Plug-in / core dispatcher base.

    Subclasses must set:
      - `name` (registry id, e.g., "core.single_impl" or "banking.drools_kbase_lookup")
      - `dispatch_kind` (which dispatch_kind to handle)
    """
    name:          str = ""
    dispatch_kind: str = ""

    @abstractmethod
    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        ...


class _SignatureLockedDispatcher:
    name = "core.signature_locked_dispatcher"
    dispatch_kind = ""

    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        return DispatchOutput(
            python_source=(
                f"# UNCLEAR: dispatch_kind = {context.dispatch_kind!r} not handled.\n"
                f"# SIGNATURE_LOCKED. Add backend/sim_v2/plugins/{context.plugin_name or '<sys>'}/dispatchers/ extension.\n"
                f"raise NotImplementedError({context.dispatch_kind!r} + ': SIGNATURE_LOCKED')"
            ),
            signature_locked=True,
            notes=(f"SIGNATURE_LOCKED for dispatch_kind={context.dispatch_kind!r}",),
        )


class DispatcherRegistry:
    """dispatch_kind → DispatcherBase lookup. ADR-013 §2 의 registry pattern."""

    def __init__(self) -> None:
        self._by_name: dict[str, DispatcherBase] = {}
        self._by_kind: dict[str, DispatcherBase] = {}
        self._fallback: Any = _SignatureLockedDispatcher()

    def register(self, dispatcher: DispatcherBase, *, override: bool = False) -> None:
        if not dispatcher.name:
            raise ValueError(f"Dispatcher {dispatcher.__class__.__name__} must define .name")
        if not dispatcher.dispatch_kind:
            raise ValueError(f"Dispatcher {dispatcher.name!r} must define .dispatch_kind")
        if dispatcher.name in self._by_name and not override:
            raise ValueError(f"Dispatcher name conflict: {dispatcher.name!r}")
        if dispatcher.dispatch_kind in self._by_kind and not override:
            raise ValueError(
                f"dispatch_kind conflict: {dispatcher.dispatch_kind!r} "
                f"already handled by {self._by_kind[dispatcher.dispatch_kind].name!r}"
            )
        self._by_name[dispatcher.name] = dispatcher
        self._by_kind[dispatcher.dispatch_kind] = dispatcher

    def get(self, dispatch_kind: str) -> DispatcherBase:
        return self._by_kind.get(dispatch_kind, self._fallback)  # type: ignore[return-value]

    def get_by_name(self, name: str) -> DispatcherBase | None:
        return self._by_name.get(name)

    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        return self.get(context.dispatch_kind).synthesize(context)

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())

    def count(self) -> int:
        return len(self._by_name)


_default_registry: DispatcherRegistry | None = None


def get_default_registry() -> DispatcherRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = DispatcherRegistry()
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None


def register_dispatcher(dispatcher: DispatcherBase, *, override: bool = False) -> None:
    get_default_registry().register(dispatcher, override=override)


def get_dispatcher(dispatch_kind: str) -> DispatcherBase:
    return get_default_registry().get(dispatch_kind)


__all__ = [
    "DispatchContext",
    "DispatchOutput",
    "DispatcherBase",
    "DispatcherRegistry",
    "get_default_registry",
    "get_dispatcher",
    "register_dispatcher",
    "reset_default_registry",
]
