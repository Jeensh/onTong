"""broadleaf.dynamic_entity_dao_proxy bytecode handler — BROADLEAF-ONBOARDING.md §4.5.

BLC DynamicEntityDao — runtime CGLib proxy 로 entity behavior 변경.
Python equivalent: __getattr__ 기반 lazy-loading proxy.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    BytecodeHandlerBase,
    BytecodeOutput,
)


class DynamicEntityDaoProxyHandler(BytecodeHandlerBase):
    """CGLib proxy → Python lazy-loading proxy class.

    Strategy: proxy class 가 __getattr__ 으로 lazy-load entity field, repository 호출 trigger.
    Java CGLib intercept 와 동등 semantics (lazy lookup, transparent surface).
    """
    name = "broadleaf.dynamic_entity_dao_proxy"
    pattern = "broadleaf.dynamic_entity_dao_proxy"

    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        entity_class = context.target_class or context.pattern_args.get("entity_class", "")
        repository_class = context.pattern_args.get("repository_class", "")

        if not entity_class:
            return BytecodeOutput(
                python_source=(
                    "# UNCLEAR: broadleaf.dynamic_entity_dao_proxy requires target_class.\n"
                    "# SIGNATURE_LOCKED."
                ),
                signature_locked=True,
                notes=("entity_class missing",),
            )

        proxy_class_name = f"{entity_class.rpartition('.')[-1]}Proxy"
        python_source = (
            f"# DynamicEntityDao CGLib proxy → Python lazy-loading proxy\n"
            f"# Target entity: {entity_class}\n"
            f"# Backing repository: {repository_class or '(unspecified)'}\n"
            f"class {proxy_class_name}:\n"
            f"    '''Lazy-loading proxy for {entity_class}. Mirrors CGLib intercept semantics.'''\n"
            f"\n"
            f"    def __init__(self, entity_id, repository):\n"
            f"        self.__dict__['_id'] = entity_id\n"
            f"        self.__dict__['_repository'] = repository\n"
            f"        self.__dict__['_loaded'] = None\n"
            f"\n"
            f"    def _load(self):\n"
            f"        if self._loaded is None:\n"
            f"            self.__dict__['_loaded'] = self._repository.find_by_id(\n"
            f"                {entity_class.rpartition('.')[-1]!r}, self._id\n"
            f"            )\n"
            f"        return self._loaded\n"
            f"\n"
            f"    def __getattr__(self, name):\n"
            f"        return getattr(self._load(), name)\n"
            f"\n"
            f"    def __setattr__(self, name, value):\n"
            f"        setattr(self._load(), name, value)"
        )

        return BytecodeOutput(
            python_source=python_source,
            notes=(
                f"DynamicEntityDaoProxyHandler — proxy class {proxy_class_name} for {entity_class}",
            ),
        )


__all__ = ["DynamicEntityDaoProxyHandler"]
