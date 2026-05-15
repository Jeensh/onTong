"""broadleaf.factory_dispatch dispatcher — BROADLEAF-ONBOARDING.md §4.2.

BLC factory pattern — interface FQN → concrete class FQN runtime selection.
ADR-006 의 8 dispatch_kind 외 9번째 candidate.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    DispatcherBase,
    DispatchOutput,
)


class FactoryDispatchDispatcher(DispatcherBase):
    """BLC factory pattern — runtime concrete class selection via mapping.

    Strategy: factory.create(InterfaceClass) → _FACTORY_REGISTRY[interface_fqn] lookup.
    Configured via plugin manifest 또는 application context.
    """
    name = "broadleaf.factory_dispatch"
    dispatch_kind = "broadleaf.factory_dispatch"

    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        interface_fqn = context.call_site.get("interface_fqn", "")
        concrete_mapping: dict[str, str] = context.call_site.get("concrete_mapping", {})

        if not interface_fqn:
            return DispatchOutput(
                python_source=(
                    "# UNCLEAR: broadleaf.factory_dispatch requires interface_fqn.\n"
                    "# SIGNATURE_LOCKED."
                ),
                signature_locked=True,
                notes=("interface_fqn missing",),
            )

        if not concrete_mapping:
            return DispatchOutput(
                python_source=(
                    f"# BLC factory for {interface_fqn!r} — no concrete mapping declared.\n"
                    f"# Caller must supply concrete class (W6 limitation)."
                ),
                notes=(f"no concrete mapping for {interface_fqn!r}",),
            )

        mapping_entries = "\n".join(
            f"    {iface!r}: {concrete!r},"
            for iface, concrete in concrete_mapping.items()
        )

        python_source = (
            f"# BLC factory dispatch — interface_fqn → concrete class FQN string mapping\n"
            f"_BLC_FACTORY_MAPPING = {{\n"
            f"{mapping_entries}\n"
            f"}}\n\n"
            f"def blc_create(interface_fqn: str):\n"
            f"    import importlib\n"
            f"    from backend.sim_v2.plugins.broadleaf.contracts.exception import CatalogException\n"
            f"    concrete_fqn = _BLC_FACTORY_MAPPING.get(interface_fqn)\n"
            f"    if concrete_fqn is None:\n"
            f"        raise CatalogException(\n"
            f"            f'BLC factory: no concrete class registered for {{interface_fqn!r}}'\n"
            f"        )\n"
            f"    module_name, _, class_name = concrete_fqn.rpartition('.')\n"
            f"    module = importlib.import_module(module_name)\n"
            f"    return getattr(module, class_name)()"
        )

        return DispatchOutput(
            python_source=python_source,
            notes=(
                f"FactoryDispatchDispatcher — interface={interface_fqn!r}, mappings={len(concrete_mapping)}",
            ),
        )


__all__ = ["FactoryDispatchDispatcher"]
