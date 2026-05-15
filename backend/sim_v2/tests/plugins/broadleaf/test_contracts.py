"""Broadleaf plugin contract test — BROADLEAF-ONBOARDING.md §5.2."""
from __future__ import annotations

from pathlib import Path

from backend.sim_v2.core.contracts.base import JavaContract, RoundingMode
from backend.sim_v2.core.plugin_loader import load_plugin
from backend.sim_v2.plugins.broadleaf.contracts.base import BroadleafContract
from backend.sim_v2.plugins.broadleaf.contracts.domain_namespace import (
    BLCConstants,
    FulfillmentType,
    OfferDiscountType,
    OrderStatus,
)
from backend.sim_v2.plugins.broadleaf.contracts.exception import (
    BroadleafException,
    CatalogException,
    OfferException,
    OrderException,
    PricingException,
)

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins" / "broadleaf"


# ─────────────────────────────────────────────────────────────────────────────
# Plugin loader integration
# ─────────────────────────────────────────────────────────────────────────────


def test_plugin_loads_via_loader():
    info = load_plugin(PLUGIN_DIR, strict=True)
    assert info.name == "broadleaf"
    assert info.manifest.fixtures.ids == ["B1", "B2", "B3", "B4", "B5"]


def test_manifest_extensions_declared():
    info = load_plugin(PLUGIN_DIR, strict=True)
    exts = info.manifest.extensions
    assert "broadleaf.factory_dispatch" in exts.dispatchers
    assert "broadleaf.configurable_handler" in exts.aop
    assert "broadleaf.dynamic_field" in exts.aop
    assert "broadleaf.dynamic_entity_dao_proxy" in exts.bytecode


# ─────────────────────────────────────────────────────────────────────────────
# BroadleafContract
# ─────────────────────────────────────────────────────────────────────────────


def test_broadleaf_contract_is_java_contract():
    c = BroadleafContract()
    assert isinstance(c, JavaContract)


def test_exception_base_is_broadleaf_exception():
    c = BroadleafContract()
    assert c.exception_base is BroadleafException


def test_exception_hierarchy():
    assert issubclass(OrderException, BroadleafException)
    assert issubclass(CatalogException, BroadleafException)
    assert issubclass(OfferException, BroadleafException)
    assert issubclass(PricingException, BroadleafException)


def test_numeric_convention_2decimal_money():
    c = BroadleafContract()
    nc = c.numeric_convention()
    assert nc.bigdecimal_precision == 10
    assert nc.bigdecimal_rounding == RoundingMode.HALF_UP
    assert nc.domain_scales["money.amount"] == 2
    assert nc.domain_scales["weight.kg"] == 3


def test_scale_for_domain():
    c = BroadleafContract()
    assert c.scale_for_domain("money.amount") == 2
    assert c.scale_for_domain("tax.rate") == 5
    assert c.scale_for_domain("unknown", fallback=99) == 99


def test_domain_namespace_exposes_enums():
    c = BroadleafContract()
    ns = c.domain_namespace()
    assert ns["BLCConstants"] is BLCConstants
    assert ns["OrderStatus"] is OrderStatus
    assert ns["FulfillmentType"] is FulfillmentType
    assert ns["OfferDiscountType"] is OfferDiscountType


def test_order_status_enum_values():
    assert OrderStatus.SUBMITTED.value == "SUBMITTED"
    assert OrderStatus.COMPLETED.value == "COMPLETED"
    assert {s.value for s in OrderStatus} >= {
        "NAMED", "IN_PROCESS", "SUBMITTED", "COMPLETED", "CANCELLED"
    }


def test_blc_constants_currency_set():
    assert "USD" in BLCConstants.SUPPORTED_CURRENCIES
    assert BLCConstants.DEFAULT_CURRENCY_CODE == "USD"
    assert BLCConstants.MONEY_SCALE == 2
