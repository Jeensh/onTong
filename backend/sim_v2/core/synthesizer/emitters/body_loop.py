"""P08 body.loop — for / iterate emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyLoopEmitter(Emitter):
    """body.loop / body.iterate_orders / body.loop_init.

    W12: When `anchor_metadata['java_ast_node']` is an enhanced_for_statement /
    for_statement / while_statement, the translator emits the full Python loop.
    Otherwise falls back to (iter_var, iterable, body) string template.
    """
    name = "core.body_loop"
    target_slots = ("body.loop", "body.iterate_orders", "body.loop_init")

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodyLoopEmitter — Java loop translated",),
                signature_locked=tr.signature_locked,
            )

        iter_var = context.anchor_metadata.get("iter_var", "item")
        iterable = context.anchor_metadata.get("iterable", "items")
        body = context.anchor_metadata.get("body", "pass")
        return EmitOutput(
            python_source=(
                f"for {iter_var} in {iterable}:  # body.loop\n"
                f"    {body}"
            ),
            notes=("BodyLoopEmitter — caller-supplied iter/iterable/body strings",),
        )
