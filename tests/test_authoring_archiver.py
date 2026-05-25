"""S — Archiver capability tests."""

from __future__ import annotations

import asyncio
import os

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import answer_absorber as aa
from backend.application.authoring.capabilities import archiver as ar
from backend.application.authoring.capabilities import gap_detector as gd
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.capabilities import naming as nm
from backend.application.authoring.capabilities import option_proposer as op
from backend.application.authoring.schemas import ModelTier


# ── Fixtures (mini end-to-end inputs for archiver) ───────────────────


def _hypothesis() -> hp.EntityHypothesis:
    return hp.EntityHypothesis(
        candidate_term_korean="열연공장 표준",
        candidate_term_english="HrSpec",
        domain_role="standard",
        pk_role_summary="온톨로지·소·열연공장·품종 4축",
        column_notes=[],
        relations_hint=[],
        domain_questions=[],
        confidence=0.6,
        assumptions=[],
        concerns=[],
    )


def _answers() -> aa.AbsorbedAnswers:
    return aa.AbsorbedAnswers(
        per_question={
            "owner": aa.AbsorbedAnswer(
                question_id="owner",
                raw_text="공정계획에서 관리해",
                normalized="공정계획",
                picked_option="공정계획",
            ),
            "wildcard": aa.AbsorbedAnswer(
                question_id="wildcard",
                raw_text="*도 쓸 수 있고 LIKE 도 지원",
                normalized="와일드카드 + LIKE 매칭",
                contradicts_my_guess=True,
                contradicts_note="가설은 정확매칭만, 실제는 *+LIKE",
            ),
            "miss": aa.AbsorbedAnswer(
                question_id="miss",
                raw_text="기준 없으면 NPE",
                normalized="룩업 실패 → NPE",
            ),
            "extra": aa.AbsorbedAnswer(question_id="extra", is_unknown=True),
        },
        unanswered=["extra"],
        emergent_facts=["NULL PK 컬럼은 자동 true"],
        contradictions=["wildcard: 가설(정확매칭만) vs 실제(*+LIKE)"],
    )


def _accepted_option() -> op.OntologyOption:
    return op.OntologyOption(
        id="C",
        name="옵션 C — Plant + Constraint Composition",
        description="HrPlant 와 그 산하 HrPlantConstraint 로 분리.",
        structure_sketch="HrPlant\n  └── N HrPlantConstraint",
        pros=["도메인 응집 ↑"],
        cons=["entity 수 증가"],
        entities_count_hint="중간 (1+N)",
        domain_alignment="high",
        trade_offs_one_line="도메인 ↑ / entity 수 ↑",
    )


def _names() -> nm.NamingDecision:
    return nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연공장",
                english_id="HrPlant",
                role="root",
                description_short="온톨로지·소 단위의 물리 열연 설비",
            ),
            nm.EntityName(
                korean_label="열연공장제약",
                english_id="HrPlantConstraint",
                role="child",
                parent_english_id="HrPlant",
                description_short="열연공장 산하 품종별 폭/길이 제약",
            ),
        ],
        naming_conflicts=[],
        naming_rationale="parent prefix 'HrPlant' 유지로 형제 패턴 일관.",
    )


def _gap_high() -> gd.GapAnalysis:
    return gd.GapAnalysis(
        gaps=[
            gd.Gap(
                id="wildcard_intent",
                kind="intent",
                severity="high",
                title="HrSpec 룩업이 와일드카드/LIKE 매칭이지만 코드는 정확매칭만 구현",
                description="사용자는 *+LIKE 매칭 가능 — 코드는 findById 정확매칭.",
                evidence_code="HrSpecService.lookup → repository.findById(pk)",
                evidence_domain="사용자: \"*도 쓸 수 있고 LIKE 도 지원\"",
                recommended_resolution="code_fix_scenario",
                resolution_rationale="ontology 가 도메인 정확 표현 — 코드 수정 필요. 영향도 분석 demo 시나리오.",
                demo_potential=True,
            )
        ],
        severity_summary="high 1건",
        blocks_modeling=False,
        recommendation="옵션 결정 후 wildcard 처리 합의 필요.",
    )


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert ar.CAPABILITY_NAME == "archiver"
    assert ar.TIER == ModelTier.STANDARD


def test_prompt_loads_and_mentions_archive_pattern():
    p = ar._system_prompt()
    assert "received" in p.lower() or "받은 가르침" in p
    assert "structure_diagram" in p


def test_settings_enable_instruction_caching():
    assert ar._settings().get("anthropic_cache_instructions") is True


def test_archive_body_round_trip():
    b = ar.ArchiveBody(
        summary_korean="HrPlant + HrPlantConstraint 분리 채택. 와일드카드 갭 발견.",
        decisions=[
            ar.ArchiveDecision(
                topic_korean="모델링 옵션",
                decision_korean="옵션 C (Plant + Constraint Composition)",
                rationale_korean="도메인 응집 ↑, 사용자 답변 일치",
            )
        ],
        structure_diagram="HrPlant\n  └── N HrPlantConstraint",
    )
    blob = b.model_dump_json()
    b2 = ar.ArchiveBody.model_validate_json(blob)
    assert b2.decisions[0].topic_korean == "모델링 옵션"


