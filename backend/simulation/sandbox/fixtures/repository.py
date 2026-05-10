"""기준 마스터 in-memory 저장소.

Java의 JPA Repository 미러. dict 기반 단순 룩업.
실제 데모/테스트에서 fixtures.py가 미리 등록한 데이터를 조회.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .domain import (
    CastSpec,
    CustomerStd,
    EdgingGroup,
    EdgingSpec,
    EdgingSpecMissingError,
    HrMaxWgt,
    HrMinWgt,
    HrSpec,
    PlantMapping,
    ProductivityStd,
)

# ─── PlantMapping (레거시 하드코딩) ─────────────────────────────────

_DEFAULT_PLANT_MAPPING: dict[str, PlantMapping] = {
    "A": PlantMapping(castCd="CC1", machineCd="M1"),
    "B": PlantMapping(castCd="CC2", machineCd="M2"),
    "C": PlantMapping(castCd="CC3", machineCd="M3"),
    "D": PlantMapping(castCd="CC4", machineCd="M4"),
    "K": PlantMapping(castCd="CC1", machineCd="M1"),  # 데모 기본 (광양 K)
}


class PlantMappingRepo:
    """레거시 PlantMapping 룩업.

    Phase 6-A: PROC_MAPPING 테이블 마이그 시뮬을 위해 dict 교체 가능 + 변경 diff 비교 지원.
    """

    def __init__(self, mappings: Optional[dict[str, PlantMapping]] = None):
        self._m = dict(mappings or _DEFAULT_PLANT_MAPPING)

    def get(self, sm_cd: str) -> Optional[PlantMapping]:
        return self._m.get(sm_cd)

    def has(self, sm_cd: str) -> bool:
        return sm_cd in self._m

    def all(self) -> dict[str, PlantMapping]:
        return dict(self._m)

    @classmethod
    def default(cls) -> "PlantMappingRepo":
        return cls(_DEFAULT_PLANT_MAPPING)


# ─── CastSpec ────────────────────────────────────────────────────────


class CastSpecRepo:
    def __init__(self, rows: Optional[list[CastSpec]] = None):
        self._rows: dict[tuple, CastSpec] = {}
        for r in rows or []:
            self.add(r)

    @staticmethod
    def _key(cmp: str, org: str, sm: str, cast: str, machine: str, prod: str) -> tuple:
        return (cmp, org, sm, cast, machine, prod)

    def add(self, row: CastSpec) -> None:
        self._rows[self._key(row.cmpCd, row.orgCd, row.smPlantCd, row.castCd, row.machineCd, row.prodTypeCd)] = row

    def lookup(
        self,
        cmp_cd: str, org_cd: str, sm_cd: str, cast_cd: str, machine_cd: str, prod_type_cd: str,
    ) -> Optional[CastSpec]:
        return self._rows.get(self._key(cmp_cd, org_cd, sm_cd, cast_cd, machine_cd, prod_type_cd))


# ─── ProductivityStd ─────────────────────────────────────────────────


class ProductivityStdRepo:
    """SD_PRODUCTIVITY_STD 미러. lookup 미스 시 ProductivityService에서 default 0.95 처리."""

    DEFAULT_PRODUCTIVITY = Decimal("0.95")

    def __init__(self, rows: Optional[list[ProductivityStd]] = None):
        self._rows: dict[tuple, ProductivityStd] = {}
        for r in rows or []:
            self.add(r)

    @staticmethod
    def _key(cmp: str, org: str, proc: str, grade: str, kind: str, customer: str) -> tuple:
        return (cmp, org, proc, grade, kind, customer)

    def add(self, row: ProductivityStd) -> None:
        self._rows[self._key(row.cmpCd, row.orgCd, row.procCd, row.gradeCd, row.prodKindCd, row.customerCd)] = row

    def lookup(
        self,
        cmp_cd: str, org_cd: str, proc_cd: str,
        grade_cd: str, prod_kind_cd: str, customer_cd: str,
    ) -> Optional[Decimal]:
        row = self._rows.get(self._key(cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd))
        return row.productivity if row else None

    def lookup_or_default(
        self,
        cmp_cd: str, org_cd: str, proc_cd: str,
        grade_cd: str, prod_kind_cd: str, customer_cd: str,
    ) -> Decimal:
        v = self.lookup(cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd)
        return v if v is not None else self.DEFAULT_PRODUCTIVITY


# ─── Phase 6-A 추가 repo ────────────────────────────────────────────


class HrSpecRepo:
    """SD_HR_SPEC — 4-key composite, 정확 매칭."""

    def __init__(self, rows: Optional[list[HrSpec]] = None):
        self._rows: dict[tuple, HrSpec] = {}
        for r in rows or []:
            self.add(r)

    @staticmethod
    def _key(cmp: str, org: str, hr: str, prod: str) -> tuple:
        return (cmp, org, hr, prod)

    def add(self, row: HrSpec) -> None:
        self._rows[self._key(row.cmpCd, row.orgCd, row.hrPlantCd, row.prodTypeCd)] = row

    def lookup(self, cmp_cd: str, org_cd: str, hr_cd: str, prod_type_cd: str) -> Optional[HrSpec]:
        return self._rows.get(self._key(cmp_cd, org_cd, hr_cd, prod_type_cd))


class _Hr2DRepo:
    """HrMinWgt / HrMaxWgt 공용 2D sheet 룩업.

    cell.thickness ≥ input AND cell.width ≥ input
    ORDER BY thickness ASC, width ASC LIMIT 1
    = 입력값을 cover 하는 가장 작은 cell.
    """

    def __init__(self, rows: Optional[list] = None):
        self._rows: list = list(rows or [])

    def add(self, row) -> None:
        self._rows.append(row)

    def _candidates(self, cmp_cd: str, org_cd: str, hr_cd: str):
        return [r for r in self._rows if r.cmpCd == cmp_cd and r.orgCd == org_cd and r.hrCd == hr_cd]

    def lookup(self, cmp_cd: str, org_cd: str, hr_cd: str,
               thickness: Decimal, width: Decimal):
        matches = [
            r for r in self._candidates(cmp_cd, org_cd, hr_cd)
            if r.thickness >= thickness and r.width >= width
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: (r.thickness, r.width))
        return matches[0]


class HrMinWgtRepo(_Hr2DRepo):
    def __init__(self, rows: Optional[list[HrMinWgt]] = None):
        super().__init__(rows)


class HrMaxWgtRepo(_Hr2DRepo):
    def __init__(self, rows: Optional[list[HrMaxWgt]] = None):
        super().__init__(rows)


class EdgingGroupRepo:
    """EDGING_GROUP — 조건 매칭 + 우선순위 ASC, 첫 row 반환."""

    def __init__(self, rows: Optional[list[EdgingGroup]] = None):
        self._rows: list[EdgingGroup] = list(rows or [])

    def add(self, row: EdgingGroup) -> None:
        self._rows.append(row)

    def find_group(
        self,
        cmp_cd: str, org_cd: str,
        grade_cd: str, prod_type_cd: str, customer_cd: str,
        hr_tgt_width: Decimal,
    ) -> Optional[EdgingGroup]:
        matches = [
            r for r in self._rows
            if r.cmpCd == cmp_cd and r.orgCd == org_cd
            and r.gradeCd == grade_cd and r.prodTypeCd == prod_type_cd
            and r.customerCd == customer_cd
            and r.hrTgtWidthLow <= hr_tgt_width <= r.hrTgtWidthHigh
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: r.priority)
        return matches[0]


class EdgingSpecRepo:
    """EDGING_SPEC — 정확매칭 → '*' fallback → 양쪽 모두 미존재 시 EdgingSpecMissingError.

    Phase 6-A 핵심 시나리오: '*' fallback row 가 누락되면 알고리즘 실패. 데이터 정합성 차원에서 검출.
    """

    def __init__(self, rows: Optional[list[EdgingSpec]] = None):
        self._rows: dict[tuple, EdgingSpec] = {}
        for r in rows or []:
            self.add(r)

    @staticmethod
    def _key(cmp: str, org: str, group: str) -> tuple:
        return (cmp, org, group)

    def add(self, row: EdgingSpec) -> None:
        self._rows[self._key(row.cmpCd, row.orgCd, row.edgingGroupCd)] = row

    def find_spec(self, cmp_cd: str, org_cd: str, edging_group_cd: str) -> EdgingSpec:
        exact = self._rows.get(self._key(cmp_cd, org_cd, edging_group_cd))
        if exact is not None:
            return exact
        wildcard = self._rows.get(self._key(cmp_cd, org_cd, "*"))
        if wildcard is not None:
            return wildcard
        raise EdgingSpecMissingError(edging_group_cd)


class CustomerStdRepo:
    """CUSTOMER_STD — 옵션 제약. priority 순 첫 매칭 (정확 → '*' wildcard 허용)."""

    def __init__(self, rows: Optional[list[CustomerStd]] = None):
        self._rows: list[CustomerStd] = list(rows or [])

    def add(self, row: CustomerStd) -> None:
        self._rows.append(row)

    def find_first_match(
        self,
        cmp_cd: str, org_cd: str, prod_type_cd: str, customer_cd: str,
    ) -> Optional[CustomerStd]:
        # 정확 → 품종 '*' → 고객 '*' → 양쪽 '*' 순. 첫 매치 반환.
        priority_keys = [
            (prod_type_cd, customer_cd),
            ("*", customer_cd),
            (prod_type_cd, "*"),
            ("*", "*"),
        ]
        for prod, cust in priority_keys:
            for r in self._rows:
                if (r.cmpCd == cmp_cd and r.orgCd == org_cd
                        and r.prodTypeCd == prod and r.customerCd == cust):
                    return r
        return None
