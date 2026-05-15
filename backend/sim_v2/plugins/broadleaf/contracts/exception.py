"""Broadleaf domain exception hierarchy.

BROADLEAF-ONBOARDING.md §5.2 — exception_base.
"""
from __future__ import annotations


class BroadleafException(Exception):
    """Root exception for Broadleaf plugin (Java BroadleafException 의 mirror)."""


class OrderException(BroadleafException):
    """Order processing exception."""


class CatalogException(BroadleafException):
    """Catalog (product/sku/category) exception."""


class OfferException(BroadleafException):
    """Offer / OfferRule evaluation exception (incl. MVEL eval failure)."""


class PricingException(BroadleafException):
    """Pricing workflow activity exception."""
