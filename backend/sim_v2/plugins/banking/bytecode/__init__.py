"""Banking bytecode extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].bytecode.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    get_default_registry,
    register_bytecode_handler,
)

from .bpmn_dynamic_class import BpmnDynamicClassHandler


def _register_banking_bytecode() -> None:
    """Idempotent — skip if already registered (handles re-import in tests)."""
    registry = get_default_registry()
    if registry.get_by_name("banking.bpmn_dynamic_class") is None:
        register_bytecode_handler(BpmnDynamicClassHandler())


_register_banking_bytecode()


__all__ = ["BpmnDynamicClassHandler"]
