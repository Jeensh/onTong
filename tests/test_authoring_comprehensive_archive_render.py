"""P1a-E — comprehensive_archive deterministic markdown rendering."""

from __future__ import annotations

from backend.application.authoring.capabilities.comprehensive_archive import (
    ComprehensiveArchiveBody,
    CrossCuttingObservation,
    EntitySectionSummary,
    _render_markdown,
)


def _body_minimal() -> ComprehensiveArchiveBody:
    return ComprehensiveArchiveBody(
        title="Slab 도메인 — 2 entity",
        executive_summary="2 entity 처리. master/child 패턴 적용.",
        entity_sections=[
            EntitySectionSummary(
                class_name="HrPlantJpo",
                candidate_term_korean="열연공장",
                candidate_term_english="HrPlant",
                domain_role="standard",
                accepted_option_name="단일 master",
                persisted_fqns=["term.scm.hr_plant"],
                summary_korean="공장 마스터로 채택.",
                notable_gaps_or_concerns=["region_code 의미 미확정"],
            ),
        ],
        cross_cutting_observations=[
            CrossCuttingObservation(
                title="Hr* prefix 일관 적용",
                description_korean="모든 entity 가 Hr 접두사를 가짐.",
                affected_entities=["HrPlantJpo"],
            )
        ],
        decisions_made=["PartitionType=String 으로 통일"],
        next_steps_korean=["region_code lookup table 별도 작업"],
    )


def test_render_includes_title_and_executive_summary():
    md = _render_markdown(_body_minimal(), repo_id="slab-design-real")
    assert "# Slab 도메인 — 2 entity" in md
    assert "## 요약" in md
    assert "2 entity 처리. master/child 패턴 적용." in md


def test_render_per_entity_section_has_persisted_fqns():
    md = _render_markdown(_body_minimal(), repo_id="x")
    assert "### 1. HrPlantJpo → HrPlant (열연공장)" in md
    assert "**역할**: standard" in md
    assert "**채택 옵션**: 단일 master" in md
    assert "`term.scm.hr_plant`" in md
    assert "**미해결/주의**:" in md
    assert "region_code 의미 미확정" in md


def test_render_cross_cutting_observations():
    md = _render_markdown(_body_minimal(), repo_id="x")
    assert "## 종합 관찰 (1)" in md
    assert "### Hr* prefix 일관 적용" in md
    assert "_관련 entity_: HrPlantJpo" in md


def test_render_decisions_and_next_steps():
    md = _render_markdown(_body_minimal(), repo_id="x")
    assert "## 이번 세션 결정" in md
    assert "- PartitionType=String 으로 통일" in md
    assert "## 다음 세션 follow-up" in md
    assert "- region_code lookup table 별도 작업" in md


def test_render_skips_optional_sections_when_empty():
    body = ComprehensiveArchiveBody(
        title="t",
        executive_summary="s",
        entity_sections=[
            EntitySectionSummary(
                class_name="J",
                candidate_term_korean="K",
                candidate_term_english="E",
                domain_role="standard",
                accepted_option_name=None,
                persisted_fqns=[],
                summary_korean="ok",
                notable_gaps_or_concerns=[],
            ),
        ],
        cross_cutting_observations=[],
        decisions_made=[],
        next_steps_korean=[],
    )
    md = _render_markdown(body, repo_id="")
    assert "## 종합 관찰" not in md
    assert "## 이번 세션 결정" not in md
    assert "## 다음 세션 follow-up" not in md
    # No accepted_option_name → no '채택 옵션' bit
    assert "**채택 옵션**" not in md
    # No persisted FQNs → no Persisted line
    assert "**Persisted**" not in md
