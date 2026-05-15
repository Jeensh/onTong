"""banking.tenant_context aspect end-to-end test — W5.5."""
from __future__ import annotations

import pytest

from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectContext,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def fresh_aspect_registry_with_banking():
    """Each test starts with a fresh registry + banking.tenant_context auto-registered.

    The autouse fixture resets the registry then triggers banking aop module
    re-registration via importlib.reload — module-level register_aspect() call
    runs again against the fresh registry.
    """
    reset_default_registry()
    import importlib
    import backend.sim_v2.plugins.banking.aop as _banking_aop
    importlib.reload(_banking_aop)
    yield
    reset_default_registry()


def test_aspect_auto_registers_on_import():
    """plugins/banking/aop/__init__.py 가 import 시 register_aspect 호출."""
    # Fresh import — ensure registration happens
    import importlib
    import backend.sim_v2.plugins.banking.aop  # noqa: F401
    importlib.reload(backend.sim_v2.plugins.banking.aop)

    reg = get_default_registry()
    aspect = reg.get_by_name("banking.tenant_context")
    assert aspect is not None
    assert aspect.aspect_kind == "banking.tenant_context"


def test_aspect_weave_emits_wrapper():
    import backend.sim_v2.plugins.banking.aop  # noqa: F401 — trigger registration

    reg = get_default_registry()
    out = reg.weave(AspectContext(
        aspect_name="banking.tenant_context",
        advice_kind="around",
        pointcut="@within(bank.annotation.TenantContext)",
        target_method={
            "class_fqn": "com.bank.UnderwritingService",
            "method_name": "underwrite",
        },
        plugin_name="banking",
    ))
    assert out.signature_locked is False
    assert "TenantContextHolder" in out.python_source
    assert "MissingTenantException" in out.python_source
    assert "underwrite" in out.python_source
    assert "UnderwritingService" in out.python_source


def test_aspect_output_includes_imports():
    import backend.sim_v2.plugins.banking.aop  # noqa: F401

    reg = get_default_registry()
    out = reg.weave(AspectContext(
        aspect_name="banking.tenant_context",
        advice_kind="around",
        target_method={"class_fqn": "Svc", "method_name": "do"},
    ))
    assert "backend.sim_v2.plugins.banking.contracts.domain_namespace" in out.imports_needed
    assert "backend.sim_v2.plugins.banking.contracts.exception" in out.imports_needed


def test_aspect_idempotent_double_import():
    """Re-import 가 idempotent — 두 번째 register 실패 silent."""
    import importlib
    import backend.sim_v2.plugins.banking.aop as banking_aop
    importlib.reload(banking_aop)
    importlib.reload(banking_aop)  # second reload should not raise

    reg = get_default_registry()
    aspect = reg.get_by_name("banking.tenant_context")
    assert aspect is not None


def test_unknown_aspect_still_signature_locked():
    """다른 aspect 는 여전히 SIGNATURE_LOCKED."""
    import backend.sim_v2.plugins.banking.aop  # noqa: F401

    reg = get_default_registry()
    out = reg.weave(AspectContext(
        aspect_name="banking.unknown_aspect",
        advice_kind="around",
        plugin_name="banking",
    ))
    assert out.signature_locked is True


def test_emitted_wrapper_is_syntactically_valid_python():
    """Emit output 의 python_source 가 valid Python 인지 확인 — exec/compile."""
    import backend.sim_v2.plugins.banking.aop  # noqa: F401

    reg = get_default_registry()
    out = reg.weave(AspectContext(
        aspect_name="banking.tenant_context",
        advice_kind="around",
        target_method={"class_fqn": "X", "method_name": "y"},
    ))
    # compile() raises SyntaxError if invalid
    compile(out.python_source, "<test>", "exec")
