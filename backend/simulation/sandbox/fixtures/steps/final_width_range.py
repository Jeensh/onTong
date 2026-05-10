"""Phase 6-A — step 16: 최종 slab 폭 범위 산정 (Java SdFinalWidthRangeAction 미러).

slab폭하한 = ceil(slabWgtInProgress × 1e6 / (firstLengthHigh × thickness × density))
slab폭상한 = floor(slabWgtInProgress × 1e6 / (firstLengthLow × thickness × density))

단위: kg / (mm × mm × g/cm³) = mm × 1e6 → 분자에 ×1e6.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 16
_STEP_NAME = "FINAL_WIDTH_RANGE"
_INVERSE_UNIT = Decimal("1000000")


def execute(order: SDOrder, slab: SDSlab) -> None:
    if slab.slabWgtInProgress is None or slab.slabWgtInProgress <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "slabWgtInProgress 미설정 (step 11/15 선행 필요)")
    if slab.slabThickness is None or slab.slabThickness <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "slabThickness 미설정")
    if slab.firstLengthLow is None or slab.firstLengthHigh is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "firstLengthLow/High 미설정 (step 3 선행 필요)")
    density = order.specificGravity

    numerator = slab.slabWgtInProgress * _INVERSE_UNIT

    denom_low = slab.firstLengthHigh * slab.slabThickness * density
    raw_low = numerator / denom_low
    width_low = raw_low.to_integral_value(rounding=ROUND_CEILING)

    denom_high = slab.firstLengthLow * slab.slabThickness * density
    raw_high = numerator / denom_high
    width_high = raw_high.to_integral_value(rounding=ROUND_FLOOR)

    slab.finalWidthLow = width_low
    slab.finalWidthHigh = width_high
