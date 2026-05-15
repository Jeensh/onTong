"""Broadleaf 의 namespace constants + enums.

BROADLEAF-ONBOARDING.md §2 + §5.2 — Java BLC namespace 의 Python mirror.
"""
from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    """Broadleaf 의 OrderStatus enum."""
    NAMED = "NAMED"
    IN_PROCESS = "IN_PROCESS"
    SUBMITTED = "SUBMITTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    QUOTE = "QUOTE"
    CSR_OWNED = "CSR_OWNED"


class FulfillmentType(str, Enum):
    """Fulfillment group type."""
    PHYSICAL_SHIP = "PHYSICAL_SHIP"
    DIGITAL = "DIGITAL"
    PICKUP = "PICKUP"
    GIFT_CARD = "GIFT_CARD"


class OfferDiscountType(str, Enum):
    """Offer 의 discount type."""
    PERCENT_OFF = "PERCENT_OFF"
    AMOUNT_OFF = "AMOUNT_OFF"
    FIX_PRICE = "FIX_PRICE"


class BLCConstants:
    """Broadleaf Commerce 의 namespace constants (Java BLCConstants 의 mirror).

    BROADLEAF-ONBOARDING.md §4.4 의 numeric convention (USD/EUR/GBP minor unit 2 decimal).
    """
    # Currency
    DEFAULT_CURRENCY_CODE = "USD"
    SUPPORTED_CURRENCIES = frozenset(["USD", "EUR", "GBP", "JPY", "KRW"])

    # Scale conventions (BROADLEAF-ONBOARDING.md §5.2)
    MONEY_SCALE = 2
    WEIGHT_SCALE_KG = 3
    QUANTITY_SCALE = 0
    TAX_RATE_SCALE = 5

    # Offer rule MVEL — null sentinel
    MVEL_NULL_RESULT = "__BLC_MVEL_NULL__"
