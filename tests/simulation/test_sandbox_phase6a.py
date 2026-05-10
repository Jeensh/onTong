"""Phase 6-A — 신규 sandbox step + repo 단위 테스트.

검증 범위:
- HrMinWgtRepo / HrMaxWgtRepo: 2D sheet 룩업 (cover 가장 작은 cell)
- EdgingSpecRepo: 정확매칭 → '*' fallback → EdgingSpecMissingError
- EdgingGroupRepo: priority ASC 첫 row
- PlantMappingRepo: default + override
- step 2 (width_range), step 3 (length_range)
- step 5+6 (second_wgt) — HR_MIN_WGT/HR_MAX_WGT 룩업
- step 7 (max_split)
- step 16/17 (final_*_range), step 18+19 (target_size)
- pipeline_full end-to-end
- plant_mapping_migrate 시나리오
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.simulation.sandbox import registry
from backend.simulation.sandbox.fixtures import fixtures as fx
from backend.simulation.sandbox.fixtures.domain import (
    AlgorithmError,
    EdgingSpec,
    EdgingSpecMissingError,
    ErrorCode,
    HrMinWgt,
)
from backend.simulation.sandbox.fixtures.repository import (
    EdgingSpecRepo,
    HrMinWgtRepo,
    PlantMappingRepo,
)
from backend.simulation.sandbox.fixtures.steps import (
    final_length_range as final_length_range_step,
    final_width_range as final_width_range_step,
    length_range as length_range_step,
    max_split as max_split_step,
    second_wgt as second_wgt_step,
    target_size as target_size_step,
    width_range as width_range_step,
)


# ─── 2D sheet lookup ────────────────────────────────────────────────


class TestHrMinWgt2D:
    def setup_method(self):
        self.repo = fx.make_default_hr_min_wgt()

    def test_exact_cover(self):
        # thickness=220, width=1500 → cell (220, 1500), minWgt=9
        row = self.repo.lookup("K", "K01", "K", Decimal("220"), Decimal("1500"))
        assert row is not None
        assert row.minWgt == Decimal("9")

    def test_pick_smallest_cover(self):
        # thickness=210, width=1100 → 가장 작은 cover = (220, 1200), minWgt=11
        row = self.repo.lookup("K", "K01", "K", Decimal("210"), Decimal("1100"))
        assert row is not None
        assert row.thickness == Decimal("220")
        assert row.width == Decimal("1200")
        assert row.minWgt == Decimal("11")

    def test_no_cover_returns_none(self):
        # thickness=300 > 모든 cell → None
        row = self.repo.lookup("K", "K01", "K", Decimal("300"), Decimal("1200"))
        assert row is None

    def test_other_hr_isolated(self):
        row = self.repo.lookup("K", "K01", "X", Decimal("220"), Decimal("1500"))
        assert row is None


class TestHrMaxWgt2D:
    def test_default_lookup(self):
        repo = fx.make_default_hr_max_wgt()
        row = repo.lookup("K", "K01", "K", Decimal("220"), Decimal("1500"))
        assert row is not None
        assert row.maxWgt == Decimal("34")


# ─── Edging Spec ('*' fallback / missing) ────────────────────────────


class TestEdgingSpec:
    def test_exact_match(self):
        repo = fx.make_default_edging_spec()
        spec = repo.find_spec("K", "K01", "EDG-NARROW")
        assert spec.edgingCapLow == Decimal("-50")

    def test_wildcard_fallback(self):
        # PHANTOM 그룹은 등록 안되어 있음 → '*' fallback
        repo = fx.make_default_edging_spec(include_wildcard=True)
        spec = repo.find_spec("K", "K01", "EDG-PHANTOM")
        assert spec.edgingGroupCd == "*"
        assert spec.edgingCapHigh == Decimal("60")

    def test_missing_raises(self):
        # wildcard 없는 repo + 미등록 그룹 → EdgingSpecMissingError
        repo = fx.make_default_edging_spec(include_wildcard=False)
        with pytest.raises(EdgingSpecMissingError) as exc_info:
            repo.find_spec("K", "K01", "EDG-PHANTOM")
        assert exc_info.value.edging_group_cd == "EDG-PHANTOM"


# ─── Edging Group (priority ASC) ─────────────────────────────────────


class TestEdgingGroup:
    def test_priority_first_match(self):
        # width=1200 → NARROW(priority 1) 우선 매칭
        repo = fx.make_default_edging_group()
        g = repo.find_group("K", "K01", "G01", "A001", "C001", Decimal("1200"))
        assert g is not None
        assert g.edgingGroupCd == "EDG-NARROW"

    def test_only_generic_in_range(self):
        # width=1500 → NARROW 범위(1100~1300) 외 → GENERIC(1000~1600) 매칭
        repo = fx.make_default_edging_group()
        g = repo.find_group("K", "K01", "G01", "A001", "C001", Decimal("1500"))
        assert g is not None
        assert g.edgingGroupCd == "EDG-GENERIC"

    def test_no_match(self):
        repo = fx.make_default_edging_group()
        g = repo.find_group("K", "K01", "G01", "A001", "C001", Decimal("1700"))
        assert g is None


# ─── PlantMapping (migrate) ──────────────────────────────────────────


class TestPlantMapping:
    def test_default_K(self):
        repo = PlantMappingRepo.default()
        m = repo.get("K")
        assert m.castCd == "CC1" and m.machineCd == "M1"

    def test_override(self):
        from backend.simulation.sandbox.fixtures.domain import PlantMapping
        d = PlantMappingRepo.default().all()
        d["K"] = PlantMapping(castCd="CC9", machineCd="M9")
        repo = PlantMappingRepo(d)
        assert repo.get("K").castCd == "CC9"


# ─── step 2 (width_range) ───────────────────────────────────────────


class TestWidthRange:
    def setup_method(self):
        self.order = fx.make_step2_order()
        self.slab = fx.make_default_slab()
        self.plant = fx.make_default_plant_mapping()
        self.cast = fx.make_default_cast_spec()
        self.hr = fx.make_default_hr_spec()
        self.eg = fx.make_default_edging_group()
        self.es = fx.make_default_edging_spec()

    def test_default_passes(self):
        width_range_step.execute(self.order, self.slab, self.plant, self.cast,
                                  self.hr, self.eg, self.es)
        # selectedHrTgtWidth=1200 → NARROW group (cap -50, +80)
        # widthLow = max(900, 1000, 1200-50)=1150, widthHigh = min(2000, 1600, 1200+80)=1280
        assert self.slab.firstWidthLow == Decimal("1150")
        assert self.slab.firstWidthHigh == Decimal("1280")

    def test_hr_inactive(self):
        self.order.confirmedPlantCd = "K       "  # SM only
        with pytest.raises(AlgorithmError) as exc_info:
            width_range_step.execute(self.order, self.slab, self.plant, self.cast,
                                      self.hr, self.eg, self.es)
        assert exc_info.value.error_code == ErrorCode.ALG_HR_SPEC_NOT_FOUND

    def test_edging_group_miss(self):
        # selectedHrTgtWidth=1700 → 어떤 그룹도 매칭 안됨
        self.order.selectedHrTgtWidth = Decimal("1700")
        with pytest.raises(AlgorithmError) as exc_info:
            width_range_step.execute(self.order, self.slab, self.plant, self.cast,
                                      self.hr, self.eg, self.es)
        assert exc_info.value.error_code == ErrorCode.ALG_EDGING_GROUP_NOT_FOUND


# ─── step 3 (length_range) ──────────────────────────────────────────


class TestLengthRange:
    def setup_method(self):
        self.order = fx.make_step2_order()
        self.slab = fx.make_default_slab()

    def test_default_passes(self):
        length_range_step.execute(
            self.order, self.slab,
            fx.make_default_plant_mapping(),
            fx.make_default_cast_spec(),
            fx.make_default_hr_spec(),
        )
        # lengthLow = max(2000, 2000)=2000, lengthHigh = min(13000, 12000)=12000
        assert self.slab.firstLengthLow == Decimal("2000")
        assert self.slab.firstLengthHigh == Decimal("12000")


# ─── step 5+6 (second_wgt) ──────────────────────────────────────────


class TestSecondWgt:
    def setup_method(self):
        self.order = fx.make_step2_order()
        self.order.productivity = Decimal("0.85")
        self.slab = fx.make_default_slab()
        self.slab.slabThickness = Decimal("220")
        self.slab.firstWidthLow = Decimal("1200")
        self.slab.firstWidthHigh = Decimal("1500")
        self.slab.firstWgtLow = Decimal("8")
        self.slab.firstWgtHigh = Decimal("25")

    def test_low_uses_hr_min(self):
        second_wgt_step.execute_low(
            self.order, self.slab,
            fx.make_default_hr_min_wgt(),
            fx.make_default_customer_std(),
        )
        # firstWgtLow=8, hrMin@(220,1200)=11 → max=11
        assert self.slab.secondWgtLow == Decimal("11")

    def test_high_uses_hr_max(self):
        second_wgt_step.execute_high(
            self.order, self.slab,
            fx.make_default_hr_max_wgt(),
            fx.make_default_customer_std(),
        )
        # firstWgtHigh=25, hrMax@(220,1500)=34, designPendQtyHigh/productivity=150/0.85≈176.47
        # min(25, 34, 176.47) = 25
        assert self.slab.secondWgtHigh == Decimal("25")

    def test_low_hr_min_miss(self):
        # thickness=300 → 격자 밖 → DG106
        self.slab.slabThickness = Decimal("300")
        with pytest.raises(AlgorithmError) as exc_info:
            second_wgt_step.execute_low(
                self.order, self.slab,
                fx.make_default_hr_min_wgt(),
                fx.make_default_customer_std(),
            )
        assert exc_info.value.error_code == ErrorCode.ALG_HR_MIN_WGT_NOT_FOUND


# ─── step 7 (max_split) ─────────────────────────────────────────────


class TestMaxSplit:
    def test_basic(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.85")
        slab = fx.make_default_slab()
        slab.secondWgtHigh = Decimal("50")  # override
        max_split_step.execute(order, slab)
        # ceil(50 / 25 / 0.85) = ceil(2.35) = 3
        assert slab.maxSplitCountUpper == 3
        assert slab.currentSplitCount == 3  # A-a 루프 시작점

    def test_zero_max_raises(self):
        order = fx.make_default_order()
        order.productivity = Decimal("0.85")
        slab = fx.make_default_slab()
        slab.secondWgtHigh = Decimal("0")  # 0 → ceil(0)=0 < 1 → DG108
        with pytest.raises(AlgorithmError) as exc_info:
            max_split_step.execute(order, slab)
        assert exc_info.value.error_code == ErrorCode.ALG_ITERATION_NEEDED


# ─── step 16/17 (final_range) + 18+19 (target_size) ─────────────────


class TestFinalRangeAndTarget:
    def setup_method(self):
        self.order = fx.make_default_order()
        # 큰 slab 단중으로 현실적 폭/길이 산정
        self.slab = fx.make_default_slab()
        self.slab.slabThickness = Decimal("220")
        self.slab.firstLengthLow = Decimal("3000")
        self.slab.firstLengthHigh = Decimal("9000")
        self.slab.slabWgtInProgress = Decimal("18000")  # 18ton

    def test_final_width_range(self):
        final_width_range_step.execute(self.order, self.slab)
        # numerator = 18000 × 1e6 = 18e9
        # denomLow  = 9000 × 220 × 7.82 = 15,483,600 → 18e9/15,483,600 ≈ 1162.6 → ceil = 1163
        # denomHigh = 3000 × 220 × 7.82 = 5,161,200  → 18e9/5,161,200 ≈ 3487.9 → floor = 3487
        assert self.slab.finalWidthLow == Decimal("1163")
        assert self.slab.finalWidthHigh == Decimal("3487")

    def test_final_length_range(self):
        # 선행 step 16 결과 필요
        final_width_range_step.execute(self.order, self.slab)
        final_length_range_step.execute(self.order, self.slab)
        assert self.slab.finalLengthLow is not None
        assert self.slab.finalLengthHigh is not None
        assert self.slab.finalLengthLow <= self.slab.finalLengthHigh

    def test_target_size(self):
        final_width_range_step.execute(self.order, self.slab)
        final_length_range_step.execute(self.order, self.slab)
        self.slab.splitWgtHigh = Decimal("18000")
        target_size_step.execute(self.order, self.slab)
        assert self.slab.targetWidth is not None
        assert self.slab.targetLength is not None
        # targetWidth 는 [finalWidthLow, finalWidthHigh] 또는 finalWidthLow
        assert self.slab.targetWidth >= self.slab.finalWidthLow


# ─── pipeline_full end-to-end ───────────────────────────────────────


class TestPipelineFull:
    def test_default_runs_to_ok(self):
        out = registry.run_step("pipeline_full", {})
        assert out["stage"] == "ok"
        slab = out["slab"]
        assert slab["slabThickness"] == "220"
        assert slab["firstWidthLow"] is not None
        assert slab["firstLengthLow"] is not None
        assert slab["secondWgtLow"] is not None
        assert slab["maxSplitCountUpper"] is not None
        assert slab["targetWidth"] is not None

    def test_edging_group_miss_blocks_at_step2(self):
        out = registry.run_step(
            "pipeline_full",
            {"order": {"selectedHrTgtWidth": "1700"}},
        )
        assert out["stage"] == "algorithm"
        assert out["error"]["error_code"] == ErrorCode.ALG_EDGING_GROUP_NOT_FOUND


# ─── plant_mapping_migrate 시나리오 ─────────────────────────────────


class TestPlantMappingMigrate:
    def test_no_change(self):
        out = registry.run_step("plant_mapping_migrate", {
            "smCd": "K", "productTypeCd": "A001", "mapping_overrides": {},
        })
        assert out["changed"] is False

    def test_K_to_CC2_breaks_lookup(self):
        # K → CC2/M2 는 CastSpec 에 등록 안됨 → after.thickness=null
        out = registry.run_step("plant_mapping_migrate", {
            "smCd": "K", "productTypeCd": "A001",
            "mapping_overrides": {"K": {"castCd": "CC2", "machineCd": "M2"}},
        })
        assert out["changed"] is True
        assert out["before"]["thickness"] == "220"
        assert out["after"]["thickness"] is None
