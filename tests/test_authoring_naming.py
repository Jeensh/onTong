"""S — Naming (Sonnet) capability tests."""

from __future__ import annotations

import asyncio
import os

import pytest
from pydantic import ValidationError

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import hypothesis as hp
from backend.application.authoring.capabilities import naming as nm
from backend.application.authoring.capabilities import option_proposer as op
from backend.application.authoring.schemas import ModelTier


# ── Fixtures ─────────────────────────────────────────────────────────


def _hr_plant_hypothesis() -> hp.EntityHypothesis:
    return hp.EntityHypothesis(
        candidate_term_korean="열연공장 표준",
        candidate_term_english="HrSpec",
        domain_role="standard",
        pk_role_summary="회사·소·열연공장·품종 4축 — 한 row = 한 열연공장의 한 품종에 대한 폭/길이 범위",
        column_notes=[],
        relations_hint=["PK 의 PRODUCT_TYPE_CD 가 자식 entity 분리 신호"],
        domain_questions=[],
        confidence=0.6,
        assumptions=[],
        concerns=[],
    )


def _accepted_plant_constraint_option() -> op.OntologyOption:
    """Round 5 Step 5 옵션 C 모양 — Plant + Constraint."""
    return op.OntologyOption(
        id="C",
        name="옵션 C — Plant + Constraint Composition",
        description=(
            "HrPlant (열연공장, 회사·소·HR_PLANT_CD 식별) 와 그 산하의 "
            "HrPlantConstraint (품종별 폭/길이) 로 분리. PK 의 앞 3축은 plant, "
            "PRODUCT_TYPE_CD 는 자식 entity 의 키."
        ),
        structure_sketch=(
            "HrPlant (열연공장)\n"
            "  └── N HrPlantConstraint (품종별 폭/길이)"
        ),
        pros=["도메인 응집 ↑", "row-level 추적 가능"],
        cons=["entity 수 증가 (1+N)"],
        entities_count_hint="중간 (1+N)",
        domain_alignment="high",
        trade_offs_one_line="도메인 ↑ / entity 수 ↑",
    )


# ── Unit tests ───────────────────────────────────────────────────────


def test_capability_metadata():
    assert nm.CAPABILITY_NAME == "naming"
    assert nm.TIER == ModelTier.STANDARD


def test_prompt_loads_and_mentions_sibling_pattern():
    p = nm._system_prompt()
    assert "Sibling consistency" in p
    assert "압연MAX단중기준" in p
    assert "PascalCase" in p


def test_settings_enable_instruction_caching():
    assert nm._settings().get("anthropic_cache_instructions") is True


def test_naming_decision_round_trip():
    d = nm.NamingDecision(
        entities=[
            nm.EntityName(
                korean_label="열연공장",
                english_id="HrPlant",
                role="root",
                description_short="회사·소 단위의 물리 열연 설비",
            ),
            nm.EntityName(
                korean_label="열연공장제약",
                english_id="HrPlantConstraint",
                role="child",
                parent_english_id="HrPlant",
                description_short="열연공장 산하의 품종별 폭/길이 제약",
            ),
        ],
        naming_conflicts=[],
        naming_rationale="parent prefix 'HrPlant' 를 유지하여 형제 패턴 일관 유지.",
        alternatives_considered=["HrSpecConstraint (table 명 그대로) — 도메인 의미 약해서 기각"],
    )
    blob = d.model_dump_json()
    d2 = nm.NamingDecision.model_validate_json(blob)
    assert len(d2.entities) == 2
    assert d2.entities[1].parent_english_id == "HrPlant"


def test_validator_rejects_child_without_parent():
    with pytest.raises(ValidationError, match="parent_english_id is empty"):
        nm.NamingDecision(
            entities=[
                nm.EntityName(
                    korean_label="X",
                    english_id="X",
                    role="child",
                    parent_english_id=None,
                    description_short="d",
                )
            ],
            naming_rationale="r",
        )


def test_validator_rejects_non_child_with_parent():
    with pytest.raises(ValidationError, match="parent_english_id is set"):
        nm.NamingDecision(
            entities=[
                nm.EntityName(
                    korean_label="X",
                    english_id="X",
                    role="root",
                    parent_english_id="Y",
                    description_short="d",
                )
            ],
            naming_rationale="r",
        )


