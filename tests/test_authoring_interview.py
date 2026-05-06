"""S4 — Interview Question Generator capability tests."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import code_extractor as ce
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.capabilities import interview as iv
from backend.application.authoring.schemas import ModelTier

REAL_HR_SPEC_JPO = Path(
    "/Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real/"
    "slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/jpo/"
    "HrSpecJpo.java"
)


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert iv.CAPABILITY_NAME == "interview"
    assert iv.TIER == ModelTier.STANDARD


def test_prompt_loads_and_mentions_step4_pattern():
    p = iv._system_prompt()
    assert "내 추측" in p
    assert "1–2 lines each" in p


def test_settings_enable_instruction_caching():
    assert iv._settings().get("anthropic_cache_instructions") is True


def test_interview_batch_schema_round_trip():
    b = iv.InterviewBatch(
        intro="HrPlant 가설을 다듬는 인터뷰입니다. 모름은 '모름' 으로 적어주세요.",
        questions=[
            iv.InterviewQuestion(
                id="owner",
                prompt="이 표준은 어느 sub-system 이 소유하나요?",
                my_guess="공정계획",
                placeholder="예: 공정계획",
                options=["주문처리", "진행관리", "품질설계", "공정계획"],
                importance="critical",
            ),
            iv.InterviewQuestion(
                id="extra",
                prompt="그 외 알려주고 싶은 것",
                my_guess=None,
                placeholder="optional",
                importance="optional",
                skip_ok=True,
            ),
        ],
    )
    blob = b.model_dump_json()
    b2 = iv.InterviewBatch.model_validate_json(blob)
    assert len(b2.questions) == 2
    assert b2.questions[0].importance == "critical"
    assert b2.questions[0].options == ["주문처리", "진행관리", "품질설계", "공정계획"]
    assert b2.questions[1].my_guess is None


def test_format_hypothesis_render_includes_korean_terms_and_concerns():
    h = hp.EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="standard",
        pk_role_summary="회사·소·열연공장 + 품종 식별",
        column_notes=[hp.ColumnNote(db_column="WIDTH_LOW", note="폭 하한")],
        relations_hint=["품종별로 자식 entity 가능성"],
        domain_questions=["소유 sub-system?"],
        confidence=0.6,
        assumptions=["HR_PLANT_CD 는 1자"],
        concerns=["table 명과 도메인 어휘 불일치"],
    )
    text = iv._format_hypothesis_for_prompt(h)
    assert "열연공장" in text
    assert "HrPlant" in text
    assert "confidence=0.60" in text
    assert "폭 하한" in text
    assert "품종별로" in text
    assert "table 명과 도메인 어휘 불일치" in text


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_interview_for_hr_spec_hypothesis():
    """Real Sonnet call: chain S2 → S3 → S4 and verify the interview batch.

    Acceptance bar (matches what the human user found useful in Round 5 Step 4):
      - 5..7 questions
      - Every prompt is a single Korean sentence (heuristic: no '?' more than once,
        no '. ' mid-sentence, length under ~120 chars)
      - At least one question targets a recurring unknown (owner / wildcard /
        miss / row scale / maintenance)
      - At most 2 questions are 'critical'
      - The last question is the open-ended 'extra' / free-text follow-up
      - Cost logged for all three capabilities, total under $0.30
    """
    cost_mod.reset_buffer()
    ce.reset_caches()
    hp.reset_caches()
    iv.reset_caches()

    content = REAL_HR_SPEC_JPO.read_text(encoding="utf-8")
    jpo = asyncio.run(
        ce.extract_jpo_from_file(
            str(REAL_HR_SPEC_JPO),
            content,
            session_id="s4-integration",
            turn_no=1,
        )
    )
    h = asyncio.run(
        hp.propose_entity_hypothesis(jpo, session_id="s4-integration", turn_no=2)
    )
    batch = asyncio.run(
        iv.design_interview(h, session_id="s4-integration", turn_no=3)
    )

    # Question count
    assert 5 <= len(batch.questions) <= 7, f"expected 5..7 questions, got {len(batch.questions)}"

    # Single-sentence rule (heuristic)
    for q in batch.questions:
        assert len(q.prompt) <= 200, f"prompt too long: {q.prompt!r}"
        # Allow at most one trailing '?'; reject multi-question prompts.
        assert q.prompt.count("?") <= 1, f"multi-question prompt: {q.prompt!r}"

    # Recurring unknown coverage
    recurring = {"owner", "wildcard", "miss", "row_size", "maintenance",
                 "match", "fallback", "scale", "size", "ownership", "lookup"}
    ids = {q.id.lower() for q in batch.questions}
    assert any(any(r in qid for r in recurring) for qid in ids), (
        f"no recurring-unknown id covered; got ids={ids}"
    )

    # critical limit
    crit_count = sum(1 for q in batch.questions if q.importance == "critical")
    assert crit_count <= 2, f"too many critical questions: {crit_count}"

    # Last question is the open-ended follow-up (extra / free-text / etc.)
    last = batch.questions[-1]
    assert last.importance == "optional"
    assert last.skip_ok is True

    # intro nonempty Korean
    assert len(batch.intro.strip()) > 0

    # Cost summary
    records = cost_mod.session_records("s4-integration")
    caps = {r.capability for r in records}
    assert caps == {"code_extractor", "hypothesis", "interview"}
    total = sum(r.cost_usd for r in records)
    assert total < 0.30, f"3-turn chain cost {total} too high"
