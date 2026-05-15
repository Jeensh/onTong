"""P04 body.return — 메서드 return emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyReturnEmitter(Emitter):
    """body.return / body.return_aggregate.

    W7: When `anchor_metadata['java_ast_node']` is a return_statement node,
    the translator emits `return <expr>` with full BigDecimal mapping.
    Otherwise falls back to `return_expression` string.
    """
    name = "core.body_return"
    target_slots = ("body.return", "body.return_aggregate")

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodyReturnEmitter — Java return_statement translated",),
                signature_locked=tr.signature_locked,
            )

        return_expression = context.anchor_metadata.get("return_expression", "None")
        return EmitOutput(
            python_source=f"return {return_expression}  # body.return",
            notes=("BodyReturnEmitter — caller-supplied return_expression string",),
        )
