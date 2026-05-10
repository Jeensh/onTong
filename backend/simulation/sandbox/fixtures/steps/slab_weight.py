"""Phase 1 — step 10: 초기 Slab 단중 + 설계대기량 만족 점검 (Java SdInitialSlabWgtAction 미러)."""

from __future__ import annotations

from decimal import Decimal

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 10
_STEP_NAME = "INITIAL_SLAB_WGT"


def execute(order: SDOrder, slab: SDSlab) -> None:
    """slab단중 = splitWgtHigh.

    설계대기량 만족? = (slab단중 × 매수) ∈ (designPendQtyLow/productivity ~ designPendQtyHigh/productivity)
    NO → DG108 (iteration).
    """
    if slab.splitWgtHigh is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "splitWgtHigh 미설정 (step 8 선행 필요)")
    if slab.slabCountInProgress <= 0:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "slabCountInProgress 미설정 (step 9 선행 필요)")
    if order.productivity is None or order.productivity <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "productivity 미설정")
    if order.designPendQtyLow is None or order.designPendQtyHigh is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "designPendQty 범위 미설정")

    slab_wgt = slab.splitWgtHigh
    slab.slabWgtInProgress = slab_wgt

    slab_count = Decimal(slab.slabCountInProgress)
    total_produced = slab_wgt * slab_count

    yield_low = order.designPendQtyLow / order.productivity
    yield_high = order.designPendQtyHigh / order.productivity

    if not (yield_low <= total_produced <= yield_high):
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            f"step 10 NO branch — 분할수={slab.currentSplitCount}, "
            f"totalProduced={total_produced}, "
            f"실수율고려 설계대기량 범위=[{yield_low}, {yield_high}] — iteration 필요",
        )
