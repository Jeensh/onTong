"""P13 body.repository_call — JPA Repository 호출 emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyRepositoryCallEmitter(Emitter):
    """body.repository_call — JPA findById / save / delete 등.

    W12: When `anchor_metadata['java_ast_node']` is a method_invocation
    representing the repository call, translator emits passthrough (e.g.,
    `repo.findById(id)`). Caller-supplied template path remains as fallback.
    """
    name = "core.body_repository_call"
    target_slots = ("body.repository_call",)

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted({*tr.imports_needed, "backend.sim_v2.core.contracts.base"})),
                notes=tuple(tr.notes) or ("BodyRepositoryCallEmitter — Java repository call translated",),
                signature_locked=tr.signature_locked,
            )

        method = context.anchor_metadata.get("repo_method", "find_by_id")
        repo = context.anchor_metadata.get("repo_var", "repo")
        args = context.anchor_metadata.get("args", "")
        var = context.anchor_metadata.get("result_var", "result")
        return EmitOutput(
            python_source=f"{var} = {repo}.{method}({args})  # body.repository_call",
            imports_needed=("backend.sim_v2.core.contracts.base",),
            notes=("BodyRepositoryCallEmitter — caller-supplied strings (JPA)",),
        )
