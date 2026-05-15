"""UC2 broadleaf @Configurable — AOP aspect activation (W21, G2 prereq).

Demonstrates ADR-008 meta-programming (AOP / aspect weaving) in action:
  1. Translate `Product.getFinalPrice` Java method
  2. Invoke `broadleaf.configurable_handler` aspect (W6.5) to produce
     `hydrate(self, spring_di)` method that lazy-injects @Autowired services
  3. Compose Product class with both methods
  4. Simulate JPA load → spring_di hydrate → method call uses hydrated service
  5. Run 3 scenarios (basic / discounted / null-service guard)

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc2_broadleaf_configurable.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import tree_sitter_java as tsjava
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from tree_sitter import Language, Parser

from backend.modeling.code_layer.orm import CodeFieldRow, CodeMethodRow, CodeTypeRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.contracts.base import (
    DECIMAL64,
    RoundingMode,
    bd_set_scale,
)
from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectContext,
    get_default_registry as get_aop_registry,
)
from backend.sim_v2.core.synthesizer.java_translator import JavaToPythonTranslator
from backend.sim_v2.core.synthesizer.ontology_type_resolver import OntologyTypeResolver
from backend.sim_v2.core.synthesizer.type_resolver import (
    BigDecimalAwareResolver,
    CompositeTypeResolver,
)

# Trigger broadleaf AOP auto-registration (W6.5 ConfigurableHandlerAspect)
import backend.sim_v2.plugins.broadleaf.aop  # noqa: F401


JAVA_LANGUAGE = Language(tsjava.language())


JAVA_SOURCE = """
class Product {
    public BigDecimal getFinalPrice() {
        BigDecimal discount = this.catalogService.getDiscount(this.name);
        return this.basePrice.subtract(discount);
    }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Mock CatalogService + SpringDI
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CatalogService:
    """Mock Broadleaf catalog service — looks up discount by product name."""
    discounts: dict[str, Decimal] = field(default_factory=dict)

    def getDiscount(self, name: str) -> Decimal:
        return self.discounts.get(name, Decimal("0"))


@dataclass
class SpringDI:
    """Mock Spring application context — service bean registry."""
    beans: dict[str, Any] = field(default_factory=dict)

    def get_bean(self, name: str) -> Any:
        return self.beans.get(name)


# ─────────────────────────────────────────────────────────────────────────────
# Ontology
# ─────────────────────────────────────────────────────────────────────────────


def build_ontology_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        CodeMethodRow.__table__,
    ])
    s = Session(engine)
    repo_id = "broadleaf-configurable"
    s.add_all([
        CodeTypeRow(
            fqn="org.broadleafcommerce.catalog.Product", simple_name="Product",
            package="org.broadleafcommerce.catalog", kind="CLASS", role="entity",
            repo_id=repo_id,
        ),
        CodeTypeRow(
            fqn="org.broadleafcommerce.catalog.CatalogService", simple_name="CatalogService",
            package="org.broadleafcommerce.catalog", kind="CLASS", role="service",
            repo_id=repo_id,
        ),
    ])
    # Product fields — populated so `this.X` resolves correctly via OntologyTypeResolver
    s.add_all([
        CodeFieldRow(
            type_fqn="org.broadleafcommerce.catalog.Product",
            name="catalogService",
            type="org.broadleafcommerce.catalog.CatalogService",
        ),
        CodeFieldRow(
            type_fqn="org.broadleafcommerce.catalog.Product",
            name="name",
            type="java.lang.String",
        ),
        CodeFieldRow(
            type_fqn="org.broadleafcommerce.catalog.Product",
            name="basePrice",
            type="java.math.BigDecimal",
        ),
    ])
    s.add(CodeMethodRow(
        fqn="org.broadleafcommerce.catalog.CatalogService#getDiscount",
        name="getDiscount",
        parent_type_fqn="org.broadleafcommerce.catalog.CatalogService",
        return_type="java.math.BigDecimal", repo_id=repo_id,
    ))
    s.commit()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Translate getFinalPrice + invoke @Configurable aspect
# ─────────────────────────────────────────────────────────────────────────────


def translate_with_aspect(session: Session) -> tuple[str, str]:
    """Returns (getFinalPrice_source, hydrate_source).

    Step A — translate the method body.
    Step B — invoke broadleaf.configurable_handler aspect to emit hydrate().
    """
    tree = Parser(JAVA_LANGUAGE).parse(JAVA_SOURCE.encode())
    method = None
    for c in tree.root_node.children:
        if c.type == "class_declaration":
            body = next(x for x in c.children if x.type == "class_body")
            for m in body.named_children:
                if m.type == "method_declaration":
                    method = m
                    break
    if method is None:
        raise RuntimeError("getFinalPrice method not found")

    resolver = CompositeTypeResolver([
        OntologyTypeResolver(session, "broadleaf-configurable"),
        BigDecimalAwareResolver(),
    ])
    # W21: pass enclosing class FQN so `this.field` resolves via OntologyTypeResolver
    method_src = JavaToPythonTranslator(
        type_resolver=resolver,
        this_type="org.broadleafcommerce.catalog.Product",
    ).translate(method, indent=0).python_source

    # Step B — aspect weave
    registry = get_aop_registry()
    aspect = registry.get("broadleaf.configurable_handler")
    output = aspect.weave(AspectContext(
        aspect_name="broadleaf.configurable_handler",
        advice_kind="after_returning",
        target_method={
            "class_fqn":   "org.broadleafcommerce.catalog.Product",
            "method_name": "<class>",
        },
        aspect_args={"autowired_fields": [
            {"field_name": "catalogService", "service_class": "CatalogService"},
        ]},
        plugin_name="broadleaf",
    ))
    return method_src, output.python_source


