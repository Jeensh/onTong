"""Phase 1 — 정합성 점검 (DG001~005).

Java mirror: ``slab-design/.../SdOrderValidator.java``
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..domain import ErrorCode, PROCESS_NAMES_KO, SDOrder, ValidationResult


def _is_positive(v: Decimal | None) -> bool:
    return v is not None and v > Decimal(0)


def check_stock_order(order: SDOrder) -> ValidationResult | None:
    """DG001 — 재고주문(STOCK_CODE=1) → FAIL."""
    if order.stockCode == 1:
        return ValidationResult.fail(
            ErrorCode.VAL_STOCK_ORDER, "재고주문 — 새 Slab 설계 대상 아님"
        )
    return None


def check_order_size(order: SDOrder) -> ValidationResult | None:
    """DG002 — 폭/길이 양수."""
    if not _is_positive(order.orderWidth):
        return ValidationResult.fail(
            ErrorCode.VAL_ORDER_SIZE, "주문 폭이 양수 아님 (NULL/0/음수)"
        )
    if not _is_positive(order.orderLength):
        return ValidationResult.fail(
            ErrorCode.VAL_ORDER_SIZE, "주문 길이가 양수 아님 (NULL/0/음수)"
        )
    return None


def check_pkg_wgt_range(order: SDOrder) -> ValidationResult | None:
    """DG003 — 포장단중 range integrity."""
    if not _is_positive(order.pkgWgtLow) or not _is_positive(order.pkgWgtHigh):
        return ValidationResult.fail(
            ErrorCode.VAL_PKG_WGT_RANGE, "포장 단중 하/상한이 양수 아님"
        )
    if order.pkgWgtLow > order.pkgWgtHigh:  # type: ignore[operator]
        return ValidationResult.fail(
            ErrorCode.VAL_PKG_WGT_RANGE,
            "포장 단중 하한 > 상한 (range integrity violation)",
        )
    return None


def check_design_pend_qty(order: SDOrder) -> ValidationResult | None:
    """DG004 — 설계대기량 양수 + 상한 ≥ 포장단중 하한."""
    if not _is_positive(order.designPendQty):
        return ValidationResult.fail(ErrorCode.VAL_DESIGN_PEND_QTY, "설계대기량이 양수 아님")
    if not _is_positive(order.designPendQtyHigh):
        return ValidationResult.fail(
            ErrorCode.VAL_DESIGN_PEND_QTY, "설계대기량 상한이 양수 아님"
        )
    if not _is_positive(order.designPendQtyLow):
        return ValidationResult.fail(
            ErrorCode.VAL_DESIGN_PEND_QTY, "설계대기량 하한이 양수 아님"
        )
    if order.pkgWgtLow is not None and order.designPendQtyHigh < order.pkgWgtLow:  # type: ignore[operator]
        return ValidationResult.fail(
            ErrorCode.VAL_DESIGN_PEND_QTY,
            "설계대기량 상한 < 포장단중 하한 — 설계 가능한 양이 최소 포장 단위 미만",
        )
    return None


def check_work_due(order: SDOrder, today: date | None = None) -> ValidationResult | None:
    """DG005 — 활성공정 8 due + WORK_DUE 모두 미래(today.isAfter, 즉 strict greater)."""
    today = today or date.today()
    confirmed = order.confirmedPlantCd
    if confirmed is None or len(confirmed) < 8:
        return ValidationResult.fail(
            ErrorCode.VAL_WORK_DUE, "확정통과공장코드 형식 오류 (8자리 필요)"
        )
    for i in range(8):
        if confirmed[i] == " ":
            continue
        due = order.due_at(i)
        if due is None or due <= today:  # Java: !due.isAfter(today)
            return ValidationResult.fail(
                ErrorCode.VAL_WORK_DUE,
                f"{PROCESS_NAMES_KO[i]} 작업기한일 미설정 또는 과거 날짜",
            )
    if order.workDue is None or order.workDue <= today:
        return ValidationResult.fail(
            ErrorCode.VAL_WORK_DUE, "ORDER_OM 작업기한일 미설정 또는 과거 날짜"
        )
    return None


def validate(order: SDOrder, today: date | None = None) -> ValidationResult:
    """전체 5종 short-circuit."""
    for check in (
        lambda: check_stock_order(order),
        lambda: check_order_size(order),
        lambda: check_pkg_wgt_range(order),
        lambda: check_design_pend_qty(order),
        lambda: check_work_due(order, today),
    ):
        r = check()
        if r is not None:
            return r
    return ValidationResult.ok()
