"""Phase 1 — sandbox 단위 테스트.

In-process registry 호출 + subprocess CLI 양쪽 검증.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.simulation.sandbox import registry
from backend.simulation.sandbox.fixtures import fixtures as fx
from backend.simulation.sandbox.fixtures.domain import ErrorCode, SDOrder, SDSlab
from backend.simulation.sandbox.fixtures.steps import (
    productivity as productivity_step,
    slab_count as slab_count_step,
    slab_weight as slab_weight_step,
    split_range as split_range_step,
    thickness as thickness_step,
    validator as validator_step,
)
from backend.simulation.sandbox.fixtures.domain import AlgorithmError


# ─── Validator (DG001~005) ──────────────────────────────────────────


class TestValidator:
    def test_default_order_passes(self):
        order = fx.make_default_order()
        assert validator_step.validate(order).passed is True

    def test_dg001_stock_order(self):
        order = fx.make_default_order()
        order.stockCode = 1
        r = validator_step.validate(order)
        assert r.passed is False
        assert r.error_code == ErrorCode.VAL_STOCK_ORDER

    def test_dg002_zero_width(self):
        order = fx.make_default_order()
        order.orderWidth = Decimal(0)
        r = validator_step.validate(order)
        assert not r.passed
        assert r.error_code == ErrorCode.VAL_ORDER_SIZE

    def test_dg002_null_length(self):
        order = fx.make_default_order()
        order.orderLength = None
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_ORDER_SIZE

    def test_dg003_inverted_pkg_range(self):
        order = fx.make_default_order()
        order.pkgWgtLow = Decimal(40)
        order.pkgWgtHigh = Decimal(30)
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_PKG_WGT_RANGE

    def test_dg004_high_below_pkg_low(self):
        """설계대기량 상한 < 포장단중 하한 → DG004 (cross-table)."""
        order = fx.make_default_order()
        order.pkgWgtLow = Decimal(100)
        order.pkgWgtHigh = Decimal(200)  # DG003 통과 (low ≤ high)
        order.designPendQtyHigh = Decimal(50)
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_DESIGN_PEND_QTY

    def test_dg005_past_due(self):
        order = fx.make_default_order()
        order.workDue = date.today() - timedelta(days=1)
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_WORK_DUE

    def test_dg005_today_is_fail(self):
        """Java isAfter: due가 today와 동일하면 FAIL (당일 마감 차단)."""
        order = fx.make_default_order()
        order.workDue = date.today()
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_WORK_DUE

    def test_dg005_inactive_process_skipped(self):
        """확통 위치가 ' '면 due 점검 skip — 비활성 공정."""
        order = fx.make_default_order()
        # GAL 위치(idx 6) 비활성 + galDue None — 통과해야 함
        order.confirmedPlantCd = "K K K  K"  # GAL은 ' '
        order.galDue = None
        # 활성 공정 due 모두 future, workDue future
        assert validator_step.validate(order).passed

    def test_short_circuit(self):
        """DG001 실패 시 DG002~005 미실행 (다른 필드 NULL이어도 DG001만 보고)."""
        order = fx.make_default_order()
        order.stockCode = 1
        order.orderWidth = None  # DG002도 fail이지만
        r = validator_step.validate(order)
        assert r.error_code == ErrorCode.VAL_STOCK_ORDER  # 첫 fail만


# ─── Productivity (cumulative) ──────────────────────────────────────


class TestProductivity:
    def test_3_active_processes(self):
        """K K K   ' = SM, HRF, ANL1 활성. SM lookup 미존재 → default 0.95."""
        order = fx.make_default_order()
        order.confirmedPlantCd = "K K K   "
        repo = fx.make_default_productivity_std()
        # SM=default 0.95 × HRF=0.93 × ANL1=0.92 = 0.81282
        result = productivity_step.cumulative_productivity(order, repo)
        # Decimal precision: exactly 0.95 * 0.93 * 0.92
        expected = Decimal("0.95") * Decimal("0.93") * Decimal("0.92")
        assert result == expected

    def test_inactive_all(self):
        order = fx.make_default_order()
        order.confirmedPlantCd = "        "  # 전부 비활성
        repo = fx.make_default_productivity_std()
        result = productivity_step.cumulative_productivity(order, repo)
        assert result == Decimal(1)  # 곱 = 1 (empty product)

    def test_short_confirmed_returns_default(self):
        """8자리 미만 → 0.95 보수 처리."""
        order = fx.make_default_order()
        order.confirmedPlantCd = "K"
        repo = fx.make_default_productivity_std()
        assert productivity_step.cumulative_productivity(order, repo) == Decimal("0.95")

    def test_scenario5_hr_drop(self):
        """시나리오 5: HR 0.95→0.92로 변경 시 cumulative 변동 측정."""
        order = fx.make_default_order()
        order.confirmedPlantCd = " K      "  # HR만 활성 (idx=1)
        repo_before = fx.make_default_productivity_std(hr_productivity=Decimal("0.95"))
        repo_after = fx.make_default_productivity_std(hr_productivity=Decimal("0.92"))
        before = productivity_step.cumulative_productivity(order, repo_before)
        after = productivity_step.cumulative_productivity(order, repo_after)
        assert before == Decimal("0.95")
        assert after == Decimal("0.92")
        # 영향도: 약 -3.16% (단일 공정이므로 그대로)
        assert (before - after) / before > Decimal("0.03")


