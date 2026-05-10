"""slab-design Java 엔티티의 Python 미러.

`sample-repos/slab-design`의 핵심 도메인을 dataclass로 정리.
- BigDecimal → decimal.Decimal (정확한 산술 유지)
- LocalDate → datetime.date
- 컬럼명은 Java getter 명에 맞춤 (camelCase 유지)

핵심 엔티티만 포함. 21-step 알고리즘 중 데모 시나리오에 필요한 영역.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


# ─── 8 공정 ──────────────────────────────────────────────────────────

PROC_CODES: tuple[str, ...] = ("SM", "HR", "HRF", "CR", "ANL1", "ANL2", "GAL", "CRF")
"""confirmedPlantCd 8자리 위치 → 공정 약어."""

PROCESS_NAMES_KO: tuple[str, ...] = (
    "제강", "열연", "열연정정", "냉연", "1차소둔", "2차소둔", "도금", "냉연정정"
)


# ─── ORDER ───────────────────────────────────────────────────────────


@dataclass
class SDOrder:
    """ORDER_OS + ORDER_OM + ORDER_QD + ORDER_CHEMICAL 통합 작업 엔티티.

    Java: ``SDOrderEntity`` — 4 JPO를 SDOrderLogic의 reflection 매핑으로 통합.
    Python에선 통합본만 모델링 (드라마 DNA 보존이 목적이 아니므로 단순화).
    """

    # 복합 PK
    cmpCd: str
    orgCd: str
    orderNo: str

    # OS
    stockCode: int = 0
    productTypeCd: str = ""
    confirmedPlantCd: str = "        "  # 8자리, ' '=비활성

    # ORDER_OS due (8 공정)
    smDue: Optional[date] = None
    hrDue: Optional[date] = None
    hrfDue: Optional[date] = None
    crDue: Optional[date] = None
    anl1Due: Optional[date] = None
    anl2Due: Optional[date] = None
    galDue: Optional[date] = None
    crfDue: Optional[date] = None

    # OM
    workDue: Optional[date] = None
    orderWidth: Optional[Decimal] = None
    orderLength: Optional[Decimal] = None
    pkgWgtLow: Optional[Decimal] = None
    pkgWgtHigh: Optional[Decimal] = None
    orderWgtLow: Optional[Decimal] = None
    orderWgtHigh: Optional[Decimal] = None

    # QD
    designPendQty: Optional[Decimal] = None
    designPendQtyLow: Optional[Decimal] = None
    designPendQtyHigh: Optional[Decimal] = None

    # CHEMICAL
    gradeCd: str = ""
    customerCd: str = ""

    # 작업용 캐시 필드 (Phase 1 후반에 채움)
    productivity: Optional[Decimal] = None
    selectedHrTgtWidth: Optional[Decimal] = None
    specificGravity: Decimal = Decimal("7.82")

    def due_at(self, idx: int) -> Optional[date]:
        """0~7 위치 → 해당 공정 due."""
        return (
            self.smDue, self.hrDue, self.hrfDue, self.crDue,
            self.anl1Due, self.anl2Due, self.galDue, self.crfDue,
        )[idx]


# ─── SLAB (작업/결과) ────────────────────────────────────────────────


@dataclass
class SDSlab:
    """SDSlabEntity — 알고리즘 진행 중 한 Slab의 working 상태.

    A-a 루프에서 currentSplitCount/InProgress 필드들이 갱신됨.
    """

    # 진행 중 분할수 (A-a 루프)
    currentSplitCount: int = 0
    optimalSplitCount: int = 0
    maxSplitCount: int = 0
    maxSplitCountUpper: int = 0  # step 7 산정 최대분할수

    # step 1
    slabThickness: Optional[Decimal] = None

    # step 2
    firstWidthLow: Optional[Decimal] = None
    firstWidthHigh: Optional[Decimal] = None

    # step 3
    firstLengthLow: Optional[Decimal] = None
    firstLengthHigh: Optional[Decimal] = None

    # step 4 (1차 단중 — secondWgt 계산 입력. 단순화: orderWgt low/high 사용)
    firstWgtLow: Optional[Decimal] = None
    firstWgtHigh: Optional[Decimal] = None

    # step 5/6
    secondWgtLow: Optional[Decimal] = None
    secondWgtHigh: Optional[Decimal] = None

    # step 8
    splitWgtLow: Optional[Decimal] = None
    splitWgtHigh: Optional[Decimal] = None

    # step 9/10
    slabCountInProgress: int = 0
    slabWgtInProgress: Optional[Decimal] = None

    # step 16~19
    finalWidthLow: Optional[Decimal] = None
    finalWidthHigh: Optional[Decimal] = None
    finalLengthLow: Optional[Decimal] = None
    finalLengthHigh: Optional[Decimal] = None
    targetWidth: Optional[Decimal] = None
    targetLength: Optional[Decimal] = None


# ─── 기준 마스터 ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class CastSpec:
    """SD_CAST_SPEC — (회사, 소, 제강, 연주, 머신, 품종) → Slab 두께 + 폭/길이 범위.

    widthLow/High/lengthLow/High: Phase 6-A step 2/3 용. default 는 광범위 한계.
    """

    cmpCd: str
    orgCd: str
    smPlantCd: str
    castCd: str
    machineCd: str
    prodTypeCd: str
    slabThickness: Decimal
    widthLow: Decimal = Decimal("900")
    widthHigh: Decimal = Decimal("2000")
    lengthLow: Decimal = Decimal("2000")
    lengthHigh: Decimal = Decimal("13000")


@dataclass(frozen=True)
class ProductivityStd:
    """SD_PRODUCTIVITY_STD — (회사, 소, 공정, 강종, 품종, 고객) → 실수율."""

    cmpCd: str
    orgCd: str
    procCd: str
    gradeCd: str
    prodKindCd: str
    customerCd: str
    productivity: Decimal


@dataclass(frozen=True)
class PlantMapping:
    """레거시 하드코딩 매핑 (smCd → castCd, machineCd)."""

    castCd: str
    machineCd: str


# ─── Phase 6-A 추가 마스터 ──────────────────────────────────────────


@dataclass(frozen=True)
class HrSpec:
    """SD_HR_SPEC — (회사, 소, 열연, 품종) → 폭/길이 범위. step 2/3 입력."""

    cmpCd: str
    orgCd: str
    hrPlantCd: str
    prodTypeCd: str
    widthLow: Decimal
    widthHigh: Decimal
    lengthLow: Decimal
    lengthHigh: Decimal


@dataclass(frozen=True)
class HrMinWgt:
    """SD_HR_MIN_WGT — 2차원 sheet 단일 cell.

    룩업: cell.thickness ≥ input.thickness AND cell.width ≥ input.width
          ORDER BY thickness ASC, width ASC LIMIT 1
    의미: 입력값을 cover 하는 가장 작은 cell 의 minWgt 반환.
    """

    cmpCd: str
    orgCd: str
    hrCd: str
    thickness: Decimal
    width: Decimal
    minWgt: Decimal


@dataclass(frozen=True)
class HrMaxWgt:
    """SD_HR_MAX_WGT — HrMinWgt 와 동일 패턴, maxWgt 반환."""

    cmpCd: str
    orgCd: str
    hrCd: str
    thickness: Decimal
    width: Decimal
    maxWgt: Decimal


@dataclass(frozen=True)
class EdgingGroup:
    """SD_EDGING_GROUP — 매칭 row → edgingGroupCd 결정.

    조건: cmp/org/grade/product/customer 정확매칭 AND
          hrTgtWidthLow ≤ input ≤ hrTgtWidthHigh
    ORDER BY priority ASC, 첫 row.
    """

    cmpCd: str
    orgCd: str
    gradeCd: str
    prodTypeCd: str
    customerCd: str
    hrTgtWidthLow: Decimal
    hrTgtWidthHigh: Decimal
    priority: int
    edgingGroupCd: str


@dataclass(frozen=True)
class EdgingSpec:
    """SD_EDGING_SPEC — (회사, 소, 그룹코드) → 능력 하/상한.

    그룹코드 정확매칭 → 미존재 시 '*' fallback → 양쪽 다 없으면 IllegalState.
    """

    cmpCd: str
    orgCd: str
    edgingGroupCd: str  # '*' 가능
    edgingCapLow: Decimal
    edgingCapHigh: Decimal


@dataclass(frozen=True)
class CustomerStd:
    """SD_CUSTOMER_STD — 옵션 제약 (특정 고객/품종 단중 제한)."""

    cmpCd: str
    orgCd: str
    prodTypeCd: str  # '*' 가능 = 모든 품종
    customerCd: str  # '*' 가능 = 모든 고객
    pkgWgtLow: Optional[Decimal] = None
    pkgWgtHigh: Optional[Decimal] = None


class EdgingSpecMissingError(RuntimeError):
    """EDGING_SPEC 그룹코드 + '*' fallback 모두 미존재 — 데이터 정합성 이슈."""

    def __init__(self, edging_group_cd: str):
        self.edging_group_cd = edging_group_cd
        super().__init__(
            f"EDGING_SPEC not found: groupCd={edging_group_cd} AND '*' fallback both missing"
        )

    def to_json(self) -> dict:
        return {
            "step_no": 2,
            "step_name": "FIRST_WIDTH_RANGE",
            "error_code": "EDGING_SPEC_MISSING",
            "message": str(self),
            "edging_group_cd": self.edging_group_cd,
        }


# ─── 결과 ─────────────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    """SdOrderValidator의 결과."""

    passed: bool
    error_code: Optional[str] = None
    message: Optional[str] = None

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(passed=True)

    @classmethod
    def fail(cls, code: str, message: str) -> "ValidationResult":
        return cls(passed=False, error_code=code, message=message)

    def to_json(self) -> dict:
        return {"passed": self.passed, "error_code": self.error_code, "message": self.message}


# ─── 에러 ─────────────────────────────────────────────────────────────


class AlgorithmError(Exception):
    """sd-design AlgorithmException 미러."""

    def __init__(self, step_no: int, step_name: str, error_code: str, message: str):
        self.step_no = step_no
        self.step_name = step_name
        self.error_code = error_code
        self.message = message
        super().__init__(f"[step {step_no}/{step_name}] {error_code}: {message}")

    def to_json(self) -> dict:
        return {
            "step_no": self.step_no,
            "step_name": self.step_name,
            "error_code": self.error_code,
            "message": self.message,
        }


# ─── 에러코드 enum (문자열 상수) ──────────────────────────────────────


class ErrorCode:
    # Validation (DG001~005)
    VAL_STOCK_ORDER = "DG001"
    VAL_ORDER_SIZE = "DG002"
    VAL_PKG_WGT_RANGE = "DG003"
    VAL_DESIGN_PEND_QTY = "DG004"
    VAL_WORK_DUE = "DG005"

    # Algorithm (DG101~109) — Java SdErrorCode 미러
    ALG_CAST_SPEC_NOT_FOUND = "DG101"
    ALG_HR_SPEC_NOT_FOUND = "DG102"
    ALG_EDGING_GROUP_NOT_FOUND = "DG103"
    ALG_INVALID_WIDTH_RANGE = "DG104"
    ALG_INVALID_LENGTH_RANGE = "DG105"
    ALG_HR_MIN_WGT_NOT_FOUND = "DG106"
    ALG_HR_MAX_WGT_NOT_FOUND = "DG107"
    ALG_ITERATION_NEEDED = "DG108"
    ALG_DESIGN_FAILED = "DG109"

    # Legacy aliases (Phase 1 호환)
    ALG_HR_WGT_NOT_FOUND = ALG_HR_MIN_WGT_NOT_FOUND
    ALG_EDGING_SPEC_NOT_FOUND = ALG_INVALID_WIDTH_RANGE  # 미사용 (실제는 EdgingSpecMissingError)
    ALG_CUSTOMER_STD_NOT_FOUND = ALG_HR_MIN_WGT_NOT_FOUND  # 미사용 (CUSTOMER_STD 는 옵션)
    ALG_PRODUCTIVITY_NOT_FOUND = ALG_HR_MAX_WGT_NOT_FOUND  # 미사용 (default fallback)
