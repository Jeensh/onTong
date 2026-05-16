"""@Compensable annotation handler — banking saga (ADR-007 + BANKING-DESIGN.md §7).

@Compensable annotation 가 붙은 method 의 emit:
  - try {원본 method} except: compensation_method() 호출 후 SagaCompensatedException re-raise
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    AnnotationHandlerBase,
    AnnotationOutput,
)


class CompensableHandler(AnnotationHandlerBase):
    """@Compensable handler — Saga pattern compensation (BANKING-DESIGN §7.1)."""
    name = "banking.compensable"
    annotation_fqn = "bank.annotation.Compensable"

    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        method = context.target_metadata.get("method_name", "<unknown_method>")
        target_class = context.target_metadata.get("class_fqn", "<unknown_class>")
        compensation_method = context.annotation_args.get("compensationMethod", "")

        if not compensation_method:
            return AnnotationOutput(
                python_source=(
                    f"# @Compensable on {target_class}.{method} but compensationMethod arg missing.\n"
                    f"# SIGNATURE_LOCKED: compensation handler ambiguous."
                ),
                signature_locked=True,
                notes=("compensationMethod arg required",),
            )

        python_source = (
            f"# @Compensable wraps {target_class}.{method} with saga compensation\n"
            f"def _compensable_wrap(__fn):\n"
            f"    def __wrapped(self, *args, **kwargs):\n"
            f"        from backend.sim_v2.plugins.banking.contracts.exception import SagaCompensatedException\n"
            f"        try:\n"
            f"            return __fn(self, *args, **kwargs)\n"
            f"        except Exception as __exc:\n"
            f"            self.{compensation_method}(*args, **kwargs)\n"
            f"            raise SagaCompensatedException(\n"
            f"                f'compensated {{__fn.__qualname__}} via {compensation_method}'\n"
            f"            ) from __exc\n"
            f"    __wrapped.__name__ = __fn.__name__\n"
            f"    return __wrapped"
        )

        return AnnotationOutput(
            python_source=python_source,
            imports_needed=("backend.sim_v2.plugins.banking.contracts.exception",),
            notes=(
                f"CompensableHandler — compensation method={compensation_method!r}",
                f"target={target_class}.{method}",
            ),
        )


__all__ = ["CompensableHandler"]