def test_format_for_prompt_includes_all_inputs():
    text = ar._format_for_prompt(
        _hypothesis(), _answers(), _accepted_option(), _names(), _gap_high()
    )
    # Names
    assert "HrPlant" in text and "HrPlantConstraint" in text
    # Option
    assert "옵션 C" in text
    # Hypothesis
    assert "열연공장 표준" in text
    # Answered fields only (extra was unknown — should not appear)
    assert "owner" in text and "공정계획" in text
    assert "wildcard" in text
    assert "extra" not in text  # unknown filtered out
    # Emergent facts
    assert "NULL" in text
    # Gap
    assert "wildcard_intent" in text
    assert "code_fix_scenario" in text


def test_format_handles_no_gaps():
    text = ar._format_for_prompt(
        _hypothesis(), _answers(), _accepted_option(), _names(), gaps=None
    )
    assert "Detected gaps" not in text


def test_render_markdown_table_escapes_pipes():
    body = ar.ArchiveBody(
        summary_korean="요약",
        decisions=[
            ar.ArchiveDecision(
                topic_korean="필드 | 충돌",
                decision_korean="A | B",
                rationale_korean="이유",
            )
        ],
        structure_diagram="X",
    )
    md = ar._render_markdown(
        title="t", status="completed", body=body, accepted_option=_accepted_option()
    )
    assert "필드 \\| 충돌" in md
    assert "A \\| B" in md


def test_render_markdown_includes_status_badge_and_sections():
    body = ar.ArchiveBody(
        summary_korean="요약 텍스트",
        decisions=[
            ar.ArchiveDecision(
                topic_korean="모델링", decision_korean="옵션 C", rationale_korean="응집 ↑"
            )
        ],
        structure_diagram="HrPlant\n  └── N HrPlantConstraint",
    )
    md = ar._render_markdown(
        title="Step 1 — 열연공장 entity 결정 ✓",
        status="partial",
        body=body,
        accepted_option=_accepted_option(),
    )
    assert "# Step 1 — 열연공장 entity 결정 ✓" in md
    assert "⚠️ 부분 완료" in md  # partial badge
    assert "## 요약" in md
    assert "## 채택 옵션" in md
    assert "## 구조" in md
    assert "## 결정 사항" in md
    assert "```" in md
    assert "HrPlant" in md


def test_build_title_uses_root_or_standalone_label():
    names_root_child = _names()
    assert ar._build_title(names_root_child, step_number=3) == (
        "Step 3 — 열연공장 entity 결정 ✓"
    )
    # Without step number
    assert ar._build_title(names_root_child, step_number=None) == (
        "열연공장 entity 결정 ✓"
    )

    # Standalone-only case
    standalone = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연Edging규격그룹기준",
                english_id="EdgingGroupRule",
                role="standalone",
                description_short="온톨로지·소 단위 그룹 분류 룰",
            )
        ],
        naming_rationale="r",
    )
    assert "열연Edging규격그룹기준" in ar._build_title(standalone, 5)


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_archive_for_hr_plant_cycle():
    """Real Sonnet call: produces summary + decisions + diagram, Python wraps markdown.

    Acceptance bar:
      - status == 'partial' when a high-severity gap is present
      - body.summary_korean non-empty Korean
      - body.decisions has rows for at least: 모델링 옵션, 명명, 갭 처리
      - body.structure_diagram contains both HrPlant and HrPlantConstraint
        (uses the names from the NamingDecision verbatim)
      - rendered markdown contains the title, ⚠️ partial badge, structure
        code-fence, and the decisions table
      - cost logged for one Sonnet call
    """
    cost_mod.reset_buffer()
    ar.reset_caches()

    out = asyncio.run(
        ar.archive_entity_cycle(
            hypothesis=_hypothesis(),
            answers=_answers(),
            accepted_option=_accepted_option(),
            names=_names(),
            gaps=_gap_high(),
            step_number=3,
            session_id="cap9-integration",
            turn_no=1,
        )
    )

    assert out.status == "partial", "high-severity gap should mark archive partial"
    assert out.title == "Step 3 — 열연공장 entity 결정 ✓"
    assert out.body.summary_korean.strip()

    decision_topics = [d.topic_korean for d in out.body.decisions]
    # Required topics — verify by substring (model can phrase variably)
    assert any("옵션" in t or "모델링" in t for t in decision_topics), (
        f"missing 모델링 옵션 row: {decision_topics}"
    )
    assert any("명명" in t or "이름" in t for t in decision_topics), (
        f"missing 명명 row: {decision_topics}"
    )
    assert any("갭" in t or "와일드카드" in t for t in decision_topics), (
        f"missing 갭/wildcard row: {decision_topics}"
    )

    diagram = out.body.structure_diagram
    assert "HrPlant" in diagram and "HrPlantConstraint" in diagram, (
        f"diagram should reuse final names: {diagram!r}"
    )

    md = out.markdown
    assert "# Step 3 — 열연공장 entity 결정 ✓" in md
    assert "⚠️ 부분 완료" in md
    assert "```" in md and "HrPlant" in md
    assert "| 항목 | 결정 | 근거 |" in md
    # Each decision row appears in the rendered table
    for d in out.body.decisions:
        # Allow Markdown rendering to escape pipes
        topic_safe = d.topic_korean.replace("|", "\\|")
        assert topic_safe in md, f"decision row missing from markdown: {d.topic_korean}"

    records = cost_mod.session_records("cap9-integration")
    assert len(records) == 1
    assert records[0].capability == "archiver"
    assert records[0].tier == ModelTier.STANDARD
