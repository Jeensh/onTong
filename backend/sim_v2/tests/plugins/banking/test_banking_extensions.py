"""Banking plugin extensions end-to-end tests — W6.1–W6.4.

Covers:
  - banking.compensable (annotation)
  - banking.drools_kbase_lookup (dispatcher)
  - banking.bpmn_dynamic_class (bytecode)
  - banking.audit (aop)
"""
from __future__ import annotations

import importlib

import pytest

from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    reset_default_registry as reset_annotations,
)
from backend.sim_v2.core.synthesizer.annotations.registry import (
    get_default_registry as annotations_registry,
)
from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectContext,
    reset_default_registry as reset_aop,
)
from backend.sim_v2.core.synthesizer.aop.registry import (
    get_default_registry as aop_registry,
)
from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    reset_default_registry as reset_bytecode,
)
from backend.sim_v2.core.synthesizer.bytecode.registry import (
    get_default_registry as bytecode_registry,
)
from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    reset_default_registry as reset_dispatchers,
)
from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    get_default_registry as dispatchers_registry,
)


@pytest.fixture(autouse=True)
def reset_and_reload_banking_extensions():
    """Reset all 4 registries then reload banking extension modules.

    Module-level register_* calls re-execute against the fresh registries.
    """
    reset_annotations()
    reset_dispatchers()
    reset_bytecode()
    reset_aop()

    import backend.sim_v2.plugins.banking.annotations as _ann
    import backend.sim_v2.plugins.banking.aop as _aop
    import backend.sim_v2.plugins.banking.bytecode as _byt
    import backend.sim_v2.plugins.banking.dispatchers as _disp
    importlib.reload(_ann)
    importlib.reload(_aop)
    importlib.reload(_byt)
    importlib.reload(_disp)

    yield

    reset_annotations()
    reset_dispatchers()
    reset_bytecode()
    reset_aop()


# ─────────────────────────────────────────────────────────────────────────────
# W6.1 — banking.compensable annotation
# ─────────────────────────────────────────────────────────────────────────────


def test_compensable_auto_registers():
    handler = annotations_registry().get_by_name("banking.compensable")
    assert handler is not None
    assert handler.annotation_fqn == "bank.annotation.Compensable"


def test_compensable_handle_emits_wrapper():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        annotation_args={"compensationMethod": "refundCharge"},
        target_kind="method",
        target_metadata={
            "class_fqn": "com.bank.LoanService",
            "method_name": "approve",
        },
        plugin_name="banking",
    ))
    assert out.signature_locked is False
    assert "refundCharge" in out.python_source
    assert "SagaCompensatedException" in out.python_source
    assert "approve" in out.python_source


def test_compensable_missing_compensation_method_signature_locked():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        annotation_args={},
        target_metadata={"class_fqn": "X", "method_name": "y"},
    ))
    assert out.signature_locked is True


def test_compensable_emit_compiles():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        annotation_args={"compensationMethod": "rollback"},
        target_metadata={"class_fqn": "Svc", "method_name": "do"},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.2 — banking.drools_kbase_lookup dispatcher
# ─────────────────────────────────────────────────────────────────────────────


def test_drools_kbase_auto_registers():
    disp = dispatchers_registry().get_by_name("banking.drools_kbase_lookup")
    assert disp is not None
    assert disp.dispatch_kind == "banking.drools_kbase_lookup"


def test_drools_kbase_synthesize_with_rules():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={
            "kbase_name": "loan-approval-kbase",
            "rules": [
                {"name": "credit_too_low", "lhs": "applicant.credit_score < 500",
                 "rhs": "decision = 'DECLINED'"},
                {"name": "loan_too_large", "lhs": "loan.amount > 1_000_000",
                 "rhs": "decision = 'ESCALATE'"},
            ],
        },
        plugin_name="banking",
    ))
    assert out.signature_locked is False
    assert "loan-approval-kbase" in out.python_source
    assert "credit_too_low" in out.python_source
    assert "loan_too_large" in out.python_source
    assert "DECLINED" in out.python_source


def test_drools_kbase_missing_name_signature_locked():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={},
    ))
    assert out.signature_locked is True


def test_drools_kbase_empty_rules():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"kbase_name": "empty-kbase", "rules": []},
    ))
    assert out.signature_locked is False
    assert "APPROVED" in out.python_source  # default fallthrough


