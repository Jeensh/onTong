"""Phase 6-A — step 3: 1차 설계가능 길이범위 산정 (Java SdLengthRangeAction 미러).

길이하한 = max(연주설비하한길이, 열연설비하한길이)
길이상한 = min(연주설비상한길이, 열연설비상한길이)

step 2 와 달리 EDGING 미참조. 실패코드:
  - DG102 HR_SPEC 미존재 (재검증)
  - DG105 산정 길이 범위 invalid
"""

from __future__ import annotations

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab
from ..repository import CastSpecRepo, HrSpecRepo, PlantMappingRepo

_STEP_NO = 3
_STEP_NAME = "FIRST_LENGTH_RANGE"


def execute(
    order: SDOrder,
    slab: SDSlab,
    plant_mapping: PlantMappingRepo,
    cast_spec: CastSpecRepo,
    hr_spec: HrSpecRepo,
) -> None:
    confirmed = order.confirmedPlantCd or "        "
    if len(confirmed) < 2:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             "확정통과공장코드 8자리 형식 위반")

    sm_char = confirmed[0]
    hr_char = confirmed[1]

    if sm_char == " ":
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_CAST_SPEC_NOT_FOUND,
                             "제강 공장 비활성")
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

    if hr_char == " ":
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             "열연 공장 비활성")
    hr_cd = hr_char
    hr = hr_spec.lookup(order.cmpCd, order.orgCd, hr_cd, order.productTypeCd)
    if hr is None:
        raise AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_HR_SPEC_NOT_FOUND,
                             f"HR_SPEC 미존재 (length 산정 단계, hrPlant={hr_cd})")

    length_low = max(cast.lengthLow, hr.lengthLow)
    length_high = min(cast.lengthHigh, hr.lengthHigh)

    if length_low > length_high:
        raise AlgorithmError(
            _STEP_NO, _STEP_NAME, ErrorCode.ALG_INVALID_LENGTH_RANGE,
            f"길이 하한({length_low}) > 상한({length_high})",
        )

    slab.firstLengthLow = length_low
    slab.firstLengthHigh = length_high
