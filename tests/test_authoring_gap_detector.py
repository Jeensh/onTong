"""S — Gap Detector (Opus) capability tests.

Two integration scenarios verify two of the four gap kinds:
  - HrPlant w/ wildcard contradiction → at least 1 `intent`-class gap
  - HrPlant w/ no contradictions      → empty `gaps` (no false positives)
"""

from __future__ import annotations

import asyncio
import os

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import answer_absorber as aa
from backend.application.authoring.capabilities import code_extractor as ce
from backend.application.authoring.capabilities import gap_detector as gd
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.schemas import ModelTier


# ── Fixtures ─────────────────────────────────────────────────────────


def _hr_spec_jpo() -> ce.ExtractedJpo:
    """Hand-built ExtractedJpo for HrSpec — avoids depending on cap1 at unit level."""
    return ce.ExtractedJpo(
        package="com.example.slabdesign.store.sd.std.oracle.jpo",
        class_name="HrSpecJpo",
        table_name="HR_SPEC",
        pk_class="HrSpecPK",
        class_docstring="sd · std · HR_SPEC — 열연설비사양기준 JPO. 룩업 시 ORDER_OS.CONFIRMED_PLANT_CD 의 2자리(열연위치) → HR_PLANT_CD 매칭.",
        pk_columns=[
            ce.CodeColumn(name="cmpCd", db_column="CMP_CD", java_type="String", db_length=2, is_pk=True),
            ce.CodeColumn(name="orgCd", db_column="ORG_CD", java_type="String", db_length=1, is_pk=True),
            ce.CodeColumn(
                name="hrPlantCd",
                db_column="HR_PLANT_CD",
                java_type="String",
                db_length=1,
                is_pk=True,
                comment="열연공장코드 (확통2자리)",
            ),
            ce.CodeColumn(
                name="productTypeCd",
                db_column="PRODUCT_TYPE_CD",
                java_type="String",
                db_length=4,
                is_pk=True,
            ),
        ],
        regular_columns=[
            ce.CodeColumn(name="widthLow", db_column="WIDTH_LOW", java_type="BigDecimal",
                          db_precision=10, db_scale=2, comment="step 2 폭하한 계산"),
            ce.CodeColumn(name="widthHigh", db_column="WIDTH_HIGH", java_type="BigDecimal",
                          db_precision=10, db_scale=2, comment="step 2 폭상한 계산"),
            ce.CodeColumn(name="lengthLow", db_column="LENGTH_LOW", java_type="BigDecimal",
                          db_precision=10, db_scale=2, comment="step 3 길이하한 계산"),
            ce.CodeColumn(name="lengthHigh", db_column="LENGTH_HIGH", java_type="BigDecimal",
                          db_precision=10, db_scale=2, comment="step 3 길이상한 계산"),
        ],
    )


def _hr_spec_hypothesis() -> hp.EntityHypothesis:
    return hp.EntityHypothesis(
        candidate_term_korean="열연공장 표준",
        candidate_term_english="HrSpec",
        domain_role="standard",
        pk_role_summary="온톨로지·소·열연공장·품종 4축 — 한 row = 한 열연공장의 한 품종에 대한 폭/길이 범위",
        column_notes=[
            hp.ColumnNote(db_column="WIDTH_LOW", note="폭 하한 (mm)"),
            hp.ColumnNote(db_column="WIDTH_HIGH", note="폭 상한 (mm)"),
        ],
        relations_hint=["PK 의 PRODUCT_TYPE_CD 가 자식 entity 분리 신호"],
        domain_questions=[],
        confidence=0.6,
        assumptions=["HrSpecService.lookup 은 정확매칭만 (와일드카드 없음)"],
        concerns=[],
    )


