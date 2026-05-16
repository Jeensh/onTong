"""Anti-pattern catalog test — Phase α 5 lessons (W5.1)."""
from __future__ import annotations

from backend.sim_v2.core.recommendation.anti_patterns.catalog import (
    DEFAULT_CATALOG,
    LESSON_1_KNOWN_DIVERGENCE,
    AntiPattern,
    AntiPatternScanner,
)


def test_default_catalog_has_nine_entries():
    """5 from Lesson 1 + 1 each from Lesson 2-5 = 9 total."""
    assert len(DEFAULT_CATALOG) == 9


def test_lesson_1_has_five_entries():
    assert len(LESSON_1_KNOWN_DIVERGENCE) == 5
    ids = {ap.id for ap in LESSON_1_KNOWN_DIVERGENCE}
    assert "phase_alpha_bigdecimal_class_vs_function" in ids
    assert "phase_alpha_mathcontext_namespace_vs_constants" in ids
    assert "phase_alpha_roundingmode_enum_vs_constants" in ids
    assert "phase_alpha_sdconstants_namespace_vs_imports" in ids
    assert "phase_alpha_validationresult_missing_implementation" in ids


def test_each_entry_has_lesson_ref():
    for ap in DEFAULT_CATALOG:
        assert ap.lesson_ref in {"L1", "L2", "L3", "L4", "L5"}
        assert ap.signal_pattern
        assert ap.rationale


def test_lesson_1_entries_are_error_severity():
    for ap in LESSON_1_KNOWN_DIVERGENCE:
        assert ap.severity == "ERROR"


def test_scanner_detects_bigdecimal_class_call():
    scanner = AntiPatternScanner()
    source = "x = BigDecimal('100').multiply(y)"
    hits = scanner.scan(source)
    assert len(hits) >= 1
    assert any(h.pattern_id == "phase_alpha_bigdecimal_class_vs_function" for h in hits)


def test_scanner_detects_mathcontext_namespace():
    scanner = AntiPatternScanner()
    source = "result = a.multiply(b, MathContext.DECIMAL64)"
    hits = scanner.scan(source)
    assert any(h.pattern_id == "phase_alpha_mathcontext_namespace_vs_constants" for h in hits)


def test_scanner_detects_roundingmode_enum():
    scanner = AntiPatternScanner()
    source = "scaled = x.setScale(2, RoundingMode.HALF_EVEN)"
    hits = scanner.scan(source)
    assert any(h.pattern_id == "phase_alpha_roundingmode_enum_vs_constants" for h in hits)


def test_scanner_detects_sdconstants_namespace():
    scanner = AntiPatternScanner()
    source = "if plant_cd == SdConstants.POS_SM:"
    hits = scanner.scan(source)
    assert any(h.pattern_id == "phase_alpha_sdconstants_namespace_vs_imports" for h in hits)


def test_scanner_detects_validationresult_call():
    scanner = AntiPatternScanner()
    source = "return ValidationResult.fail('x', 'CODE', 'reason')"
    hits = scanner.scan(source)
    assert any(h.pattern_id == "phase_alpha_validationresult_missing_implementation" for h in hits)


def test_scanner_detects_silent_drift_negative_scale():
    scanner = AntiPatternScanner()
    source = '''
def bd_set_scale(value, scale):
    if scale < 0:
        raise NotImplementedError("negative scale not implemented")
'''
    hits = scanner.scan(source)
    assert any(h.pattern_id == "phase_alpha_silent_negative_scale_reject" for h in hits)


def test_scanner_detects_fixture_no_metadata_hardcode():
    scanner = AntiPatternScanner()
    source = "abs_tol = 1e-6\nrel_tol = 1e-9"
    hits = scanner.scan(source)
    # Both abs_tol and rel_tol patterns match
    fixture_hits = [h for h in hits if h.pattern_id == "phase_alpha_fixture_no_metadata"]
    assert len(fixture_hits) >= 2


def test_scanner_clean_source():
    scanner = AntiPatternScanner()
    source = """
from backend.sim_v2.core.contracts.base import DECIMAL64, RoundingMode
x = bd('100')
y = bd_multiply(x, bd('2'), DECIMAL64)
"""
    hits = scanner.scan(source)
    # Should not flag — uses contract-provided forms
    error_hits = [h for h in hits if h.severity == "ERROR"]
    assert error_hits == []


def test_scanner_has_errors():
    scanner = AntiPatternScanner()
    bad = "x = BigDecimal('100')"
    good = "x = bd('100')"
    assert scanner.has_errors(bad) is True
    assert scanner.has_errors(good) is False


def test_custom_catalog():
    custom = (
        AntiPattern(
            id="custom.test",
            title="Custom",
            lesson_ref="L1",
            severity="WARN",
            signal_pattern=r"FORBIDDEN_TOKEN",
            rationale="test",
        ),
    )
    scanner = AntiPatternScanner(catalog=custom)
    assert len(scanner.catalog) == 1
    hits = scanner.scan("found FORBIDDEN_TOKEN here")
    assert len(hits) == 1
