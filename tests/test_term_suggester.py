"""Tests for ClaudeTermSuggester (LLM 호출 mocked) + bulk-add endpoint.

LLM call 자체는 외부 의존이라 mock 으로 대체. JSON parse 경로 + suggester
no-op 모드 + bulk-add 의 dedup 동작에 집중.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import terms_api
from backend.modeling.api.terms_api import (
    TermBulkAddRequest,
    TermSuggestionDto,
)
from backend.modeling.manual_ingest.manual_registry import InMemoryManualRegistry
from backend.modeling.manuals.manual_models import (
    ManualDocument,
    ManualFormat,
    ManualFragment,
    ManualFragmentKind,
    ManualSection,
)
from backend.modeling.mapping.business_term_registry import (
    InMemoryBusinessTermRegistry,
)
from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
from backend.modeling.mapping.mapping_models import BusinessTerm, BusinessTermSource
from backend.modeling.mapping.propose_bindings_service import ProposeBindingsService
from backend.modeling.mapping.term_suggester import (
    ClaudeTermSuggester,
    TermSuggestion,
)


# ---------------------------------------------------------------------------
# Suggester unit tests (LLM client mocked)
# ---------------------------------------------------------------------------
def test_suggester_no_op_when_no_api_key(monkeypatch):
    """API key 없으면 graceful no-op (빈 리스트 반환, 예외 X)."""
    sg = ClaudeTermSuggester(api_key=None)
    sg._client = None   # explicit
    out = sg.suggest_from_manual(
        doc_title="t", fragments=["품종코드는 4자리 영문숫자."], max_terms=5,
    )
    assert out == []
    assert sg.is_available is False


def test_suggester_parses_json_array_response():
    """LLM 이 JSON 배열을 반환하면 TermSuggestion 으로 파싱."""
    sg = ClaudeTermSuggester(api_key="dummy")

    fake_resp = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = """```json
[
  {
    "qualified_name": "term.품종코드",
    "canonical_label": "품종코드",
    "aliases": ["productCode", "prodCd"],
    "description": "강재 품종 코드 4자리.",
    "evidence": "품종코드는 4자리 영문숫자",
    "confidence": 0.92
  },
  {
    "qualified_name": "term.열연공장코드",
    "canonical_label": "열연공장코드",
    "aliases": ["hr_plant_cd"],
    "description": "열연 공장 1자리 코드.",
    "evidence": "열연공장코드 1자리",
    "confidence": 0.85
  }
]
```"""
    fake_resp.content = [block]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    sg._client = fake_client

    out = sg.suggest_from_manual(
        doc_title="슬라브 매뉴얼",
        fragments=["품종코드는 4자리 영문숫자.", "열연공장코드 1자리"],
        max_terms=10,
    )

    assert len(out) == 2
    assert out[0].qualified_name == "term.품종코드"
    assert "productCode" in out[0].aliases
    assert 0.0 <= out[0].confidence <= 1.0
    assert out[1].canonical_label == "열연공장코드"


def test_suggester_handles_invalid_json_gracefully():
    """LLM 이 망가진 응답 → 빈 리스트."""
    sg = ClaudeTermSuggester(api_key="dummy")
    fake_resp = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = "응 그냥 텍스트 응답 (파싱 불가)"
    fake_resp.content = [block]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    sg._client = fake_client

    out = sg.suggest_from_manual(
        doc_title="t", fragments=["foo"], max_terms=5,
    )
    assert out == []


# ---------------------------------------------------------------------------
# terms_api 엔드포인트 e2e (suggester mocked)
# ---------------------------------------------------------------------------
@pytest.fixture
def wired_app():
    """매뉴얼 1건 + mocked suggester 가 wire 된 FastAPI app."""
    term_registry = InMemoryBusinessTermRegistry()
    binding_store = InMemoryConceptBindingStore()
    propose_service = ProposeBindingsService(
        term_registry=term_registry,
        binding_store=binding_store,
        llm_resolver=None,
    )
    manual_registry = InMemoryManualRegistry()

    now = datetime.now(timezone.utc)
    doc = ManualDocument(
        qualified_name="manual.test_doc",
        title="테스트 매뉴얼",
        source_path="/tmp/test.md",
        format=ManualFormat.MARKDOWN,
        version="",
        checksum="abc123",
        authoritative=False,
        created_at=now,
    )
    section = ManualSection(
        qualified_name="manual.test_doc#sec0",
        doc_fqn=doc.qualified_name,
        title="섹션",
        heading_path=["섹션"],
        order_index=0,
        created_at=now,
    )
    frag = ManualFragment(
        qualified_name="manual.test_doc#sec0#0",
        section_fqn=section.qualified_name,
        kind=ManualFragmentKind.TEXT,
        text="품종코드는 4자리 영문숫자.",
        order_index=0,
        attributes={},
        created_at=now,
    )
    manual_registry.add(doc, sections=[section], fragments=[frag])

    suggester = ClaudeTermSuggester(api_key="dummy")
    fake_resp = MagicMock()
    block = MagicMock()
    block.type = "text"
    block.text = """[
  {"qualified_name": "term.품종코드", "canonical_label": "품종코드",
   "aliases": ["productCode"], "description": "강재 품종.", "evidence": "품종코드",
   "confidence": 0.9}
]"""
    fake_resp.content = [block]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    suggester._client = fake_client

    terms_api.reset()
    terms_api.init(
        term_registry=term_registry,
        binding_store=binding_store,
        propose_service=propose_service,
        repo_registry=None,
        manual_registry=manual_registry,
        term_suggester=suggester,
    )

    app = FastAPI()
    app.include_router(terms_api.router)
    return TestClient(app), term_registry


def test_suggest_from_manual_endpoint(wired_app):
    client, term_registry = wired_app
    r = client.post(
        "/api/modeling/terms/suggest-from-manual",
        json={"repo_id": "demo-repo", "doc_fqn": "manual.test_doc", "max_terms": 5},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fragments_inspected"] == 1
    assert len(body["suggestions"]) == 1
    s0 = body["suggestions"][0]
    assert s0["qualified_name"] == "term.품종코드"
    assert s0["already_exists"] is False
    assert "productCode" in s0["aliases"]


def test_bulk_add_dedup(wired_app):
    """이미 등록된 fqn 은 skip, 새 것만 추가."""
    client, term_registry = wired_app
    # Pre-register one term
    term_registry.put("demo-repo", BusinessTerm(
        qualified_name="term.기존",
        canonical_label="기존 용어",
        aliases=[],
        domain="",
        description="",
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=datetime.now(timezone.utc),
    ))

    r = client.post(
        "/api/modeling/terms/bulk-add",
        json={
            "repo_id": "demo-repo",
            "terms": [
                {
                    "qualified_name": "term.신규",
                    "canonical_label": "신규 용어",
                    "aliases": ["new"],
                    "description": "테스트",
                    "evidence": "어딘가",
                    "confidence": 0.8,
                    "already_exists": False,
                },
                {
                    "qualified_name": "term.기존",
                    "canonical_label": "기존 용어 dup",
                    "aliases": [],
                    "description": "",
                    "evidence": "",
                    "confidence": 0.5,
                    "already_exists": True,
                },
                {
                    "qualified_name": "",
                    "canonical_label": "invalid",
                    "aliases": [],
                    "description": "",
                    "evidence": "",
                    "confidence": 0.0,
                    "already_exists": False,
                },
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 1
    assert body["skipped_existing"] == 1
    assert body["skipped_invalid"] == 1
    assert term_registry.get("demo-repo", "term.신규") is not None


def test_collect_column_summaries_from_jpa_class():
    """`_collect_column_summaries` — JPA 컬럼 + 필드 + Javadoc 합성."""
    from backend.modeling.api.terms_api import _collect_column_summaries
    from backend.modeling.code_analysis.parser_protocol import (
        CodeEntity,
        ParseResult,
    )

    cls = CodeEntity(
        kind="class",
        qualified_name="com.demo.Order",
        name="Order",
        file_path="Order.java",
        line_start=1,
        line_end=20,
        attributes={
            "jpa_columns_meta": {
                "productCode": {"name": "PROD_CD", "is_id": False},
                "id": {"name": "ID", "is_id": True},
            },
        },
    )
    field_pc = CodeEntity(
        kind="field",
        qualified_name="com.demo.Order.productCode",
        name="productCode",
        file_path="Order.java",
        line_start=5,
        line_end=5,
        parent="com.demo.Order",
        attributes={"field_type": "String", "javadoc": "강재 품종 4자리 코드"},
    )
    field_id = CodeEntity(
        kind="field",
        qualified_name="com.demo.Order.id",
        name="id",
        file_path="Order.java",
        line_start=4,
        line_end=4,
        parent="com.demo.Order",
        attributes={"field_type": "Long"},
    )
    pr = ParseResult(
        entities=[cls, field_pc, field_id],
        relations=[],
        file_path="Order.java",
        language="java",
    )
    rows = _collect_column_summaries([pr])
    joined = "\n".join(rows)
    assert "Order.productCode" in joined
    assert "PROD_CD" in joined
    assert "강재 품종" in joined
    assert "@Id" in joined  # id 필드 표시
    assert len(rows) == 2


def test_suggest_endpoint_503_when_suggester_unavailable():
    """API key 없는 suggester → 503."""
    term_registry = InMemoryBusinessTermRegistry()
    binding_store = InMemoryConceptBindingStore()
    propose_service = ProposeBindingsService(
        term_registry=term_registry,
        binding_store=binding_store,
        llm_resolver=None,
    )
    manual_registry = InMemoryManualRegistry()
    suggester = ClaudeTermSuggester(api_key=None)
    suggester._client = None

    terms_api.reset()
    terms_api.init(
        term_registry=term_registry,
        binding_store=binding_store,
        propose_service=propose_service,
        repo_registry=None,
        manual_registry=manual_registry,
        term_suggester=suggester,
    )

    app = FastAPI()
    app.include_router(terms_api.router)
    client = TestClient(app)

    r = client.post(
        "/api/modeling/terms/suggest-from-manual",
        json={"repo_id": "demo-repo", "doc_fqn": None, "max_terms": 5},
    )
    assert r.status_code == 503