def _answers_with_wildcard_contradiction() -> aa.AbsorbedAnswers:
    """User explicitly contradicts the 'exact match only' assumption."""
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
                raw_text="*도 쓸 수 있고 LIKE 패턴도 지원해. NULL 이면 자동 true 로 처리됨.",
                normalized="와일드카드 + LIKE 매칭, NULL=자동 true",
                contradicts_my_guess=True,
                contradicts_note="가설은 정확매칭만, 실제는 *+LIKE+NULL 모두 지원",
            ),
            "miss": aa.AbsorbedAnswer(
                question_id="miss",
                raw_text="기준 없으면 NPE 발생 — 데이터 결함",
                normalized="룩업 실패 → NPE (데이터 결함)",
            ),
        },
        unanswered=[],
        emergent_facts=["NULL PK 컬럼은 자동 true (조건 무시) 로 처리"],
        contradictions=["wildcard: 가설(정확매칭만) vs 실제(*+LIKE+NULL)"],
    )


def _answers_no_contradiction() -> aa.AbsorbedAnswers:
    """Clean answers fully consistent with hypothesis — gap detector should return empty."""
    return aa.AbsorbedAnswers(
        per_question={
            "owner": aa.AbsorbedAnswer(
                question_id="owner",
                raw_text="공정계획",
                normalized="공정계획",
                picked_option="공정계획",
            ),
            "wildcard": aa.AbsorbedAnswer(
                question_id="wildcard",
                raw_text="와일드카드 없음",
                normalized="정확매칭만",
            ),
            "miss": aa.AbsorbedAnswer(
                question_id="miss",
                raw_text="DG 에러로 즉시 중단",
                normalized="룩업 실패 → DG 에러",
            ),
        },
        unanswered=[],
        emergent_facts=[],
        contradictions=[],
    )


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert gd.CAPABILITY_NAME == "gap_detector"
    assert gd.TIER == ModelTier.HARD


def test_prompt_loads_and_lists_four_gap_kinds():
    p = gd._system_prompt()
    for kind in ("structure", "consistency", "intent", "historical"):
        assert kind in p


def test_settings_enable_instruction_caching():
    assert gd._settings().get("anthropic_cache_instructions") is True


def test_gap_analysis_schema_round_trip_with_one_gap():
    g = gd.GapAnalysis(
        gaps=[
            gd.Gap(
                id="wildcard_lookup_intent",
                kind="intent",
                severity="high",
                title="HrSpec 룩업이 와일드카드/LIKE 매칭이지만 코드는 정확매칭만 구현",
                description=(
                    "사용자는 PK 컬럼에 '*' 와 'LIKE' 매칭이 가능하다고 했고 NULL 은 자동 true. "
                    "하지만 HrSpecService.lookup 은 findById 정확매칭만 호출. "
                    "코드와 실제 운영 룩업 동작 사이 갭."
                ),
                evidence_code="HrSpecService.lookup(...) → repository.findById(pk)",
                evidence_domain="사용자: \"*도 쓸 수 있고 LIKE 패턴도 지원해. NULL 이면 자동 true.\"",
                recommended_resolution="code_fix_scenario",
                resolution_rationale="ontology 가 실제 도메인을 표현 — 코드 수정 필요. 영향도 분석 demo 시나리오.",
                demo_potential=True,
            )
        ],
        severity_summary="high 1건",
        blocks_modeling=False,
        recommendation="옵션 제시 전에 룩업 동작 확인 필요. 사용자에게 정확매칭 vs 와일드카드 처리 방식 합의 요청.",
    )
    blob = g.model_dump_json()
    g2 = gd.GapAnalysis.model_validate_json(blob)
    assert len(g2.gaps) == 1
    assert g2.gaps[0].kind == "intent"
    assert g2.gaps[0].demo_potential is True


def test_gap_analysis_schema_allows_empty_gaps():
    """No-gap result is a valid output — false positives are explicitly disallowed."""
    g = gd.GapAnalysis(
        gaps=[],
        severity_summary="갭 없음",
        blocks_modeling=False,
        recommendation="추가 갭 없음 — 옵션 제시로 진행해도 됩니다.",
    )
    assert g.gaps == []


