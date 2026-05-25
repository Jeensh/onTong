"""S — Answer Absorber capability tests."""

from __future__ import annotations

import asyncio
import os

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import answer_absorber as aa
from backend.application.authoring.capabilities import interview as iv
from backend.application.authoring.schemas import ModelTier


def _sample_batch() -> iv.InterviewBatch:
    """A realistic HrPlant-shaped interview batch for tests.

    Mirrors the kinds of questions Round 5 Step 4 produced so the absorber's
    behaviour is exercised against the real-world reply patterns.
    """
    return iv.InterviewBatch(
        intro="HrPlant 가설을 다듬는 인터뷰입니다. 모름은 '모름' 으로 적어주세요.",
        questions=[
            iv.InterviewQuestion(
                id="meaning",
                prompt="HrPlant 한 row 가 의미하는 것을 한 줄로 알려주세요.",
                my_guess="온톨로지·소·열연공장·품종 조합의 폭/길이 가능 범위",
                placeholder="예: 맞음 / 정확히는 ...",
                importance="critical",
            ),
            iv.InterviewQuestion(
                id="owner",
                prompt="이 표준은 어느 sub-system 이 소유하나요?",
                my_guess="공정계획",
                placeholder="예: 공정계획",
                options=["주문처리", "진행관리", "품질설계", "공정계획"],
                importance="standard",
            ),
            iv.InterviewQuestion(
                id="wildcard",
                prompt="PK 컬럼에 와일드카드 row 가 있나요?",
                my_guess="정확매칭만 (와일드카드 없음)",
                placeholder="예: 와일드카드 없음 / 또는 ...",
                importance="standard",
            ),
            iv.InterviewQuestion(
                id="miss",
                prompt="룩업 결과가 null 일 때 알고리즘은 어떻게 처리하나요?",
                my_guess="DG 에러로 즉시 중단",
                placeholder="예: DG 에러 / 또는 ...",
                importance="critical",
            ),
            iv.InterviewQuestion(
                id="row_size",
                prompt="대략 몇 row 정도인가요?",
                my_guess="수백 정도",
                placeholder="예: 수십 / 수천",
                importance="optional",
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


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert aa.CAPABILITY_NAME == "answer_absorber"
    assert aa.TIER == ModelTier.STANDARD


def test_prompt_loads_and_mentions_verbatim_rule():
    p = aa._system_prompt()
    assert "Verbatim raw_text" in p
    assert "emergent_facts" in p
    assert "contradicts_my_guess" in p


def test_settings_enable_instruction_caching():
    assert aa._settings().get("anthropic_cache_instructions") is True


def test_absorbed_answer_schema_round_trip():
    a = aa.AbsorbedAnswers(
        per_question={
            "owner": aa.AbsorbedAnswer(
                question_id="owner",
                raw_text="공정계획에서 관리해",
                normalized="공정계획",
                picked_option="공정계획",
            ),
            "wildcard": aa.AbsorbedAnswer(
                question_id="wildcard",
                raw_text="*를 쓸 수도 있고 LIKE 도 지원해",
                normalized="와일드카드 + LIKE 매칭 모두 지원",
                contradicts_my_guess=True,
                contradicts_note="가설은 정확매칭만, 실제는 와일드카드/LIKE 사용",
            ),
        },
        unanswered=["miss"],
        emergent_facts=["기준값이 NULL 이면 자동 true 로 처리"],
        contradictions=["wildcard: 가설(정확매칭만) vs 실제(* + LIKE)"],
    )
    blob = a.model_dump_json()
    a2 = aa.AbsorbedAnswers.model_validate_json(blob)
    assert a2.per_question["wildcard"].contradicts_my_guess is True
    assert a2.unanswered == ["miss"]
    assert "NULL" in a2.emergent_facts[0]


def test_format_includes_intro_options_and_user_reply():
    batch = _sample_batch()
    text = aa._format_for_prompt(batch, "공정계획에서 관리해. 와일드카드는 *와 LIKE 둘다.")
    assert "intro:" in text
    assert "id: owner" in text
    assert "options: ['주문처리'" in text
    assert "공정계획에서 관리해" in text


def test_ensure_every_id_present_fills_missing_with_unknown():
    batch = _sample_batch()
    partial = aa.AbsorbedAnswers(
        per_question={
            "owner": aa.AbsorbedAnswer(
                question_id="owner",
                raw_text="공정계획에서 관리해",
                normalized="공정계획",
            )
        }
    )
    full = aa._ensure_every_id_present(partial, batch)
    expected_ids = {q.id for q in batch.questions}
    assert set(full.per_question.keys()) == expected_ids
    # Filled-in entries should be marked unknown
    assert full.per_question["miss"].is_unknown is True
    assert "miss" in full.unanswered
    # Original answered entry preserved
    assert full.per_question["owner"].normalized == "공정계획"
    assert "owner" not in full.unanswered


def test_ensure_every_id_recomputes_unanswered_from_empty_normalized():
    """An entry with empty normalized text is treated as unanswered even if present."""
    batch = _sample_batch()
    sketch = aa.AbsorbedAnswers(
        per_question={
            q.id: aa.AbsorbedAnswer(question_id=q.id, normalized="", is_unknown=False)
            for q in batch.questions
        }
    )
    full = aa._ensure_every_id_present(sketch, batch)
    assert set(full.unanswered) == {q.id for q in batch.questions}


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_absorbs_realistic_korean_reply():
    """Real Sonnet call against a realistic free-form Korean reply.

    Reply mixes:
      - direct answers (owner, miss, row_size)
      - a contradiction vs my_guess (wildcard)
      - explicit 모름 (extra)
      - missing answer (meaning — not addressed)
      - emergent fact (NULL semantics — not asked)

    Acceptance bar:
      - per_question has every id
      - 'owner' picked the option string verbatim
      - 'wildcard' is contradicts_my_guess=True with non-empty contradicts_note
      - 'meaning' is_unknown=True (user did not address it)
      - 'extra' is_unknown=True (user said 모름)
      - emergent_facts has at least one Korean line about NULL
      - cost logged for one call
    """
    cost_mod.reset_buffer()
    aa.reset_caches()

    batch = _sample_batch()
    reply = (
        "공정계획에서 관리해. "
        "와일드카드는 PK 에 *를 쓸 수도 있고 %LIKE 패턴도 지원해. "
        "기준값이 NULL 이면 자동 true 로 처리되는 점도 알아둬. "
        "룩업 실패하면 후속 로직에서 NPE 가 발생할 거야. 데이터 결함이지. "
        "row 는 수십 정도. "
        "그 외는 모름."
    )

    out = asyncio.run(
        aa.absorb_answers(batch, reply, session_id="cap4-integration", turn_no=1)
    )

    expected_ids = {q.id for q in batch.questions}
    assert set(out.per_question.keys()) == expected_ids

    owner = out.per_question["owner"]
    assert owner.is_unknown is False
    assert owner.picked_option == "공정계획"

    wildcard = out.per_question["wildcard"]
    assert wildcard.contradicts_my_guess is True
    assert wildcard.contradicts_note and len(wildcard.contradicts_note.strip()) > 0
    # contradiction should also surface in the top-level list
    assert any("wildcard" in c.lower() or "와일드카드" in c for c in out.contradictions)

    meaning = out.per_question["meaning"]
    assert meaning.is_unknown is True or not meaning.normalized.strip()
    assert "meaning" in out.unanswered or meaning.is_unknown

    extra = out.per_question["extra"]
    assert extra.is_unknown is True

    miss = out.per_question["miss"]
    assert miss.is_unknown is False
    assert "NPE" in miss.raw_text or "npe" in miss.raw_text.lower() or "결함" in miss.raw_text

    # The NULL semantics fact is not in any question — should appear as emergent
    assert any("NULL" in f or "null" in f.lower() for f in out.emergent_facts), (
        f"expected NULL emergent fact, got {out.emergent_facts}"
    )

    records = cost_mod.session_records("cap4-integration")
    assert len(records) == 1
    assert records[0].capability == "answer_absorber"
    assert records[0].tier == ModelTier.STANDARD
    assert records[0].cost_usd > 0
