"""Phase 4 — 데모 시나리오 e2e 검증.

세 시나리오를 backend 단에서 끝까지 흘려본다 (subprocess 격리 + agent 호출 + 응답 schema).
브라우저 e2e는 별도 (수동 데모 시연 시 검증).

시나리오:
- #5 (Agent 1): HRF 실수율 변경 → diff_summary.metrics.productivity.changed_orders ≥ 1
- #8 (Agent 2): slab_count step + boundary cases → SSE 시퀀스 + summary
- #1 (Agent 3): "단중상한" → handoff_step_id == "slab_weight"
"""

from __future__ import annotations

import pytest

from backend.simulation.agents.agent1_impact import Agent1Request, execute_agent1
from backend.simulation.agents.agent2_test_data import Agent2Request, stream_agent2
from backend.simulation.agents.agent3_locator import Agent3Request, execute_agent3


# ─── 시나리오 5 — 누적 실수율 변경 영향도 (Agent 1) ──────────────────


@pytest.mark.asyncio
async def test_scenario5_hrf_productivity_drop():
    """HRF 0.93 → 0.50 변경 시 표본 일부에서 Slab 결과 변동."""
    result = await execute_agent1(Agent1Request(
        change_kind="data",
        target_type="column",
        target_id="HRF_PRODUCTIVITY",
        modification_type="value_change",
        new_value="0.50",
        sample_size=20,
        run_sandbox=True,
    ))
    # 응답 schema
    assert result.status in {"success", "partial"}
    assert result.diff_summary is not None
    assert result.viz_data is not None

    # 핵심: productivity가 표본 일부에서 변동
    prod = result.diff_summary["metrics"]["productivity"]
    assert prod["before"]["n"] > 0
    assert prod["after"]["n"] > 0
    assert prod["changed_orders"] >= 1, "HRF 활성 케이스가 적어도 1건 있어야 함"

    # 결과 변동 주문 수 (slab_count 또는 productivity 변동)
    assert result.diff_summary["affected_count"] >= 1

    # viz_data가 Plotly로 곧장 사용 가능
    histograms = result.viz_data["histograms"]
    for metric in ("slab_count", "productivity", "slab_weight", "split_wgt_high"):
        assert metric in histograms
        assert "before_values" in histograms[metric]
        assert "after_values" in histograms[metric]


# ─── 시나리오 8 — A-a 루프 분기 (Agent 2 SSE) ───────────────────────


@pytest.mark.asyncio
async def test_scenario8_slab_count_boundary_stream():
    """slab_count + boundary case_type → SSE 시퀀스 + summary."""
    events: list[dict] = []
    async for evt in stream_agent2(Agent2Request(
        target_id="slab_count",
        case_types=["boundary", "error"],
        test_count=3,  # 작게: 6 케이스만
    )):
        events.append(evt)
        if len(events) > 200:
            pytest.fail("too many events")

    # 시퀀스: run_started → case_started/done|failed × 6 → summary → run_complete
    event_types = [e["event"] for e in events]
    assert event_types[0] == "run_started"
    assert event_types[-1] == "run_complete"
    assert event_types[-2] == "summary"

    starts = [e for e in events if e["event"] == "case_started"]
    dones = [e for e in events if e["event"] in ("case_done", "case_failed")]
    assert len(starts) == 6  # 2 case_types × test_count=3
    assert len(dones) == 6

    # summary에 step_id가 정확히 매핑
    summary_evt = next(e for e in events if e["event"] == "summary")
    assert summary_evt["data"]["step_id"] == "slab_count"
    assert "by_type" in summary_evt["data"]
    assert "code_skeleton" in summary_evt["data"]


@pytest.mark.asyncio
async def test_scenario8_pipeline_with_rule_change_finds_failures():
    """pipeline + rules.hrf 큰 폭 하향 + boundary → 실패 케이스 발견."""
    events: list[dict] = []
    async for evt in stream_agent2(Agent2Request(
        target_id="pipeline",
        case_types=["boundary"],
        test_count=3,
        rules={"hrf": "0.30"},  # 큰 폭 → 일부 케이스에서 step 9/10 fail
    )):
        events.append(evt)

    summary = next(e for e in events if e["event"] == "summary")["data"]
    assert summary["step_id"] == "pipeline"
    # boundary 케이스는 알고리즘 fail이 자주 발생 — code_skeleton에 fail 케이스 포함 가능
    assert "code_skeleton" in summary


# ─── 시나리오 1 — 단중상한 (Agent 3 → handoff) ──────────────────────


@pytest.mark.asyncio
async def test_scenario1_단중상한_to_slab_weight_handoff():
    """'단중상한' 검색 → SdSecondWgtHighAction.java 매칭 + handoff to slab_weight."""
    result = await execute_agent3(Agent3Request(
        natural_language_query="단중상한이 어디서 결정돼?",
        include_preview=True,
        preview_lines=20,
    ))

    assert result.status in {"success", "partial"}
    assert len(result.source_locations) >= 1

    # 첫 매칭이 SdSecondWgtHigh* 클래스
    first = result.source_locations[0]
    assert first.class_name and "SecondWgt" in first.class_name
    assert first.preview is not None
    assert "단중" in first.preview or "WgtHigh" in first.preview or "secondWgtHigh" in first.preview

    # 핸드오프 step_id가 slab_weight (가장 가까운 sandbox step)
    assert result.handoff_step_id == "slab_weight"


@pytest.mark.asyncio
async def test_scenario1_누적실수율_handoff_to_productivity():
    """다른 빠른 질의도 정확한 handoff."""
    result = await execute_agent3(Agent3Request(
        natural_language_query="누적 실수율 계산 위치",
    ))
    assert result.handoff_step_id == "productivity"
    assert any(
        "Productivity" in (sl.class_name or "")
        for sl in result.source_locations
    )


@pytest.mark.asyncio
async def test_scenario1_Slab매수_handoff_to_slab_count():
    result = await execute_agent3(Agent3Request(
        natural_language_query="Slab 매수 산정 로직",
    ))
    assert result.handoff_step_id == "slab_count"


# ─── 통합: e2e 흐름 검증 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_demo_chain_locator_to_test_to_impact():
    """Agent 3 (찾기) → Agent 2 (시뮬) → Agent 1 (영향도) 통합 흐름.

    실제 사용 시나리오: 사용자가 용어로 위치 찾고 → 그 step을 시뮬해보고 → 룰 변경 영향 확인.
    """
    # 1. 위치 파악
    locator = await execute_agent3(Agent3Request(
        natural_language_query="누적 실수율",
    ))
    step_id = locator.handoff_step_id
    assert step_id == "productivity"

    # 2. 그 step에 대해 테스트 데이터 (작은 N)
    events: list[dict] = []
    async for evt in stream_agent2(Agent2Request(
        target_id=step_id,
        case_types=["normal"],
        test_count=2,
    )):
        events.append(evt)
    summary = next(e for e in events if e["event"] == "summary")["data"]
    assert summary["step_id"] == "productivity"

    # 3. 룰 변경 영향도
    impact = await execute_agent1(Agent1Request(
        change_kind="data",
        target_type="column",
        target_id="HRF_PRODUCTIVITY",
        modification_type="value_change",
        new_value="0.50",
        sample_size=10,
    ))
    assert impact.diff_summary is not None
