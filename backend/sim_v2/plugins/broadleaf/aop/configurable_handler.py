"""broadleaf.configurable_handler aspect — BROADLEAF-ONBOARDING.md §4.1.

@Configurable JPA entity 의 @Autowired field 처리.

Broadleaf 의 핵심 패턴: JPA load 후 Spring 이 @Autowired field 에 service 를 inject.
Python equivalent — entity __post_init__ 또는 explicit hydrate() 가 service registry lookup.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectBase,
    AspectContext,
    AspectOutput,
)


class ConfigurableHandlerAspect(AspectBase):
    """@Configurable JPA entity 의 @Autowired field hydration.

    Strategy: entity 의 hydrate(spring_di) method 가 @Autowired field 를 service registry 에서 lookup.
    JPA repository find_by_id() 후 자동 hydrate.
    """
    name = "broadleaf.configurable_handler"
    aspect_kind = "broadleaf.configurable_handler"

    def weave(self, context: AspectContext) -> AspectOutput:
        target_class = context.target_method.get("class_fqn", "<unknown_class>")
        autowired_fields: list[dict] = context.aspect_args.get("autowired_fields", [])

        if not autowired_fields:
            return AspectOutput(
                python_source=(
                    f"# @Configurable on {target_class} but no @Autowired fields declared.\n"
                    f"# No hydration required — pass-through."
                ),
                notes=("no @Autowired fields",),
            )

        lookup_lines: list[str] = []
        for field in autowired_fields:
            field_name = field.get("field_name", "")
            service_class = field.get("service_class", "")
            if not field_name or not service_class:
                continue
            lookup_lines.append(
                f"    self.{field_name} = spring_di.get_bean({service_class!r})"
            )

        python_source = (
            f"# @Configurable hydration for {target_class}\n"
            f"def hydrate(self, spring_di):\n"
            f"    '''Lazy-inject @Autowired fields after JPA load.'''\n"
            + ("\n".join(lookup_lines) if lookup_lines else "    pass")
        )

        return AspectOutput(
            python_source=python_source,
            imports_needed=("backend.sim_v2.core.contracts.base",),
            notes=(
                f"ConfigurableHandler — hydrate() injects {len(autowired_fields)} field(s) on {target_class}",
            ),
        )


__all__ = ["ConfigurableHandlerAspect"]
