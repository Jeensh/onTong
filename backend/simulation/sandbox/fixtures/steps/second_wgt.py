"""Phase 6-A — step 5+6: 2차 설계가능 단중 하한/상한 산정.

step 5 (SdSecondWgtLowAction):
    secondWgtLow = max(firstWgtLow, custStd.pkgWgtLow?, hrMin.minWgt)
    HR_MIN_WGT 룩업 입력: (slabThickness, firstWidthLow) — 작은 폭에서 MIN 제약 적용.
    miss → DG106.

step 6 (SdSecondWgtHighAction):
    secondWgtHigh = min(firstWgtHigh, hrMax.maxWgt, designPendQtyHigh / productivity, custStd.pkgWgtHigh?)
    절대 안전한도 ABSOLUTE_MAX_KG 적용.
    miss → DG107.

★ Phase 6-A 핵심 시나리오: HR_MIN_WGT/HR_MAX_WGT 2D sheet 룩업.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab
from ..repository import CustomerStdRepo, HrMaxWgtRepo, HrMinWgtRepo

_STEP5_NO = 5
_STEP5_NAME = "SECOND_WGT_LOW"
_STEP6_NO = 6
_STEP6_NAME = "SECOND_WGT_HIGH"

# Java SdSecondWgtHighAction.ABSOLUTE_MAX_KG (2017년 회의 결정).
_ABSOLUTE_MAX_KG = Decimal("999999.999")


def execute_low(
    order: SDOrder,
    slab: SDSlab,
    hr_min_wgt: HrMinWgtRepo,
    customer_std: CustomerStdRepo,
) -> None:
    """secondWgtLow 산정 (step 5)."""
    if slab.slabThickness is None or slab.firstWidthLow is None:
        raise AlgorithmError(_STEP5_NO, _STEP5_NAME, ErrorCode.ALG_HR_MIN_WGT_NOT_FOUND,
                             "slabThickness 또는 firstWidthLow 미설정 (step 1/2 선행 필요)")

    confirmed = order.confirmedPlantCd or "  "
    hr_cd = confirmed[1] if len(confirmed) >= 2 and confirmed[1] != " " else None
    if hr_cd is None:
        raise AlgorithmError(_STEP5_NO, _STEP5_NAME, ErrorCode.ALG_HR_MIN_WGT_NOT_FOUND,
                             "열연 공장 비활성 (확통[1] = ' ')")

    min_row = hr_min_wgt.lookup(
        order.cmpCd, order.orgCd, hr_cd,
        slab.slabThickness, slab.firstWidthLow,
    )
    if min_row is None:
        raise AlgorithmError(
            _STEP5_NO, _STEP5_NAME, ErrorCode.ALG_HR_MIN_WGT_NOT_FOUND,
            f"HR_MIN_WGT 미존재 (hr={hr_cd}, thickness={slab.slabThickness}, "
            f"width={slab.firstWidthLow}) — 2D sheet 격자 외 입력값",
        )

    first_low = slab.firstWgtLow if slab.firstWgtLow is not None else (order.orderWgtLow or Decimal("0"))
    result = max(first_low, min_row.minWgt)

    cust = customer_std.find_first_match(
        order.cmpCd, order.orgCd, order.productTypeCd, order.customerCd,
    )
    if cust is not None and cust.pkgWgtLow is not None:
        result = max(result, cust.pkgWgtLow)

    slab.secondWgtLow = result


def execute_high(
    order: SDOrder,
    slab: SDSlab,
    hr_max_wgt: HrMaxWgtRepo,
    customer_std: CustomerStdRepo,
) -> None:
    """secondWgtHigh 산정 (step 6)."""
    if slab.slabThickness is None or slab.firstWidthHigh is None:
        raise AlgorithmError(_STEP6_NO, _STEP6_NAME, ErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
                             "slabThickness 또는 firstWidthHigh 미설정 (step 1/2 선행 필요)")

    confirmed = order.confirmedPlantCd or "  "
    hr_cd = confirmed[1] if len(confirmed) >= 2 and confirmed[1] != " " else None
    if hr_cd is None:
        raise AlgorithmError(_STEP6_NO, _STEP6_NAME, ErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
                             "열연 공장 비활성 (확통[1] = ' ')")

    max_row = hr_max_wgt.lookup(
        order.cmpCd, order.orgCd, hr_cd,
        slab.slabThickness, slab.firstWidthHigh,
    )
    if max_row is None:
        raise AlgorithmError(
            _STEP6_NO, _STEP6_NAME, ErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
            f"HR_MAX_WGT 미존재 (hr={hr_cd}, thickness={slab.slabThickness}, "
            f"width={slab.firstWidthHigh}) — 2D sheet 격자 외 입력값",
        )

    if order.productivity is None or order.productivity <= Decimal(0):
        raise AlgorithmError(_STEP6_NO, _STEP6_NAME, ErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
                             "productivity 미설정 (cumulative 선행 필요)")
    if order.designPendQtyHigh is None:
        raise AlgorithmError(_STEP6_NO, _STEP6_NAME, ErrorCode.ALG_HR_MAX_WGT_NOT_FOUND,
                             "designPendQtyHigh 미설정")

    yield_adjusted = order.designPendQtyHigh / order.productivity
    first_high = slab.firstWgtHigh if slab.firstWgtHigh is not None else (order.orderWgtHigh or _ABSOLUTE_MAX_KG)

    result = min(first_high, max_row.maxWgt, yield_adjusted)

    cust = customer_std.find_first_match(
        order.cmpCd, order.orgCd, order.productTypeCd, order.customerCd,
    )
    if cust is not None and cust.pkgWgtHigh is not None and cust.pkgWgtHigh > Decimal(0):
        result = min(result, cust.pkgWgtHigh)

    if result > _ABSOLUTE_MAX_KG:
        result = _ABSOLUTE_MAX_KG

    slab.secondWgtHigh = result
