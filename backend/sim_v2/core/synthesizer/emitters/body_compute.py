"""P01 body.compute — 산술 식 계산 emitter.

Lesson 2 §6.1 — system-agnostic. BigDecimal arithmetic 의 generic mapping.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyComputeEmitter(Emitter):
    """body.compute target_slot — arithmetic / function call emit.

    W7: When `anchor_metadata['java_ast_node']` is provided, the JavaToPython
    translator emits real Python source (BigDecimal-aware). Otherwise falls back
    to the `expression` string template (caller provides Python-ready code).
    """
    name = "core.body_compute"
    target_slots = ("body.compute",)

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")
        result_var = context.anchor_metadata.get("result_var", "result")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=f"{result_var} = {tr.python_source}  # body.compute",
                imports_needed=tuple(sorted(tr.imports_needed)),
                notes=tuple(tr.notes) or ("BodyComputeEmitter — Java AST translated",),
                signature_locked=tr.signature_locked,
            )

        expression = context.anchor_metadata.get("expression", "")
        return EmitOutput(
            python_source=(
                f"{result_var} = {expression}  # body.compute"
                if expression
                else "# body.compute: expression metadata 부재 — anchor enrichment 필요"
            ),
            imports_needed=("backend.sim_v2.core.contracts.base",),
            notes=("BodyComputeEmitter — caller-supplied expression string",),
        )
