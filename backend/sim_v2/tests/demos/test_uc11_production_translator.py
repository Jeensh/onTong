"""UC11 — Production translator demo verification — W38.2.

Validates that the framework translates real Java method bodies from
data/ontology.db. Skips cleanly if production DB missing.
"""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc11_production_translator.run import (
    DEFAULT_REPO_ID,
    fetch_methods,
    main,
    parse_method_declaration,
    run_translation_survey,
    translate_method,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(tmp_path, monkeypatch):
    """main() must exit 0 even when production DB absent."""
    from backend.sim_v2.demos.uc11_production_translator import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session",
                        lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Method fetch
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_fetch_methods_returns_nonempty():
    session = open_readonly_session()
    try:
        methods = fetch_methods(session, DEFAULT_REPO_ID, limit=10)
        assert len(methods) > 0
        for m in methods:
            assert "fqn" in m
            assert "body_text" in m
            assert m["body_text"]  # non-empty after WHERE filter
    finally:
        if session:
            session.close()


@requires_production_db
def test_fetch_methods_respects_limit():
    session = open_readonly_session()
    try:
        methods = fetch_methods(session, DEFAULT_REPO_ID, limit=3)
        assert len(methods) <= 3
    finally:
        if session:
            session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Parse wrapper
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_method_declaration_handles_simple_body():
    body = """
public int square(int x) {
    return x * x;
}
"""
    node = parse_method_declaration(body)
    assert node is not None
    assert node.type == "method_declaration"


def test_parse_method_declaration_returns_none_on_no_method():
    """A class-only body (no method_declaration) should return None."""
    body = "int x = 5;"  # not a method declaration
    node = parse_method_declaration(body)
    assert node is None


# ─────────────────────────────────────────────────────────────────────────────
# Translation classification
# ─────────────────────────────────────────────────────────────────────────────


def test_translate_method_pass_for_simple():
    method = {
        "fqn":       "test.T#square",
        "name":      "square",
        "body_text": "public int square(int x) { return x * x; }",
        "parent_type": "test.T",
        "return_type": "int",
    }
    result = translate_method(method)
    assert result.status == "PASS"
    assert result.python_lines > 0


def test_translate_method_signature_locked_for_unsupported():
    """`synchronized` blocks currently signature-lock.

    (Was `i++` before W39, then `String.class` before W40; updated as the
    translator absorbs more constructs.)
    """
    method = {
        "fqn":       "test.T#sync",
        "name":      "sync",
        "body_text": (
            "public void sync() { Object lock = new Object();"
            " synchronized(lock) { int x = 1; } }"
        ),
        "parent_type": "test.T",
        "return_type": "void",
    }
    result = translate_method(method)
    assert result.status == "SIGNATURE_LOCKED"
    assert any("synchronized_statement" in n for n in result.notes)


def test_translate_method_empty_body():
    method = {
        "fqn": "test.T#blank", "name": "blank",
        "body_text": "   \n\t  ",
        "parent_type": "test.T", "return_type": "void",
    }
    result = translate_method(method)
    assert result.status == "EMPTY"


# ─────────────────────────────────────────────────────────────────────────────
# Survey against real DB
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_survey_returns_report_with_classified_results():
    session = open_readonly_session()
    try:
        report = run_translation_survey(session, DEFAULT_REPO_ID, sample_size=20)
        assert report.repo_id == DEFAULT_REPO_ID
        assert report.sample_size == len(report.sample_results)
        assert report.sample_size <= 20
        # Each result classified exactly once
        total = (report.pass_count + report.locked_count
                 + report.parse_error_count + report.empty_count)
        assert total == report.sample_size
    finally:
        if session:
            session.close()


@requires_production_db
def test_survey_pass_rate_nontrivial():
    """At time of writing, the translator passes a meaningful fraction of real
    production methods. Threshold is conservative (≥ 30%) so it survives
    incidental drift in the production data."""
    session = open_readonly_session()
    try:
        report = run_translation_survey(session, DEFAULT_REPO_ID, sample_size=20)
        nonempty = report.sample_size - report.empty_count
        if nonempty == 0:
            pytest.skip("no non-empty methods in sample")
        assert report.pass_rate >= 0.30, f"unexpectedly low pass rate: {report.pass_rate}"
    finally:
        if session:
            session.close()


@requires_production_db
def test_survey_surfaces_locked_notes_when_any():
    session = open_readonly_session()
    try:
        report = run_translation_survey(session, DEFAULT_REPO_ID, sample_size=20)
        # If any method locked, there must be at least one note explaining why
        if report.locked_count > 0:
            assert len(report.locked_notes) > 0
            for note in report.locked_notes:
                assert isinstance(note, str)
                assert note
    finally:
        if session:
            session.close()
