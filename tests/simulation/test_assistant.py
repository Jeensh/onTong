"""Phase 7-B — AI 시나리오 어시스턴트 + 7-C export/import 검증.

LLM 미사용 환경 가정 (SIMULATION_DISABLE_LLM_ASSIST=1) — fallback 경로만 검증.
LLM 통합 e2e 는 별도 (key 필요).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.simulation.agents.scenario_assistant import (
    AssistRequest,
    ScenarioDraft,
    _fallback_draft,
    assist,
)
from backend.simulation.sandbox import registry
from backend.simulation.storage import db as db_mod
from backend.simulation.storage import scenarios as scn_store


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "assist_test.db"
    db_mod.init_schema(db_path)
    monkeypatch.setattr(scn_store, "db_mod", db_mod)
    return db_path


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch):
    monkeypatch.setenv("SIMULATION_DISABLE_LLM_ASSIST", "1")


# ─── Fallback 경로 ──────────────────────────────────────────────────


class TestFallback:
    def test_productivity_keyword(self):
        draft = _fallback_draft("HR 실수율 0.85로 줄이면?")
        assert draft.method == "fallback"
        assert draft.extracted_term == "실수율"
        assert draft.step_id in registry.STEP_REGISTRY
        assert draft.confidence >= 0.5

    def test_edging_keyword(self):
        draft = _fallback_draft("EDGING wildcard 가 사라지면?")
        assert draft.extracted_term == "EDGING"
        assert "edging" in [t.lower() for t in draft.tags]

    def test_plant_mapping_keyword(self):
        draft = _fallback_draft("제강 K → CC2 마이그하면?")
        assert draft.extracted_term == "제강"
        assert draft.step_id == "plant_mapping_migrate"

    def test_no_match_returns_baseline(self):
        draft = _fallback_draft("XYZ ABC random query")
        assert draft.extracted_term is None
        assert draft.confidence < 0.5
        assert draft.step_id == "thickness"

    def test_korean_alias_resolution(self):
        # productivity 영문 alias
        draft = _fallback_draft("productivity 변경")
        assert draft.extracted_term == "실수율"


# ─── assist() (LLM 비활성 → fallback 라우팅) ────────────────────────


class TestAssist:
    @pytest.mark.asyncio
    async def test_disable_llm_uses_fallback(self):
        draft = await assist(AssistRequest(natural_language="실수율 0.85"))
        assert draft.method == "fallback"
        assert draft.extracted_term == "실수율"

    @pytest.mark.asyncio
    async def test_prefer_llm_false_uses_fallback(self):
        draft = await assist(AssistRequest(natural_language="EDGING", prefer_llm=False))
        assert draft.method == "fallback"


# ─── ScenarioDraft schema ───────────────────────────────────────────


class TestSchema:
    def test_step_id_validation(self):
        draft = ScenarioDraft(
            title="t", rationale="r",
            step_id="thickness", inputs={}, tags=[], confidence=0.5,
        )
        assert draft.step_id in registry.STEP_REGISTRY

    def test_confidence_bounded(self):
        with pytest.raises(Exception):
            ScenarioDraft(
                title="t", rationale="r", step_id="thickness", confidence=1.5,
            )


# ─── Export / Import ────────────────────────────────────────────────


class TestExportImport:
    def test_export_round_trip(self, temp_db: Path):
        # 시나리오 2건 등록
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="A", step_id="thickness",
            inputs={"order": {}}, tags=["t1"]), db_path=temp_db)
        scn_store.upsert_scenario(scn_store.Scenario(
            id="", name="B", step_id="validator",
            inputs={"order": {"stockCode": 1}}, tags=["t2"]), db_path=temp_db)

        items = scn_store.list_scenarios(db_path=temp_db)
        assert len(items) == 2

        # export 직렬화 (router 호출 대신 store 함수만 검증 — list+yaml 변환 동등)
        payload = [
            {
                "id": s.id, "name": s.name, "description": s.description,
                "step_id": s.step_id, "tags": list(s.tags), "inputs": s.inputs,
            }
            for s in items
        ]
        text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
        assert "name: A" in text
        assert "step_id: validator" in text

        # 새 DB 에 import
        new_db = temp_db.parent / "imp_test.db"
        db_mod.init_schema(new_db)
        parsed = yaml.safe_load(text)
        for item in parsed:
            scn_store.upsert_scenario(scn_store.Scenario(
                id=item["id"], name=item["name"], description=item.get("description"),
                step_id=item["step_id"], inputs=item.get("inputs") or {},
                tags=item.get("tags") or [], source="user",
            ), db_path=new_db)
        new_items = scn_store.list_scenarios(db_path=new_db)
        assert len(new_items) == 2
        names = {s.name for s in new_items}
        assert names == {"A", "B"}
