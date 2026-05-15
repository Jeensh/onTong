"""BroadleafContract — plugin contract for Broadleaf Commerce community v6.x.

BROADLEAF-ONBOARDING.md §5.2 + Lesson 4 §5.1.
"""
from __future__ import annotations

from typing import Any

from backend.sim_v2.core.contracts.base import (
    JavaContract,
    NumericConvention,
    RoundingMode,
)

from .domain_namespace import BLCConstants, FulfillmentType, OfferDiscountType, OrderStatus
from .exception import (
    BroadleafException,
    CatalogException,
    OfferException,
    OrderException,
    PricingException,
)


class BroadleafContract(JavaContract):
    """Broadleaf Commerce (community) plugin contract.

    BROADLEAF-ONBOARDING.md §1.3 — core / cart / order / pricing / offer / profile / framework 만 scope.
    admin / cms / workflow / integration 은 SIGNATURE_LOCKED (M-D4).
    """

    @property
    def exception_base(self) -> type[Exception]:
        return BroadleafException

    def domain_namespace(self) -> dict[str, Any]:
        return {
            "BLCConstants":       BLCConstants,
            "OrderStatus":        OrderStatus,
            "FulfillmentType":    FulfillmentType,
            "OfferDiscountType":  OfferDiscountType,
            "BroadleafException": BroadleafException,
            "OrderException":     OrderException,
            "CatalogException":   CatalogException,
            "OfferException":     OfferException,
            "PricingException":   PricingException,
        }

    def numeric_convention(self) -> NumericConvention:
        return NumericConvention(
            bigdecimal_precision=10,
            bigdecimal_rounding=RoundingMode.HALF_UP,
            domain_scales={
                "money.amount":    BLCConstants.MONEY_SCALE,        # 2 (USD, EUR, GBP minor unit)
                "weight.kg":       BLCConstants.WEIGHT_SCALE_KG,     # 3
                "quantity":        BLCConstants.QUANTITY_SCALE,      # 0 (integer)
                "tax.rate":        BLCConstants.TAX_RATE_SCALE,      # 5
                "offer.percent":   4,
            },
        )
