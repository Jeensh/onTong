"""Agent 1 — 영향도 + sandbox diff 테스트."""

from __future__ import annotations

import pytest

from backend.simulation.agents.agent1_impact import (
    Agent1Request,
    _resolve_rule_key,
    execute_agent1,
)


class TestRuleKeyResolve:
    def test_canonical(self):
        assert _resolve_rule_key("HR_PRODUCTIVITY") == "hr"
        assert _resolve_rule_key("hr_productivity") == "hr"
        assert _resolve_rule_key("HRF_PRODUCTIVITY") == "hrf"
        assert _resolve_rule_key("ANL1_PRODUCTIVITY") == "anl1"

    def test_colon_form(self):
        assert _resolve_rule_key("productivity:HR") == "hr"
        assert _resolve_rule_key("productivity:HRF") == "hrf"

    def test_unknown_returns_none(self):
        assert _resolve_rule_key("UNKNOWN") is None
        assert _resolve_rule_key("orderWidth") is None


@pytest.mark.asyncio
class TestExecuteAgent1:
    async def test_no_sandbox_when_disabled(self):
        result = await execute_agent1(Agent1Request(
            change_kind="data",
            target_type="column",
            target_id="HR_PRODUCTIVITY",
            modification_type="value_change",
            new_value="0.92",
            run_sandbox=False,
        ))
        assert result.diff_summary is None
        assert result.viz_data is None

    async def test_sandbox_diff_for_hr_productivity(self):
        """시나리오 5 핵심: HR 0.95→0.92 변경 → sandbox 비교 실행."""
        result = await execute_agent1(Agent1Request(
            change_kind="data",
            target_type="column",
            target_id="HR_PRODUCTIVITY",
            modification_type="value_change",
            new_value="0.92",
            sample_size=5,  # 빠른 테스트용
        ))
        assert result.diff_summary is not None
        assert result.diff_summary["sample_size"] == 5
        assert "metrics" in result.diff_summary
        # productivity 분포가 측정됨
        assert "productivity" in result.diff_summary["metrics"]
        # viz_data가 함께 채워짐
        assert result.viz_data is not None
        assert "histograms" in result.viz_data

    async def test_unknown_target_no_sandbox(self):
        """매핑 없는 target은 sandbox 비교 미실행 — partial 또는 success status."""
        result = await execute_agent1(Agent1Request(
            change_kind="program",
            target_type="method",
            target_id="some.unknown.method",
            modification_type="logic",
        ))
        assert result.diff_summary is None
        assert result.status in {"success", "partial"}

    async def test_sandbox_diff_significant_change(self):
        """HRF 큰 폭 하향 → 표본의 일부에서 productivity 변동.

        Hypothesis가 confirmedPlantCd를 랜덤 생성하므로 HRF 비활성 케이스도 섞임.
        sample_size를 키워서 HRF 활성 케이스가 ≥1건 포함되도록.
        """
        result = await execute_agent1(Agent1Request(
            change_kind="data",
            target_type="column",
            target_id="HRF_PRODUCTIVITY",
            modification_type="value_change",
            new_value="0.50",  # 큰 하향
            sample_size=20,
        ))
        assert result.diff_summary is not None
        prod_metric = result.diff_summary["metrics"]["productivity"]
        # before/after 분포 데이터 수집됨
        assert prod_metric["before"]["n"] > 0
        assert prod_metric["after"]["n"] > 0
        # changed_orders ≥ 1 (적어도 한 케이스는 HRF 활성)
        assert prod_metric["changed_orders"] >= 1
