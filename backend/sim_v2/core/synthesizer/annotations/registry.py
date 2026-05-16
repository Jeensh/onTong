"""Annotation handler base + registry — ADR-007 + ADR-013 §2.

Annotation processing (Lombok / @Compensable 등) — Java annotation 의 Python emit.

Public API:
    - AnnotationHandlerBase
    - AnnotationContext / AnnotationOutput
    - AnnotationRegistry + register_annotation_handler / get_annotation_handler
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnnotationContext:
    annotation_fqn:   str             # "lombok.Data", "bank.annotation.Compensable" 등
    annotation_args:  dict[str, Any] = field(default_factory=dict)
    target_kind:      str = ""        # "class" / "method" / "field" / "parameter"
    target_metadata:  dict[str, Any] = field(default_factory=dict)
    plugin_name:      str = ""
    plugin_contract:  Any | None = None


@dataclass(frozen=True)
class AnnotationOutput:
    python_source:    str            # decorator / pre-/post-wrapping
    imports_needed:   tuple[str, ...] = ()
    signature_locked: bool = False
    notes:            tuple[str, ...] = ()


class AnnotationHandlerBase(ABC):
    name:           str = ""
    annotation_fqn: str = ""   # which annotation FQN this handler covers

    @abstractmethod
    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        ...


class _SignatureLockedAnnotation:
    name = "core.signature_locked_annotation"
    annotation_fqn = ""

    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        return AnnotationOutput(
            python_source=(
                f"# UNCLEAR: annotation {context.annotation_fqn!r} not handled.\n"
                f"# SIGNATURE_LOCKED. Add plugins/{context.plugin_name or '<sys>'}/annotations/ extension."
            ),
            signature_locked=True,
            notes=(f"SIGNATURE_LOCKED for annotation={context.annotation_fqn!r}",),
        )


class AnnotationRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, AnnotationHandlerBase] = {}
        self._by_fqn:  dict[str, AnnotationHandlerBase] = {}
        self._fallback: Any = _SignatureLockedAnnotation()

    def register(self, handler: AnnotationHandlerBase, *, override: bool = False) -> None:
        if not handler.name:
            raise ValueError("handler must define .name")
        if not handler.annotation_fqn:
            raise ValueError(f"handler {handler.name!r} must define .annotation_fqn")
        if handler.name in self._by_name and not override:
            raise ValueError(f"annotation handler name conflict: {handler.name!r}")
        if handler.annotation_fqn in self._by_fqn and not override:
            raise ValueError(
                f"annotation_fqn conflict: {handler.annotation_fqn!r} "
                f"already handled by {self._by_fqn[handler.annotation_fqn].name!r}"
            )
        self._by_name[handler.name] = handler
        self._by_fqn[handler.annotation_fqn] = handler

    def get(self, annotation_fqn: str) -> AnnotationHandlerBase:
        return self._by_fqn.get(annotation_fqn, self._fallback)  # type: ignore[return-value]

    def get_by_name(self, name: str) -> AnnotationHandlerBase | None:
        return self._by_name.get(name)

    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        return self.get(context.annotation_fqn).handle(context)

    def names(self) -> list[str]:
        return sorted(self._by_name.keys())

    def count(self) -> int:
        return len(self._by_name)


_default_registry: AnnotationRegistry | None = None


def get_default_registry() -> AnnotationRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = AnnotationRegistry()
    return _default_registry


def reset_default_registry() -> None:
    global _default_registry
    _default_registry = None


def register_annotation_handler(handler: AnnotationHandlerBase, *, override: bool = False) -> None:
    get_default_registry().register(handler, override=override)


def get_annotation_handler(annotation_fqn: str) -> AnnotationHandlerBase:
    return get_default_registry().get(annotation_fqn)


__all__ = [
    "AnnotationContext",
    "AnnotationHandlerBase",
    "AnnotationOutput",
    "AnnotationRegistry",
    "get_annotation_handler",
    "get_default_registry",
    "register_annotation_handler",
    "reset_default_registry",
]
