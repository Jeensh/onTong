"""banking.audit aspect — BANKING-DESIGN.md §6.3 / §1.3.

Compliance / audit log emission — 모든 service call 의 immutable append-only log.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectBase,
    AspectContext,
    AspectOutput,
)


class AuditAspect(AspectBase):
    """Service call audit logger — Around advice.

    Strategy: method 진입 시 before-snapshot, 종료 시 after-snapshot + outcome 을 audit log 에 append.
    """
    name = "banking.audit"
    aspect_kind = "banking.audit"

    def weave(self, context: AspectContext) -> AspectOutput:
        target = context.target_method.get("method_name", "<unknown_method>")
        target_class = context.target_method.get("class_fqn", "<unknown_class>")

        python_source = (
            f"# @Audit aspect — wraps {target_class}.{target}\n"
            f"def _audit_wrap(__fn):\n"
            f"    def __wrapped(self, *args, **kwargs):\n"
            f"        from backend.sim_v2.plugins.banking.contracts.domain_namespace import TenantContextHolder\n"
            f"        from datetime import datetime, timezone\n"
            f"        tenant_id = TenantContextHolder.get_current_tenant_id()\n"
            f"        before_ts = datetime.now(timezone.utc).isoformat()\n"
            f"        try:\n"
            f"            result = __fn(self, *args, **kwargs)\n"
            f"            outcome = 'SUCCESS'\n"
            f"            return result\n"
            f"        except Exception as __exc:\n"
            f"            outcome = f'FAILURE:{{type(__exc).__name__}}'\n"
            f"            raise\n"
            f"        finally:\n"
            f"            # Audit log emit — production wires to audit_log table; W6 stub stores in-memory\n"
            f"            audit_record = {{\n"
            f"                'tenant_id': tenant_id,\n"
            f"                'entity_type': {target_class!r},\n"
            f"                'operation': {target!r},\n"
            f"                'timestamp_before': before_ts,\n"
            f"                'timestamp_after': datetime.now(timezone.utc).isoformat(),\n"
            f"                'outcome': outcome,\n"
            f"            }}\n"
            f"            # TODO W7+: append audit_record to audit_log table via Session\n"
            f"    __wrapped.__name__ = __fn.__name__\n"
            f"    return __wrapped"
        )

        return AspectOutput(
            python_source=python_source,
            imports_needed=(
                "backend.sim_v2.plugins.banking.contracts.domain_namespace",
                "datetime",
            ),
            notes=(
                f"AuditAspect — woven around {target_class}.{target}",
                "before/after snapshots + outcome captured",
            ),
        )


__all__ = ["AuditAspect"]
