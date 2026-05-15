"""BigDecimal / MathContext / RoundingMode mapper — Lesson 1 §4.

Phase α 의 5 KNOWN_DIVERGENCE 의 root cause: emitter 가 referent 하는 namespace 가
contract 와 미합의. 본 mapper 가 Java AST 의 BigDecimal-family API → Python 의
contract namespace (core.contracts.base) 로 1:1 변환을 강제.

Public API:
  - map_bigdecimal_method(receiver, method_name, args) -> str
  - map_static_field(class_name, field_name) -> str | None
  - REQUIRED_IMPORTS — emit 시 always-include set
"""
from __future__ import annotations

from typing import Sequence

# emitter 가 emit 한 Python source 가 의존하는 contract symbol.
# 본 set 은 emitter output 의 imports_needed 에 항상 포함.
REQUIRED_IMPORTS: tuple[str, ...] = (
    "backend.sim_v2.core.contracts.base",
)


# ─────────────────────────────────────────────────────────────────────────────
# Java BigDecimal method → Python operator/method mapping (Lesson 1 §4.1)
# ─────────────────────────────────────────────────────────────────────────────

# Java BigDecimal 의 산술 method → Python operator (Decimal 가 native 지원).
# 두번째 인자 MathContext 는 Python 의 decimal.localcontext 로 처리되지만,
# DECIMAL64 정도의 fixed precision 이면 transparent 통과 가능.
_BINARY_OP_MAP: dict[str, str] = {
    "add":      "+",
    "subtract": "-",
    "multiply": "*",
    "divide":   "/",
    "remainder": "%",
}

# Java BigDecimal comparison method → Python operator
_COMPARISON_MAP: dict[str, str] = {
    "compareTo":  "<comparison>",  # special — needs result post-processing
    "equals":     "==",
}

# Java BigDecimal 의 명시적 method → Python method (Decimal 의 method 이름이 다른 경우만 mapping).
_METHOD_RENAME: dict[str, str] = {
    "setScale":          "quantize",     # Decimal.quantize takes (Decimal, rounding=...)
    "negate":            "__neg__",      # -decimal
    "abs":               "__abs__",      # abs(decimal)
    "intValue":          "__int__",
    "doubleValue":       "__float__",
    "toString":          "__str__",
}


def is_binary_op(method_name: str) -> bool:
    return method_name in _BINARY_OP_MAP


def is_comparison(method_name: str) -> bool:
    return method_name in _COMPARISON_MAP


def binary_op_symbol(method_name: str) -> str:
    """e.g. 'add' → '+'."""
    return _BINARY_OP_MAP[method_name]


def map_bigdecimal_method(
    receiver: str,
    method_name: str,
    args: Sequence[str],
) -> str:
    """Java `receiver.method(args)` → Python expression string.

    - add/subtract/multiply/divide/remainder → binary operator
    - compareTo → expression that returns -1/0/1 sign (use python compare)
    - equals → `==`
    - setScale → `receiver.quantize(Decimal('1.' + '0'*scale), rounding=...)`
    - negate / abs → unary op
    - 알 수 없는 method → fall-through (caller logs SIGNATURE_LOCKED)
    """
    if method_name in _BINARY_OP_MAP and len(args) >= 1:
        return f"({receiver} {_BINARY_OP_MAP[method_name]} {args[0]})"

    if method_name == "compareTo" and len(args) >= 1:
        # Java compareTo returns -1/0/+1. Python: sign of difference via comparison.
        # Simple equivalent: (a > b) - (a < b)
        return f"(({receiver} > {args[0]}) - ({receiver} < {args[0]}))"

    if method_name == "equals" and len(args) >= 1:
        return f"({receiver} == {args[0]})"

    if method_name == "setScale" and len(args) >= 1:
        scale_arg = args[0]
        rounding_arg = args[1] if len(args) >= 2 else None
        if rounding_arg:
            return (
                f"bd_set_scale({receiver}, {scale_arg}, "
                f"{_translate_rounding_mode(rounding_arg)})"
            )
        return f"bd_set_scale({receiver}, {scale_arg})"

    if method_name == "negate":
        return f"(-{receiver})"

    if method_name == "abs":
        return f"abs({receiver})"

    if method_name in {"intValue", "intValueExact", "byteValue", "byteValueExact",
                       "shortValue", "shortValueExact", "longValue", "longValueExact"}:
        return f"int({receiver})"

    if method_name in {"doubleValue", "floatValue"}:
        return f"float({receiver})"

    if method_name in {"toString", "toPlainString", "toEngineeringString"}:
        return f"str({receiver})"

    if method_name == "signum":
        return f"((1 if {receiver} > 0 else 0) - (1 if {receiver} < 0 else 0))"

    if method_name == "scale":
        return f"(-{receiver}.as_tuple().exponent)"

    # Instance min/max (Java) → Python `max()` / `min()` of two values
    if method_name == "max" and len(args) >= 1:
        return f"max({receiver}, {args[0]})"
    if method_name == "min" and len(args) >= 1:
        return f"min({receiver}, {args[0]})"

    # Java BigDecimal.valueOf is normally encountered as a static call —
    # `BigDecimal.valueOf(N)` arrives here with receiver="BigDecimal".
    # Map to `Decimal(N)` (or `Decimal(str(N))` for double-precision safety
    # would be safer, but Decimal(int)/Decimal(str) already cover the cases).
    if method_name == "valueOf" and len(args) >= 1 and receiver == "BigDecimal":
        return f"Decimal({args[0]})"

    # SIGNATURE_LOCKED fall-through — caller renders as comment + signature_locked
    return f"# UNMAPPED BigDecimal.{method_name}({', '.join(args)}) on {receiver}"


