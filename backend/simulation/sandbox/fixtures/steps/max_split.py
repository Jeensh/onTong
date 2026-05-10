"""Phase 6-A — step 7: 최대분할수 산정 (Java SdMaxSplitCountAction 미러).

maxSplitCountUpper = ceil(secondWgtHigh / orderWgtHigh / productivity)

산정 결과 ≤ 0 이면 DG108 (분할 불가).
A-a 루프는 currentSplitCount = maxSplitCountUpper 부터 1 씩 감소.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab

_STEP_NO = 7
_STEP_NAME = "MAX_SPLIT_COUNT"


def execute(order: SDOrder, slab: SDSlab) -> None:
    if slab.secondWgtHigh is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "secondWgtHigh 미설정 (step 6 선행 필요)")
    if order.orderWgtHigh is None or order.orderWgtHigh <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "orderWgtHigh 미설정")
    if order.productivity is None or order.productivity <= Decimal(0):
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
                             "productivity 미설정")

    raw = slab.secondWgtHigh / order.orderWgtHigh / order.productivity
    max_split = int(raw.to_integral_value(rounding=ROUND_CEILING))

    if max_split < 1:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_ITERATION_NEEDED,
            f"최대분할수상한 < 1 (raw={raw}) — 분할 불가",
        )

    slab.maxSplitCountUpper = max_split
    slab.currentSplitCount = max_split  # A-a 루프 시작점
