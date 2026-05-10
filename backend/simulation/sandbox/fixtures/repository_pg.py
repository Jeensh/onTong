"""PostgreSQL backed Repo 9종 — `repository.py` in-memory 버전과 동일한 public 인터페이스.

각 클래스는 in-memory 버전을 상속하지 않고 별개로 구현 (SQL 쿼리 명시화).
도메인 dataclass 인스턴스를 반환하여 호출부가 in-memory 버전과 동일하게 사용 가능.

활성화 조건: `SIMULATION_DATABASE_URL` 또는 `SIM_DB_HOST` 환경변수 + psycopg 설치.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from backend.simulation.storage.postgres.connection import get_connection

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


# ─── PlantMapping (sm_cd 단일키) ───────────────────────────────────────


class PlantMappingPgRepo:
    def get(self, sm_cd: str) -> Optional[PlantMapping]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT cast_cd, machine_cd FROM plant_mapping WHERE sm_cd = %s",
                (sm_cd,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return PlantMapping(castCd=row["cast_cd"], machineCd=row["machine_cd"])

    def has(self, sm_cd: str) -> bool:
        return self.get(sm_cd) is not None

    def all(self) -> dict[str, PlantMapping]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT sm_cd, cast_cd, machine_cd FROM plant_mapping")
            rows = cur.fetchall()
        return {
            r["sm_cd"]: PlantMapping(castCd=r["cast_cd"], machineCd=r["machine_cd"])
            for r in rows
        }


# ─── CastSpec (6-key 정확 매칭) ────────────────────────────────────────


class CastSpecPgRepo:
    def lookup(
        self,
        cmp_cd: str, org_cd: str, sm_cd: str, cast_cd: str, machine_cd: str, prod_type_cd: str,
    ) -> Optional[CastSpec]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM cast_spec
                   WHERE cmp_cd=%s AND org_cd=%s AND sm_plant_cd=%s
                     AND cast_cd=%s AND machine_cd=%s AND prod_type_cd=%s""",
                (cmp_cd, org_cd, sm_cd, cast_cd, machine_cd, prod_type_cd),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return CastSpec(
            cmpCd=r["cmp_cd"], orgCd=r["org_cd"], smPlantCd=r["sm_plant_cd"],
            castCd=r["cast_cd"], machineCd=r["machine_cd"], prodTypeCd=r["prod_type_cd"],
            slabThickness=r["slab_thickness"],
            widthLow=r["width_low"], widthHigh=r["width_high"],
            lengthLow=r["length_low"], lengthHigh=r["length_high"],
        )


# ─── ProductivityStd (6-key 정확 + default 0.95) ──────────────────────


class ProductivityStdPgRepo:
    DEFAULT_PRODUCTIVITY = Decimal("0.95")

    def lookup(
        self,
        cmp_cd: str, org_cd: str, proc_cd: str,
        grade_cd: str, prod_kind_cd: str, customer_cd: str,
    ) -> Optional[Decimal]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT productivity FROM productivity_std
                   WHERE cmp_cd=%s AND org_cd=%s AND proc_cd=%s
                     AND grade_cd=%s AND prod_kind_cd=%s AND customer_cd=%s""",
                (cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd),
            )
            r = cur.fetchone()
        return r["productivity"] if r else None

    def lookup_or_default(
        self,
        cmp_cd: str, org_cd: str, proc_cd: str,
        grade_cd: str, prod_kind_cd: str, customer_cd: str,
    ) -> Decimal:
        v = self.lookup(cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd)
        return v if v is not None else self.DEFAULT_PRODUCTIVITY


# ─── HrSpec (4-key 정확) ───────────────────────────────────────────────


class HrSpecPgRepo:
    def lookup(self, cmp_cd: str, org_cd: str, hr_cd: str, prod_type_cd: str) -> Optional[HrSpec]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM hr_spec
                   WHERE cmp_cd=%s AND org_cd=%s AND hr_plant_cd=%s AND prod_type_cd=%s""",
                (cmp_cd, org_cd, hr_cd, prod_type_cd),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return HrSpec(
            cmpCd=r["cmp_cd"], orgCd=r["org_cd"],
            hrPlantCd=r["hr_plant_cd"], prodTypeCd=r["prod_type_cd"],
            widthLow=r["width_low"], widthHigh=r["width_high"],
            lengthLow=r["length_low"], lengthHigh=r["length_high"],
        )


# ─── Hr2D (HrMinWgt / HrMaxWgt 공용) ──────────────────────────────────


