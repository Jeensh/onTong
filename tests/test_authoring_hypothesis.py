"""S3 — Hypothesis capability tests.

Same two-layer pattern as S2:
  1. Always-on unit tests.
  2. Integration test: real Opus call against the HrSpecJpo hypothesis.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import code_extractor as ce
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.schemas import ModelTier

REAL_HR_SPEC_JPO = Path(
    "/Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real/"
    "slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/jpo/"
    "HrSpecJpo.java"
)


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert hp.CAPABILITY_NAME == "hypothesis"
    assert hp.TIER == ModelTier.HARD


def test_prompt_loads_and_mentions_korean():
    p = hp._system_prompt()
    # Round 2 P1-B: prompt was rewritten to be more humble. Check the
    # calibration guidance + question section instead of the old wording.
    assert "Korean inline comments" in p or "Korean comments" in p
    assert "domain_questions" in p
    assert "humble" in p.lower() or "추정" in p


def test_settings_enable_instruction_caching():
    assert hp._settings().get("anthropic_cache_instructions") is True


def test_entity_hypothesis_schema_round_trip():
    h = hp.EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="equipment",
        pk_role_summary="온톨로지·소·열연공장 식별. 품종은 별도 자식 entity 의 키.",
        column_notes=[hp.ColumnNote(db_column="WIDTH_LOW", note="열연 폭 하한")],
        relations_hint=["품종별 제약은 자식 entity 로 분리될 후보"],
        domain_questions=[
            "이 열연공장은 물리 설비인가요, 논리 그룹인가요?",
            "PK 의 PRODUCT_TYPE_CD 는 품종별 제약을 분리하는 신호로 봐도 되나요?",
            "와일드카드 row 가 있나요?",
        ],
        confidence=0.7,
        assumptions=["HR_PLANT_CD 는 8자 confirmedPlantCd 의 한 자리"],
        concerns=["table 명 HR_SPEC vs domain 명 HR plant 의 어휘 불일치"],
    )
    blob = h.model_dump_json()
    h2 = hp.EntityHypothesis.model_validate_json(blob)
    assert h2.candidate_term_korean == "열연공장"
    assert h2.confidence == 0.7
    assert len(h2.domain_questions) == 3


def test_format_jpo_includes_korean_comments_and_pk_marker():
    jpo = ce.ExtractedJpo(
        package="com.example",
        class_name="HrSpecJpo",
        table_name="HR_SPEC",
        pk_class="HrSpecPK",
        class_docstring="열연설비사양기준 — 도메인 설명",
        pk_columns=[
            ce.CodeColumn(
                name="hrPlantCd",
                db_column="HR_PLANT_CD",
                java_type="String",
                db_length=1,
                is_pk=True,
                comment="열연공장코드 (확통2자리)",
            ),
        ],
        regular_columns=[
            ce.CodeColumn(
                name="widthLow",
                db_column="WIDTH_LOW",
                java_type="BigDecimal",
                db_precision=10,
                db_scale=2,
                comment="step 2 폭하한 계산",
            ),
        ],
    )
    text = hp._format_jpo_for_prompt(jpo)
    assert "열연설비사양기준" in text
    assert "확통2자리" in text
    assert "step 2 폭하한 계산" in text
    assert "PK" in text
    assert "regular" in text


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_hypothesis_for_hr_spec_jpo():
    """Real Opus call: HrSpecJpo hypothesis should land near 'HrPlant'-shaped entity.

    We chain S2 → S3: extract first, then hypothesise. The acceptance bar
    is the same one a domain expert would set when reading the proposal:
      - Korean term mentions 열연
      - English id is PascalCase, mentions HR or Plant
      - At least 3 follow-up questions
      - Confidence inside [0,1]
      - Cost logged for both calls
    """
    cost_mod.reset_buffer()
    ce.reset_caches()
    hp.reset_caches()

    content = REAL_HR_SPEC_JPO.read_text(encoding="utf-8")
    jpo = asyncio.run(
        ce.extract_jpo_from_file(
            str(REAL_HR_SPEC_JPO),
            content,
            session_id="s3-integration",
            turn_no=1,
        )
    )
    assert jpo.class_name == "HrSpecJpo"

    h = asyncio.run(
        hp.propose_entity_hypothesis(jpo, session_id="s3-integration", turn_no=2)
    )

    assert "열연" in h.candidate_term_korean, (
        f"expected Korean term about 열연, got {h.candidate_term_korean!r}"
    )
    eng_lower = h.candidate_term_english.lower()
    assert "hr" in eng_lower or "plant" in eng_lower or "spec" in eng_lower
    assert h.candidate_term_english[0].isupper(), "English id must be PascalCase"
    assert 3 <= len(h.domain_questions) <= 5
    assert all(2 < len(q) < 400 for q in h.domain_questions), "questions should be short"
    assert 0.0 <= h.confidence <= 1.0

    # Cost logged for both turns.
    records = cost_mod.session_records("s3-integration")
    assert {r.capability for r in records} == {"code_extractor", "hypothesis"}
    by_cap = {r.capability: r for r in records}
    assert by_cap["code_extractor"].tier == ModelTier.STANDARD
    assert by_cap["hypothesis"].tier == ModelTier.HARD
    assert by_cap["hypothesis"].cost_usd > by_cap["code_extractor"].cost_usd, (
        "Opus call must cost more per token than Sonnet for similar I/O"
    )
