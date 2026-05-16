"""Bytecode handler base + registry — ADR-009 + ADR-013 §2.

Bytecode generation (CGLib / Activiti BPMN dynamic class / Drools KIE dynamic compile).

Public API:
    - BytecodeHandlerBase
    - BytecodeContext / BytecodeOutput
    - BytecodeRegistry + register_bytecode_handler / get_bytecode_handler
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BytecodeContext:
    pattern_name:    str            # "cglib_proxy", "activiti_bpmn_deploy" 등
    target_class:    str = ""
    pattern_args:    dict[str, Any] = field(default_factory=dict)
    plugin_name:     str = ""
    plugin_contract: Any | None = None


@dataclass(frozen=True)
class BytecodeOutput:
    python_source:    str
    imports_needed:   tuple[str, ...] = ()
    signature_locked: bool = False
    notes:            tuple[str, ...] = ()


class BytecodeHandlerBase(ABC):
    name:    str = ""
    pattern: str = ""   # registry identifier ("banking.bpmn_dynamic_class")

    @abstractmethod
    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        ...


class _SignatureLockedBytecode:
    name = "core.signature_locked_bytecode"
    pattern = ""

    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        return BytecodeOutput(
            python_source=(
                f"# UNCLEAR: bytecode pattern {context.pattern_name!r} not handled.\n"
                f"# SIGNATURE_LOCKED. Add plugins/{context.plugin_name or '<sys>'}/bytecode/ extension."
            ),
            signature_locked=True,
            notes=(f"SIGNATURE_LOCKED for bytecode pattern={context.pattern_name!r}",),
        )


class BytecodeRegistry:
    def __init__(self) -> None:
        self._by_name:    dict[str, BytecodeHandlerBase] = {}
        self._by_pattern: dict[str, BytecodeHandlerBase] = {}
        self._fallback: Any = _SignatureLockedBytecode()

    def register(self, handler: BytecodeHandlerBase, *, override: bool = False) -> None:
        if not handler.name:
            raise ValueError("handler must define .name")
        if not handler.pattern:
            raise ValueError(f"handler {handler.name!r} must define .pattern")
        if handler.name in self._by_name and not override:
            raise ValueError(f"bytecode handler name conflict: {handler.name!r}")
        if handler.pattern in self._by_pattern and not override:
            raise ValueError(
                f"bytecode pattern conflict: {handler.pattern!r} "
                f"already handled by {self._by_pattern[handler.pattern].name!r}"
            )
        self._by_name[handler.name] = handler
        self._by_pattern[handler.pattern] = handler

    def get(self, pattern: str) -> BytecodeHandlerBase:
        return self._by_pattern.get(pattern, self._fallback)  # type: ignore[return-value]

    def get_by_name(self, name: str) -> BytecodeHandlerBase | None:
        return self._by_name.get(name)

    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        return self.get(context.pattern_name).synthesize(context)

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())

    def count(self) -> int:
        return len(self._by_name)


_default_registry: BytecodeRegistry | None = None


def get_default_registry() -> BytecodeRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = BytecodeRegistry()
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None


def register_bytecode_handler(handler: BytecodeHandlerBase, *, override: bool = False) -> None:
    get_default_registry().register(handler, override=override)


def get_bytecode_handler(pattern: str) -> BytecodeHandlerBase:
    return get_default_registry().get(pattern)


__all__ = [
    "BytecodeContext",
    "BytecodeHandlerBase",
    "BytecodeOutput",
    "BytecodeRegistry",
    "get_bytecode_handler",
    "get_default_registry",
    "register_bytecode_handler",
    "reset_default_registry",
]
