"""4-category extension registries test — ADR-013 §2 (W5.4).

Covers: dispatchers / annotations / aop / bytecode.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    AnnotationHandlerBase,
    AnnotationOutput,
    AnnotationRegistry,
    reset_default_registry as reset_annotations,
)
from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectBase,
    AspectContext,
    AspectOutput,
    AspectRegistry,
    reset_default_registry as reset_aop,
)
from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    BytecodeHandlerBase,
    BytecodeOutput,
    BytecodeRegistry,
    reset_default_registry as reset_bytecode,
)
from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    DispatchOutput,
    DispatcherBase,
    DispatcherRegistry,
    reset_default_registry as reset_dispatchers,
)


@pytest.fixture(autouse=True)
def reset_all_registries():
    yield
    reset_dispatchers()
    reset_annotations()
    reset_aop()
    reset_bytecode()


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────


class _FakeDispatcher(DispatcherBase):
    name = "test.fake_dispatch"
    dispatch_kind = "test.fake_dispatch"

    def synthesize(self, context: DispatchContext) -> DispatchOutput:
        return DispatchOutput(python_source=f"# dispatched {context.dispatch_kind}")


def test_dispatcher_register_and_synthesize():
    reg = DispatcherRegistry()
    reg.register(_FakeDispatcher())
    out = reg.synthesize(DispatchContext(dispatch_kind="test.fake_dispatch"))
    assert "dispatched" in out.python_source
    assert out.signature_locked is False


def test_dispatcher_unknown_kind_signature_locked():
    reg = DispatcherRegistry()
    out = reg.synthesize(DispatchContext(dispatch_kind="banking.drools_kbase_lookup", plugin_name="banking"))
    assert out.signature_locked is True
    assert "banking" in out.python_source


def test_dispatcher_name_conflict():
    reg = DispatcherRegistry()
    reg.register(_FakeDispatcher())
    with pytest.raises(ValueError, match="name conflict"):
        reg.register(_FakeDispatcher())


def test_dispatcher_kind_conflict():
    reg = DispatcherRegistry()
    reg.register(_FakeDispatcher())

    class _Conflict(DispatcherBase):
        name = "test.other"
        dispatch_kind = "test.fake_dispatch"
        def synthesize(self, ctx):
            return DispatchOutput(python_source="")

    with pytest.raises(ValueError, match="dispatch_kind conflict"):
        reg.register(_Conflict())


def test_dispatcher_missing_kind():
    reg = DispatcherRegistry()

    class _MissingKind(DispatcherBase):
        name = "test.broken"
        dispatch_kind = ""
        def synthesize(self, ctx):
            return DispatchOutput(python_source="")

    with pytest.raises(ValueError, match="must define .dispatch_kind"):
        reg.register(_MissingKind())


# ─────────────────────────────────────────────────────────────────────────────
# Annotation
# ─────────────────────────────────────────────────────────────────────────────


class _FakeAnnotationHandler(AnnotationHandlerBase):
    name = "test.compensable"
    annotation_fqn = "bank.annotation.Compensable"

    def handle(self, context: AnnotationContext) -> AnnotationOutput:
        return AnnotationOutput(
            python_source=f"# @Compensable wrap {context.target_metadata.get('method', '?')}"
        )


def test_annotation_register_and_handle():
    reg = AnnotationRegistry()
    reg.register(_FakeAnnotationHandler())
    out = reg.handle(AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        target_metadata={"method": "execute"},
    ))
    assert "execute" in out.python_source


def test_annotation_unknown_signature_locked():
    reg = AnnotationRegistry()
    out = reg.handle(AnnotationContext(annotation_fqn="banking.compensable", plugin_name="banking"))
    assert out.signature_locked is True


def test_annotation_conflict():
    reg = AnnotationRegistry()
    reg.register(_FakeAnnotationHandler())

    # name conflict (same name + same fqn) caught first
    with pytest.raises(ValueError, match="annotation handler name conflict"):
        reg.register(_FakeAnnotationHandler())

    # fqn conflict (different name, same fqn)
    class _DiffName(AnnotationHandlerBase):
        name = "test.compensable_v2"
        annotation_fqn = "bank.annotation.Compensable"
        def handle(self, ctx):
            return AnnotationOutput(python_source="")

    with pytest.raises(ValueError, match="annotation_fqn conflict"):
        reg.register(_DiffName())


# ─────────────────────────────────────────────────────────────────────────────
# Aspect
# ─────────────────────────────────────────────────────────────────────────────


class _FakeAspect(AspectBase):
    name = "test.audit_log"
    aspect_kind = "test.audit_log"

    def weave(self, context: AspectContext) -> AspectOutput:
        return AspectOutput(python_source=f"# {context.advice_kind} audit_log")


def test_aspect_register_and_weave():
    reg = AspectRegistry()
    reg.register(_FakeAspect())
    out = reg.weave(AspectContext(aspect_name="test.audit_log", advice_kind="around"))
    assert "around" in out.python_source


def test_aspect_unknown_signature_locked():
    reg = AspectRegistry()
    out = reg.weave(AspectContext(aspect_name="banking.tenant_context", advice_kind="around", plugin_name="banking"))
    assert out.signature_locked is True


def test_aspect_get_by_name():
    reg = AspectRegistry()
    aspect = _FakeAspect()
    reg.register(aspect)
    assert reg.get_by_name("test.audit_log") is aspect
    assert reg.get_by_name("nonexistent") is None


# ─────────────────────────────────────────────────────────────────────────────
# Bytecode
# ─────────────────────────────────────────────────────────────────────────────


class _FakeBytecodeHandler(BytecodeHandlerBase):
    name = "test.cglib_proxy"
    pattern = "test.cglib_proxy"

    def synthesize(self, context: BytecodeContext) -> BytecodeOutput:
        return BytecodeOutput(python_source=f"# proxy for {context.target_class}")


def test_bytecode_register_and_synthesize():
    reg = BytecodeRegistry()
    reg.register(_FakeBytecodeHandler())
    out = reg.synthesize(BytecodeContext(pattern_name="test.cglib_proxy", target_class="com.example.Foo"))
    assert "com.example.Foo" in out.python_source


def test_bytecode_unknown_signature_locked():
    reg = BytecodeRegistry()
    out = reg.synthesize(BytecodeContext(pattern_name="banking.bpmn_dynamic_class", plugin_name="banking"))
    assert out.signature_locked is True


# ─────────────────────────────────────────────────────────────────────────────
# Independence — 4 registries don't bleed between each other
# ─────────────────────────────────────────────────────────────────────────────


def test_registries_independent():
    """4 registry 가 각자 isolated."""
    disp = DispatcherRegistry()
    ann = AnnotationRegistry()
    aop = AspectRegistry()
    byt = BytecodeRegistry()

    disp.register(_FakeDispatcher())
    assert disp.count() == 1
    assert ann.count() == 0
    assert aop.count() == 0
    assert byt.count() == 0
