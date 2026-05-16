"""Emitter base — Java AST → Python source fragment (ADR-001 + ADR-006).

ADR-006 의 8 dispatch_kind 의 generic emitter base class. Plugin override 가능
(ADR-013 의 Tier 2 plugin extension).

Public API:
    - EmitContext — emit() input (anchor + ontology + plugin context)
    - EmitOutput — emit() output (Python source fragment + imports + notes)
    - Emitter — abstract base
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmitContext:
    """One emit() 의 input — anchor 의 target_slot + context.

    Plug-in 의 emitter override 가 사용할 수 있도록 plugin_contract 도 보유.
    """
    target_slot:     str
    anchor_metadata: dict[str, Any] = field(default_factory=dict)
    plugin_contract: Any | None = None  # JavaContract subclass
    plugin_name:     str = ""
    # 추가 context — anchor 의 caller method, source line, etc.
    caller_method:   str = ""
    source_line:     int | None = None


@dataclass(frozen=True)
class EmitOutput:
    """emit() output — Python source fragment + import 의도 + 사람 readable notes."""
    python_source:  str
    imports_needed: tuple[str, ...] = ()
    notes:          tuple[str, ...] = ()
    # 명시적 SIGNATURE_LOCKED 경우 — fallback 표시
    signature_locked: bool = False


class Emitter(ABC):
    """Generic emitter base — Java AST 한 anchor 의 Python emit.

    Tier 1 (core) 의 8 dispatch_kind generic emitter 가 subclass.
    Tier 2 (plugin) 의 system-specific override 도 subclass.

    Subclasses must override:
      - `target_slots` (class attr) — handled `target_slot` value(s)
      - `emit(context)` — emit logic
    """

    target_slots: tuple[str, ...] = ()
    name:         str = ""  # registry identifier

    def supports(self, target_slot: str) -> bool:
        return target_slot in self.target_slots

    @abstractmethod
    def emit(self, context: EmitContext) -> EmitOutput:
        """Return Python source fragment for the anchor.

        EmitContext 의 target_slot + anchor_metadata + plugin_contract 활용.
        Output 의 python_source 는 valid Python — contract validator 가 검사.
        """
        ...


__all__ = ["EmitContext", "EmitOutput", "Emitter"]
