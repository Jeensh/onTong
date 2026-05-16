"""Broadleaf AOP extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].aop.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    get_default_registry,
    register_aspect,
)

from .configurable_handler import ConfigurableHandlerAspect
from .dynamic_field import DynamicFieldAspect


def _register_broadleaf_aspects() -> None:
    """Idempotent — skip each aspect if already registered."""
    registry = get_default_registry()
    if registry.get_by_name("broadleaf.configurable_handler") is None:
        register_aspect(ConfigurableHandlerAspect())
    if registry.get_by_name("broadleaf.dynamic_field") is None:
        register_aspect(DynamicFieldAspect())


_register_broadleaf_aspects()


__all__ = ["ConfigurableHandlerAspect", "DynamicFieldAspect"]
