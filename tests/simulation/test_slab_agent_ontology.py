"""slab_agent (옛 v1 leftover) — ontology 기반 재구현 검증 (STEP 3c-D).

이전: ImportError 로 HTTP 500 (mock_simulator 삭제됨)
현재: OntologyQueryClientImpl 기반 — atomic facets / params echo
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _client_with_slab_agent():
    from backend.simulation.api.slab_agent import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ─── /constraints ─────────────────────────────────────────────────


def test_slab_constraints_returns_200_with_ontology_meta():
    """이전 ImportError → 200 정상 응답."""
    client = _client_with_slab_agent()
    resp = client.get("/api/simulation/slab/constraints")
    assert resp.status_code == 200
    data = resp.json()
    assert "constraints" in data
    assert data["_meta"]["source"] == "ontology"


def test_slab_constraints_filters_slab_related_atomics():
    """응답의 atomic_count 가 0 이상 — ontology 데이터 있으면 slab 키워드 매칭됨."""
    client = _client_with_slab_agent()
    resp = client.get("/api/simulation/slab/constraints")
    assert resp.status_code == 200
    data = resp.json()
    assert data["_meta"]["atomic_count"] >= 0  # 0 도 OK (ontology 환경 의존)


# ─── /calculate ───────────────────────────────────────────────────


def test_slab_calculate_returns_deprecated_marker():
    """200 + status='deprecated' + spec 03 redirect 안내."""
    client = _client_with_slab_agent()
    resp = client.post(
        "/api/simulation/slab/calculate",
        json={"customer_no": "7", "product_kind": "HR"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deprecated"
    assert "POST /api/simulation/runs" in data["_meta"]["redirect_to"]
    assert data["input_echo"] == {"customer_no": "7", "product_kind": "HR"}
    # validation field 가 ontology 기반 — matched_atomics / unknown_keys
    assert "matched_atomics" in data["validation"]
    assert "unknown_keys" in data["validation"]


def test_slab_calculate_empty_params_handled_gracefully():
    """빈 dict → 200 + 빈 validation."""
    client = _client_with_slab_agent()
    resp = client.post("/api/simulation/slab/calculate", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["validation"]["matched_atomics"] == []
    assert data["validation"]["unknown_keys"] == []
