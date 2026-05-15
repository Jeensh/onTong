"""Banking dispatcher extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].dispatchers.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    get_default_registry,
    register_dispatcher,
)

from .drools_kbase_lookup import DroolsKbaseLookupDispatcher


def _register_banking_dispatchers() -> None:
    """Idempotent — skip if already registered (handles re-import in tests)."""
    registry = get_default_registry()
    if registry.get_by_name("banking.drools_kbase_lookup") is None:
        register_dispatcher(DroolsKbaseLookupDispatcher())


_register_banking_dispatchers()


__all__ = ["DroolsKbaseLookupDispatcher"]
