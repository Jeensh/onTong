"""데모/테스트용 미리 채워진 mock 데이터.

실제 운영값이 아니라 알고리즘 실행이 가능한 최소 데이터.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from .domain import (
    CastSpec,
    CustomerStd,
    EdgingGroup,
    EdgingSpec,
    HrMaxWgt,
    HrMinWgt,
    HrSpec,
    ProductivityStd,
    SDOrder,
    SDSlab,
)
from .repository import (
    CastSpecRepo,
    CustomerStdRepo,
    EdgingGroupRepo,
    EdgingSpecRepo,
    HrMaxWgtRepo,
    HrMinWgtRepo,
    HrSpecRepo,
    PlantMappingRepo,
    ProductivityStdRepo,
)


def make_default_order(
    *,
    cmpCd: str = "K", orgCd: str = "K01", orderNo: str = "ORD-DEMO-001",
    confirmedPlantCd: str = "K K K   ",  # SM, HRF, ANL1 활성 (3 공정만 — 데모용)
    productTypeCd: str = "A001",
    gradeCd: str = "G01",
    customerCd: str = "C001",
) -> SDOrder:
    """validator + algorithm 통과하는 표준 주문."""
    today = date.today()
    future = today + timedelta(days=30)
    return SDOrder(
        cmpCd=cmpCd,
        orgCd=orgCd,
        orderNo=orderNo,
        stockCode=0,
        productTypeCd=productTypeCd,
        confirmedPlantCd=confirmedPlantCd,
        smDue=future,
        hrDue=future,
        hrfDue=future,
        crDue=future,
        anl1Due=future,
        anl2Due=future,
        galDue=future,
        crfDue=future,
        workDue=future,
        orderWidth=Decimal("1200"),
        orderLength=Decimal("3000"),
        pkgWgtLow=Decimal("5"),
        pkgWgtHigh=Decimal("30"),
        orderWgtLow=Decimal("8"),
        orderWgtHigh=Decimal("25"),
        designPendQty=Decimal("100"),
        designPendQtyLow=Decimal("50"),
        designPendQtyHigh=Decimal("150"),
        gradeCd=gradeCd,
        customerCd=customerCd,
    )


def make_default_slab() -> SDSlab:
    """A-a 루프 진입 시점의 빈 Slab."""
    return SDSlab(
        currentSplitCount=1,
        maxSplitCount=5,
        secondWgtLow=Decimal("8"),
        secondWgtHigh=Decimal("25"),
    )


def make_default_plant_mapping() -> PlantMappingRepo:
    return PlantMappingRepo()  # default mapping 사용 (A-D + K)


def make_default_cast_spec() -> CastSpecRepo:
    return CastSpecRepo([
        CastSpec(
            cmpCd="K", orgCd="K01",
            smPlantCd="K", castCd="CC1", machineCd="M1",
            prodTypeCd="A001",
            slabThickness=Decimal("220"),
        ),
        CastSpec(
            cmpCd="K", orgCd="K01",
            smPlantCd="K", castCd="CC1", machineCd="M1",
            prodTypeCd="B002",
            slabThickness=Decimal("250"),
        ),
        CastSpec(
            cmpCd="K", orgCd="K01",
            smPlantCd="A", castCd="CC1", machineCd="M1",
            prodTypeCd="A001",
            slabThickness=Decimal("210"),
        ),
    ])


def make_step2_order(**overrides) -> SDOrder:
    """step 2 (width_range) 이상에서 사용. confirmedPlantCd[1]=HR 활성 + 열연 목표폭 설정."""
    base = make_default_order(**overrides)
    base.confirmedPlantCd = "KKKK    "  # SM/HR/HRF/CR 활성
    base.selectedHrTgtWidth = Decimal("1200")  # 열연 목표폭 (step 2 입력)
    return base


def make_default_productivity_std(
    *,
    hr_productivity: Decimal = Decimal("0.95"),
    hrf_productivity: Decimal = Decimal("0.93"),
    anl1_productivity: Decimal = Decimal("0.92"),
) -> ProductivityStdRepo:
    """시나리오 5에서 hr_productivity 값을 0.92로 바꿔 영향도 측정."""
    return ProductivityStdRepo([
        ProductivityStd(
            cmpCd="K", orgCd="K01", procCd="HR",
            gradeCd="G01", prodKindCd="A001", customerCd="C001",
            productivity=hr_productivity,
        ),
        ProductivityStd(
            cmpCd="K", orgCd="K01", procCd="HRF",
            gradeCd="G01", prodKindCd="A001", customerCd="C001",
            productivity=hrf_productivity,
        ),
        ProductivityStd(
            cmpCd="K", orgCd="K01", procCd="ANL1",
            gradeCd="G01", prodKindCd="A001", customerCd="C001",
            productivity=anl1_productivity,
        ),
    ])


# ─── Phase 6-A 추가 fixtures ────────────────────────────────────────


def make_default_hr_spec() -> HrSpecRepo:
    """K 광양 + A001 품종에 대한 HR_SPEC."""
    return HrSpecRepo([
        HrSpec(
            cmpCd="K", orgCd="K01", hrPlantCd="K", prodTypeCd="A001",
            widthLow=Decimal("1000"), widthHigh=Decimal("1600"),
            lengthLow=Decimal("2000"), lengthHigh=Decimal("12000"),
        ),
        HrSpec(
            cmpCd="K", orgCd="K01", hrPlantCd="K", prodTypeCd="B002",
            widthLow=Decimal("1100"), widthHigh=Decimal("1500"),
            lengthLow=Decimal("2500"), lengthHigh=Decimal("11000"),
        ),
    ])


def make_default_hr_min_wgt() -> HrMinWgtRepo:
    """2D sheet — (thickness, width) 격자별 minWgt.

    실제 운영표는 작은 폭/얇은 두께 → 큰 minWgt (롤링 한계).
    데모: thickness 200/220/250 × width 1200/1500/1800 격자.
    """
    rows: list[HrMinWgt] = []
    grid = [
        # (thickness, width, minWgt)
        (Decimal("200"), Decimal("1200"), Decimal("12")),
        (Decimal("200"), Decimal("1500"), Decimal("10")),
        (Decimal("200"), Decimal("1800"), Decimal("8")),
        (Decimal("220"), Decimal("1200"), Decimal("11")),
        (Decimal("220"), Decimal("1500"), Decimal("9")),
        (Decimal("220"), Decimal("1800"), Decimal("7")),
        (Decimal("250"), Decimal("1200"), Decimal("10")),
        (Decimal("250"), Decimal("1500"), Decimal("8")),
        (Decimal("250"), Decimal("1800"), Decimal("6")),
    ]
    for t, w, mw in grid:
        rows.append(HrMinWgt(
            cmpCd="K", orgCd="K01", hrCd="K",
            thickness=t, width=w, minWgt=mw,
        ))
    return HrMinWgtRepo(rows)


def make_default_hr_max_wgt() -> HrMaxWgtRepo:
    """2D sheet — (thickness, width) 격자별 maxWgt."""
    rows: list[HrMaxWgt] = []
    grid = [
        (Decimal("200"), Decimal("1200"), Decimal("28")),
        (Decimal("200"), Decimal("1500"), Decimal("32")),
        (Decimal("200"), Decimal("1800"), Decimal("36")),
        (Decimal("220"), Decimal("1200"), Decimal("30")),
        (Decimal("220"), Decimal("1500"), Decimal("34")),
        (Decimal("220"), Decimal("1800"), Decimal("38")),
        (Decimal("250"), Decimal("1200"), Decimal("32")),
        (Decimal("250"), Decimal("1500"), Decimal("36")),
        (Decimal("250"), Decimal("1800"), Decimal("40")),
    ]
    for t, w, mw in grid:
        rows.append(HrMaxWgt(
            cmpCd="K", orgCd="K01", hrCd="K",
            thickness=t, width=w, maxWgt=mw,
        ))
    return HrMaxWgtRepo(rows)


def make_default_edging_group() -> EdgingGroupRepo:
    """EDGING_GROUP — 데모용 priority 1, 2 두 row.

    priority 1 = customer-specific (C001 + 1100~1300)
    priority 2 = generic (catchall 1000~1600)
    """
    return EdgingGroupRepo([
        EdgingGroup(
            cmpCd="K", orgCd="K01",
            gradeCd="G01", prodTypeCd="A001", customerCd="C001",
            hrTgtWidthLow=Decimal("1100"), hrTgtWidthHigh=Decimal("1300"),
            priority=1, edgingGroupCd="EDG-NARROW",
        ),
        EdgingGroup(
            cmpCd="K", orgCd="K01",
            gradeCd="G01", prodTypeCd="A001", customerCd="C001",
            hrTgtWidthLow=Decimal("1000"), hrTgtWidthHigh=Decimal("1600"),
            priority=2, edgingGroupCd="EDG-GENERIC",
        ),
    ])


def make_default_edging_spec(*, include_wildcard: bool = True) -> EdgingSpecRepo:
    """EDGING_SPEC — 그룹별 능력 + '*' fallback.

    include_wildcard=False → '*' row 없음. 매칭 못한 그룹코드에서 EdgingSpecMissingError 발생.
    Phase 6-A 데이터 정합성 시뮬에 사용.
    """
    rows = [
        EdgingSpec(
            cmpCd="K", orgCd="K01", edgingGroupCd="EDG-NARROW",
            edgingCapLow=Decimal("-50"), edgingCapHigh=Decimal("80"),
        ),
        EdgingSpec(
            cmpCd="K", orgCd="K01", edgingGroupCd="EDG-GENERIC",
            edgingCapLow=Decimal("-30"), edgingCapHigh=Decimal("100"),
        ),
    ]
    if include_wildcard:
        rows.append(EdgingSpec(
            cmpCd="K", orgCd="K01", edgingGroupCd="*",
            edgingCapLow=Decimal("-20"), edgingCapHigh=Decimal("60"),
        ))
    return EdgingSpecRepo(rows)


def make_default_customer_std() -> CustomerStdRepo:
    """CUSTOMER_STD — 옵션 제약. 데모는 비어있고 필요 시 add."""
    return CustomerStdRepo()
