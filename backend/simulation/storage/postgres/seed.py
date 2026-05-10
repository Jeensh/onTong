"""마스터 데이터 + 샘플 주문 시드.

`fixtures.py` 의 default 데이터와 동일 내용을 PG 에 INSERT.
멱등 — 호출 전 TRUNCATE 후 INSERT (또는 ON CONFLICT DO UPDATE).

사용:
    from backend.simulation.storage.postgres.migrate import apply_schema, reset_schema
    from backend.simulation.storage.postgres.seed import seed_all
    apply_schema()
    seed_all()  # → 9 마스터 + 샘플 주문 5건
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Sequence

from backend.simulation.sandbox.fixtures import fixtures as fx
from backend.simulation.sandbox.fixtures.domain import SDOrder
from backend.simulation.storage.postgres.connection import get_connection
from backend.simulation.storage.postgres.migrate import apply_schema, reset_schema


# ─── 마스터 데이터 시드 ────────────────────────────────────────────────


def _seed_plant_mapping(cur) -> int:
    repo = fx.make_default_plant_mapping()
    rows = [(sm_cd, m.castCd, m.machineCd) for sm_cd, m in repo.all().items()]
    cur.executemany(
        "INSERT INTO plant_mapping (sm_cd, cast_cd, machine_cd) VALUES (%s, %s, %s)",
        rows,
    )
    return len(rows)


def _seed_cast_spec(cur) -> int:
    repo = fx.make_default_cast_spec()
    rows = [
        (
            r.cmpCd, r.orgCd, r.smPlantCd, r.castCd, r.machineCd, r.prodTypeCd,
            r.slabThickness, r.widthLow, r.widthHigh, r.lengthLow, r.lengthHigh,
            None, None,  # wgtLow, wgtHigh — 도메인 dataclass 미보유
        )
        for r in repo._rows.values()
    ]
    cur.executemany(
        """INSERT INTO cast_spec
           (cmp_cd, org_cd, sm_plant_cd, cast_cd, machine_cd, prod_type_cd,
            slab_thickness, width_low, width_high, length_low, length_high, wgt_low, wgt_high)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_productivity_std(cur) -> int:
    repo = fx.make_default_productivity_std()
    rows = [
        (r.cmpCd, r.orgCd, r.procCd, r.gradeCd, r.prodKindCd, r.customerCd, r.productivity)
        for r in repo._rows.values()
    ]
    cur.executemany(
        """INSERT INTO productivity_std
           (cmp_cd, org_cd, proc_cd, grade_cd, prod_kind_cd, customer_cd, productivity)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_hr_spec(cur) -> int:
    repo = fx.make_default_hr_spec()
    rows = [
        (r.cmpCd, r.orgCd, r.hrPlantCd, r.prodTypeCd,
         r.widthLow, r.widthHigh, r.lengthLow, r.lengthHigh)
        for r in repo._rows.values()
    ]
    cur.executemany(
        """INSERT INTO hr_spec
           (cmp_cd, org_cd, hr_plant_cd, prod_type_cd,
            width_low, width_high, length_low, length_high)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_hr_min_wgt(cur) -> int:
    repo = fx.make_default_hr_min_wgt()
    rows = [
        (r.cmpCd, r.orgCd, r.hrCd, r.thickness, r.width, r.minWgt)
        for r in repo._rows
    ]
    cur.executemany(
        """INSERT INTO hr_min_wgt
           (cmp_cd, org_cd, hr_cd, thickness, width, min_wgt)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_hr_max_wgt(cur) -> int:
    repo = fx.make_default_hr_max_wgt()
    rows = [
        (r.cmpCd, r.orgCd, r.hrCd, r.thickness, r.width, r.maxWgt)
        for r in repo._rows
    ]
    cur.executemany(
        """INSERT INTO hr_max_wgt
           (cmp_cd, org_cd, hr_cd, thickness, width, max_wgt)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_edging_group(cur) -> int:
    repo = fx.make_default_edging_group()
    rows = [
        (r.cmpCd, r.orgCd, r.priority, r.edgingGroupCd,
         r.gradeCd, r.prodTypeCd, r.customerCd,
         r.hrTgtWidthLow, r.hrTgtWidthHigh)
        for r in repo._rows
    ]
    cur.executemany(
        """INSERT INTO edging_group
           (cmp_cd, org_cd, priority, edging_group_cd, grade_cd, prod_type_cd, customer_cd,
            hr_tgt_width_low, hr_tgt_width_high)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_edging_spec(cur) -> int:
    repo = fx.make_default_edging_spec(include_wildcard=True)
    rows = [
        (r.cmpCd, r.orgCd, r.edgingGroupCd, r.edgingCapLow, r.edgingCapHigh)
        for r in repo._rows.values()
    ]
    cur.executemany(
        """INSERT INTO edging_spec
           (cmp_cd, org_cd, edging_group_cd, edging_cap_low, edging_cap_high)
           VALUES (%s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


def _seed_customer_std(cur) -> int:
    repo = fx.make_default_customer_std()
    rows = []
    for idx, r in enumerate(repo._rows, start=1):
        rows.append((
            r.cmpCd, r.orgCd, idx,  # priority — 도메인엔 없으므로 INSERT 순서 사용
            r.prodTypeCd, r.customerCd,
            r.pkgWgtLow, r.pkgWgtHigh,
        ))
    cur.executemany(
        """INSERT INTO customer_std
           (cmp_cd, org_cd, priority, product_name_cd, customer_cd, pkg_wgt_low, pkg_wgt_high)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


# ─── 샘플 주문 ─────────────────────────────────────────────────────────


def _sample_orders() -> list[SDOrder]:
    """검증 시나리오에 매핑되는 5건 주문.

    1. 정상 주문 — pipeline_full PASS
    2. DG001 — 재고주문 (stockCode=1)
    3. DG003 — 포장단중 범위 위반 (low > high)
    4. DG002 — 폭/길이 양수 아님
    5. 좁은 단중 — A-a 루프 끝까지 실패 (DG109 후보)
    """
    today = date.today()
    future = today + timedelta(days=30)

    # 1. 정상
    o1 = fx.make_default_order(orderNo="ORD-NORMAL-001")

    # 2. DG001 — 재고주문
    o2 = fx.make_default_order(orderNo="ORD-DG001-STOCK")
    o2.stockCode = 1

    # 3. DG003 — 포장단중 범위 위반
    o3 = fx.make_default_order(orderNo="ORD-DG003-PKGWGT")
    o3.pkgWgtLow = Decimal("12")
    o3.pkgWgtHigh = Decimal("8")  # low > high

    # 4. DG002 — 폭/길이 음수
    o4 = fx.make_default_order(orderNo="ORD-DG002-SIZE")
    o4.orderWidth = Decimal("0")

    # 5. DG109 후보 — 좁은 단중
    o5 = fx.make_default_order(orderNo="ORD-DG109-NARROW")
    o5.orderWgtLow = Decimal("99.0")
    o5.orderWgtHigh = Decimal("99.5")
    o5.pkgWgtLow = Decimal("99.0")
    o5.pkgWgtHigh = Decimal("99.5")

    return [o1, o2, o3, o4, o5]


def _seed_sample_orders(cur, orders: Sequence[SDOrder]) -> int:
    rows = []
    for o in orders:
        rows.append((
            o.cmpCd, o.orgCd, o.orderNo,
            None,  # os_progress
            None,  # close_flag
            o.stockCode,
            o.designPendQtyHigh, o.designPendQtyLow, o.designPendQty,
            o.confirmedPlantCd, None,  # possible_plant_cd
            o.smDue, o.hrDue, o.hrfDue, o.crDue,
            o.anl1Due, o.anl2Due, o.galDue, o.crfDue,
            o.orderWgtLow, o.orderWgtHigh, o.orderWidth, o.orderLength,
            o.workDue,
            o.pkgWgtLow, o.pkgWgtHigh,
            o.productTypeCd, o.customerCd,
            None, None,  # prod_due, delivery_due
            o.gradeCd,
            None, None, None, None, None,  # hr_tgt_width 1~5
        ))
    cur.executemany(
        """INSERT INTO order_os
           (cmp_cd, org_cd, order_no,
            os_progress, close_flag, stock_code,
            design_pend_qty_high, design_pend_qty_low, design_pend_qty,
            confirmed_plant_cd, possible_plant_cd,
            sm_due, hr_due, hrf_due, cr_due, anl1_due, anl2_due, gal_due, crf_due,
            order_wgt_low, order_wgt_high, order_width, order_length,
            work_due, pkg_wgt_low, pkg_wgt_high,
            product_type_cd, customer_cd, prod_due, delivery_due, grade_cd,
            hr_tgt_width1, hr_tgt_width2, hr_tgt_width3, hr_tgt_width4, hr_tgt_width5)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, %s)""",
        rows,
    )
    return len(rows)


# ─── 오케스트레이션 ────────────────────────────────────────────────────


def seed_all(*, reset: bool = True) -> dict[str, int]:
    """전체 시드. reset=True 면 모든 테이블 TRUNCATE 후 INSERT."""
    apply_schema()
    if reset:
        reset_schema()

    counts: dict[str, int] = {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            counts["plant_mapping"] = _seed_plant_mapping(cur)
            counts["cast_spec"] = _seed_cast_spec(cur)
            counts["productivity_std"] = _seed_productivity_std(cur)
            counts["hr_spec"] = _seed_hr_spec(cur)
            counts["hr_min_wgt"] = _seed_hr_min_wgt(cur)
            counts["hr_max_wgt"] = _seed_hr_max_wgt(cur)
            counts["edging_group"] = _seed_edging_group(cur)
            counts["edging_spec"] = _seed_edging_spec(cur)
            counts["customer_std"] = _seed_customer_std(cur)
            counts["order_os"] = _seed_sample_orders(cur, _sample_orders())
        conn.commit()
    return counts
