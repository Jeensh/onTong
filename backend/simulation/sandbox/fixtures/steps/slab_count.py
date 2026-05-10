"""Phase 1 — step 9: 분할수 고려 매수 산정 (Java SdSlabCountAction 미러)."""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 9
_STEP_NAME = "SLAB_COUNT"


def execute(order: SDOrder, slab: SDSlab) -> None:
    """매수 = floor(designPendQtyHigh / productivity / splitWgtHigh).

    매수 < 1 → DG108 (iteration 필요).
    """
    if order.designPendQtyHigh is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "designPendQtyHigh 미설정")
    if order.productivity is None or order.productivity <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "productivity 미설정")
    if slab.splitWgtHigh is None or slab.splitWgtHigh <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "splitWgtHigh 미설정 (step 8 선행 필요)")

    raw = order.designPendQtyHigh / order.productivity / slab.splitWgtHigh
    slab_count = int(raw.to_integral_value(rounding=ROUND_FLOOR))

    if slab_count < 1:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            f"분할수={slab.currentSplitCount} 에서 매수 < 1 (raw={raw})",
        )

    slab.slabCountInProgress = slab_count
