"""Phase 4 — HybridOntologyClient: sec2 HTTP API + sim_v2 fallback."""
from __future__ import annotations

import json

import httpx
import pytest

from backend.section3.agents.multiturn.ontology_client import (
    HybridOntologyClient,
    SimV2BackedOntologyClient,
)


# ─────────────────────────────────────────────────────────────────────────────
# httpx mock transport — sec2 API simulation
# ─────────────────────────────────────────────────────────────────────────────


def _make_mock_transport(handlers: dict[str, callable]):  # type: ignore[type-arg]
    """url path → handler(request) -> httpx.Response."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        for prefix, fn in handlers.items():
            if path.startswith(prefix):
                return fn(request)
        return httpx.Response(404, text=f"unmocked path: {path}")

    return httpx.MockTransport(handler)


def _build_client(handlers: dict[str, callable]) -> HybridOntologyClient:  # type: ignore[type-arg]
    transport = _make_mock_transport(handlers)
    http_client = httpx.AsyncClient(transport=transport, base_url="http://sec2-mock")
    return HybridOntologyClient(
        base_url="http://sec2-mock", http_client=http_client,
    )


# ─────────────────────────────────────────────────────────────────────────────
# search_action_by_keyword — sec2 /api/ontology/search wire
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_search_calls_sec2_search_endpoint() -> None:
    captured = {}

    def search_handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=[
            {"fqn": "act:OrderService.validateOrder", "label": "주문 검증",
             "kind": "action", "domain": "scm", "score": 8.5},
            {"fqn": "term.scm.주문", "label": "주문",
             "kind": "term", "domain": "scm", "score": 5.0},
            {"fqn": "act:CumulativeProductivity.compute", "label": "누적 생산성",
             "kind": "action", "domain": "scm", "score": 7.0},
        ])

    client = _build_client({"/api/ontology/search": search_handler})
    hits = await client.search_action_by_keyword(
        "주문 검증", repo_id="slab-design-real-v2", top_n=5,
    )
    assert "/api/ontology/search" in captured["url"]
    assert "q=" in captured["url"]
    # term 은 제외, action 2개만
    assert len(hits) == 2
    labels = {h.label for h in hits}
    assert "주문 검증" in labels
    assert "누적 생산성" in labels


@pytest.mark.asyncio
async def test_hybrid_search_empty_results_returns_empty_list() -> None:
    client = _build_client({
        "/api/ontology/search": lambda r: httpx.Response(200, json=[]),
    })
    hits = await client.search_action_by_keyword(
        "no match", repo_id="x", top_n=5,
    )
    assert hits == []


@pytest.mark.asyncio
async def test_hybrid_search_http_error_returns_empty(monkeypatch) -> None:
    """sec2 API 가 500 반환해도 empty list (Q5 "빠진 대로")."""
    client = _build_client({
        "/api/ontology/search": lambda r: httpx.Response(500, text="boom"),
    })
    hits = await client.search_action_by_keyword(
        "x", repo_id="x", top_n=5,
    )
    assert hits == []


# ─────────────────────────────────────────────────────────────────────────────
# get_action_detail — sec2 /api/ontology/actions/{fqn} wire
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_get_action_detail_returns_action_ref() -> None:
    """sec2 ActionDTO 의 realizations[0].code_method_fqn 을 ActionRef 로 매핑."""

    def action_handler(req: httpx.Request) -> httpx.Response:
        if "validateOrder" in str(req.url):
            return httpx.Response(200, json={
                "fqn": "act:OrderService.validateOrder",
                "label": "주문 검증",
                "kind": "effectful",
                "realizations": [
                    {
                        "code_method_fqn": (
                            "com.slab.SdOrderValidator.validate(SDOrderEntity)"
                        ),
                        "applies_to_subtype": "SDOrderEntity",
                        "dispatch_source": "user_confirmed",
                        "scope": "primary",
                    },
                ],
            })
        return httpx.Response(404)

    client = _build_client({"/api/ontology/actions/": action_handler})
    ref = await client.get_action_detail(
        "act:OrderService.validateOrder", repo_id="slab-design-real-v2",
    )
    assert ref is not None
    assert ref.action_id == "act:OrderService.validateOrder"
    assert "validate" in ref.code_method_fqn


@pytest.mark.asyncio
async def test_hybrid_get_action_detail_404_returns_none() -> None:
    client = _build_client({
        "/api/ontology/actions/": lambda r: httpx.Response(404),
    })
    ref = await client.get_action_detail("nope", repo_id="x")
    assert ref is None


@pytest.mark.asyncio
async def test_hybrid_get_action_detail_no_realizations_returns_empty_fqn() -> None:
    """realizations 비어 있어도 ActionRef 반환 (code_method_fqn="")."""
    client = _build_client({
        "/api/ontology/actions/": lambda r: httpx.Response(200, json={
            "fqn": "act:abstract",
            "label": "abstract",
            "kind": "workflow",
            "realizations": [],
        }),
    })
    ref = await client.get_action_detail("act:abstract", repo_id="x")
    assert ref is not None
    assert ref.code_method_fqn == ""


# ─────────────────────────────────────────────────────────────────────────────
# Fallback (sim_v2) delegation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_method_body_calls_sec2_endpoint() -> None:
    """sec2 가 body 반환 시 sec2 값 사용 (fallback 안 함)."""
    captured = {}

    def body_handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json={
            "fqn": "com.x.Y.z",
            "body_text": "public void z() { /* sec2 source */ }",
            "line_start": 1, "line_end": 3, "return_type": "void",
        })

    client = _build_client({"/api/ontology/code-methods/": body_handler})
    body = await client.get_method_body("com.x.Y.z", repo_id="r")
    assert body is not None
    assert "sec2 source" in body
    assert "/body" in captured["url"]


@pytest.mark.asyncio
async def test_hybrid_method_body_404_falls_back_to_sim_v2(monkeypatch) -> None:
    """sec2 404 → sim_v2.load_body_text fallback."""
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass
    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "load_body_text",
        lambda session, fqn, repo: f"// fallback {fqn}",
    )

    client = _build_client({
        "/api/ontology/code-methods/": lambda r: httpx.Response(404),
    })
    body = await client.get_method_body("com.x.Y.z", repo_id="r")
    assert body == "// fallback com.x.Y.z"


@pytest.mark.asyncio
async def test_hybrid_entity_schema_calls_sec2_endpoint() -> None:
    def schema_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "entity_name": "Order", "fqn": "com.scm.Order",
            "fields": [
                {"name": "id", "type_name": "String", "nullable": False},
                {"name": "qty", "type_name": "int", "nullable": False},
            ],
        })

    client = _build_client({"/api/ontology/entities/": schema_handler})
    schema = await client.get_entity_schema("Order", repo_id="r")
    assert schema is not None
    assert schema.entity_name == "Order"
    assert len(schema.fields) == 2
    assert schema.fields[0].name == "id"


@pytest.mark.asyncio
async def test_hybrid_entity_schema_404_returns_none() -> None:
    """sec2 404 + sim_v2 fallback 도 None → None."""
    client = _build_client({
        "/api/ontology/entities/": lambda r: httpx.Response(404),
    })
    schema = await client.get_entity_schema("Unknown", repo_id="r")
    assert schema is None


@pytest.mark.asyncio
async def test_hybrid_caller_graph_calls_sec2_endpoint() -> None:
    def callers_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "callers": [
                {"fqn": "com.scm.OrderService.process",
                 "distance": 1, "via": "direct_caller"},
                {"fqn": "com.scm.OrderController.submit",
                 "distance": 1, "via": "interface_impl"},
            ],
        })

    client = _build_client({"/api/ontology/code-methods/": callers_handler})
    affected = await client.get_caller_graph("com.scm.Order.validate", repo_id="r")
    assert len(affected) == 2
    fqns = [m.fqn for m in affected]
    assert "com.scm.OrderService.process" in fqns
    assert "com.scm.OrderController.submit" in fqns


@pytest.mark.asyncio
async def test_hybrid_caller_graph_404_returns_empty() -> None:
    client = _build_client({
        "/api/ontology/code-methods/": lambda r: httpx.Response(404),
    })
    affected = await client.get_caller_graph("com.x.Y.z", repo_id="r")
    assert affected == []


# ─────────────────────────────────────────────────────────────────────────────
# Custom fallback injection
# ─────────────────────────────────────────────────────────────────────────────


class _CustomFallback:
    async def search_action_by_keyword(self, q, *, repo_id, top_n=5):
        return []

    async def get_action_detail(self, action_id, *, repo_id):
        return None

    async def get_method_body(self, fqn, *, repo_id):
        return "fallback body"

    async def get_entity_schema(self, entity_name, *, repo_id):
        return None

    async def get_caller_graph(self, method_fqn, *, repo_id):
        return []


@pytest.mark.asyncio
async def test_hybrid_uses_custom_fallback() -> None:
    transport = httpx.MockTransport(lambda r: httpx.Response(200))
    http = httpx.AsyncClient(transport=transport, base_url="http://sec2")
    client = HybridOntologyClient(
        base_url="http://sec2", http_client=http,
        fallback=_CustomFallback(),
    )
    body = await client.get_method_body("x", repo_id="r")
    assert body == "fallback body"
