"""@TenantContext aspect — banking plugin extension (ADR-008 + ADR-013).

BANKING-DESIGN.md §6 의 정식 구현. @TenantContext annotation 가 붙은 method 의
emit 시 wrapper 생성 — TenantContextHolder.get_current_tenant_id() check + filter activate.

Plug-in extension registry pattern (ADR-013 §2):
    plugins/banking/aop/__init__.py 가 import 시 register_aspect() 호출.

Plug-in 의 register_aspect 호출 시점 = plugin_loader 가 manifest 의
`[extensions].aop = ["banking.tenant_context", ...]` 발견 후 `plugins/banking/aop` 모듈을
import 할 때. (현재 plugin_loader 는 dash-named plugin 의 경우 skip 하지만
banking/broadleaf 는 underscore directory 사용해 OK.)
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectBase,
    AspectContext,
    AspectOutput,
)


class TenantContextAspect(AspectBase):
    """@TenantContext aspect (BANKING-DESIGN §6.1).

    Strategy: emit() 의 wrapper 가 method body 진입 직전 TenantContextHolder 체크.
    """
    name = "banking.tenant_context"
    aspect_kind = "banking.tenant_context"

    def weave(self, context: AspectContext) -> AspectOutput:
        target = context.target_method.get("method_name", "<unknown_method>")
        target_class = context.target_method.get("class_fqn", "<unknown_class>")

        python_source = (
            f"# @TenantContext aspect — wraps {target_class}.{target}\n"
            f"def _tenant_context_wrap(__fn):\n"
            f"    def __wrapped(*args, **kwargs):\n"
            f"        from backend.sim_v2.plugins.banking.contracts.domain_namespace import TenantContextHolder\n"
            f"        from backend.sim_v2.plugins.banking.contracts.exception import MissingTenantException\n"
            f"        tenant_id = TenantContextHolder.get_current_tenant_id()\n"
            f"        if tenant_id is None:\n"
            f"            raise MissingTenantException(\n"
            f"                f'{{__fn.__qualname__}}: tenant_id required but not in context'\n"
            f"            )\n"
            f"        # Hibernate-equivalent filter activation deferred to W6+ (entity_manager wiring).\n"
            f"        return __fn(*args, **kwargs)\n"
            f"    __wrapped.__name__ = __fn.__name__\n"
            f"    return __wrapped"
        )

        return AspectOutput(
            python_source=python_source,
            imports_needed=(
                "backend.sim_v2.plugins.banking.contracts.domain_namespace",
                "backend.sim_v2.plugins.banking.contracts.exception",
            ),
            notes=(
                f"TenantContextAspect — woven around {target_class}.{target}",
                f"Pointcut: {context.pointcut!r}",
            ),
        )


__all__ = ["TenantContextAspect"]