# ─── Thickness (step 1) ─────────────────────────────────────────────


class TestThickness:
    def test_default_lookup(self):
        order = fx.make_default_order()
        slab = fx.make_default_slab()
        plant = fx.make_default_plant_mapping()
        cast = fx.make_default_cast_spec()
        thickness_step.execute(order, slab, plant, cast)
        assert slab.slabThickness == Decimal("220")

    def test_inactive_sm_fails(self):
        order = fx.make_default_order()
        order.confirmedPlantCd = "  K K   "  # 제강 비활성
        slab = fx.make_default_slab()
        with pytest.raises(AlgorithmError) as exc:
            thickness_step.execute(
                order, slab,
                fx.make_default_plant_mapping(),
                fx.make_default_cast_spec(),
            )
        assert exc.value.error_code == ErrorCode.ALG_CAST_SPEC_NOT_FOUND
        assert "비활성" in exc.value.message

    def test_unknown_product_type_fails(self):
        order = fx.make_default_order()
        order.productTypeCd = "UNKNOWN"
        slab = fx.make_default_slab()
        with pytest.raises(AlgorithmError):
            thickness_step.execute(
                order, slab,
                fx.make_default_plant_mapping(),
                fx.make_default_cast_spec(),
            )


# ─── Split range (step 8) ───────────────────────────────────────────


