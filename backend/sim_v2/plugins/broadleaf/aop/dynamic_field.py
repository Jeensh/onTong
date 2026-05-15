"""broadleaf.dynamic_field aspect — BROADLEAF-ONBOARDING.md §6.2.

Dynamic field injection — admin-driven entity extension. Community edition 에서는 minimal,
enterprise feature 에서 본격 사용. 본 implementation 은 attribute map 기반의 light version.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectBase,
    AspectContext,
    AspectOutput,
)


class DynamicFieldAspect(AspectBase):
    """Dynamic field attribute map — entity 의 attribute extension.

    Strategy: entity 가 attributes: dict[str, Any] 를 통해 dynamic field 제공.
    getter/setter 가 dict 안의 값을 surface 처럼 노출.
    """
    name = "broadleaf.dynamic_field"
    aspect_kind = "broadleaf.dynamic_field"

    def weave(self, context: AspectContext) -> AspectOutput:
        target_class = context.target_method.get("class_fqn", "<unknown_class>")
        dynamic_fields: list[str] = context.aspect_args.get("dynamic_fields", [])

        if not dynamic_fields:
            python_source = (
                f"# {target_class}: no dynamic_fields declared — attributes dict only\n"
                f"def get_attribute(self, name: str):\n"
                f"    return self.attributes.get(name) if hasattr(self, 'attributes') else None\n"
                f"def set_attribute(self, name: str, value):\n"
                f"    if not hasattr(self, 'attributes'):\n"
                f"        self.attributes = {{}}\n"
                f"    self.attributes[name] = value"
            )
            return AspectOutput(
                python_source=python_source,
                notes=("generic attributes dict only",),
            )

        # Generate explicit property accessors for declared dynamic fields
        property_blocks: list[str] = []
        for field_name in dynamic_fields:
            property_blocks.append(
                f"@property\n"
                f"def {field_name}(self):\n"
                f"    return self.attributes.get({field_name!r}) if hasattr(self, 'attributes') else None\n\n"
                f"@{field_name}.setter\n"
                f"def {field_name}(self, value):\n"
                f"    if not hasattr(self, 'attributes'):\n"
                f"        self.attributes = {{}}\n"
                f"    self.attributes[{field_name!r}] = value"
            )

        python_source = (
            f"# {target_class}: dynamic_field aspect — {len(dynamic_fields)} accessor(s)\n"
            + "\n\n".join(property_blocks)
        )

        return AspectOutput(
            python_source=python_source,
            notes=(
                f"DynamicFieldAspect — {len(dynamic_fields)} dynamic field(s) on {target_class}",
            ),
        )


__all__ = ["DynamicFieldAspect"]
