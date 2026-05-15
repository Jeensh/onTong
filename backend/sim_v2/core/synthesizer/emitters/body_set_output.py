"""P02 body.set_output — output field 할당 emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodySetOutputEmitter(Emitter):
    """body.set_output — entity setter / field assignment.

    W7: When `anchor_metadata['java_ast_node']` is an assignment_expression or
    expression_statement node, translator emits `target.field = value` with
    BigDecimal mapping on the RHS.
    """
    name = "core.body_set_output"
    target_slots = ("body.set_output",)

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodySetOutputEmitter — Java assignment translated",),
                signature_locked=tr.signature_locked,
            )

        target_field = context.anchor_metadata.get("target_field", "")
        source_expression = context.anchor_metadata.get("source_expression", "")
        target_obj = context.anchor_metadata.get("target_object", "self")
        return EmitOutput(
            python_source=(
                f"{target_obj}.{target_field} = {source_expression}  # body.set_output"
                if target_field
                else "# body.set_output: target_field metadata 부재"
            ),
            notes=("BodySetOutputEmitter — caller-supplied strings",),
        )
