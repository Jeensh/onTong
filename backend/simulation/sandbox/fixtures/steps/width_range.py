"""Phase 6-A — step 2: 1차 설계가능 폭범위 산정 (Java SdWidthRangeAction 미러).

폭하한 = max(연주설비하한폭, 열연설비하한폭, 열연목표폭 + EDGING_능력하한)
폭상한 = min(연주설비상한폭, 열연설비상한폭, 열연목표폭 + EDGING_능력상한)

실패 코드:
  - DG102 HR_SPEC 미존재 (또는 HR 비활성)
  - DG103 EDGING_GROUP 매칭 실패
  - DG104 산정 폭 범위 invalid
  - EdgingSpecMissingError — '*' fallback 까지 미존재 (데이터 정합성 운영 이슈)
"""

from __future__ import annotations

from decimal import Decimal

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab
from ..repository import (
    CastSpecRepo,
    EdgingGroupRepo,
    EdgingSpecRepo,
    HrSpecRepo,
    PlantMappingRepo,
)

_STEP_NO = 2
_STEP_NAME = "FIRST_WIDTH_RANGE"


def execute(
    order: SDOrder,
    slab: SDSlab,
    plant_mapping: PlantMappingRepo,
    cast_spec: CastSpecRepo,
    hr_spec: HrSpecRepo,
    edging_group: EdgingGroupRepo,
    edging_spec: EdgingSpecRepo,
) -> None:
    confirmed = order.confirmedPlantCd or "        "
    if len(confirmed) < 2:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             "확정통과공장코드 8자리 형식 위반")

    sm_char = confirmed[0]
    hr_char = confirmed[1]

    # CAST_SPEC 재룩업
    if sm_char == " ":
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_CAST_SPEC_NOT_FOUND,
                             "제강 공장 비활성 (확통[0] = ' ')")
    sm_cd = sm_char
    mapping = plant_mapping.get(sm_cd)
    if mapping is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_CAST_SPEC_NOT_FOUND,
                             f"PlantMapping 미정의 for smCd={sm_cd}")
    cast = cast_spec.lookup(
        order.cmpCd, order.orgCd, sm_cd, mapping.castCd, mapping.machineCd, order.productTypeCd,
    )
    if cast is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_CAST_SPEC_NOT_FOUND,
                             f"CAST_SPEC 미존재 (sm={sm_cd}, productType={order.productTypeCd})")

    # HR_SPEC
    if hr_char == " ":
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             "열연 공장 비활성 (확통[1] = ' ')")
    hr_cd = hr_char
    hr = hr_spec.lookup(order.cmpCd, order.orgCd, hr_cd, order.productTypeCd)
    if hr is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             f"HR_SPEC 미존재 (hrPlant={hr_cd}, productType={order.productTypeCd})")

    # EDGING_GROUP
    selected_width = order.selectedHrTgtWidth
    if selected_width is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_EDGING_GROUP_NOT_FOUND,
                             "selectedHrTgtWidth 미설정 — 열연 위치 매핑 실패")
    group = edging_group.find_group(
        order.cmpCd, order.orgCd, order.gradeCd, order.productTypeCd, order.customerCd,
        selected_width,
    )
    if group is None:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_EDGING_GROUP_NOT_FOUND,
            f"EDGING_GROUP 매칭 실패 (grade={order.gradeCd}, "
            f"product={order.productTypeCd}, customer={order.customerCd}, width={selected_width})",
        )

    # EDGING_SPEC ('*' fallback, 모두 미존재 시 EdgingSpecMissingError 가 buble up)
    spec = edging_spec.find_spec(order.cmpCd, order.orgCd, group.edgingGroupCd)

    width_low = max(cast.widthLow, hr.widthLow, selected_width + spec.edgingCapLow)
    width_high = min(cast.widthHigh, hr.widthHigh, selected_width + spec.edgingCapHigh)

    if width_low > width_high:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_INVALID_WIDTH_RANGE,
            f"폭 하한({width_low}) > 상한({width_high})",
        )

    slab.firstWidthLow = width_low
    slab.firstWidthHigh = width_high
