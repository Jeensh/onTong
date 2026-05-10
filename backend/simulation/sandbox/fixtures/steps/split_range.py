"""Phase 1 — step 8: 분할수 고려 단중 범위 (Java SdSplitRangeAction 미러)."""

from __future__ import annotations

from decimal import Decimal

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 8
_STEP_NAME = "SPLIT_RANGE"


def execute(order: SDOrder, slab: SDSlab) -> None:
    """splitWgtLow/High 산정.

    splitWgtLow  = max(orderWgtLow  × split / productivity, secondWgtLow)
    splitWgtHigh = min(orderWgtHigh × split / productivity, secondWgtHigh)

    공통 범위 없음 → DG108 (iteration 필요).
    """
    if slab.currentSplitCount <= 0:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            f"분할수={slab.currentSplitCount} (양수 필요)",
        )
    if order.productivity is None or order.productivity <= Decimal(0):
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            "productivity 미설정 (선행 cumulativeProductivity 호출 필요)",
        )
    if order.orderWgtLow is None or order.orderWgtHigh is None:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            "orderWgtLow/High 미설정",
        )
    if slab.secondWgtLow is None or slab.secondWgtHigh is None:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            "secondWgtLow/High 미설정 (step 5/6 선행 필요)",
        )

    split = Decimal(slab.currentSplitCount)
    productivity = order.productivity

    order_range_low = (order.orderWgtLow * split) / productivity
    order_range_high = (order.orderWgtHigh * split) / productivity

    split_wgt_low = max(order_range_low, slab.secondWgtLow)
    split_wgt_high = min(order_range_high, slab.secondWgtHigh)

    if split_wgt_low > split_wgt_high:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            f"분할수={slab.currentSplitCount} 에서 공통 단중범위 없음 "
            f"(splitLow={split_wgt_low} > splitHigh={split_wgt_high})",
        )

    slab.optimalSplitCount = slab.currentSplitCount
    slab.splitWgtLow = split_wgt_low
    slab.splitWgtHigh = split_wgt_high
