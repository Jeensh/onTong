"""Broadleaf bytecode extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].bytecode.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    get_default_registry,
    register_bytecode_handler,
)

from .dynamic_entity_dao_proxy import DynamicEntityDaoProxyHandler


def _register_broadleaf_bytecode() -> None:
    """Idempotent — skip if already registered (handles re-import in tests)."""
    registry = get_default_registry()
    if registry.get_by_name("broadleaf.dynamic_entity_dao_proxy") is None:
        register_bytecode_handler(DynamicEntityDaoProxyHandler())


_register_broadleaf_bytecode()


__all__ = ["DynamicEntityDaoProxyHandler"]
