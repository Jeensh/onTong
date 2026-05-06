"""P1a-D — pattern_checker prompt accepts prior_session_entities."""

from __future__ import annotations

from backend.application.authoring.capabilities import pattern_checker as pc
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.capabilities.option_proposer import OntologyOption


def _hypothesis() -> EntityHypothesis:
    return EntityHypothesis(
        candidate_term_korean="HrPlantConstraint",
        candidate_term_english="HrPlantConstraint",
        domain_role="rule_table",
        pk_role_summary="공장+제약 PK",
        column_notes=[],
        relations_hint=[],
        domain_questions=["q1"],
        confidence=0.55,
        assumptions=[],
        concerns=[],
    )


def _option() -> OntologyOption:
    return OntologyOption(
        id="A",
        name="단일 entity",
        description="HrPlantConstraint 단독",
        structure_sketch="HrPlantConstraint",
        pros=["단순"],
        cons=["관계 표현 어려움"],
        entities_count_hint="1",
        domain_alignment="medium",
        trade_offs_one_line="단순함 vs 표현력",
    )


def test_format_no_priors_omits_prior_section():
    text = pc._format_for_prompt(_hypothesis(), _option(), None)
    assert "Prior entities completed THIS SESSION" not in text


def test_format_with_priors_renders_each_entity():
    priors = [
        pc.PriorEntitySnapshot(
            class_name="HrPlantJpo",
            candidate_term_korean="열연공장",
            candidate_term_english="HrPlant",
            domain_role="standard",
            accepted_option_name="단일 master entity",
            accepted_option_structure="HrPlant\n  pk: hrPlantCd",
            accepted_option_alignment="high",
            persisted_fqns=["term.scm.hr_plant"],
            archive_summary="공장 마스터 — 4개 PK 컬럼",
        ),
        pc.PriorEntitySnapshot(
            class_name="HrSpecJpo",
            candidate_term_korean="열연 사양",
            candidate_term_english="HrSpec",
            domain_role="standard",
            accepted_option_name="HrPlant 마스터 + 자매 standard",
            accepted_option_structure="HrSpec ◇ HrPlant",
            accepted_option_alignment="high",
            persisted_fqns=[],
            archive_summary=None,
        ),
    ]
    text = pc._format_for_prompt(_hypothesis(), _option(), priors)
    # Header + count
    assert "Prior entities completed THIS SESSION" in text
    assert "Prior #1 — HrPlantJpo" in text
    assert "Prior #2 — HrSpecJpo" in text
    # Important fields rendered
    assert "열연공장" in text
    assert "단일 master entity" in text
    assert "term.scm.hr_plant" in text
    # Alignment carried through
    assert "alignment: high" in text


def test_format_handles_partial_prior_no_accepted_option():
    """Prior cycle where user moved on without accepting an option — only
    the hypothesis is set. Renderer must not crash on Nones."""
    priors = [
        pc.PriorEntitySnapshot(
            class_name="MysteryJpo",
            candidate_term_korean="신비",
            candidate_term_english="Mystery",
            domain_role="unknown",
            accepted_option_name=None,
            accepted_option_structure=None,
            accepted_option_alignment=None,
            persisted_fqns=[],
            archive_summary=None,
        ),
    ]
    text = pc._format_for_prompt(_hypothesis(), _option(), priors)
    assert "Prior #1 — MysteryJpo" in text
    # No accepted option block
    assert "채택 옵션" not in text.split("Prior #1")[1].split("\n# ")[0]


def test_format_truncates_archive_summary_at_300_chars():
    long = "x" * 500
    priors = [
        pc.PriorEntitySnapshot(
            class_name="J",
            candidate_term_korean="K",
            candidate_term_english="E",
            domain_role="standard",
            accepted_option_name=None,
            accepted_option_structure=None,
            accepted_option_alignment=None,
            persisted_fqns=[],
            archive_summary=long,
        ),
    ]
    text = pc._format_for_prompt(_hypothesis(), _option(), priors)
    # 300 chars max — assert the slice happened (full 500-char string not in)
    assert "x" * 300 in text
    assert "x" * 301 not in text
