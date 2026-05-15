"""P07 body.branch — if-else branching emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyBranchEmitter(Emitter):
    """body.branch / body.fallback / body.fallback_strategy.

    W7: When `anchor_metadata['java_ast_node']` is provided (an if_statement node),
    the translator emits the entire if/elif/else cascade. Otherwise falls back to
    `condition` / `then_body` / `else_body` string template path.
    """
    name = "core.body_branch"
    target_slots = ("body.branch", "body.fallback", "body.fallback_strategy")

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodyBranchEmitter — Java if_statement translated",),
                signature_locked=tr.signature_locked,
            )

        condition = context.anchor_metadata.get("condition", "True")
        then_body = context.anchor_metadata.get("then_body", "pass")
        else_body = context.anchor_metadata.get("else_body", None)

        lines = [f"if {condition}:  # body.branch", f"    {then_body}"]
        if else_body:
            lines.append("else:")
            lines.append(f"    {else_body}")

        return EmitOutput(
            python_source="\n".join(lines),
            notes=("BodyBranchEmitter — caller-supplied condition/then/else strings",),
        )