def test_drools_kbase_emit_compiles():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"kbase_name": "test", "rules": [
            {"name": "r1", "lhs": "x > 0", "rhs": "decision = 'YES'"},
        ]},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.3 — banking.bpmn_dynamic_class bytecode
# ─────────────────────────────────────────────────────────────────────────────


def test_bpmn_dynamic_class_auto_registers():
    handler = bytecode_registry().get_by_name("banking.bpmn_dynamic_class")
    assert handler is not None
    assert handler.pattern == "banking.bpmn_dynamic_class"


def test_bpmn_dynamic_class_synthesize_with_delegates():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={
            "process_id": "loan-app-v1",
            "delegates": {
                "submit-task": "com.bank.SubmitDelegate",
                "review-task": "com.bank.ReviewDelegate",
            },
        },
        plugin_name="banking",
    ))
    assert out.signature_locked is False
    assert "loan-app-v1" in out.python_source
    assert "submit-task" in out.python_source
    assert "review-task" in out.python_source
    assert "BpmnDeploymentException" in out.python_source
    # Regression: emitted source must actually compile as valid Python (nested
    # f-string + repr quoting can silently produce SyntaxError otherwise).
    g: dict = {
        "com_bank_SubmitDelegate": type("com_bank_SubmitDelegate", (), {}),
        "com_bank_ReviewDelegate": type("com_bank_ReviewDelegate", (), {}),
    }
    exec(compile(out.python_source, "<test-bpmn>", "exec"), g)
    assert callable(g["lookup_bpmn_delegate"])


def test_bpmn_dynamic_class_missing_process_id_signature_locked():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={},
    ))
    assert out.signature_locked is True


def test_bpmn_dynamic_class_empty_delegates():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={"process_id": "no-tasks", "delegates": {}},
    ))
    assert out.signature_locked is False
    assert "no-tasks" in out.python_source.lower() or "NO_TASKS" in out.python_source


def test_bpmn_dynamic_class_emit_with_empty_delegates_compiles():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        pattern_args={"process_id": "proc-1", "delegates": {}},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.4 — banking.audit aspect
# ─────────────────────────────────────────────────────────────────────────────


def test_audit_auto_registers():
    aspect = aop_registry().get_by_name("banking.audit")
    assert aspect is not None
    assert aspect.aspect_kind == "banking.audit"


def test_audit_weave_emits_wrapper():
    out = aop_registry().weave(AspectContext(
        aspect_name="banking.audit",
        advice_kind="around",
        target_method={
            "class_fqn": "com.bank.LoanService",
            "method_name": "approve",
        },
        plugin_name="banking",
    ))
    assert out.signature_locked is False
    assert "approve" in out.python_source
    assert "LoanService" in out.python_source
    assert "outcome" in out.python_source
    assert "TenantContextHolder" in out.python_source


def test_audit_emit_compiles():
    out = aop_registry().weave(AspectContext(
        aspect_name="banking.audit",
        advice_kind="around",
        target_method={"class_fqn": "Svc", "method_name": "do"},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# Cross-category — independence & idempotency
# ─────────────────────────────────────────────────────────────────────────────


def test_all_4_banking_extensions_register_in_separate_registries():
    """4 extensions sit in 4 separate registries — no bleed."""
    assert annotations_registry().get_by_name("banking.compensable") is not None
    assert dispatchers_registry().get_by_name("banking.drools_kbase_lookup") is not None
    assert bytecode_registry().get_by_name("banking.bpmn_dynamic_class") is not None
    assert aop_registry().get_by_name("banking.audit") is not None
    # tenant_context (W5.5) also still registered in aop
    assert aop_registry().get_by_name("banking.tenant_context") is not None


def test_double_reload_is_idempotent():
    """Idempotent re-import — module-level register_* skips on existing entry."""
    import backend.sim_v2.plugins.banking.annotations as _ann
    import backend.sim_v2.plugins.banking.aop as _aop
    import backend.sim_v2.plugins.banking.bytecode as _byt
    import backend.sim_v2.plugins.banking.dispatchers as _disp
    importlib.reload(_ann)
    importlib.reload(_aop)
    importlib.reload(_byt)
    importlib.reload(_disp)
    # second reload — should be no-op (idempotent guard)
    importlib.reload(_ann)
    importlib.reload(_aop)
    importlib.reload(_byt)
    importlib.reload(_disp)

    assert annotations_registry().get_by_name("banking.compensable") is not None
    assert aop_registry().get_by_name("banking.audit") is not None