class TestSplitRange:
    def test_normal(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.8")
        slab = fx.make_default_slab()
        slab.currentSplitCount = 1
        split_range_step.execute(order, slab)
        # orderRangeLow = 8*1/0.8 = 10, orderRangeHigh = 25*1/0.8 = 31.25
        # secondWgtLow=8, secondWgtHigh=25 → splitWgt range = [10, 25]
        assert slab.splitWgtLow == Decimal(10)
        assert slab.splitWgtHigh == Decimal(25)
        assert slab.optimalSplitCount == 1

    def test_no_overlap_fails(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.8")
        slab = fx.make_default_slab()
        slab.currentSplitCount = 1
        # 2차 단중 범위를 order 범위와 겹치지 않게
        slab.secondWgtLow = Decimal(50)
        slab.secondWgtHigh = Decimal(100)
        with pytest.raises(AlgorithmError) as exc:
            split_range_step.execute(order, slab)
        assert exc.value.error_code == ErrorCode.ALG_ITERATION_NEEDED


# ─── Slab count (step 9) ────────────────────────────────────────────


class TestSlabCount:
    def test_normal(self):
        order = fx.make_default_order()
        order.designPendQtyHigh = Decimal(100)
        order.productivity = Decimal("0.8")
        slab = fx.make_default_slab()
        slab.splitWgtHigh = Decimal(10)
        slab_count_step.execute(order, slab)
        # 100 / 0.8 / 10 = 12.5 → floor → 12
        assert slab.slabCountInProgress == 12

    def test_count_below_one_fails(self):
        order = fx.make_default_order()
        order.designPendQtyHigh = Decimal("0.5")
        order.productivity = Decimal("0.95")
        slab = fx.make_default_slab()
        slab.splitWgtHigh = Decimal(10)
        with pytest.raises(AlgorithmError) as exc:
            slab_count_step.execute(order, slab)
        assert exc.value.error_code == ErrorCode.ALG_ITERATION_NEEDED


# ─── Slab weight (step 10) ──────────────────────────────────────────


class TestSlabWeight:
    def test_satisfies(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.8")
        order.designPendQtyLow = Decimal(50)
        order.designPendQtyHigh = Decimal(100)
        slab = fx.make_default_slab()
        slab.splitWgtHigh = Decimal(10)
        slab.slabCountInProgress = 10  # 10*10=100, yieldHigh=100/0.8=125, yieldLow=50/0.8=62.5 → ok
        slab_weight_step.execute(order, slab)
        assert slab.slabWgtInProgress == Decimal(10)

    def test_below_yield_low_fails(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.8")
        order.designPendQtyLow = Decimal(200)
        order.designPendQtyHigh = Decimal(300)
        slab = fx.make_default_slab()
        slab.splitWgtHigh = Decimal(10)
        slab.slabCountInProgress = 5  # totalProduced=50, yieldLow=250 → fail
        with pytest.raises(AlgorithmError) as exc:
            slab_weight_step.execute(order, slab)
        assert exc.value.error_code == ErrorCode.ALG_ITERATION_NEEDED


# ─── Registry (in-process) ──────────────────────────────────────────


class TestRegistryInProcess:
    def test_list_steps(self):
        steps = registry.list_steps()
        assert "validator" in steps
        assert "productivity" in steps
        assert "pipeline" in steps

    def test_unknown_step_raises(self):
        with pytest.raises(ValueError):
            registry.run_step("unknown", {})

    def test_validator_via_registry(self):
        result = registry.run_step("validator", {"order": {"stockCode": 1}})
        assert result["validation"]["passed"] is False
        assert result["validation"]["error_code"] == ErrorCode.VAL_STOCK_ORDER

    def test_productivity_via_registry(self):
        result = registry.run_step("productivity", {"order": {"confirmedPlantCd": "K K K   "}})
        # 0.95 * 0.93 * 0.92 = 0.81282 (Decimal precise)
        assert Decimal(result["cumulative_productivity"]) == Decimal("0.95") * Decimal("0.93") * Decimal("0.92")

    def test_pipeline_happy_path(self):
        result = registry.run_step("pipeline", {})
        assert result["stage"] == "ok"
        # productivity 결과
        assert Decimal(result["productivity"]) > Decimal("0.5")
        # Slab 매수 ≥ 1
        assert result["slab"]["slabCountInProgress"] >= 1

    def test_pipeline_fails_on_stock_order(self):
        result = registry.run_step("pipeline", {"order": {"stockCode": 1}})
        assert result["stage"] == "validate"
        assert result["validation"]["error_code"] == ErrorCode.VAL_STOCK_ORDER

    def test_pipeline_scenario5_hr_drop(self):
        """시나리오 5 핵심: HR 실수율 변경이 Slab 매수에 영향."""
        # K K K   = SM(default 0.95) + HRF(0.93) + ANL1(0.92)
        # rules.hr는 K K K   에서 영향 없음 (HR 비활성). HRF는 영향 받음.
        before = registry.run_step("pipeline", {"rules": {"hrf": "0.95"}})
        after = registry.run_step("pipeline", {"rules": {"hrf": "0.85"}})
        # 둘 다 ok stage
        assert before["stage"] == "ok"
        assert after["stage"] == "ok"
        # productivity 변동
        assert Decimal(before["productivity"]) > Decimal(after["productivity"])
