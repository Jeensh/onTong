"""S — Option Proposer (Opus) capability tests."""

from __future__ import annotations

import asyncio
import os

import pytest
from pydantic import ValidationError

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import answer_absorber as aa
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.capabilities import option_proposer as op
from backend.application.authoring.schemas import ModelTier


# ── Fixtures ─────────────────────────────────────────────────────────


def _hr_plant_hypothesis() -> hp.EntityHypothesis:
    return hp.EntityHypothesis(
        candidate_term_korean="열연공장 표준",
        candidate_term_english="HrSpec",
        domain_role="standard",
        pk_role_summary=(
            "온톨로지·소·열연공장·품종 4축 조합 — 한 row = 한 열연공장의 한 품종에 대한 폭/길이 범위"
        ),
        column_notes=[
            hp.ColumnNote(db_column="WIDTH_LOW", note="step 2 폭하한 계산"),
            hp.ColumnNote(db_column="WIDTH_HIGH", note="step 2 폭상한 계산"),
            hp.ColumnNote(db_column="LENGTH_LOW", note="step 3 길이하한 계산"),
            hp.ColumnNote(db_column="LENGTH_HIGH", note="step 3 길이상한 계산"),
        ],
        relations_hint=[
            "PK 가 (CMP, ORG, HR_PLANT_CD, PRODUCT_TYPE_CD) — 앞 3축은 HrPlant, 뒤 1축은 품종 → 자식 entity 가능",
        ],
        domain_questions=[
            "이 표준은 열연공장의 능력인가, 품종별 제약인가?",
            "와일드카드 매칭 사용?",
            "룩업 실패 시 처리?",
        ],
        confidence=0.55,
        assumptions=["HR_PLANT_CD 는 8자 confirmedPlantCd 의 한 자리"],
        concerns=["table 명 HR_SPEC vs 도메인 어휘 '열연공장' 불일치"],
    )


def _hr_plant_answers() -> aa.AbsorbedAnswers:
    """Realistic absorbed answers showing user confirms the hypothesis but adds wildcard semantics."""
    return aa.AbsorbedAnswers(
        per_question={
            "meaning": aa.AbsorbedAnswer(
                question_id="meaning",
                raw_text="열연공장의 능력 + 품종별 제약. 즉 온톨로지·소·공장 단위의 설비, 그 산하에 품종별 제약",
                normalized="열연공장 (설비) + 품종별 제약 — composite 가능성",
            ),
            "owner": aa.AbsorbedAnswer(
                question_id="owner",
                raw_text="공정계획에서 관리해",
                normalized="공정계획",
                picked_option="공정계획",
            ),
            "wildcard": aa.AbsorbedAnswer(
                question_id="wildcard",
                raw_text="*도 쓸 수 있고 LIKE 도 지원, NULL 은 자동 true",
                normalized="와일드카드 + LIKE 매칭, NULL=자동 true",
                contradicts_my_guess=True,
                contradicts_note="가설은 정확매칭만, 실제는 *+LIKE 모두 지원",
            ),
            "miss": aa.AbsorbedAnswer(
                question_id="miss",
                raw_text="기준 없으면 NPE — 데이터 결함",
                normalized="룩업 실패 → NPE (데이터 결함)",
            ),
            "row_size": aa.AbsorbedAnswer(
                question_id="row_size",
                raw_text="수십 정도",
                normalized="수십",
            ),
            "extra": aa.AbsorbedAnswer(question_id="extra", is_unknown=True),
        },
        unanswered=["extra"],
        emergent_facts=["NULL PK 컬럼은 자동 true (조건 무시) 로 처리"],
        contradictions=["wildcard: 가설(정확매칭만) vs 실제(*+LIKE+NULL)"],
    )


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert op.CAPABILITY_NAME == "option_proposer"
    assert op.TIER == ModelTier.HARD


def test_prompt_loads_and_mentions_step5_pattern():
    p = op._system_prompt()
    assert "옵션" in p or "Option" in p
    assert "recommended_id" in p
    assert "domain_alignment" in p


def test_settings_enable_instruction_caching():
    assert op._settings().get("anthropic_cache_instructions") is True


def test_option_table_validator_rejects_dangling_recommended_id():
    with pytest.raises(ValidationError, match="not in options"):
        op.OptionTable(
            title="t",
            context_summary="s",
            options=[
                op.OntologyOption(
                    id="A",
                    name="옵션 A",
                    description="A 옵션 설명",
                    structure_sketch="HrSpec",
                    pros=["단순"],
                    cons=["응집 약함"],
                    entities_count_hint="중간",
                    domain_alignment="medium",
                    trade_offs_one_line="단순 / 응집 약함",
                ),
                op.OntologyOption(
                    id="B",
                    name="옵션 B",
                    description="B 옵션 설명",
                    structure_sketch="Plant + Spec",
                    pros=["도메인 ↑"],
                    cons=["row 추적 ↓"],
                    entities_count_hint="중간",
                    domain_alignment="high",
                    trade_offs_one_line="도메인 ↑ / 추적 ↓",
                ),
            ],
            recommended_id="Z",  # not in options → must fail
            recommendation_reasoning="r",
        )


