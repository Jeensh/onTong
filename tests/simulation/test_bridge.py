"""Phase 6-D — OntologyBridge 단위 테스트.

ontology client 미가용 환경 가정 (SIMULATION_SKIP_ONTOLOGY=1 default).
"""

from __future__ import annotations

import pytest

from backend.simulation.ontology_bridge.bridge import OntologyBridge


class TestTermResolution:
    def test_korean_canonical(self):
        assert OntologyBridge.resolve("실수율") == "실수율"

    def test_english_alias(self):
        assert OntologyBridge.resolve("productivity") == "실수율"
        assert OntologyBridge.resolve("yield") == "실수율"

    def test_case_insensitive(self):
        assert OntologyBridge.resolve("Productivity") == "실수율"

    def test_unknown_returns_none(self):
        assert OntologyBridge.resolve("XYZ") is None


class TestTermToSteps:
    def test_productivity_impacts_pipeline(self):
        steps = OntologyBridge.term_to_steps("실수율")
        assert "pipeline_full" in steps
        assert "productivity" in steps
        assert "split_range" in steps

    def test_edging_impacts_width_range(self):
        steps = OntologyBridge.term_to_steps("EDGING")
        assert "width_range" in steps

    def test_unknown_returns_empty(self):
        assert OntologyBridge.term_to_steps("XYZ") == []


class TestStepToTerms:
    def test_pipeline_full_has_many_terms(self):
        terms = OntologyBridge.step_to_terms("pipeline_full")
        # pipeline_full 은 거의 모든 용어의 영향을 받음
        assert "실수율" in terms
        assert "두께" in terms
        assert "EDGING" in terms

    def test_thickness_subset(self):
        terms = OntologyBridge.step_to_terms("thickness")
        assert "두께" in terms
        assert "제강" in terms
        assert "CAST_SPEC" in terms


class TestSuggestions:
    def test_productivity_suggestions_have_rules(self):
        sugs = OntologyBridge.suggest_scenarios("실수율")
        assert len(sugs) >= 2
        # 적어도 하나는 hr productivity 변경 시나리오
        hr_sug = next((s for s in sugs if "hr" in s.inputs.get("rules", {})), None)
        assert hr_sug is not None
        assert hr_sug.step_id == "pipeline_full"

    def test_edging_suggestions(self):
        sugs = OntologyBridge.suggest_scenarios("EDGING")
        assert len(sugs) >= 1
        wildcard_sug = next(
            (s for s in sugs if s.inputs.get("rules", {}).get("edging_wildcard") is False),
            None,
        )
        assert wildcard_sug is not None

    def test_unknown_term_no_suggestions(self):
        assert OntologyBridge.suggest_scenarios("XYZ") == []


class TestOverlay:
    @pytest.mark.asyncio
    async def test_overlay_skipped_ontology(self, monkeypatch):
        monkeypatch.setenv("SIMULATION_SKIP_ONTOLOGY", "1")
        bridge = OntologyBridge(client=None)
        out = await bridge.overlay("실수율")
        assert out["matched"] is True
        assert out["canonical"] == "실수율"
        assert "pipeline_full" in out["impacted_steps"]
        assert len(out["scenario_suggestions"]) >= 2
        assert out["ontology"]["available"] is False

    @pytest.mark.asyncio
    async def test_overlay_unknown_term(self):
        bridge = OntologyBridge(client=None)
        out = await bridge.overlay("XYZ")
        assert out["matched"] is False
        assert out["impacted_steps"] == []
        assert out["scenario_suggestions"] == []


class TestStepIndex:
    def test_all_terms_listed(self):
        terms = OntologyBridge.all_terms()
        canonicals = {t["canonical"] for t in terms}
        assert "실수율" in canonicals
        assert "두께" in canonicals
        assert "EDGING" in canonicals

    def test_full_index(self):
        idx = OntologyBridge.all_step_to_terms()
        # 모든 등록된 step 이 키로 존재
        assert "thickness" in idx
        assert "pipeline_full" in idx
        # 일부 step (validator) 는 직접 매핑이 적을 수 있음
        # 확실한 case: pipeline_full 은 다수
        assert len(idx["pipeline_full"]) >= 5
