"""P12 body.service_lookup — Spring @Service / DI lookup emitter."""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator

from .base import EmitContext, EmitOutput, Emitter


class BodyServiceLookupEmitter(Emitter):
    """body.service_lookup — Spring service injection.

    Generic: most Java codebases use Spring DI. Plugin override 가 system-specific
    factory (e.g., Broadleaf 의 BLC factory) 를 처리.

    W12: When `anchor_metadata['java_ast_node']` is a method_invocation / field_access
    representing the Java service lookup site, translator emits the call passthrough.
    """
    name = "core.body_service_lookup"
    target_slots = ("body.service_lookup",)

    def emit(self, context: EmitContext) -> EmitOutput:
        java_node = context.anchor_metadata.get("java_ast_node")

        if java_node is not None:
            translator = JavaToPythonTranslator(plugin_contract=context.plugin_contract)
            tr = translator.translate(java_node, indent=0)
            return EmitOutput(
                python_source=tr.python_source,
                imports_needed=tuple(sorted({*tr.imports_needed, "backend.sim_v2.core.contracts.base"})),
                notes=tuple(tr.notes) or ("BodyServiceLookupEmitter — Java service lookup translated",),
                signature_locked=tr.signature_locked,
            )

        service_name = context.anchor_metadata.get("service_name", "")
        var = context.anchor_metadata.get("result_var", "service")
        return EmitOutput(
            python_source=(
                f"{var} = spring_di.get_bean({service_name!r})  # body.service_lookup"
                if service_name
                else "# body.service_lookup: service_name metadata 부재"
            ),
            imports_needed=("backend.sim_v2.core.contracts.base",),
            notes=("BodyServiceLookupEmitter — caller-supplied service_name (Spring DI)",),
        )