def test_format_includes_hypothesis_option_and_existing_names():
    text = nm._format_for_prompt(
        _hr_plant_hypothesis(),
        _accepted_plant_constraint_option(),
        existing_names=["Order", "Slab"],
    )
    assert "열연공장 표준" in text
    assert "옵션 C" in text
    assert "structure_sketch" in text
    assert "HrPlantConstraint" in text  # appears in the sketch
    assert "  - Order" in text
    assert "  - Slab" in text


def test_format_handles_empty_existing_names():
    text = nm._format_for_prompt(
        _hr_plant_hypothesis(),
        _accepted_plant_constraint_option(),
        existing_names=None,
    )
    assert "(none — cold start)" in text


# ── Integration ──────────────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_naming_for_plant_constraint_option():
    """Real Sonnet call: option C (Plant+Constraint) → 2 entities with sibling-consistent names.

    Acceptance bar:
      - 2 entities (the option introduces a parent + child shape)
      - Roles are exactly {root, child}
      - The child's parent_english_id matches the root's english_id
      - Korean labels include 열연 / 공장 / 제약 vocabulary
      - English ids share a common prefix (sibling consistency)
      - No conflicts (existing_names is empty)
      - Cost logged for one Sonnet call
    """
    cost_mod.reset_buffer()
    nm.reset_caches()

    out = asyncio.run(
        nm.decide_names(
            _hr_plant_hypothesis(),
            _accepted_plant_constraint_option(),
            existing_names=None,
            session_id="cap8-integration",
            turn_no=1,
        )
    )

    # 2 entities (root + child)
    assert len(out.entities) == 2, f"expected 2 entities, got {len(out.entities)}"

    roles = sorted(e.role for e in out.entities)
    assert roles == ["child", "root"], f"expected {{root, child}}, got {roles}"

    root = next(e for e in out.entities if e.role == "root")
    child = next(e for e in out.entities if e.role == "child")
    assert child.parent_english_id == root.english_id, (
        f"child.parent_english_id {child.parent_english_id!r} != root.english_id {root.english_id!r}"
    )

    # Korean vocabulary
    blob_ko = root.korean_label + " " + child.korean_label
    assert "열연" in blob_ko or "공장" in blob_ko
    assert "제약" in child.korean_label or "Constraint" in child.korean_label

    # PascalCase + sibling prefix consistency
    for e in out.entities:
        assert e.english_id[0].isupper(), f"{e.english_id!r} must be PascalCase"
        assert " " not in e.english_id and "_" not in e.english_id
    # Common prefix ≥3 chars (e.g. "HrP")
    common = os.path.commonprefix([root.english_id, child.english_id])
    assert len(common) >= 3, (
        f"sibling ids should share a prefix; got {root.english_id!r}, {child.english_id!r}"
    )

    # No collisions when existing_names was empty
    assert out.naming_conflicts == [], (
        f"unexpected conflicts on cold start: {out.naming_conflicts}"
    )

    # description_short non-empty for both
    for e in out.entities:
        assert e.description_short.strip(), f"{e.english_id} missing description_short"

    # Cost summary
    records = cost_mod.session_records("cap8-integration")
    assert len(records) == 1
    assert records[0].capability == "naming"
    assert records[0].tier == ModelTier.STANDARD


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_naming_surfaces_conflict_when_existing_name_collides():
    """When existing_names already contains 'HrPlant', the model should flag it.

    We don't dictate exactly what alternative it picks — just that the
    conflict is acknowledged in `naming_conflicts` rather than silently
    overwritten.
    """
    cost_mod.reset_buffer()
    nm.reset_caches()

    out = asyncio.run(
        nm.decide_names(
            _hr_plant_hypothesis(),
            _accepted_plant_constraint_option(),
            existing_names=["HrPlant"],  # collision against the obvious root name
            session_id="cap8-conflict",
            turn_no=1,
        )
    )

    # Either the model surfaces the conflict OR it picks a different name and
    # mentions the prior in alternatives_considered. Both signal awareness.
    flagged = bool(out.naming_conflicts)
    referenced = any("HrPlant" in s for s in out.alternatives_considered) or any(
        "기존" in s or "충돌" in s for s in out.naming_conflicts
    )
    assert flagged or referenced, (
        f"expected the model to acknowledge HrPlant collision; "
        f"got conflicts={out.naming_conflicts}, alternatives={out.alternatives_considered}"
    )