def test_format_includes_pk_columns_and_korean_comments_and_contradictions():
    text = gd._format_for_prompt(
        _hr_spec_jpo(), _hr_spec_hypothesis(), _answers_with_wildcard_contradiction()
    )
    assert "HR_PLANT_CD" in text
    assert "확통2자리" in text  # JPO comment preserved
    assert "step 2 폭하한 계산" in text  # regular column comment preserved
    assert "공정계획" in text  # user answer
    assert "CONTRADICTS" in text
    assert "Contradictions" in text  # top-level section
    assert "Emergent facts" in text


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_detects_intent_gap_when_user_contradicts_lookup():
    """Sonnet/Opus call: contradictory wildcard answer should yield ≥1 gap.

    The user explicitly contradicted the 'exact match only' assumption →
    Opus should surface an `intent`-kind gap citing the wildcard contradiction.
    """
    cost_mod.reset_buffer()
    gd.reset_caches()

    out = asyncio.run(
        gd.detect_gaps(
            _hr_spec_jpo(),
            _hr_spec_hypothesis(),
            _answers_with_wildcard_contradiction(),
            session_id="cap5-contradiction",
            turn_no=1,
        )
    )

    assert len(out.gaps) >= 1, "expected ≥1 gap when user contradicts hypothesis"

    # Some gap should be of kind 'intent' (or 'consistency') and cite wildcard
    relevant = [
        g
        for g in out.gaps
        if g.kind in {"intent", "consistency", "structure"}
        and (
            "와일드카드" in g.title
            or "와일드카드" in g.description
            or "LIKE" in g.description
            or "wildcard" in g.description.lower()
            or "*" in g.evidence_domain
        )
    ]
    assert relevant, f"expected gap citing wildcard/LIKE, got: {[g.title for g in out.gaps]}"

    # Each gap has both code + domain evidence
    for g in out.gaps:
        assert g.evidence_code.strip(), f"gap {g.id} missing code evidence"
        assert g.evidence_domain.strip(), f"gap {g.id} missing domain evidence"
        assert g.recommended_resolution in {
            "simplification_note",
            "code_fix_scenario",
            "business_intent",
            "investigate",
        }

    assert out.severity_summary.strip()
    assert out.recommendation.strip()

    records = cost_mod.session_records("cap5-contradiction")
    assert len(records) == 1
    assert records[0].capability == "gap_detector"
    assert records[0].tier == ModelTier.HARD


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_no_false_positive_gaps_when_answers_consistent():
    """Clean consistent answers should not manufacture gaps.

    This is the trust-bar test — the user said the prompt explicitly forbids
    fabrication. With zero contradictions and zero emergent facts, the result
    should ideally be empty, or at most contain `historical`-kind gaps about
    docstring TODOs that we did not include in our fixture (so 0 expected).
    """
    cost_mod.reset_buffer()
    gd.reset_caches()

    out = asyncio.run(
        gd.detect_gaps(
            _hr_spec_jpo(),
            _hr_spec_hypothesis(),
            _answers_no_contradiction(),
            session_id="cap5-clean",
            turn_no=1,
        )
    )

    # Allow at most 1 low-severity gap (the model may flag the HR_PLANT_CD / HR_CD
    # naming inconsistency from the docstring even with our restricted JPO — fine).
    assert len(out.gaps) <= 1, (
        f"expected 0–1 gaps with consistent answers, got {len(out.gaps)}: "
        f"{[g.title for g in out.gaps]}"
    )
    if out.gaps:
        # Whatever is reported must be low/medium, never high — we did not give
        # any contradictory evidence.
        for g in out.gaps:
            assert g.severity in {"low", "medium"}, (
                f"Should not surface high-severity gap from clean answers: {g.title}"
            )
            assert g.evidence_domain.strip(), "even consistent runs must cite domain evidence"
