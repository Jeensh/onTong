"""broadleaf.merge_annotations annotation — BROADLEAF-ONBOARDING.md §4.3.

@MergeAnnotations — JPA entity inheritance + override 의 BLC-specific 처리.
Java 의 entity merge mechanism 의 Python equivalent: class dict merge with override semantics.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    AnnotationHandlerBase,
    AnnotationOutput,
)


class MergeAnnotationsHandler(AnnotationHandlerBase):
    """@MergeAnnotations entity merge handler.

    Strategy: parent entity 의 attribute dict 가 child 의 override 와 merge.
    BLC 의 OverrideEntityAnnotations 도 본 handler 가 흡수.
    """
    name = "broadleaf.merge_annotations"
    annotation_fqn = "org.broadleafcommerce.common.MergeAnnotations"

    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        target_class = context.target_metadata.get("class_fqn", "<unknown_class>")
        parent_class = context.annotation_args.get("parent", "")
        overrides: dict = context.annotation_args.get("overrides", {})

        if not parent_class:
            return AnnotationOutput(
                python_source=(
                    f"# @MergeAnnotations on {target_class} but parent missing.\n"
                    f"# SIGNATURE_LOCKED."
                ),
                signature_locked=True,
                notes=("parent class required",),
            )

        override_lines = "\n".join(
            f"    merged[{k!r}] = {v!r}"
            for k, v in overrides.items()
        )

        python_source = (
            f"# @MergeAnnotations: {target_class} inherits from {parent_class} with {len(overrides)} override(s)\n"
            f"def merge_with_parent(child_attrs: dict, parent_attrs: dict) -> dict:\n"
            f"    '''Merge parent attrs with child overrides. Child wins.'''\n"
            f"    merged = dict(parent_attrs)\n"
            f"    merged.update(child_attrs)\n"
            + (f"{override_lines}\n" if override_lines else "")
            + f"    return merged"
        )

        return AnnotationOutput(
            python_source=python_source,
            notes=(
                f"MergeAnnotationsHandler — child={target_class}, parent={parent_class}, overrides={len(overrides)}",
            ),
        )


__all__ = ["MergeAnnotationsHandler"]