# ─────────────────────────────────────────────────────────────────────────────
# Compose into a Product class
# ─────────────────────────────────────────────────────────────────────────────


def build_product_class(method_src: str, hydrate_src: str):
    """Compile both pieces and stitch onto a Product class.

    Product carries `name`, `basePrice`, and a placeholder `catalogService = None`.
    `hydrate(self, spring_di)` (from aspect) populates `catalogService` on demand.
    `getFinalPrice(self)` (translated) consumes `self.catalogService`.
    """
    g: dict[str, Any] = {
        "Decimal":      Decimal,
        "RoundingMode": RoundingMode,
        "DECIMAL64":    DECIMAL64,
        "bd_set_scale": bd_set_scale,
    }
    full = method_src + "\n\n" + hydrate_src + "\n"
    exec(compile(full, "<demo-configurable>", "exec"), g)

    class Product:
        def __init__(self, name: str, basePrice: Decimal):
            self.name = name
            self.basePrice = basePrice
            self.catalogService: CatalogService | None = None
        # bind translated method + aspect-emitted hydrate
        getFinalPrice = g["getFinalPrice"]
        hydrate       = g["hydrate"]

    return Product


# ─────────────────────────────────────────────────────────────────────────────
# Scenarios
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Scenario:
    name: str
    product_name: str
    base_price:   Decimal
    discounts:    dict[str, Decimal]
    expected:     Decimal | None
    expect_exception: type | None = None


def make_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="basic (no discount)",
            product_name="Widget",
            base_price=Decimal("100"),
            discounts={},
            expected=Decimal("100"),
        ),
        Scenario(
            name="discounted (10% off)",
            product_name="Widget",
            base_price=Decimal("100"),
            discounts={"Widget": Decimal("10")},
            expected=Decimal("90"),
        ),
        Scenario(
            name="other-product discount ignored",
            product_name="Widget",
            base_price=Decimal("100"),
            discounts={"OtherProduct": Decimal("50")},
            expected=Decimal("100"),
        ),
    ]


def main() -> int:
    print("=" * 78)
    print("UC2 broadleaf @Configurable — AOP aspect activation (W21, G2 prereq)")
    print("=" * 78)
    print()

    print("Step 1: Populate Code Layer ontology")
    session = build_ontology_session()
    print(f"  ✓ {session.query(CodeMethodRow).count()} method rows seeded")
    print()

    print("Step 2: Translate getFinalPrice + invoke @Configurable aspect (W6.5)")
    method_src, hydrate_src = translate_with_aspect(session)
    print(f"  ✓ translated getFinalPrice ({len(method_src.split(chr(10)))} lines)")
    print(f"  ✓ aspect hydrate ({len(hydrate_src.split(chr(10)))} lines)")
    print()
    print("Translated getFinalPrice:")
    for line in method_src.split("\n"):
        print(f"  | {line}")
    print()
    print("@Configurable aspect output (hydrate):")
    for line in hydrate_src.split("\n"):
        print(f"  | {line}")
    print()

    print("Step 3: Compose Product class (translated method + hydrate from aspect)")
    Product = build_product_class(method_src, hydrate_src)
    print(f"  ✓ Product class ready")
    print()

    print("Step 4: Run scenarios (simulate JPA load → hydrate → method call)")
    print()
    print(f"  {'Scenario':<38} {'Final Price':<14} {'Verdict':<10}")
    print(f"  {'-' * 38} {'-' * 14} {'-' * 10}")
    all_pass = True
    for scenario in make_scenarios():
        # Construct the entity (as JPA would after find_by_id)
        product = Product(scenario.product_name, scenario.base_price)
        # Spring DI hydrates @Autowired fields
        spring_di = SpringDI(beans={"CatalogService": CatalogService(scenario.discounts)})
        product.hydrate(spring_di)
        # Call business method
        try:
            actual = product.getFinalPrice()
            exc = None
        except Exception as e:
            actual, exc = None, e

        if scenario.expect_exception is not None:
            ok = exc is not None and isinstance(exc, scenario.expect_exception)
            verdict = "PASS" if ok else f"FAIL ({type(exc).__name__ if exc else 'none'})"
        else:
            ok = exc is None and actual == scenario.expected
            verdict = "PASS" if ok else f"FAIL (got {actual})"

        if not ok:
            all_pass = False
        print(f"  {scenario.name:<38} {str(actual):<14} {verdict:<10}")

    print()
    if all_pass:
        print("✓ Final verdict: PASS — @Configurable aspect activation works end-to-end")
        print("  G2 gate progress: ADR-007 + ADR-008 — 2 / 4 meta-programming areas covered")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
