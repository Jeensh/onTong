"""v2-slab-design plugin contracts test.

V2-MIGRATION.md §4.2 Task A2.1 acceptance:
- SlabDesignContract instantiable
- exception_base / domain_namespace / numeric_convention 정상
- SdConstants 의 plant code 값 cover
- Anti-pattern (Lesson 1 의 5 KNOWN_DIVERGENCE) 회피 (contract 가 explicit class)
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.contracts.base import (
    JavaContract,
    MathContext,
    NumericConvention,
    RoundingMode,
)
from backend.sim_v2.plugins.v2_slab_design.contracts.base import SlabDesignContract
from backend.sim_v2.plugins.v2_slab_design.contracts.domain_namespace import SdConstants
from backend.sim_v2.plugins.v2_slab_design.contracts.exception import AlgorithmException
from backend.sim_v2.plugins.v2_slab_design.contracts.validation import (
    ValidationFailure,
    ValidationResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# Contract instance
# ─────────────────────────────────────────────────────────────────────────────


def test_contract_is_java_contract():
    c = SlabDesignContract()
    assert isinstance(c, JavaContract)


def test_exception_base_is_algorithm_exception():
    c = SlabDesignContract()
    assert c.exception_base is AlgorithmException


def test_numeric_convention_decimal64():
    c = SlabDesignContract()
    nc = c.numeric_convention()
    assert isinstance(nc, NumericConvention)
    assert nc.bigdecimal_precision == 16
    assert nc.bigdecimal_rounding == RoundingMode.HALF_EVEN
    assert nc.domain_scales["slab.weight_kg"] == 3
    assert nc.domain_scales["productivity.rate"] == 6


def test_default_math_context():
    c = SlabDesignContract()
    mc = c.default_math_context()
    assert mc == MathContext(precision=16, rounding=RoundingMode.HALF_EVEN)


def test_scale_for_domain_lookup_and_fallback():
    c = SlabDesignContract()
    assert c.scale_for_domain("slab.weight_kg") == 3
    assert c.scale_for_domain("unknown.thing", fallback=4) == 4


# ─────────────────────────────────────────────────────────────────────────────
# domain_namespace — Lesson 1 의 namespace class 의 first-class contract
# ─────────────────────────────────────────────────────────────────────────────


def test_domain_namespace_exposes_sdconstants():
    c = SlabDesignContract()
    ns = c.domain_namespace()
    assert ns["SdConstants"] is SdConstants
    assert ns["ValidationResult"] is ValidationResult
    assert ns["AlgorithmException"] is AlgorithmException


def test_sdconstants_plant_codes_are_8_position():
    for attr in ("POS_SM", "POS_HR", "POS_CR", "POS_BF", "POS_AF", "POS_RB", "POS_RH", "POS_PC"):
        value = getattr(SdConstants, attr)
        assert len(value) == 8, f"{attr} = {value!r} not 8-position"


def test_sdconstants_position_groups():
    assert SdConstants.POS_SM in SdConstants.ACTIVE_POSITIONS
    assert SdConstants.POS_HR in SdConstants.HR_POSITIONS


def test_null_plant_sentinel():
    assert SdConstants.NULL_PLANT == "________"


# ─────────────────────────────────────────────────────────────────────────────
# AlgorithmException — Lesson 4 §3.2 의 slab-specific exception
# ─────────────────────────────────────────────────────────────────────────────


def test_algorithm_exception_carries_triplet():
    exc = AlgorithmException(
        step_no=7,
        step_name="cumulative_productivity",
        error_code="LOW_FEED",
        detail="feed rate < 0.5",
    )
    assert exc.step_no == 7
    assert exc.step_name == "cumulative_productivity"
    assert exc.error_code == "LOW_FEED"
    assert "step 7" in str(exc)
    assert "LOW_FEED" in str(exc)
    assert isinstance(exc, Exception)


# ─────────────────────────────────────────────────────────────────────────────
# ValidationResult — Lesson 1 mismatch #5 의 정식 대응
# ─────────────────────────────────────────────────────────────────────────────


def test_validation_result_ok():
    r = ValidationResult.ok()
    assert r.is_valid()
    assert r.failures == []
    assert r.warnings == []


def test_validation_result_fail():
    r = ValidationResult.fail(
        field_path="slab.weight_kg",
        code="OUT_OF_RANGE",
        message="must be > 0",
    )
    assert not r.is_valid()
    assert r.status == "INVALID"
    assert len(r.failures) == 1
    assert r.failures[0].field_path == "slab.weight_kg"


def test_validation_result_warn():
    r = ValidationResult.warn(
        field_path="productivity.rate",
        code="LOW",
        message="below typical floor",
    )
    assert r.status == "WARN"
    assert len(r.warnings) == 1


def test_validation_result_combine_invalidates():
    ok = ValidationResult.ok()
    bad = ValidationResult.fail("x", "E", "msg")
    combined = ok.combine(bad)
    assert combined.status == "INVALID"
    assert len(combined.failures) == 1


def test_validation_result_combine_warn_only():
    w1 = ValidationResult.warn("a", "W1")
    w2 = ValidationResult.warn("b", "W2")
    combined = w1.combine(w2)
    assert combined.status == "WARN"
    assert len(combined.warnings) == 2


def test_validation_failure_is_immutable():
    f = ValidationFailure(field_path="x", code="E")
    with pytest.raises(Exception):
        f.code = "ALTERED"  # type: ignore[misc]
