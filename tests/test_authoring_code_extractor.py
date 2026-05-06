"""S2 — Code Extractor capability tests.

Two layers:
  1. Always-on unit tests — schema shape, prompt loading, settings shape, no LLM.
  2. Integration test — real Sonnet call against HrSpecJpo.java.
     Skipped unless `ONTONG_LLM_INTEGRATION=1` and `ANTHROPIC_API_KEY` are set.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from backend.application.authoring import cost as cost_mod
from backend.application.authoring.capabilities import code_extractor as ce
from backend.application.authoring.schemas import ModelTier

REAL_HR_SPEC_JPO = Path(
    "/Users/donghae/workspace/ai/onTong/sample-repos/slab-design-real/"
    "slab-design-store/src/main/java/com/example/slabdesign/store/sd/std/oracle/jpo/"
    "HrSpecJpo.java"
)


# ── Unit tests (always run) ──────────────────────────────────────────


def test_capability_metadata():
    assert ce.CAPABILITY_NAME == "code_extractor"
    assert ce.TIER == ModelTier.STANDARD


def test_prompt_loads_and_mentions_korean_preservation():
    p = ce._system_prompt()
    assert "Preserve Korean comments verbatim" in p
    assert "@IdClass" in p


def test_settings_enable_instruction_caching():
    s = ce._settings()
    assert s.get("anthropic_cache_instructions") is True


def test_extracted_jpo_schema_round_trip():
    j = ce.ExtractedJpo(
        package="com.example",
        class_name="HrSpecJpo",
        table_name="HR_SPEC",
        pk_class="HrSpecPK",
        pk_columns=[
            ce.CodeColumn(
                name="cmpCd", db_column="CMP_CD", java_type="String", db_length=2, is_pk=True
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
    blob = j.model_dump_json()
    j2 = ce.ExtractedJpo.model_validate_json(blob)
    assert j2.regular_columns[0].comment == "step 2 폭하한 계산"
    assert j2.pk_columns[0].is_pk is True


def test_usage_extraction_handles_missing_details():
    """If pydantic_ai exposes no details dict, we still get zero cache tokens."""

    class _Fake:
        input_tokens = 100
        output_tokens = 20
        details = None

    u = ce._usage_from_result(_Fake())
    assert u.input_tokens == 100
    assert u.output_tokens == 20
    assert u.cache_read_tokens == 0
    assert u.cache_write_tokens == 0


def test_usage_extraction_reads_anthropic_cache_fields():
    class _Fake:
        input_tokens = 100
        output_tokens = 20
        details = {
            "cache_read_input_tokens": 4096,
            "cache_creation_input_tokens": 512,
        }

    u = ce._usage_from_result(_Fake())
    assert u.cache_read_tokens == 4096
    assert u.cache_write_tokens == 512


# ── Integration (gated) ──────────────────────────────────────────────


_INTEGRATION_OK = bool(os.environ.get("ONTONG_LLM_INTEGRATION")) and bool(
    os.environ.get("ANTHROPIC_API_KEY")
)


@pytest.mark.integration
@pytest.mark.skipif(
    not _INTEGRATION_OK,
    reason="set ONTONG_LLM_INTEGRATION=1 + ANTHROPIC_API_KEY to run",
)
def test_real_extraction_of_hr_spec_jpo():
    """Real Sonnet call: HrSpecJpo.java should yield 4 PK columns + 4 regular columns.

    Validates the contract used downstream by the hypothesis capability:
      - PK has CMP_CD, ORG_CD, HR_PLANT_CD, PRODUCT_TYPE_CD
      - Regular has WIDTH_LOW, WIDTH_HIGH, LENGTH_LOW, LENGTH_HIGH
      - Korean inline comments preserved (e.g. "확통2자리")
      - Class docstring preserved (mentions "열연설비사양기준")
    """
    cost_mod.reset_buffer()
    ce.reset_caches()

    content = REAL_HR_SPEC_JPO.read_text(encoding="utf-8")
    out = asyncio.run(
        ce.extract_jpo_from_file(
            str(REAL_HR_SPEC_JPO),
            content,
            session_id="s2-integration",
            turn_no=1,
        )
    )

    assert out.class_name == "HrSpecJpo"
    assert out.table_name == "HR_SPEC"
    assert out.pk_class == "HrSpecPK"

    pk_db = {c.db_column for c in out.pk_columns}
    assert pk_db == {"CMP_CD", "ORG_CD", "HR_PLANT_CD", "PRODUCT_TYPE_CD"}

    reg_db = {c.db_column for c in out.regular_columns}
    assert reg_db == {"WIDTH_LOW", "WIDTH_HIGH", "LENGTH_LOW", "LENGTH_HIGH"}

    # Korean comment fidelity — at least one column should retain a Korean substring.
    assert any(
        c.comment and ("확통" in c.comment or "폭" in c.comment or "길이" in c.comment)
        for c in (out.pk_columns + out.regular_columns)
    ), "Inline Korean comments dropped — Sonnet failed to preserve them"

    # Class docstring should mention the canonical Korean name.
    assert out.class_docstring is not None
    assert "열연" in out.class_docstring or "HR" in out.class_docstring

    # Cost was logged.
    records = cost_mod.session_records("s2-integration")
    assert len(records) == 1
    rec = records[0]
    assert rec.capability == "code_extractor"
    assert rec.tier == ModelTier.STANDARD
    assert rec.cost_usd > 0
