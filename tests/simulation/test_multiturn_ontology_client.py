"""Step 1d TDD — OntologyClient Protocol + MockOntologyClient.

Section 2 API 의 5 endpoint abstraction. Phase 1 은 mock (in-memory catalog 또는
sim_v2 fallback), Phase 2 는 HTTPOntologyClient 로 swap.
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Protocol existence
# ─────────────────────────────────────────────────────────────────────────────


def test_protocol_exposes_5_methods() -> None:
    """OntologyClient Protocol 이 5 endpoint 명시."""
    from backend.section3.agents.multiturn.ontology_client import OntologyClient
    expected = {
        "search_action_by_keyword",
        "get_action_detail",
        "get_method_body",
        "get_entity_schema",
        "get_caller_graph",
    }
    for name in expected:
        assert hasattr(OntologyClient, name), f"OntologyClient missing {name}"


# ─────────────────────────────────────────────────────────────────────────────
# MockOntologyClient — in-memory catalog
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_catalog() -> dict:
    return {
        "actions": [
            {
                "action_id": "action.scm.order.validate",
                "label": "주문 검증",
                "code_method_fqn": "com.ontong.scm.OrderService.validateOrder",
                "aliases": ["OrderValidation", "validateOrder"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "src/main/java/.../OrderService.java",
                    "line_start": 42, "line_end": 87,
                },
            },
            {
                "action_id": "action.scm.edging.lookup",
                "label": "엣징 사양 룩업",
                "code_method_fqn": "com.ontong.scm.EdgingService.lookup",
                "aliases": ["EdgingLookup"],
                "repo_id": "slab-design-real-v2",
                "location": {
                    "file_path": "src/main/java/.../EdgingService.java",
                    "line_start": 10, "line_end": 50,
                },
            },
        ],
        "method_bodies": {
            "com.ontong.scm.OrderService.validateOrder":
                "public ValidationResult validateOrder(Order o){ ... }",
        },
        "entity_schemas": {
            "Order": {
                "entity_name": "Order",
                "fields": [
                    {"name": "order_id", "type_name": "string", "nullable": False},
                    {"name": "qty", "type_name": "int", "nullable": False},
                ],
            },
        },
        "caller_graphs": {
            "com.ontong.scm.OrderService.validateOrder": [
                {"fqn": "OrderController.create", "distance": 1, "via": "direct_caller"},
                {"fqn": "OrderBatch.run", "distance": 2, "via": "indirect"},
            ],
        },
    }


@pytest.mark.asyncio
async def test_mock_search_finds_korean_label(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    hits = await c.search_action_by_keyword("주문", repo_id="slab-design-real-v2")
    assert len(hits) >= 1
    assert hits[0].action_id == "action.scm.order.validate"


@pytest.mark.asyncio
async def test_mock_search_finds_via_alias(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    hits = await c.search_action_by_keyword("validateOrder", repo_id="slab-design-real-v2")
    assert any(h.action_id == "action.scm.order.validate" for h in hits)


@pytest.mark.asyncio
async def test_mock_search_repo_filter(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    hits = await c.search_action_by_keyword("주문", repo_id="other-repo")
    assert hits == []


@pytest.mark.asyncio
async def test_mock_get_action_detail(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    detail = await c.get_action_detail(
        "action.scm.order.validate", repo_id="slab-design-real-v2",
    )
    assert detail is not None
    assert detail.code_method_fqn == "com.ontong.scm.OrderService.validateOrder"


@pytest.mark.asyncio
async def test_mock_get_action_detail_unknown(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    assert await c.get_action_detail("missing", repo_id="slab-design-real-v2") is None


@pytest.mark.asyncio
async def test_mock_get_method_body(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    body = await c.get_method_body(
        "com.ontong.scm.OrderService.validateOrder",
        repo_id="slab-design-real-v2",
    )
    assert body is not None
    assert "validateOrder" in body


@pytest.mark.asyncio
async def test_mock_get_entity_schema(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    schema = await c.get_entity_schema("Order", repo_id="slab-design-real-v2")
    assert schema is not None
    assert schema.entity_name == "Order"
    assert len(schema.fields) == 2


@pytest.mark.asyncio
async def test_mock_get_caller_graph(mock_catalog) -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    affected = await c.get_caller_graph(
        "com.ontong.scm.OrderService.validateOrder",
        repo_id="slab-design-real-v2",
    )
    assert len(affected) == 2
    assert affected[0].fqn == "OrderController.create"


@pytest.mark.asyncio
async def test_mock_missing_entries_return_none_or_empty(mock_catalog) -> None:
    """Q5 비전 — 빠진 정보는 빠진대로 (raise 안 함, None/empty 반환)."""
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog=mock_catalog)
    assert await c.get_method_body("missing.fqn", repo_id="slab-design-real-v2") is None
    assert await c.get_entity_schema("MissingEntity", repo_id="slab-design-real-v2") is None
    assert await c.get_caller_graph("missing.fqn", repo_id="slab-design-real-v2") == []


# ─────────────────────────────────────────────────────────────────────────────
# Empty catalog (no seed) — degrades gracefully
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_catalog_all_endpoints_no_crash() -> None:
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    c = MockOntologyClient(catalog={})
    assert await c.search_action_by_keyword("x", repo_id="r") == []
    assert await c.get_action_detail("x", repo_id="r") is None
    assert await c.get_method_body("x", repo_id="r") is None
    assert await c.get_entity_schema("x", repo_id="r") is None
    assert await c.get_caller_graph("x", repo_id="r") == []
