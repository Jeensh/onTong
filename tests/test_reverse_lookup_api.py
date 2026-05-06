"""OD-11-C4 TDD — `reverse_lookup_api.py` REST + SSE.

Chain : TermResolver(C3).resolve(term) → matched_term_fqn
       → QueryEngine.reverse_lookup(fqn, edge_kinds={REALIZES}, ...)

옵션 :
- include_unconfirmed (default=false) : resolution + binding 의 confirmed=False 포함 여부
- scope_filter (default=all) : primary | partial | all

Spec:
- `toClaude/modeling/HANDOFF.md` §1 (다음 세션 첫 작업 · C4)
- `backend/modeling/query/term_resolver.py` (C3)
- `backend/modeling/mapping/mapping_models.py` (C2)
- `backend/modeling/query/query_engine.py` (B8-3)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.api import reverse_lookup_api
from backend.modeling.mapping import (
    BindingScope,
    BindingSource,
    BusinessTerm,
    BusinessTermSource,
    ConceptBinding,
)
from backend.modeling.mapping.audit_store import InMemoryAuditLogStore
from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
from backend.modeling.query.query_engine import QueryEngine
from backend.modeling.query.query_models import ImpactConfig
from backend.modeling.query.term_resolver import (
    InMemoryEmbeddingProvider,
    LLMProposal,
    TermResolver,
)


_NOW = datetime(2026, 4, 20, 15, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _term(
    fqn: str,
    label: str,
    *,
    aliases: list[str] | None = None,
    domain: str = "inventory",
) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=fqn,
        canonical_label=label,
        aliases=list(aliases or []),
        domain=domain,
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=_NOW,
    )


def _binding(
    term_fqn: str,
    code_fqn: str,
    *,
    scope: BindingScope = BindingScope.PRIMARY,
    source: BindingSource = BindingSource.MANUAL,
    confidence: float = 1.0,
    confirmed: bool = True,
) -> ConceptBinding:
    return ConceptBinding(
        term_fqn=term_fqn,
        code_fqn=code_fqn,
        scope=scope,
        confidence=confidence,
        source=source,
        confirmed=confirmed,
        created_at=_NOW,
    )


class _FakeLLM:
    def __init__(self, proposal: LLMProposal | None = None) -> None:
        self._proposal = proposal

    def propose(self, query: str, available_terms):
        return self._proposal


def _make_app(
    *,
    terms: list[BusinessTerm] | None = None,
    bindings: list[ConceptBinding] | None = None,
    embeddings: dict[str, list[float]] | None = None,
    llm_proposal: LLMProposal | None = None,
):
    """Return (app, binding_store, audit_store, resolver)."""
    terms = list(terms or [])
    bindings = list(bindings or [])

    binding_store = InMemoryConceptBindingStore(bindings)
    audit_store = InMemoryAuditLogStore()

    emb_provider = None
    if embeddings is not None:
        def _embed(text: str) -> list[float]:
            lower = text.casefold()
            # Any text mentioning both "safety" and "stock" maps near the stored
            # embedding (deterministic, cutoff-satisfying).
            if "safety" in lower and "stock" in lower:
                return [1.0, 0.0, 0.0]
            return [0.0, 1.0, 0.0]
        emb_provider = InMemoryEmbeddingProvider(
            embeddings=embeddings, embed_fn=_embed
        )

    llm = _FakeLLM(llm_proposal) if llm_proposal is not None else None
    resolver = TermResolver(
        terms=terms,
        embedding_provider=emb_provider,
        llm_resolver=llm,
        clock=lambda: _NOW,
    )

    reverse_lookup_api.init(
        resolver=resolver,
        binding_store=binding_store,
        audit_store=audit_store,
        engine_config=ImpactConfig(),
    )

    app = FastAPI()
    app.include_router(reverse_lookup_api.router)
    return app, binding_store, audit_store, resolver


# ---------------------------------------------------------------------------
# 1. Service not initialized
# ---------------------------------------------------------------------------
def test_unconfigured_service_returns_503() -> None:
    reverse_lookup_api.reset()
    app = FastAPI()
    app.include_router(reverse_lookup_api.router)
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "anything"})
    assert r.status_code == 503
    assert "not initialized" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. term query missing
# ---------------------------------------------------------------------------
def test_missing_term_param_returns_422() -> None:
    app, *_ = _make_app()
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 3. miss returns null matched + empty affected, audit logged
# ---------------------------------------------------------------------------
def test_miss_returns_empty_impact_and_logs_audit() -> None:
    app, _, audit_store, _ = _make_app(terms=[_term("term.safety_stock", "Safety Stock")])
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "unknown_thing"})
    assert r.status_code == 200
    body = r.json()
    assert body["query_term"] == "unknown_thing"
    assert body["resolution"]["matched_term_fqn"] is None
    assert body["resolution"]["resolution_source"] == "miss"
    assert body["impact"] is None

    logs = audit_store.recent()
    assert len(logs) == 1
    assert logs[0].query_term == "unknown_thing"
    assert logs[0].resolution_source.value == "miss"


# ---------------------------------------------------------------------------
# 4. exact match returns affected from bindings
# ---------------------------------------------------------------------------
def test_exact_match_returns_affected_from_bindings() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding("term.safety_stock", "com.app.StockService.calculate"),
            _binding(
                "term.safety_stock",
                "com.app.StockValidator.check",
                scope=BindingScope.PARTIAL,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "Safety Stock"})
    assert r.status_code == 200
    body = r.json()
    assert body["resolution"]["matched_term_fqn"] == "term.safety_stock"
    assert body["resolution"]["resolution_source"] == "exact"
    assert body["resolution"]["confirmed"] is True

    assert body["impact"] is not None
    hits = {a["qualified_name"] for a in body["impact"]["affected"]}
    assert hits == {
        "com.app.StockService.calculate",
        "com.app.StockValidator.check",
    }


# ---------------------------------------------------------------------------
# 5. alias match works
# ---------------------------------------------------------------------------
def test_alias_match_returns_affected() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock", aliases=["안전재고"])],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
    )
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "안전재고"})
    assert r.status_code == 200
    body = r.json()
    assert body["resolution"]["resolution_source"] == "alias"
    assert body["resolution"]["confirmed"] is True
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockService.calculate"
    }


# ---------------------------------------------------------------------------
# 6. embedding match is unconfirmed → hidden by default
# ---------------------------------------------------------------------------
def test_embedding_match_hidden_when_include_unconfirmed_false() -> None:
    # 'safety stock' is aliased so make query that only embedding can match
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
        embeddings={"term.safety_stock": [1.0, 0.0, 0.0]},
    )
    client = TestClient(app)

    # Query "safety stock" matches exactly via alias index (_normalize)
    # So use a query that doesn't match exact/alias but has high embedding sim.
    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "stock safety"},  # reversed; not exact match
    )
    assert r.status_code == 200
    body = r.json()
    # matched via embedding (confirmed=False)
    assert body["resolution"]["resolution_source"] == "embedding"
    assert body["resolution"]["confirmed"] is False
    # default include_unconfirmed=false → impact gated
    assert body["impact"] is None
    assert body["include_unconfirmed"] is False


def test_embedding_match_surfaced_when_include_unconfirmed_true() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
        embeddings={"term.safety_stock": [1.0, 0.0, 0.0]},
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "safety stock", "include_unconfirmed": "true"},
    )
    # "safety stock" is the canonical → exact match (confirmed). Not useful test.
    # switch to a non-canonical query
    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "stock safety", "include_unconfirmed": "true"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["resolution"]["resolution_source"] == "embedding"
    assert body["resolution"]["confirmed"] is False
    assert body["impact"] is not None
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockService.calculate"
    }


# ---------------------------------------------------------------------------
# 7. scope_filter = primary
# ---------------------------------------------------------------------------
def test_scope_filter_primary_returns_only_primary_binding() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.StockService.calculate",
                scope=BindingScope.PRIMARY,
            ),
            _binding(
                "term.safety_stock",
                "com.app.StockValidator.check",
                scope=BindingScope.PARTIAL,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "scope_filter": "primary"},
    )
    assert r.status_code == 200
    body = r.json()
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockService.calculate"
    }


# ---------------------------------------------------------------------------
# 8. scope_filter = partial
# ---------------------------------------------------------------------------
def test_scope_filter_partial_returns_only_partial_binding() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.StockService.calculate",
                scope=BindingScope.PRIMARY,
            ),
            _binding(
                "term.safety_stock",
                "com.app.StockValidator.check",
                scope=BindingScope.PARTIAL,
            ),
            _binding(
                "term.safety_stock",
                "com.app.LogHelper.auditSafety",
                scope=BindingScope.PARTIAL,
                source=BindingSource.NAME_MATCH,
                confidence=0.9,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "scope_filter": "partial"},
    )
    assert r.status_code == 200
    body = r.json()
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockValidator.check",
        "com.app.LogHelper.auditSafety",
    }


# ---------------------------------------------------------------------------
# 9. scope_filter = all (default)
# ---------------------------------------------------------------------------
def test_scope_filter_all_is_default() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.StockService.calculate",
                scope=BindingScope.PRIMARY,
            ),
            _binding(
                "term.safety_stock",
                "com.app.StockValidator.check",
                scope=BindingScope.PARTIAL,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "Safety Stock"})
    body = r.json()
    assert body["scope_filter"] == "all"
    assert len(body["impact"]["affected"]) == 2


# ---------------------------------------------------------------------------
# 10. invalid scope_filter
# ---------------------------------------------------------------------------
def test_invalid_scope_filter_returns_422() -> None:
    app, *_ = _make_app(terms=[_term("term.safety_stock", "Safety Stock")])
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "scope_filter": "bogus"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 11. include_unconfirmed + binding confirmed=False
# ---------------------------------------------------------------------------
def test_unconfirmed_binding_hidden_by_default() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.StockService.calculate",
                confirmed=True,
            ),
            _binding(
                "term.safety_stock",
                "com.app.Proposed.auto",
                source=BindingSource.EMBEDDING,
                confidence=0.85,
                confirmed=False,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup", params={"term": "Safety Stock"})
    body = r.json()
    # resolution is exact (confirmed=True), so impact not gated — but bindings
    # filter still drops unconfirmed ones.
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockService.calculate"
    }


def test_unconfirmed_binding_surfaced_with_include_unconfirmed_true() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.StockService.calculate",
                confirmed=True,
            ),
            _binding(
                "term.safety_stock",
                "com.app.Proposed.auto",
                source=BindingSource.EMBEDDING,
                confidence=0.85,
                confirmed=False,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "include_unconfirmed": "true"},
    )
    body = r.json()
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.StockService.calculate",
        "com.app.Proposed.auto",
    }


# ---------------------------------------------------------------------------
# 12. Audit log persists every request (hit + miss)
# ---------------------------------------------------------------------------
def test_audit_log_persisted_for_hits_and_misses() -> None:
    app, _, audit_store, _ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
    )
    client = TestClient(app)

    client.get("/api/modeling/reverse_lookup", params={"term": "Safety Stock"})
    client.get("/api/modeling/reverse_lookup", params={"term": "nothing"})

    logs = audit_store.recent()
    assert len(logs) == 2
    assert logs[0].query_term == "Safety Stock"
    assert logs[0].resolution_source.value == "exact"
    assert logs[1].query_term == "nothing"
    assert logs[1].resolution_source.value == "miss"


# ---------------------------------------------------------------------------
# 13. LLM fallback accepted with include_unconfirmed
# ---------------------------------------------------------------------------
def test_llm_fallback_gated_by_include_unconfirmed() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
        llm_proposal=LLMProposal(
            term_fqn="term.safety_stock", confidence=0.8, reasoning="test"
        ),
    )
    client = TestClient(app)

    # default — LLM match is confirmed=False → impact gated
    r1 = client.get(
        "/api/modeling/reverse_lookup", params={"term": "secure stockpile"}
    )
    body1 = r1.json()
    assert body1["resolution"]["resolution_source"] == "llm"
    assert body1["resolution"]["confirmed"] is False
    assert body1["impact"] is None

    # opt-in
    r2 = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "secure stockpile", "include_unconfirmed": "true"},
    )
    body2 = r2.json()
    assert body2["resolution"]["resolution_source"] == "llm"
    assert body2["impact"] is not None


# ---------------------------------------------------------------------------
# 14. SSE stream emits stage events + complete
# ---------------------------------------------------------------------------
def test_sse_stream_emits_staged_sequence_for_hit() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[_binding("term.safety_stock", "com.app.StockService.calculate")],
    )
    client = TestClient(app)

    with client.stream(
        "GET",
        "/api/modeling/reverse_lookup/stream",
        params={"term": "Safety Stock"},
    ) as r:
        assert r.status_code == 200
        events = _parse_sse(r.iter_lines())

    names = [e["event"] for e in events]
    assert names[0] == "resolving"
    assert "resolved" in names
    assert "complete" in names

    complete_event = next(e for e in events if e["event"] == "complete")
    payload = json.loads(complete_event["data"])
    assert payload["resolution"]["matched_term_fqn"] == "term.safety_stock"
    assert payload["impact"]["affected"][0]["qualified_name"] == (
        "com.app.StockService.calculate"
    )


def test_sse_stream_emits_miss_event() -> None:
    app, *_ = _make_app(terms=[_term("term.safety_stock", "Safety Stock")])
    client = TestClient(app)

    with client.stream(
        "GET",
        "/api/modeling/reverse_lookup/stream",
        params={"term": "totally unknown"},
    ) as r:
        events = _parse_sse(r.iter_lines())

    names = [e["event"] for e in events]
    assert "resolving" in names
    assert "resolved" in names
    assert "complete" in names

    complete_event = next(e for e in events if e["event"] == "complete")
    payload = json.loads(complete_event["data"])
    assert payload["resolution"]["matched_term_fqn"] is None
    assert payload["impact"] is None


# ---------------------------------------------------------------------------
# 15. scope_filter applies pre-engine (edges not in view)
# ---------------------------------------------------------------------------
def test_scope_filter_excludes_edges_from_engine_view() -> None:
    # If we asked for primary only, partial edges should NOT be in affected regardless
    # of mode/edge filters.
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.P.primary",
                scope=BindingScope.PRIMARY,
            ),
            _binding(
                "term.safety_stock",
                "com.app.Q.partial",
                scope=BindingScope.PARTIAL,
            ),
        ],
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "scope_filter": "primary", "mode": "potential"},
    )
    body = r.json()
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.P.primary"
    }


# ---------------------------------------------------------------------------
# 16. mode filter applies (SAFE mode drops low-confidence bindings)
# ---------------------------------------------------------------------------
def test_mode_safe_drops_low_confidence_bindings() -> None:
    app, *_ = _make_app(
        terms=[_term("term.safety_stock", "Safety Stock")],
        bindings=[
            _binding(
                "term.safety_stock",
                "com.app.High.manual",
                confidence=1.0,
            ),
            _binding(
                "term.safety_stock",
                "com.app.Low.namematch",
                source=BindingSource.NAME_MATCH,
                confidence=0.85,  # < safe_min_confidence 0.9
            ),
        ],
    )
    client = TestClient(app)

    r = client.get(
        "/api/modeling/reverse_lookup",
        params={"term": "Safety Stock", "mode": "safe"},
    )
    body = r.json()
    assert {a["qualified_name"] for a in body["impact"]["affected"]} == {
        "com.app.High.manual"
    }


# ---------------------------------------------------------------------------
# Helper — SSE parser
# ---------------------------------------------------------------------------
def _parse_sse(lines) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in lines:
        line = raw if isinstance(raw, str) else raw.decode("utf-8")
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# 17. ConceptBindingStore scope_filter validation
# ---------------------------------------------------------------------------
def test_binding_store_rejects_unknown_scope_filter() -> None:
    store = InMemoryConceptBindingStore(
        [_binding("term.x", "com.y.m")]
    )
    with pytest.raises(ValueError):
        store.list_by_term("term.x", scope_filter="garbage")


def test_binding_store_returns_empty_for_unknown_term() -> None:
    store = InMemoryConceptBindingStore([])
    assert store.list_by_term("term.missing") == []


def test_audit_store_recent_is_bounded() -> None:
    store = InMemoryAuditLogStore()
    from backend.modeling.mapping import ResolutionAuditLog, ResolutionSource

    for i in range(5):
        store.append(
            ResolutionAuditLog(
                query_term=f"q{i}",
                resolved_term_fqn=None,
                resolution_source=ResolutionSource.MISS,
                confidence=0.0,
                confirmed=False,
                timestamp=_NOW,
            )
        )
    assert len(store.recent(limit=3)) == 3
    assert store.recent(limit=3)[-1].query_term == "q4"


# ---------------------------------------------------------------------------
# 회귀 (2026-04-26) — proposal-confirm 흐름이 reverse_lookup 에 반영
# concept_store.list_by_term 의 confirmed=True patch 가 빠지면 0 affected 회귀.
# ---------------------------------------------------------------------------
def test_proposal_confirm_flows_to_reverse_lookup() -> None:
    """terms_api 흐름 — propose → confirm → reverse_lookup 에서 affected 1건."""
    from datetime import datetime, timezone
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.modeling.api import reverse_lookup_api
    from backend.modeling.code_analysis.parser_protocol import EntityKinds
    from backend.modeling.mapping.concept_store import InMemoryConceptBindingStore
    from backend.modeling.mapping.mapping_models import (
        BindingScope, BindingSource, BusinessTerm, BusinessTermSource,
        ConceptBinding, ConceptBindingProposal,
    )
    from backend.modeling.query.term_resolver import (
        InMemoryEmbeddingProvider, ResolutionAuditLog, TermResolver,
    )

    ts = datetime.now(timezone.utc)
    term = BusinessTerm(
        qualified_name="term.강종코드", canonical_label="강종코드",
        aliases=["grade_cd"], domain="t",
        source=BusinessTermSource.MANUAL,
        confirmed=True, created_at=ts,
    )

    # propose-bindings 흐름 시뮬 — 일단 binding 만들어 store 에 put_proposal
    binding = ConceptBinding(
        term_fqn="term.강종코드",
        code_fqn="com.x.SteelJpo.gradeCode",
        scope=BindingScope.PRIMARY, confidence=1.0,
        source=BindingSource.NAME_MATCH,
        confirmed=False,  # PROPOSED 상태 (아직 결정 안 됨)
        created_at=ts,
    )
    proposal = ConceptBindingProposal.from_binding(
        repo_id="repo", binding=binding, proposed_at=ts,
    )
    store = InMemoryConceptBindingStore()
    store.put_proposal(proposal)

    # 결정 안 된 상태 — list_by_term 은 0
    assert store.list_by_term("term.강종코드") == []

    # 사용자가 confirm
    store.confirm(proposal.id, by="reviewer-1")

    # list_by_term — confirmed True patch 적용된 상태로 반환
    listed = store.list_by_term("term.강종코드")
    assert len(listed) == 1
    assert listed[0].confirmed is True

    # 이제 reverse_lookup_api 에 wire — 확정된 binding 으로 affected 1건이어야
    reverse_lookup_api.reset()
    resolver = TermResolver(
        terms=[term],
        embedding_provider=InMemoryEmbeddingProvider(embeddings={}, embed_fn=lambda _: []),
        llm_resolver=None,
    )

    class _NoOpAudit:
        def append(self, log: ResolutionAuditLog) -> None: pass
        def recent(self, *, limit: int) -> list: return []

    reverse_lookup_api.init(
        resolver=resolver, binding_store=store, audit_store=_NoOpAudit(),
    )
    app = FastAPI()
    app.include_router(reverse_lookup_api.router)
    client = TestClient(app)

    r = client.get("/api/modeling/reverse_lookup?term=강종코드")
    assert r.status_code == 200
    body = r.json()
    assert body["resolution"]["matched_term_fqn"] == "term.강종코드"
    impact = body.get("impact")
    assert impact is not None
    assert len(impact["affected"]) == 1
    assert impact["affected"][0]["qualified_name"] == "com.x.SteelJpo.gradeCode"
