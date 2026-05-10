"""Phase 6-A — step 18+19: 목표 slab 폭/길이 계산 (Java SdTargetWidth/LengthAction 미러).

step 18 (target_width):
    raw = ceil_to_10mm(splitWgtHigh × 1e6 / (finalLengthHigh × thickness × density))
    raw 가 [finalWidthLow, finalWidthHigh] 벗어나면 → finalWidthLow

step 19 (target_length):
    raw = floor(slabWgtInProgress × 1e6 / (targetWidth × thickness × density))
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 18
_STEP_NAME = "TARGET_SLAB_SIZE"
_INVERSE_UNIT = Decimal("1000000")
_TEN_MM = Decimal("10")


def execute(order: SDOrder, slab: SDSlab) -> None:
    """step 18 + 19 통합 실행 (target width 결정 → 그에 맞춰 target length)."""
    required = [
        slab.slabWgtInProgress, slab.splitWgtHigh, slab.slabThickness,
        slab.finalLengthLow, slab.finalLengthHigh,
        slab.finalWidthLow, slab.finalWidthHigh,
    ]
    if any(v is None or v <= Decimal(0) for v in required):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "선행 step (10/16/17) 입력 누락 또는 양수 아님")
    density = order.specificGravity

    # step 18 — target width
    raw_w = (slab.splitWgtHigh * _INVERSE_UNIT) / (slab.finalLengthHigh * slab.slabThickness * density)
    rounded_w = (raw_w / _TEN_MM).to_integral_value(rounding=ROUND_CEILING) * _TEN_MM
    if rounded_w < slab.finalWidthLow or rounded_w > slab.finalWidthHigh:
        target_w = slab.finalWidthLow
    else:
        target_w = rounded_w
    slab.targetWidth = target_w

    # step 19 — target length
    raw_l = (slab.slabWgtInProgress * _INVERSE_UNIT) / (slab.targetWidth * slab.slabThickness * density)
    target_l = raw_l.to_integral_value(rounding=ROUND_FLOOR)
    slab.targetLength = target_l
