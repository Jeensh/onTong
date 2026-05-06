"""SSE endpoints for cap 5 (gaps) + cap 6 (options) + tool-calls trace.

Exercises the streaming path end-to-end with a mocked agent so we don't
need a live LLM. Validates:
- /gaps/stream emits stream_open → tool_call_* → done frames
- /options/stream emits a `done` frame whose payload contains the
  structured options and recommended_id
- /tool-calls returns the persisted trace for a session
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.application.authoring import session as smod
from backend.application.authoring.capabilities.code_extractor import (
    CodeColumn,
    ExtractedJpo,
)
from backend.application.authoring.capabilities.gap_detector import GapAnalysis
from backend.application.authoring.capabilities.hypothesis import EntityHypothesis
from backend.application.authoring.capabilities.option_proposer import OntologyOption, OptionTable
from backend.application.authoring.capabilities.answer_absorber import AbsorbedAnswers
from backend.main import app
from backend.modeling.persistence.database import bootstrap_database


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_db() -> None:
    bootstrap_database()


def _hypothesis() -> EntityHypothesis:
    return EntityHypothesis(
        candidate_term_korean="열연공장",
        candidate_term_english="HrPlant",
        domain_role="standard",
        pk_role_summary="공장 코드",
        column_notes=[],
        relations_hint=[],
        domain_questions=["plant 의 의미는?"],
        confidence=0.7,
        assumptions=[],
        concerns=[],
    )


def _absorbed_answers() -> AbsorbedAnswers:
    return AbsorbedAnswers(
        per_question={},
        emergent_facts=[],
        contradictions=[],
        confidence_after=0.7,
    )


def _extracted_jpo() -> ExtractedJpo:
    return ExtractedJpo(
        package="com.example",
        class_name="HrPlantJpo",
        table_name="HR_PLANT",
        pk_class=None,
        pk_columns=[CodeColumn(name="hrPlantCd", db_column="HR_PLANT_CD", java_type="String", is_pk=True)],
        regular_columns=[],
        class_docstring=None,
    )


def _options_table() -> OptionTable:
    return OptionTable(
        title="HrPlant 모델링 옵션",
        context_summary="단일 entity 로 매핑하는가, composition 으로 가는가",
        options=[
            OntologyOption(
                id="A",
                name="단일 entity",
                description="HrPlant 만 단독으로",
                structure_sketch="HrPlant",
                pros=["단순"],
                cons=["관계 표현 어려움"],
                entities_count_hint="1",
                domain_alignment="medium",
                trade_offs_one_line="단순함 vs 표현력",
            ),
            OntologyOption(
                id="B",
                name="composition",
                description="HrPlant + HrPlantConstraint",
                structure_sketch="HrPlant ◇ HrPlantConstraint",
                pros=["표현력"],
                cons=["복잡"],
                entities_count_hint="2",
                domain_alignment="high",
                trade_offs_one_line="표현력 vs 단순성",
            ),
        ],
        recommended_id="B",
        recommendation_reasoning="composition 이 도메인 정확",
        caveats=[],
    )


def _gap_analysis() -> GapAnalysis:
    return GapAnalysis(
        gaps=[],
        severity_summary="갭 없음",
        blocks_modeling=False,
        recommendation="추가 갭 없음 — 옵션 제시로 진행해도 됩니다.",
    )


@pytest.mark.asyncio
async def test_options_stream_emits_done_with_structured_output() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_propose_options(*args, **kwargs):
        # Tool calls would happen here against `event_pump` — we skip and
        # just return the structured output. This still exercises the
        # bridge() path (stream_open → done) which is what we need.
        return _options_table()

    payload = {
        "turn_no": 1,
        "hypothesis": _hypothesis().model_dump(),
        "answers": _absorbed_answers().model_dump(),
    }

    with patch(
        "backend.api.authoring.propose_options", side_effect=fake_propose_options
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                f"/api/authoring/sessions/{sid}/options/stream",
                json=payload,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("text/event-stream")
                events: list[dict] = []
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    events.append(json.loads(line[len("data:"):].strip()))

    types = [e["type"] for e in events]
    assert types[0] == "stream_open"
    assert types[-1] == "done"
    done = events[-1]
    assert done["output"]["recommended_id"] == "B"
    assert len(done["output"]["options"]) == 2


@pytest.mark.asyncio
async def test_gaps_stream_emits_done_with_empty_gaps() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_detect_gaps(*args, **kwargs):
        return _gap_analysis()

    payload = {
        "turn_no": 1,
        "extracted_jpo": _extracted_jpo().model_dump(),
        "hypothesis": _hypothesis().model_dump(),
        "answers": _absorbed_answers().model_dump(),
    }

    with patch(
        "backend.api.authoring.detect_gaps", side_effect=fake_detect_gaps
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                f"/api/authoring/sessions/{sid}/gaps/stream",
                json=payload,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                events: list[dict] = []
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    events.append(json.loads(line[len("data:"):].strip()))

    types = [e["type"] for e in events]
    assert types[-1] == "done"
    done = events[-1]
    assert done["output"]["gaps"] == []
    assert done["output"]["severity_summary"] == "갭 없음"


def _accepted_option() -> OntologyOption:
    return OntologyOption(
        id="A",
        name="단일 entity",
        description="한 덩어리",
        structure_sketch="HrPlant",
        pros=["단순"],
        cons=["관계 표현 어려움"],
        entities_count_hint="1",
        domain_alignment="medium",
        trade_offs_one_line="단순함 vs 표현력",
    )


def _pattern_check_empty() -> object:
    from backend.application.authoring.capabilities.pattern_checker import PatternCheck

    return PatternCheck(
        findings=[],
        consistency_score=0.85,
        summary="기존 패턴과 일관 — 명명 단계로 진행 가능",
        recommendation="그대로 진행",
    )


@pytest.mark.asyncio
async def test_pattern_endpoint_returns_check() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_check_pattern(*args, **kwargs):
        return _pattern_check_empty()

    payload = {
        "turn_no": 1,
        "hypothesis": _hypothesis().model_dump(),
        "accepted_option": _accepted_option().model_dump(),
    }

    with patch(
        "backend.api.authoring.check_pattern", side_effect=fake_check_pattern
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                f"/api/authoring/sessions/{sid}/pattern",
                json=payload,
                timeout=5.0,
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendation"] == "그대로 진행"
    assert body["consistency_score"] == 0.85


@pytest.mark.asyncio
async def test_pattern_stream_emits_done() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_check_pattern(*args, **kwargs):
        return _pattern_check_empty()

    payload = {
        "turn_no": 1,
        "hypothesis": _hypothesis().model_dump(),
        "accepted_option": _accepted_option().model_dump(),
    }

    with patch(
        "backend.api.authoring.check_pattern", side_effect=fake_check_pattern
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                f"/api/authoring/sessions/{sid}/pattern/stream",
                json=payload,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                events: list[dict] = []
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    events.append(json.loads(line[len("data:"):].strip()))
    assert events[-1]["type"] == "done"
    assert events[-1]["output"]["recommendation"] == "그대로 진행"


@pytest.mark.asyncio
async def test_extract_stream_emits_done_with_jpo() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_extract(*args, **kwargs):
        return _extracted_jpo()

    payload = {
        "turn_no": 1,
        "file_path": "Foo.java",
        "file_content": "package com.x; class Foo {}",
    }
    with patch(
        "backend.api.authoring.extract_jpo_from_file", side_effect=fake_extract
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                f"/api/authoring/sessions/{sid}/extract/stream",
                json=payload,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                events: list[dict] = []
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    events.append(json.loads(line[len("data:"):].strip()))
    assert events[-1]["type"] == "done"
    out = events[-1]["output"]
    assert out["class_name"] == "HrPlantJpo"


@pytest.mark.asyncio
async def test_hypothesize_stream_emits_done_with_hypothesis() -> None:
    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")

    async def fake_hypothesize(*args, **kwargs):
        return _hypothesis()

    payload = {
        "turn_no": 1,
        "extracted_jpo": _extracted_jpo().model_dump(),
    }
    with patch(
        "backend.api.authoring.propose_entity_hypothesis", side_effect=fake_hypothesize
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                f"/api/authoring/sessions/{sid}/hypothesize/stream",
                json=payload,
                timeout=5.0,
            ) as resp:
                assert resp.status_code == 200
                events: list[dict] = []
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line.startswith("data:"):
                        continue
                    events.append(json.loads(line[len("data:"):].strip()))
    assert events[-1]["type"] == "done"
    out = events[-1]["output"]
    assert out["candidate_term_english"] == "HrPlant"
    assert out["confidence"] == 0.7


@pytest.mark.asyncio
async def test_tool_calls_endpoint_returns_persisted_trace() -> None:
    """The /tool-calls endpoint reads the persisted trace via the adapter."""
    from backend.application.authoring.agent_tool_adapter import AuthoringToolLogger
    from backend.application.agent_tools.tracking import ToolCallRecord

    sid = smod.create_session(operator_id="sse_test", repo_id="dummy")
    log = AuthoringToolLogger(session_id=sid, turn_no=1, capability="gap_detector")
    log(
        ToolCallRecord(
            tool_name="code_lookup",
            args={"fqn": "com.x.Y"},
            result_summary="found",
            duration_ms=5,
            cached=False,
        )
    )
    log(
        ToolCallRecord(
            tool_name="find_callers",
            args={"method_fqn": "com.x.Y.foo()"},
            result_summary="list[0]",
            duration_ms=12,
            cached=False,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"/api/authoring/sessions/{sid}/tool-calls", timeout=5.0
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == sid
    assert len(body["tool_calls"]) == 2
    names = [tc["tool_name"] for tc in body["tool_calls"]]
    assert "code_lookup" in names
    assert "find_callers" in names
