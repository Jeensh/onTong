"""Broadleaf dispatcher extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].dispatchers.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    get_default_registry,
    register_dispatcher,
)

from .factory_dispatch import FactoryDispatchDispatcher


def _register_broadleaf_dispatchers() -> None:
    """Idempotent — skip if already registered (handles re-import in tests)."""
    registry = get_default_registry()
    if registry.get_by_name("broadleaf.factory_dispatch") is None:
        register_dispatcher(FactoryDispatchDispatcher())


_register_broadleaf_dispatchers()


__all__ = ["FactoryDispatchDispatcher"]
