"""Phase 6-A — step 17: 최종 slab 길이 범위 산정 (Java SdFinalLengthRangeAction 미러).

slab길이하한 = max((slabWgt × 1e6 / (finalWidthHigh × thickness × density)), firstLengthLow)
slab길이상한 = min((slabWgt × 1e6 / (finalWidthLow × thickness × density)), firstLengthHigh)
"""

from __future__ import annotations

from decimal import Decimal

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 17
_STEP_NAME = "FINAL_LENGTH_RANGE"
_INVERSE_UNIT = Decimal("1000000")


def execute(order: SDOrder, slab: SDSlab) -> None:
    required = [
        slab.slabWgtInProgress, slab.slabThickness,
        slab.firstLengthLow, slab.firstLengthHigh,
        slab.finalWidthLow, slab.finalWidthHigh,
    ]
    if any(v is None or v <= Decimal(0) for v in required):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "선행 step (3/16) 입력 누락 또는 양수 아님")
    density = order.specificGravity
    numerator = slab.slabWgtInProgress * _INVERSE_UNIT

    length_from_width_high = numerator / (slab.finalWidthHigh * slab.slabThickness * density)
    length_from_width_low = numerator / (slab.finalWidthLow * slab.slabThickness * density)

    length_low = max(length_from_width_high, slab.firstLengthLow)
    length_high = min(length_from_width_low, slab.firstLengthHigh)

    slab.finalLengthLow = length_low
    slab.finalLengthHigh = length_high
