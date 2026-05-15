"""v2 plugin contract — SlabDesignContract.

V2-MIGRATION.md §4.2 + Lesson 4 §5.1.

Phase α 의 4 module facade 의 reusable 부분을 core 상속 + slab-specific override.
"""
from __future__ import annotations

from typing import Any

from backend.sim_v2.core.contracts.base import (
    JavaContract,
    NumericConvention,
    RoundingMode,
)

from .domain_namespace import SdConstants
from .exception import AlgorithmException
from .validation import ValidationResult


class SlabDesignContract(JavaContract):
    """v2 (slab manufacturing) plugin contract.

    Lesson 4 §5.2 — generic Java contract base + slab-specific override.
    """

    @property
    def exception_base(self) -> type[Exception]:
        return AlgorithmException

    def domain_namespace(self) -> dict[str, Any]:
        return {
            "SdConstants": SdConstants,
            "ValidationResult": ValidationResult,
            "AlgorithmException": AlgorithmException,
        }

    def numeric_convention(self) -> NumericConvention:
        return NumericConvention(
            bigdecimal_precision=16,
            bigdecimal_rounding=RoundingMode.HALF_EVEN,
            domain_scales={
                "slab.weight_kg":    3,
                "slab.dimension_mm": 0,
                "productivity.rate": 6,
                "tolerance":         9,
            },
        )