class _Hr2DPgRepo:
    """`thickness ≥ %s AND width ≥ %s ORDER BY thickness ASC, width ASC LIMIT 1`."""

    _TABLE: str
    _VALUE_COL: str
    _DOMAIN_CLS: type

    def lookup(
        self, cmp_cd: str, org_cd: str, hr_cd: str, thickness: Decimal, width: Decimal,
    ):
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"""SELECT cmp_cd, org_cd, hr_cd, thickness, width, {self._VALUE_COL}
                    FROM {self._TABLE}
                    WHERE cmp_cd=%s AND org_cd=%s AND hr_cd=%s
                      AND thickness >= %s AND width >= %s
                    ORDER BY thickness ASC, width ASC
                    LIMIT 1""",
                (cmp_cd, org_cd, hr_cd, thickness, width),
            )
            r = cur.fetchone()
        if r is None:
            return None
        kwargs = {
            "cmpCd": r["cmp_cd"], "orgCd": r["org_cd"], "hrCd": r["hr_cd"],
            "thickness": r["thickness"], "width": r["width"],
        }
        # minWgt / maxWgt 별 키
        if self._VALUE_COL == "min_wgt":
            kwargs["minWgt"] = r[self._VALUE_COL]
        else:
            kwargs["maxWgt"] = r[self._VALUE_COL]
        return self._DOMAIN_CLS(**kwargs)


class HrMinWgtPgRepo(_Hr2DPgRepo):
    _TABLE = "hr_min_wgt"
    _VALUE_COL = "min_wgt"
    _DOMAIN_CLS = HrMinWgt


class HrMaxWgtPgRepo(_Hr2DPgRepo):
    _TABLE = "hr_max_wgt"
    _VALUE_COL = "max_wgt"
    _DOMAIN_CLS = HrMaxWgt


# ─── EdgingGroup (조건 매칭 + priority ASC) ───────────────────────────


class EdgingGroupPgRepo:
    def find_group(
        self,
        cmp_cd: str, org_cd: str,
        grade_cd: str, prod_type_cd: str, customer_cd: str,
        hr_tgt_width: Decimal,
    ) -> Optional[EdgingGroup]:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM edging_group
                   WHERE cmp_cd=%s AND org_cd=%s
                     AND grade_cd=%s AND prod_type_cd=%s AND customer_cd=%s
                     AND hr_tgt_width_low  <= %s
                     AND hr_tgt_width_high >= %s
                   ORDER BY priority ASC
                   LIMIT 1""",
                (cmp_cd, org_cd, grade_cd, prod_type_cd, customer_cd, hr_tgt_width, hr_tgt_width),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return EdgingGroup(
            cmpCd=r["cmp_cd"], orgCd=r["org_cd"],
            gradeCd=r["grade_cd"], prodTypeCd=r["prod_type_cd"], customerCd=r["customer_cd"],
            hrTgtWidthLow=r["hr_tgt_width_low"], hrTgtWidthHigh=r["hr_tgt_width_high"],
            priority=r["priority"], edgingGroupCd=r["edging_group_cd"],
        )


# ─── EdgingSpec (정확 → '*' fallback → MissingError) ──────────────────


class EdgingSpecPgRepo:
    def find_spec(self, cmp_cd: str, org_cd: str, edging_group_cd: str) -> EdgingSpec:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM edging_spec
                   WHERE cmp_cd=%s AND org_cd=%s
                     AND edging_group_cd IN (%s, '*')
                   ORDER BY (CASE WHEN edging_group_cd = %s THEN 0 ELSE 1 END) ASC
                   LIMIT 1""",
                (cmp_cd, org_cd, edging_group_cd, edging_group_cd),
            )
            r = cur.fetchone()
        if r is None:
            raise EdgingSpecMissingError(edging_group_cd)
        return EdgingSpec(
            cmpCd=r["cmp_cd"], orgCd=r["org_cd"],
            edgingGroupCd=r["edging_group_cd"],
            edgingCapLow=r["edging_cap_low"], edgingCapHigh=r["edging_cap_high"],
        )


# ─── CustomerStd (4 우선순위 키 순회) ─────────────────────────────────


class CustomerStdPgRepo:
    def find_first_match(
        self,
        cmp_cd: str, org_cd: str, prod_type_cd: str, customer_cd: str,
    ) -> Optional[CustomerStd]:
        # 정확 → 품종 '*' → 고객 '*' → 양쪽 '*' 순. 첫 매칭 priority ASC 행.
        priority_keys = [
            (prod_type_cd, customer_cd),
            ("*", customer_cd),
            (prod_type_cd, "*"),
            ("*", "*"),
        ]
        with get_connection() as conn, conn.cursor() as cur:
            for prod, cust in priority_keys:
                cur.execute(
                    """SELECT * FROM customer_std
                       WHERE cmp_cd=%s AND org_cd=%s
                         AND product_name_cd=%s AND customer_cd=%s
                       ORDER BY priority ASC
                       LIMIT 1""",
                    (cmp_cd, org_cd, prod, cust),
                )
                r = cur.fetchone()
                if r:
                    return CustomerStd(
                        cmpCd=r["cmp_cd"], orgCd=r["org_cd"],
                        prodTypeCd=r["product_name_cd"], customerCd=r["customer_cd"],
                        pkgWgtLow=r["pkg_wgt_low"], pkgWgtHigh=r["pkg_wgt_high"],
                    )
        return None