# ─────────────────────────────────────────────────────────────────────────────
# Static field access (Java BigDecimal.ZERO, RoundingMode.X, MathContext.DECIMAL64)
# ─────────────────────────────────────────────────────────────────────────────


_STATIC_FIELDS: dict[tuple[str, str], str] = {
    ("BigDecimal", "ZERO"): "Decimal(0)",
    ("BigDecimal", "ONE"): "Decimal(1)",
    ("BigDecimal", "TEN"): "Decimal(10)",
    ("MathContext", "DECIMAL64"): "DECIMAL64",
    ("MathContext", "DECIMAL32"): "DECIMAL32",
    ("MathContext", "DECIMAL128"): "DECIMAL128",
    ("MathContext", "UNLIMITED"): "UNLIMITED",
}


def map_static_field(class_name: str, field_name: str) -> str | None:
    """Java `ClassName.FIELD` → Python expression, or None if unknown.

    RoundingMode.X handled separately by _translate_rounding_mode.
    """
    if class_name == "RoundingMode":
        return _translate_rounding_mode(f"RoundingMode.{field_name}")
    return _STATIC_FIELDS.get((class_name, field_name))


# ─────────────────────────────────────────────────────────────────────────────
# RoundingMode translation
# ─────────────────────────────────────────────────────────────────────────────


_ROUNDING_MODE_NAMES: frozenset[str] = frozenset({
    "HALF_EVEN", "HALF_UP", "HALF_DOWN",
    "FLOOR", "CEILING",
    "UP", "DOWN", "UNNECESSARY",
})


def _translate_rounding_mode(expr: str) -> str:
    """Translate Java RoundingMode references to contract namespace.

    'RoundingMode.HALF_UP'         → 'RoundingMode.HALF_UP'  (transparent: same name in contract)
    'java.math.RoundingMode.FLOOR' → 'RoundingMode.FLOOR'
    Other expressions returned unchanged.
    """
    expr = expr.strip()
    for prefix in ("java.math.RoundingMode.", "RoundingMode."):
        if expr.startswith(prefix):
            mode_name = expr[len(prefix):]
            if mode_name in _ROUNDING_MODE_NAMES:
                return f"RoundingMode.{mode_name}"
    return expr


# ─────────────────────────────────────────────────────────────────────────────
# BigDecimal constructor — `new BigDecimal("100")` → `Decimal("100")`
# ─────────────────────────────────────────────────────────────────────────────


def map_bigdecimal_constructor(args: Sequence[str]) -> str:
    """Java `new BigDecimal(args)` → Python `Decimal(args)`.

    BigDecimal accepts: String, int, long, double, BigInteger, char[], etc.
    Decimal accepts: similar set. Pass through args.
    """
    args_str = ", ".join(args) if args else ""
    return f"Decimal({args_str})"


__all__ = [
    "REQUIRED_IMPORTS",
    "binary_op_symbol",
    "is_binary_op",
    "is_comparison",
    "map_bigdecimal_constructor",
    "map_bigdecimal_method",
    "map_static_field",
]
