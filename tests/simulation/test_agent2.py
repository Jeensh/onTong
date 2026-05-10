"""Agent 2 통합 테스트 — 동기 + SSE 스트리밍."""

from __future__ import annotations

import asyncio

import pytest

from backend.simulation.agents.agent2_test_data import (
    Agent2Request,
    _resolve_step_id,
    execute_agent2,
    stream_agent2,
)


# ─── step_id 정규화 ─────────────────────────────────────────────────


class TestStepIdResolve:
    def test_canonical_passes_through(self):
        assert _resolve_step_id("pipeline") == "pipeline"
        assert _resolve_step_id("validator") == "validator"
        assert _resolve_step_id("slab_count") == "slab_count"

    def test_legacy_step_X_label(self):
        assert _resolve_step_id("step_9") == "slab_count"
        assert _resolve_step_id("step_1") == "thickness"

    def test_digit_only(self):
        assert _resolve_step_id("9") == "slab_count"

    def test_unknown_falls_back_to_pipeline(self):
        assert _resolve_step_id("step_999") == "pipeline"
        assert _resolve_step_id("xyz") == "pipeline"


# ─── 동기 호출 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestExecuteAgent2:
    async def test_pipeline_normal_only(self):
        result = await execute_agent2(Agent2Request(
            target_type="step",
            target_id="pipeline",
            case_types=["normal"],
            test_count=2,
        ))
        assert result.step_id == "pipeline"
        assert result.status in {"success", "partial"}  # subprocess 변동성 고려
        assert len(result.test_cases) == 2
        assert result.statistics["total"] == 2

    async def test_validator_with_errors(self):
        result = await execute_agent2(Agent2Request(
            target_type="step",
            target_id="validator",
            case_types=["error"],
            test_count=3,
        ))
        # error 타입은 expected.dg 가 채워져 있고, validator step이 그 DG로 응답해야 matches
        assert result.step_id == "validator"
        for case in result.test_cases:
            assert case.expected_output.get("dg") in {"DG001", "DG002", "DG003", "DG004", "DG005"}

    async def test_skeleton_present(self):
        result = await execute_agent2(Agent2Request(
            target_id="pipeline",
            case_types=["normal"],
            test_count=1,
        ))
        assert "import pytest" in result.code_skeleton
        assert "run_in_subprocess" in result.code_skeleton

    async def test_count_caps_to_200(self):
        # 너무 큰 count도 sync에서는 200으로 cap
        result = await execute_agent2(Agent2Request(
            target_id="validator",
            case_types=["normal"],
            test_count=99999,
        ))
        # 200 * 1 case_type = 최대 200
        assert result.statistics["total"] <= 200


# ─── SSE 스트리밍 ───────────────────────────────────────────────────


@pytest.mark.asyncio
class TestStreamAgent2:
    async def test_event_sequence(self):
        events: list[dict] = []
        async for evt in stream_agent2(Agent2Request(
            target_id="pipeline",
            case_types=["normal"],
            test_count=2,
        )):
            events.append(evt)
            if len(events) > 100:
                pytest.fail("too many events")

        # 시작 / 종료 / 요약 보장
        assert events[0]["event"] == "run_started"
        assert events[-1]["event"] == "run_complete"
        assert any(e["event"] == "summary" for e in events)
        # case_started + case_done 쌍 (case 수 = 2 → 각 2개)
        starts = [e for e in events if e["event"] == "case_started"]
        dones = [e for e in events if e["event"] in ("case_done", "case_failed")]
        assert len(starts) == 2
        assert len(dones) == 2

    async def test_summary_includes_distribution(self):
        events: list[dict] = []
        async for evt in stream_agent2(Agent2Request(
            target_id="pipeline",
            case_types=["normal"],
            test_count=2,
        )):
            events.append(evt)
        summary_evt = next(e for e in events if e["event"] == "summary")
        data = summary_evt["data"]
        assert "by_type" in data
        assert "code_skeleton" in data
        assert data["step_id"] == "pipeline"
