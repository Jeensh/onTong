"""banking.bpmn_dynamic_class bytecode handler — ADR-009 + BANKING-DESIGN.md §4.

Activiti BPMN deployment 시 generated dynamic delegate class 의 Python equivalent emit.
.bpmn20.xml 의 `activiti:class` reference → Python class registry lookup.
"""
from __future__ import annotations

from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    BytecodeHandlerBase,
    BytecodeOutput,
)


class BpmnDynamicClassHandler(BytecodeHandlerBase):
    """Activiti BPMN dynamic class generation — Python class registry approach.

    Strategy: BPMN XML 의 모든 activiti:class reference 를 Python class registry 에 등록.
    Activiti runtime 의 reflection-based class loading 을 Python 의 explicit dict lookup 으로 대체.
    """
    name = "banking.bpmn_dynamic_class"
    pattern = "banking.bpmn_dynamic_class"

    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        bpmn_id = context.pattern_args.get("process_id", "")
        delegates: dict = context.pattern_args.get("delegates", {})

        if not bpmn_id:
            return BytecodeOutput(
                python_source=(
                    "# UNCLEAR: banking.bpmn_dynamic_class requires process_id.\n"
                    "# SIGNATURE_LOCKED."
                ),
                signature_locked=True,
                notes=("process_id missing",),
            )

        if not delegates:
            return BytecodeOutput(
                python_source=(
                    f"# BPMN process {bpmn_id!r} has no activiti:class delegates.\n"
                    f"_BPMN_REGISTRY_{bpmn_id.replace('-', '_').upper()} = {{}}"
                ),
                notes=(f"empty delegate set for process {bpmn_id!r}",),
            )

        # Render the registry dict as Python literal
        entries: list[str] = []
        for task_id, class_fqn in delegates.items():
            python_module = class_fqn.replace(".", "_")
            entries.append(f"    {task_id!r}: {python_module},")

        registry_var = f"_BPMN_REGISTRY_{bpmn_id.replace('-', '_').upper()}"
        # NOTE: outer f-string + inner f-string would conflict on quotes if we
        # used {bpmn_id!r} (single-quoted repr) inside a single-quoted f-string.
        # The process id is a known constant at emit-time, so embed it as raw
        # text (no quoting required for the runtime error message).
        python_source = (
            f"# Activiti BPMN process {bpmn_id!r} — dynamic delegate class registry\n"
            f"# Python explicit dict replaces Activiti's reflection-based class loading\n"
            f"{registry_var} = {{\n"
            + "\n".join(entries) + "\n"
            f"}}\n\n"
            f"def lookup_bpmn_delegate(task_id: str):\n"
            f"    from backend.sim_v2.plugins.banking.contracts.exception import BpmnDeploymentException\n"
            f"    delegate = {registry_var}.get(task_id)\n"
            f"    if delegate is None:\n"
            f"        raise BpmnDeploymentException(\n"
            f"            f'BPMN delegate for {{task_id!r}} not registered in process {bpmn_id}'\n"
            f"        )\n"
            f"    return delegate"
        )

        return BytecodeOutput(
            python_source=python_source,
            imports_needed=("backend.sim_v2.plugins.banking.contracts.exception",),
            notes=(
                f"BpmnDynamicClassHandler — process={bpmn_id!r}, delegates={len(delegates)}",
            ),
        )


__all__ = ["BpmnDynamicClassHandler"]
