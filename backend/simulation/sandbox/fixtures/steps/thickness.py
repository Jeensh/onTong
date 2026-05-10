"""Phase 1 — step 1: Slab 두께 결정 (Java SdThicknessAction 미러)."""

from __future__ import annotations

from ..domain import AlgorithmError, ErrorCode, SDOrder, SDSlab
from ..repository import CastSpecRepo, PlantMappingRepo

_STEP_NO = 1
_STEP_NAME = "SLAB_THICKNESS"


def _fail(message: str) -> AlgorithmError:
    return AlgorithmError(_STEP_NO, _STEP_NAME, ErrorCode.ALG_CAST_SPEC_NOT_FOUND, message)


def execute(
    order: SDOrder,
    slab: SDSlab,
    plant_mapping: PlantMappingRepo,
    cast_spec: CastSpecRepo,
) -> None:
    """confirmedPlantCd[0] → smCd → mapping → CastSpec → slabThickness."""
    confirmed = order.confirmedPlantCd
    if confirmed is None or confirmed == "":
        raise _fail("확정통과공장코드 미설정")
    sm_char = confirmed[0]
    if sm_char == " ":
        raise _fail("제강 공장 비활성 (확통[0] = ' ')")
    sm_cd = sm_char

    mapping = plant_mapping.get(sm_cd)
    if mapping is None:
        raise _fail(f"PlantMapping 미정의 for smCd={sm_cd}")

    spec = cast_spec.lookup(
        order.cmpCd, order.orgCd, sm_cd, mapping.castCd, mapping.machineCd, order.productTypeCd,
    )
    if spec is None:
        raise _fail(
            f"CAST_SPEC 미존재 (sm={sm_cd}, cast={mapping.castCd}, machine={mapping.machineCd}, "
            f"productType={order.productTypeCd})"
        )
    if spec.slabThickness is None:
        raise _fail("CAST_SPEC.SLAB_THICKNESS NULL")

    slab.slabThickness = spec.slabThickness
