"""Generic Java contract base — system-agnostic substrate.

ADR-002 (Two-Engine + plugin) + Lesson 4 (facade abstraction failure):
- Phase α 의 4 module facade 가 system-specific → generalization 실패
- 새 framework 의 contract = generic base + plugin override pattern

Public API:
    - JavaContract — abstract base
    - NumericConvention — Java BigDecimal / MathContext / RoundingMode 의 Python mapping
    - SpringDI / JpaRepositoryBase / TransactionBase — stub Protocol (plugin override)
    - bd_set_scale — Lesson 1 §4.1 의 runtime helper. emitter 가 referent 하는 single source of truth.
"""
from __future__ import annotations

import decimal
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, NamedTuple, Protocol


# ─────────────────────────────────────────────────────────────────────────────
# Numeric — Lesson 1 의 KNOWN_DIVERGENCE 대응
# ─────────────────────────────────────────────────────────────────────────────


class RoundingMode(str, Enum):
    """Java RoundingMode 의 Python mirror.

    Lesson 1 §4.1 — emitter 가 referent 하는 namespace class 의 contract.
    """
    HALF_EVEN = "half_even"
    HALF_UP = "half_up"
    HALF_DOWN = "half_down"
    FLOOR = "floor"
    CEILING = "ceiling"
    UP = "up"
    DOWN = "down"
    UNNECESSARY = "unnecessary"


class MathContext(NamedTuple):
    """Java MathContext 의 Python mirror.

    NamedTuple — immutable, hashable. (precision, rounding) tuple.
    """
    precision: int
    rounding: RoundingMode


# Java MathContext.DECIMAL64 — 16 significant digits, HALF_EVEN
DECIMAL64 = MathContext(precision=16, rounding=RoundingMode.HALF_EVEN)
DECIMAL32 = MathContext(precision=7, rounding=RoundingMode.HALF_EVEN)
DECIMAL128 = MathContext(precision=34, rounding=RoundingMode.HALF_EVEN)
UNLIMITED = MathContext(precision=0, rounding=RoundingMode.HALF_UP)


class NumericConvention(NamedTuple):
    """System 별 numeric convention.

    Lesson 4 §5.3 — BigDecimal scale 의 slab convention 등 system-specific 처리.
    """
    bigdecimal_precision: int
    bigdecimal_rounding: RoundingMode
    domain_scales: dict[str, int]
    # domain type → decimal places (e.g., "money.amount" → 2, "weight.kg" → 3)


# ─────────────────────────────────────────────────────────────────────────────
# Spring / JPA / TX stub Protocol
# ─────────────────────────────────────────────────────────────────────────────


class SpringDI(Protocol):
    """@Autowired / @Service / @Component injection emulator."""

    def get_bean(self, name: str) -> Any:
        ...

    def inject(self, target: Any) -> None:
        ...


class JpaRepositoryBase(Protocol):
    """Generic JPA Repository emulator — find/save/delete."""

    def find_by_id(self, entity_class: type, id_value: Any) -> Any | None:
        ...

    def find_all(self, entity_class: type) -> list[Any]:
        ...

    def save(self, entity: Any) -> Any:
        ...

    def delete(self, entity: Any) -> None:
        ...


class TransactionBase(Protocol):
    """@Transactional propagation emulator."""

    def begin(self, propagation: str = "REQUIRED") -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# JavaContract — abstract base
# ─────────────────────────────────────────────────────────────────────────────


class JavaContract(ABC):
    """Plugin contract abstract base — ADR-002.

    각 plugin 이 subclass + system-specific override.
    Lesson 4 §6.1 의 generic Java contract base.
    """

    @property
    @abstractmethod
    def exception_base(self) -> type[Exception]:
        """System 의 root exception type."""
        ...

    @abstractmethod
    def domain_namespace(self) -> dict[str, Any]:
        """System-specific namespace constants.

        Lesson 1 §4.1 — namespace class 의 first-class contract.
        예: v2 의 SdConstants, banking 의 TenantContext.
        """
        ...

    @abstractmethod
    def numeric_convention(self) -> NumericConvention:
        """System 별 numeric scale 결정."""
        ...

    # ─────────────────────────────────────────────────────────────────────
    # Default impl — plugin override 가능
    # ─────────────────────────────────────────────────────────────────────

    def default_math_context(self) -> MathContext:
        conv = self.numeric_convention()
        return MathContext(
            precision=conv.bigdecimal_precision,
            rounding=conv.bigdecimal_rounding,
        )

    def scale_for_domain(self, domain_key: str, fallback: int = 2) -> int:
        return self.numeric_convention().domain_scales.get(domain_key, fallback)


# ─────────────────────────────────────────────────────────────────────────────
# Runtime helpers — Lesson 1 §4.1
# ─────────────────────────────────────────────────────────────────────────────


# Java RoundingMode → Python decimal module constant string.
_DECIMAL_ROUNDING_MODE: dict[RoundingMode, str] = {
    RoundingMode.HALF_EVEN:    decimal.ROUND_HALF_EVEN,
    RoundingMode.HALF_UP:      decimal.ROUND_HALF_UP,
    RoundingMode.HALF_DOWN:    decimal.ROUND_HALF_DOWN,
    RoundingMode.FLOOR:        decimal.ROUND_FLOOR,
    RoundingMode.CEILING:      decimal.ROUND_CEILING,
    RoundingMode.UP:           decimal.ROUND_UP,
    RoundingMode.DOWN:         decimal.ROUND_DOWN,
    RoundingMode.UNNECESSARY:  decimal.ROUND_HALF_EVEN,  # decimal lacks UNNECESSARY; default HALF_EVEN
}


def bd_set_scale(
    value: Decimal,
    scale: int,
    mode: RoundingMode = RoundingMode.HALF_UP,
) -> Decimal:
    """Java `value.setScale(scale, mode)` 의 Python equivalent.

    Lesson 1 §4.1: emitter 가 referent 하는 namespace 의 first-class artifact.
    Java RoundingMode 의 lowercase value 를 Python decimal 의 ROUND_* 상수로 매핑.
    """
    py_mode = _DECIMAL_ROUNDING_MODE.get(mode, decimal.ROUND_HALF_UP)
    if scale >= 0:
        quantizer = Decimal(1).scaleb(-scale)
    else:
        quantizer = Decimal(1).scaleb(-scale)
    return value.quantize(quantizer, rounding=py_mode)


__all__ = [
    "DECIMAL128",
    "DECIMAL32",
    "DECIMAL64",
    "JavaContract",
    "JpaRepositoryBase",
    "MathContext",
    "NumericConvention",
    "RoundingMode",
    "SpringDI",
    "TransactionBase",
    "UNLIMITED",
    "bd_set_scale",
]
