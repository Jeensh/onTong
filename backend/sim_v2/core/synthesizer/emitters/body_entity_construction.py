"""P18 body.entity_construction — new Entity() 등 emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyEntityConstructionEmitter(Emitter):
    """body.entity_construction + 관련 sub-slots.

    W12: When `anchor_metadata['java_ast_node']` is an object_creation_expression
    or local_variable_declaration with object_creation_expression initializer,
    translator emits `Entity(args)` with BigDecimal mapping.
    """
    name = "core.body_entity_construction"
    target_slots = (
        "body.entity_construction",
        "body.snapshot_serialization",
        "body.slab_null_marker",
        "body.error_code_propagation",
    )

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodyEntityConstructionEmitter — Java new T(args) translated",),
                signature_locked=tr.signature_locked,
            )

        entity_class = context.anchor_metadata.get("entity_class", "Entity")
        init_args = context.anchor_metadata.get("init_args", "")
        var = context.anchor_metadata.get("result_var", "entity")
        return EmitOutput(
            python_source=f"{var} = {entity_class}({init_args})  # body.entity_construction",
            notes=("BodyEntityConstructionEmitter — caller-supplied strings",),
        )
