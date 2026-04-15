# tests/test_engine_api.py
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import engine_api


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(engine_api.router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_deps():
    neo4j = MagicMock()
    neo4j.query.return_value = []

    from backend.modeling.query.query_engine import QueryEngine
    from backend.modeling.mapping.mapping_service import MappingService
    from backend.modeling.simulation.sim_engine import SimulationEngine
    from backend.modeling.query.term_resolver import TermResolver

    engine_api._query_engine = QueryEngine(neo4j)
    engine_api._mapping_svc = MappingService(neo4j)
    engine_api._sim_engine = SimulationEngine(neo4j)
    engine_api._term_resolver = TermResolver()
    engine_api._git = MagicMock()

    from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus
    mf = MappingFile(repo_id="scm-demo", mappings=[
        Mapping(code="com.ontong.scm.inventory.SafetyStockCalculator",
                domain="SCOR/Plan/InventoryPlanning",
                status=MappingStatus.CONFIRMED, owner="system"),
    ])
    engine_api._load_mapping_file = MagicMock(return_value=mf)

    yield neo4j


class TestEngineQueryEndpoint:
    def test_query_resolves_term(self, client, mock_deps):
        mock_deps.query.side_effect = [
            [],
        ]
        resp = client.post("/api/modeling/engine/query", json={
            "query": "SafetyStockCalculator",
            "repo_id": "scm-demo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert "SafetyStockCalculator" in data["source_code_entity"]

    def test_query_unresolved(self, client, mock_deps):
        resp = client.post("/api/modeling/engine/query", json={
            "query": "CompletelyUnknownThing",
            "repo_id": "scm-demo",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is False


class TestEngineSimulateEndpoint:
    def test_simulate_known_entity(self, client, mock_deps):
        mock_deps.query.return_value = []
        resp = client.post("/api/modeling/engine/simulate", json={
            "entity_id": "com.ontong.scm.inventory.SafetyStockCalculator",
            "repo_id": "scm-demo",
            "params": {"safety_factor": "2.0"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "SafetyStockCalculator"
        assert len(data["outputs"]) >= 2

    def test_simulate_unknown_entity(self, client, mock_deps):
        resp = client.post("/api/modeling/engine/simulate", json={
            "entity_id": "com.example.Unknown",
            "repo_id": "scm-demo",
            "params": {},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "지원되지 않는" in data["message"]


class TestEngineStatusEndpoint:
    def test_status_returns_counts(self, client, mock_deps):
        resp = client.get("/api/modeling/engine/status?repo_id=scm-demo")
        assert resp.status_code == 200
        data = resp.json()
        assert "mapping_count" in data
        assert "simulatable_entities" in data


class TestEngineParamsEndpoint:
    def test_get_params_for_entity(self, client, mock_deps):
        resp = client.get(
            "/api/modeling/engine/params/com.ontong.scm.inventory.SafetyStockCalculator"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["params"]) == 3
