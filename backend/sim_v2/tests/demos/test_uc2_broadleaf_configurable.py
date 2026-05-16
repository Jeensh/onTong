"""UC2 broadleaf @Configurable demo verification — W21.3.

Validates ADR-008 (AOP / aspect weaving) end-to-end activation:
  - Translator emits getFinalPrice with `this.field` resolved via ontology
  - broadleaf.configurable_handler aspect (W6.5) produces hydrate(self, spring_di)
  - Composition: Product class has __init__, hydrate (from aspect), getFinalPrice (translated)
  - Hydration injects @Autowired CatalogService at runtime
"""
from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from backend.sim_v2.demos.uc2_broadleaf_configurable.run import (
    CatalogService,
    Scenario,
    SpringDI,
    build_ontology_session,
    build_product_class,
    main,
    make_scenarios,
    translate_with_aspect,
)


@pytest.fixture(autouse=True)
def _ensure_broadleaf_aop_registered():
    """Reload to recover from cross-test registry resets (test_broadleaf_extensions autouse)."""
    import backend.sim_v2.plugins.broadleaf.aop as broadleaf_aop
    importlib.reload(broadleaf_aop)
    yield


def test_demo_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Translation
# ─────────────────────────────────────────────────────────────────────────────


def test_translated_method_uses_self_for_this_fields():
    session = build_ontology_session()
    method_src, _ = translate_with_aspect(session)
    # this.catalogService → self.catalogService
    assert "self.catalogService.getDiscount(self.name)" in method_src
    # this.basePrice + BigDecimal type from ontology → - operator
    assert "(self.basePrice - discount)" in method_src
    # No method-call fallback for .subtract()
    assert ".subtract(" not in method_src


def test_aspect_emits_hydrate_with_get_bean():
    session = build_ontology_session()
    _, hydrate_src = translate_with_aspect(session)
    assert "def hydrate(self, spring_di):" in hydrate_src
    assert "self.catalogService = spring_di.get_bean('CatalogService')" in hydrate_src


# ─────────────────────────────────────────────────────────────────────────────
# Composition + execution
# ─────────────────────────────────────────────────────────────────────────────


def test_product_class_has_both_methods():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    assert hasattr(Product, "getFinalPrice")
    assert hasattr(Product, "hydrate")


def test_product_starts_without_catalog_service():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    p = Product("Widget", Decimal("100"))
    assert p.catalogService is None


def test_hydrate_injects_catalog_service():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    p = Product("Widget", Decimal("100"))
    catalog = CatalogService(discounts={"Widget": Decimal("20")})
    spring_di = SpringDI(beans={"CatalogService": catalog})
    p.hydrate(spring_di)
    assert p.catalogService is catalog


def test_get_final_price_uses_hydrated_service():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    p = Product("Widget", Decimal("100"))
    p.hydrate(SpringDI(beans={"CatalogService": CatalogService({"Widget": Decimal("15")})}))
    assert p.getFinalPrice() == Decimal("85")


def test_get_final_price_with_no_matching_discount():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    p = Product("Widget", Decimal("100"))
    p.hydrate(SpringDI(beans={"CatalogService": CatalogService({})}))
    assert p.getFinalPrice() == Decimal("100")


def test_all_scenarios_pass():
    session = build_ontology_session()
    method_src, hydrate_src = translate_with_aspect(session)
    Product = build_product_class(method_src, hydrate_src)
    for scenario in make_scenarios():
        p = Product(scenario.product_name, scenario.base_price)
        spring_di = SpringDI(beans={"CatalogService": CatalogService(scenario.discounts)})
        p.hydrate(spring_di)
        actual = p.getFinalPrice()
        assert actual == scenario.expected, (
            f"{scenario.name}: got {actual}, expected {scenario.expected}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Ontology population
# ─────────────────────────────────────────────────────────────────────────────


def test_ontology_seeds_product_fields():
    """W21 — Product fields (catalogService/name/basePrice) must be in CodeFieldRow."""
    session = build_ontology_session()
    from backend.modeling.code_layer.orm import CodeFieldRow
    fields = session.query(CodeFieldRow).all()
    names = {f.name for f in fields}
    assert {"catalogService", "name", "basePrice"}.issubset(names)


# ─────────────────────────────────────────────────────────────────────────────
# G2 gate marker
# ─────────────────────────────────────────────────────────────────────────────


def test_g2_gate_adr_008_aop_covered():
    """G2 gate ADR-008 (AOP weaving) — W6.5 aspect activates here."""
    assert main() == 0