def test_option_table_round_trip():
    t = op.OptionTable(
        title="HrSpec 모델링",
        context_summary="와일드카드 + 품종별 제약 확인 후 결정",
        options=[
            op.OntologyOption(
                id="A",
                name="옵션 A — Spec only",
                description="HrSpec 만 entity. 코드와 1:1.",
                structure_sketch="HrSpec",
                pros=["단순"],
                cons=["도메인 의미 손실"],
                entities_count_hint="최소",
                domain_alignment="low",
                trade_offs_one_line="단순 / 도메인 ↓",
            ),
            op.OntologyOption(
                id="C",
                name="옵션 C — Plant + Constraint",
                description="HrPlant + N HrPlantConstraint 분리. 품종은 자식.",
                structure_sketch="HrPlant ── N HrPlantConstraint",
                pros=["도메인 응집 ↑", "row-level 추적 가능"],
                cons=["entity 수 증가"],
                entities_count_hint="중간 (1+N)",
                domain_alignment="high",
                trade_offs_one_line="도메인 ↑ / entity 수 ↑",
            ),
        ],
        recommended_id="C",
        recommendation_reasoning="사용자 답변에서 '열연공장 + 품종별 제약' 확인 — 옵션 C 가 도메인 멘탈 모델과 일치.",
        caveats=["entity 수가 늘어남 — UI 에서 navigation 필요"],
    )
    blob = t.model_dump_json()
    t2 = op.OptionTable.model_validate_json(blob)
    assert t2.recommended_id == "C"
    assert len(t2.options) == 2


def test_format_includes_contradictions_and_emergent_facts():
    text = op._format_for_prompt(
        _hr_plant_hypothesis(),
        _hr_plant_answers(),
        pattern_library=["Plant + Constraint Composition (Step 5)"],
    )
    assert "와일드카드" in text
    assert "공정계획" in text
    assert "CONTRADICTS" in text
    assert "Emergent facts" in text
    assert "NULL" in text
    assert "Plant + Constraint Composition" in text


def test_format_handles_no_pattern_library():
    text = op._format_for_prompt(_hr_plant_hypothesis(), _hr_plant_answers(), None)
    assert "Pattern library" not in text


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_option_table_for_hr_plant():
    """Real Opus call. Acceptance bar mirrors what Round 5 Step 5 produced:

      - 2..4 options
      - At least one option clearly favours Plant+Constraint composition
        (the user just confirmed plant + per-품종 제약 in answers)
      - Recommended option's domain_alignment is 'high' OR the option contains
        Korean substring '제약' / 'Constraint' / 'Composition' in its name
      - recommendation_reasoning references at least one of: 사용자 / 답변 /
        와일드카드 / 공정계획 / 품종 (the absorbed answers)
      - caveats may be empty but `caveats: list` exists
      - Cost logged for one Opus call
    """
    cost_mod.reset_buffer()
    op.reset_caches()

    table = asyncio.run(
        op.propose_options(
            _hr_plant_hypothesis(),
            _hr_plant_answers(),
            pattern_library=None,  # cold start — no library yet
            session_id="cap6-integration",
            turn_no=1,
        )
    )

    # Shape
    assert 2 <= len(table.options) <= 4

    # recommended_id in options (the validator already enforced this, but
    # double-check the deserialised value is sane)
    ids = [o.id for o in table.options]
    assert table.recommended_id in ids

    # Recommended option signals plant/constraint shape OR has high alignment
    rec = next(o for o in table.options if o.id == table.recommended_id)
    name_blob = (rec.name + " " + rec.description + " " + rec.structure_sketch).lower()
    favours_composition = any(
        kw in name_blob
        for kw in ("constraint", "composition", "제약", "산하", "plant +")
    )
    assert favours_composition or rec.domain_alignment == "high", (
        f"recommended option {rec.id!r} does not signal plant+constraint shape; "
        f"name={rec.name!r}, alignment={rec.domain_alignment!r}"
    )

    # Recommendation reasoning cites the user / their answers
    reasoning = table.recommendation_reasoning
    assert any(
        kw in reasoning
        for kw in ("사용자", "답변", "와일드카드", "공정계획", "품종", "열연공장")
    ), f"reasoning does not cite user evidence: {reasoning!r}"

    # Each option has structured trade-offs
    for o in table.options:
        assert o.structure_sketch.strip(), f"option {o.id} missing structure_sketch"
        assert o.trade_offs_one_line.strip(), f"option {o.id} missing trade_offs_one_line"
        assert o.domain_alignment in {"high", "medium", "low"}

    # Cost summary
    records = cost_mod.session_records("cap6-integration")
    assert len(records) == 1
    assert records[0].capability == "option_proposer"
    assert records[0].tier == ModelTier.HARD
    assert records[0].cost_usd > 0
