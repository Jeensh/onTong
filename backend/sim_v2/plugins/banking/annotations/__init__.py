"""Banking annotation extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].annotations.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.annotations.registry import (
    get_default_registry,
    register_annotation_handler,
)

from .compensable import CompensableHandler


def _register_banking_annotations() -> None:
    """Idempotent — skip if already registered (handles re-import in tests)."""
    registry = get_default_registry()
    if registry.get_by_name("banking.compensable") is None:
        register_annotation_handler(CompensableHandler())


_register_banking_annotations()


__all__ = ["CompensableHandler"]
