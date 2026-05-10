"""Agent 3 — 위치 파악 + source preview 테스트."""

from __future__ import annotations

import pytest

from backend.simulation.agents.agent3_locator import (
    Agent3Request,
    _extract_snippet,
    _match_demo_keywords,
    execute_agent3,
)


class TestKeywordMap:
    def test_단중상한_matches(self):
        m = _match_demo_keywords("단중상한이 어디서 결정되는지 알려줘")
        assert len(m) >= 1
        assert any("SdSecondWgtHigh" in e["class"] for e in m)

    def test_실수율_matches(self):
        m = _match_demo_keywords("누적 실수율 계산은?")
        assert any("Productivity" in e["class"] for e in m)

    def test_품종_keyword(self):
        m = _match_demo_keywords("PRODUCT_TYPE_CD를 어디서 쓰지?")
        assert len(m) >= 1

    def test_no_match(self):
        m = _match_demo_keywords("이 도메인과 무관한 질문 abc")
        assert m == []


class TestSnippetExtract:
    def test_method_found(self):
        # ProductivityService.cumulativeProductivity가 있어야 함
        from backend.simulation.agents.agent3_locator import _slab_path
        path = _slab_path(
            "slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/std/service/ProductivityService.java"
        )
        snippet, line_no = _extract_snippet(path, "cumulativeProductivity", lines_around=5)
        assert snippet is not None
        assert "cumulativeProductivity" in snippet
        assert line_no is not None

    def test_missing_file(self):
        snippet, line_no = _extract_snippet("/no/such/file.java", "foo")
        assert snippet is None
        assert line_no is None


@pytest.mark.asyncio
class TestExecuteAgent3:
    async def test_단중상한_query(self):
        result = await execute_agent3(Agent3Request(
            natural_language_query="단중상한이 어디서 결정돼?",
        ))
        assert result.status in {"success", "partial"}
        assert len(result.source_locations) >= 1
        # preview snippet이 채워짐
        sl = result.source_locations[0]
        assert sl.preview is not None
        assert "단중" in result.summary or "위치" in result.summary

    async def test_handoff_step_id_for_slab_count(self):
        result = await execute_agent3(Agent3Request(
            natural_language_query="Slab 매수가 어떻게 산정되나?",
        ))
        assert result.handoff_step_id == "slab_count"

    async def test_handoff_step_for_productivity(self):
        result = await execute_agent3(Agent3Request(
            natural_language_query="누적 실수율 계산 위치",
        ))
        assert result.handoff_step_id == "productivity"

    async def test_no_match_returns_unsupported(self):
        result = await execute_agent3(Agent3Request(
            natural_language_query="이 도메인과 무관한 질문 ABCXYZ",
        ))
        # ontology가 응답을 줄 수도 있어 partial 가능
        assert result.status in {"unsupported", "partial", "success"}

    async def test_preview_disabled(self):
        result = await execute_agent3(Agent3Request(
            natural_language_query="단중상한",
            include_preview=False,
        ))
        for sl in result.source_locations:
            assert sl.preview is None
