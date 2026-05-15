"""Broadleaf plugin extensions end-to-end tests — W6.5–W6.8.

Covers:
  - broadleaf.configurable_handler (aop)
  - broadleaf.dynamic_field (aop)
  - broadleaf.factory_dispatch (dispatcher)
  - broadleaf.dynamic_entity_dao_proxy (bytecode)
  - broadleaf.merge_annotations (annotation)
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
def reset_and_reload_broadleaf_extensions():
    """Reset all 4 registries then reload broadleaf extension modules."""
    reset_annotations()
    reset_dispatchers()
    reset_bytecode()
    reset_aop()

    import backend.sim_v2.plugins.broadleaf.annotations as _ann
    import backend.sim_v2.plugins.broadleaf.aop as _aop
    import backend.sim_v2.plugins.broadleaf.bytecode as _byt
    import backend.sim_v2.plugins.broadleaf.dispatchers as _disp
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
# W6.5a — broadleaf.configurable_handler aspect
# ─────────────────────────────────────────────────────────────────────────────


def test_configurable_handler_auto_registers():
    aspect = aop_registry().get_by_name("broadleaf.configurable_handler")
    assert aspect is not None
    assert aspect.aspect_kind == "broadleaf.configurable_handler"


def test_configurable_handler_weave_with_autowired_fields():
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.configurable_handler",
        advice_kind="after_returning",
        target_method={
            "class_fqn": "org.broadleafcommerce.catalog.Product",
            "method_name": "<class>",
        },
        aspect_args={"autowired_fields": [
            {"field_name": "catalogService", "service_class": "org.broadleaf.CatalogService"},
            {"field_name": "pricingService", "service_class": "org.broadleaf.PricingService"},
        ]},
        plugin_name="broadleaf",
    ))
    assert out.signature_locked is False
    assert "catalogService" in out.python_source
    assert "pricingService" in out.python_source
    assert "hydrate" in out.python_source
    assert "spring_di.get_bean" in out.python_source


def test_configurable_handler_no_autowired_fields_passthrough():
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.configurable_handler",
        advice_kind="after_returning",
        target_method={"class_fqn": "Product", "method_name": "<class>"},
        aspect_args={"autowired_fields": []},
    ))
    assert out.signature_locked is False
    assert "pass-through" in out.python_source.lower() or "no hydration" in out.python_source.lower()


def test_configurable_handler_emit_compiles():
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.configurable_handler",
        advice_kind="after_returning",
        target_method={"class_fqn": "X", "method_name": "<class>"},
        aspect_args={"autowired_fields": [
            {"field_name": "svc", "service_class": "Svc"},
        ]},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.5b — broadleaf.dynamic_field aspect
# ─────────────────────────────────────────────────────────────────────────────


def test_dynamic_field_auto_registers():
    aspect = aop_registry().get_by_name("broadleaf.dynamic_field")
    assert aspect is not None
    assert aspect.aspect_kind == "broadleaf.dynamic_field"


def test_dynamic_field_weave_with_declared_fields():
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.dynamic_field",
        advice_kind="around",
        target_method={"class_fqn": "org.broadleafcommerce.catalog.Product"},
        aspect_args={"dynamic_fields": ["customColor", "customSize"]},
        plugin_name="broadleaf",
    ))
    assert out.signature_locked is False
    assert "customColor" in out.python_source
    assert "customSize" in out.python_source
    assert "@property" in out.python_source


def test_dynamic_field_weave_generic_accessors():
    """No declared fields → generic get_attribute/set_attribute."""
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.dynamic_field",
        advice_kind="around",
        target_method={"class_fqn": "Product"},
        aspect_args={"dynamic_fields": []},
    ))
    assert out.signature_locked is False
    assert "get_attribute" in out.python_source
    assert "set_attribute" in out.python_source


def test_dynamic_field_emit_compiles_with_property_accessors():
    out = aop_registry().weave(AspectContext(
        aspect_name="broadleaf.dynamic_field",
        advice_kind="around",
        target_method={"class_fqn": "X"},
        aspect_args={"dynamic_fields": ["field_a", "field_b"]},
    ))
    # property accessors need to be inside a class — wrap before compile
    wrapped = f"class _Holder:\n    " + out.python_source.replace("\n", "\n    ")
    compile(wrapped, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.6 — broadleaf.factory_dispatch dispatcher
# ─────────────────────────────────────────────────────────────────────────────


def test_factory_dispatch_auto_registers():
    disp = dispatchers_registry().get_by_name("broadleaf.factory_dispatch")
    assert disp is not None
    assert disp.dispatch_kind == "broadleaf.factory_dispatch"


def test_factory_dispatch_synthesize_with_mapping():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="broadleaf.factory_dispatch",
        call_site={
            "interface_fqn": "org.broadleaf.PaymentGateway",
            "concrete_mapping": {
                "org.broadleaf.PaymentGateway": "org.broadleaf.payment.StripeGateway",
                "org.broadleaf.RefundGateway": "org.broadleaf.payment.StripeRefund",
            },
        },
        plugin_name="broadleaf",
    ))
    assert out.signature_locked is False
    assert "_BLC_FACTORY_MAPPING" in out.python_source
    assert "StripeGateway" in out.python_source
    assert "CatalogException" in out.python_source


def test_factory_dispatch_missing_interface_signature_locked():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="broadleaf.factory_dispatch",
        call_site={},
    ))
    assert out.signature_locked is True


def test_factory_dispatch_no_concrete_mapping():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="broadleaf.factory_dispatch",
        call_site={"interface_fqn": "X", "concrete_mapping": {}},
    ))
    assert out.signature_locked is False
    assert "no concrete mapping" in out.python_source.lower()


def test_factory_dispatch_emit_compiles():
    out = dispatchers_registry().synthesize(DispatchContext(
        dispatch_kind="broadleaf.factory_dispatch",
        call_site={
            "interface_fqn": "Iface",
            "concrete_mapping": {"Iface": "ConcreteA"},
        },
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.7 — broadleaf.dynamic_entity_dao_proxy bytecode
# ─────────────────────────────────────────────────────────────────────────────


def test_dynamic_entity_dao_proxy_auto_registers():
    handler = bytecode_registry().get_by_name("broadleaf.dynamic_entity_dao_proxy")
    assert handler is not None
    assert handler.pattern == "broadleaf.dynamic_entity_dao_proxy"


def test_dynamic_entity_dao_proxy_synthesize_with_entity():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="broadleaf.dynamic_entity_dao_proxy",
        target_class="org.broadleafcommerce.catalog.Product",
        pattern_args={"repository_class": "org.broadleafcommerce.catalog.ProductRepository"},
        plugin_name="broadleaf",
    ))
    assert out.signature_locked is False
    assert "ProductProxy" in out.python_source
    assert "__getattr__" in out.python_source
    assert "_load" in out.python_source


def test_dynamic_entity_dao_proxy_missing_entity_signature_locked():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="broadleaf.dynamic_entity_dao_proxy",
        target_class="",
        pattern_args={},
    ))
    assert out.signature_locked is True


def test_dynamic_entity_dao_proxy_emit_compiles():
    out = bytecode_registry().synthesize(BytecodeContext(
        pattern_name="broadleaf.dynamic_entity_dao_proxy",
        target_class="org.example.Foo",
        pattern_args={"repository_class": "FooRepo"},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# W6.8 — broadleaf.merge_annotations annotation
# ─────────────────────────────────────────────────────────────────────────────


def test_merge_annotations_auto_registers():
    handler = annotations_registry().get_by_name("broadleaf.merge_annotations")
    assert handler is not None
    assert handler.annotation_fqn == "org.broadleafcommerce.common.MergeAnnotations"


def test_merge_annotations_handle_with_parent():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="org.broadleafcommerce.common.MergeAnnotations",
        annotation_args={
            "parent": "org.broadleafcommerce.catalog.Product",
            "overrides": {"name": "OverriddenName", "active": True},
        },
        target_kind="class",
        target_metadata={"class_fqn": "com.acme.AcmeProduct"},
        plugin_name="broadleaf",
    ))
    assert out.signature_locked is False
    assert "AcmeProduct" in out.python_source
    assert "Product" in out.python_source
    assert "merge_with_parent" in out.python_source


def test_merge_annotations_missing_parent_signature_locked():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="org.broadleafcommerce.common.MergeAnnotations",
        annotation_args={"parent": ""},
        target_metadata={"class_fqn": "X"},
    ))
    assert out.signature_locked is True


def test_merge_annotations_emit_compiles():
    out = annotations_registry().handle(AnnotationContext(
        annotation_fqn="org.broadleafcommerce.common.MergeAnnotations",
        annotation_args={
            "parent": "Parent",
            "overrides": {"a": 1, "b": "x"},
        },
        target_metadata={"class_fqn": "Child"},
    ))
    compile(out.python_source, "<test>", "exec")


# ─────────────────────────────────────────────────────────────────────────────
# Cross-category — 5 extensions in 4 registries
# ─────────────────────────────────────────────────────────────────────────────


def test_all_5_broadleaf_extensions_register_in_separate_registries():
    """5 extensions sit in 4 registries (2 aspects + 1 dispatcher + 1 bytecode + 1 annotation)."""
    assert aop_registry().get_by_name("broadleaf.configurable_handler") is not None
    assert aop_registry().get_by_name("broadleaf.dynamic_field") is not None
    assert dispatchers_registry().get_by_name("broadleaf.factory_dispatch") is not None
    assert bytecode_registry().get_by_name("broadleaf.dynamic_entity_dao_proxy") is not None
    assert annotations_registry().get_by_name("broadleaf.merge_annotations") is not None


def test_double_reload_is_idempotent():
    """Idempotent re-import for all 4 broadleaf extension modules."""
    import backend.sim_v2.plugins.broadleaf.annotations as _ann
    import backend.sim_v2.plugins.broadleaf.aop as _aop
    import backend.sim_v2.plugins.broadleaf.bytecode as _byt
    import backend.sim_v2.plugins.broadleaf.dispatchers as _disp
    importlib.reload(_ann)
    importlib.reload(_aop)
    importlib.reload(_byt)
    importlib.reload(_disp)
    importlib.reload(_ann)
    importlib.reload(_aop)
    importlib.reload(_byt)
    importlib.reload(_disp)

    assert annotations_registry().get_by_name("broadleaf.merge_annotations") is not None
    assert aop_registry().get_by_name("broadleaf.dynamic_field") is not None
