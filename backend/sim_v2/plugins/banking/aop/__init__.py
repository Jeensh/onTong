"""Banking AOP extensions — auto-registers on import.

Plugin loader (ADR-013 §2) imports this module after parsing manifest 의 [extensions].aop.
Registration uses `register_aspect()` of the core/synthesizer/aop registry.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    get_default_registry,
    register_aspect,
)

from .audit import AuditAspect
from .tenant_context import TenantContextAspect


def _register_banking_aspects() -> None:
    """Idempotent — skip each aspect if already registered."""
    registry = get_default_registry()
    if registry.get_by_name("banking.tenant_context") is None:
        register_aspect(TenantContextAspect())
    if registry.get_by_name("banking.audit") is None:
        register_aspect(AuditAspect())


_register_banking_aspects()


__all__ = ["AuditAspect", "TenantContextAspect"]
