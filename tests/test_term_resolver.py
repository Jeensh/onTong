"""OD-11-C3 TDD — Round 2 Term Resolver 4-stage chain.

`backend/modeling/query/term_resolver.py` 의 행동 검증:

- Stage 1 : exact (canonical_label) — O(1) 룩업
- Stage 2 : alias — O(1) 룩업
- Stage 3 : embedding top-K (기본 3) + cutoff (기본 0.78, Q2 B)
- Stage 4 : LLM fallback + cutoff (기본 0.6, Q2 B)
- Miss : 4단 모두 미스 → `ResolutionSource.MISS`
- 짧은 회로 : exact/alias 히트 시 embedding/LLM 호출 금지
- 승인 체계 : exact/alias 만 `confirmed=True`. embedding/LLM 은 `False`.
- `ResolutionAuditLog` : 매 호출마다 생성, 원본 query_term 보존.

Spec: `toClaude/modeling/round2-concept-bridge.html` rev.2 §6, §7, §8.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.modeling.mapping import (
    BusinessTerm,
    BusinessTermSource,
    ResolutionAuditLog,
    ResolutionSource,
)
from backend.modeling.query.term_resolver import (
    Candidate,
    EmbeddingProvider,
    InMemoryEmbeddingProvider,
    LLMProposal,
    LLMResolver,
    ResolutionCutoffs,
    ResolutionResult,
    SimHit,
    TermResolver,
)

_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _term(
    qn: str,
    label: str,
    aliases: tuple[str, ...] = (),
    *,
    embedding: list[float] | None = None,
    description: str = "",
) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=qn,
        canonical_label=label,
        aliases=list(aliases),
        domain="test",
        description=description,
        embedding=embedding,
        source=BusinessTermSource.MANUAL,
        confirmed=True,
        created_at=_NOW,
    )


_SAFETY = _term(
    "inventory.safety_stock",
    "안전재고",
    aliases=("Safety Stock", "SS", "안전 재고"),
)
_ORDER = _term("order.placement", "주문 생성", aliases=("place order",))


class _FakeEmb:
    """Deterministic embedding stub. Returns pre-configured hits per query."""

    def __init__(self, hits_by_query: dict[str, list[SimHit]] | None = None) -> None:
        self._hits = hits_by_query or {}
        self.calls: list[tuple[str, int]] = []

    def search_similar(self, query: str, top_k: int) -> list[SimHit]:
        self.calls.append((query, top_k))
        return list(self._hits.get(query, []))[:top_k]

    def index(self, term: BusinessTerm) -> None:  # no-op
        return None


class _FakeLLM:
    def __init__(self, proposal: LLMProposal | None) -> None:
        self._proposal = proposal
        self.calls: list[str] = []

    def propose(
        self, query: str, available_terms: list[BusinessTerm]
    ) -> LLMProposal | None:
        self.calls.append(query)
        return self._proposal


# ---------------------------------------------------------------------------
# ResolutionCutoffs
# ---------------------------------------------------------------------------
def test_cutoffs_defaults_match_spec_q2b() -> None:
    c = ResolutionCutoffs()
    assert c.embedding == 0.78
    assert c.llm == 0.6
    assert c.top_k == 3


def test_cutoffs_range_validated() -> None:
    with pytest.raises(ValidationError):
        ResolutionCutoffs(embedding=1.1)
    with pytest.raises(ValidationError):
        ResolutionCutoffs(llm=-0.1)
    with pytest.raises(ValidationError):
        ResolutionCutoffs(top_k=0)


# ---------------------------------------------------------------------------
# Stage 1 : exact (canonical_label)
# ---------------------------------------------------------------------------
def test_exact_match_canonical_label() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("안전재고")
    assert result.matched_term_fqn == "inventory.safety_stock"
    assert result.resolution_source is ResolutionSource.EXACT
    assert result.confidence == 1.0
    assert result.confirmed is True
    assert result.candidates == []


def test_exact_match_case_insensitive() -> None:
    r = TermResolver(terms=[_ORDER], clock=lambda: _NOW)
    result = r.resolve("주문 생성")
    assert result.resolution_source is ResolutionSource.EXACT


def test_exact_normalizes_whitespace() -> None:
    """'주문 생성' (canonical, with space) == '주문생성' (query, no space)."""
    r = TermResolver(terms=[_ORDER], clock=lambda: _NOW)
    result = r.resolve("주문생성")
    assert result.matched_term_fqn == "order.placement"
    assert result.resolution_source is ResolutionSource.EXACT


def test_exact_wins_over_embedding_without_calling_provider() -> None:
    spy = _FakeEmb()
    r = TermResolver(terms=[_SAFETY], embedding_provider=spy, clock=lambda: _NOW)
    r.resolve("안전재고")
    assert spy.calls == []  # short-circuit


# ---------------------------------------------------------------------------
# Stage 2 : alias
# ---------------------------------------------------------------------------
def test_alias_match() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("SS")
    assert result.matched_term_fqn == "inventory.safety_stock"
    assert result.resolution_source is ResolutionSource.ALIAS
    assert result.confidence == 1.0
    assert result.confirmed is True


def test_alias_match_case_insensitive() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("safety stock")
    assert result.resolution_source is ResolutionSource.ALIAS
    assert result.matched_term_fqn == "inventory.safety_stock"


def test_alias_wins_over_embedding_without_calling_provider() -> None:
    spy = _FakeEmb()
    r = TermResolver(terms=[_SAFETY], embedding_provider=spy, clock=lambda: _NOW)
    r.resolve("SS")
    assert spy.calls == []


def test_canonical_wins_over_alias_when_normalized_collides() -> None:
    """canonical_label 가 다른 term 의 alias 와 normalize 후 충돌 시 canonical 우선."""
    t1 = _term("t1", "재고")
    t2 = _term("t2", "stock", aliases=("재고",))
    r = TermResolver(terms=[t1, t2], clock=lambda: _NOW)
    result = r.resolve("재고")
    assert result.matched_term_fqn == "t1"
    assert result.resolution_source is ResolutionSource.EXACT


# ---------------------------------------------------------------------------
# Stage 3 : embedding
# ---------------------------------------------------------------------------
def test_embedding_hit_above_cutoff() -> None:
    stub = _FakeEmb(
        hits_by_query={
            "재고 부족 경고": [
                SimHit(term_fqn="inventory.safety_stock", similarity=0.82),
                SimHit(term_fqn="inventory.stock_alert", similarity=0.79),
            ]
        }
    )
    alert = _term("inventory.stock_alert", "재고경고")
    r = TermResolver(
        terms=[_SAFETY, alert], embedding_provider=stub, clock=lambda: _NOW
    )
    result = r.resolve("재고 부족 경고")
    assert result.resolution_source is ResolutionSource.EMBEDDING
    assert result.matched_term_fqn == "inventory.safety_stock"
    assert result.confidence == pytest.approx(0.82)
    assert result.confirmed is False  # 임베딩 매칭은 사람 승인 필요
    assert [c.term_fqn for c in result.candidates] == [
        "inventory.safety_stock",
        "inventory.stock_alert",
    ]
    assert all(c.source is ResolutionSource.EMBEDDING for c in result.candidates)


def test_embedding_cutoff_boundary_inclusive() -> None:
    stub = _FakeEmb(
        hits_by_query={"zzz": [SimHit(term_fqn="t1", similarity=0.78)]}
    )
    t1 = _term("t1", "abc")
    r = TermResolver(
        terms=[t1],
        embedding_provider=stub,
        cutoffs=ResolutionCutoffs(embedding=0.78),
        clock=lambda: _NOW,
    )
    result = r.resolve("zzz")
    assert result.resolution_source is ResolutionSource.EMBEDDING
    assert result.confidence == pytest.approx(0.78)


def test_embedding_below_cutoff_falls_through_to_miss_without_llm() -> None:
    stub = _FakeEmb(
        hits_by_query={"zzz": [SimHit(term_fqn="t1", similarity=0.70)]}
    )
    t1 = _term("t1", "abc")
    r = TermResolver(terms=[t1], embedding_provider=stub, clock=lambda: _NOW)
    result = r.resolve("zzz")
    assert result.resolution_source is ResolutionSource.MISS
    # candidates 는 참고용으로 보존
    assert len(result.candidates) == 1
    assert result.candidates[0].confidence == pytest.approx(0.70)


def test_embedding_empty_hits_returns_miss_without_llm() -> None:
    stub = _FakeEmb()  # 모든 쿼리 → []
    r = TermResolver(terms=[_SAFETY], embedding_provider=stub, clock=lambda: _NOW)
    result = r.resolve("완전 생소한 표현")
    assert result.resolution_source is ResolutionSource.MISS
    assert result.candidates == []


def test_embedding_top_k_passed_from_cutoffs() -> None:
    stub = _FakeEmb(hits_by_query={"q": [SimHit(term_fqn="t1", similarity=0.5)]})
    t1 = _term("t1", "abc")
    r = TermResolver(
        terms=[t1],
        embedding_provider=stub,
        cutoffs=ResolutionCutoffs(top_k=5),
        clock=lambda: _NOW,
    )
    r.resolve("q")
    assert stub.calls[-1] == ("q", 5)


# ---------------------------------------------------------------------------
# Stage 4 : LLM fallback
# ---------------------------------------------------------------------------
def test_llm_fallback_hit_above_cutoff() -> None:
    stub_emb = _FakeEmb()  # 모든 쿼리 미스
    stub_llm = _FakeLLM(
        LLMProposal(
            term_fqn="inventory.safety_stock",
            confidence=0.75,
            reasoning="semantic overlap",
        )
    )
    r = TermResolver(
        terms=[_SAFETY],
        embedding_provider=stub_emb,
        llm_resolver=stub_llm,
        clock=lambda: _NOW,
    )
    result = r.resolve("슬랩 폭 조정")
    assert result.resolution_source is ResolutionSource.LLM
    assert result.matched_term_fqn == "inventory.safety_stock"
    assert result.confidence == pytest.approx(0.75)
    assert result.confirmed is False


def test_llm_fallback_below_cutoff_is_miss() -> None:
    stub_llm = _FakeLLM(LLMProposal(term_fqn="inventory.safety_stock", confidence=0.4))
    r = TermResolver(
        terms=[_SAFETY], llm_resolver=stub_llm, clock=lambda: _NOW
    )
    result = r.resolve("unknown")
    assert result.resolution_source is ResolutionSource.MISS


def test_llm_returns_none_is_miss() -> None:
    stub_llm = _FakeLLM(None)
    r = TermResolver(
        terms=[_SAFETY], llm_resolver=stub_llm, clock=lambda: _NOW
    )
    result = r.resolve("unknown")
    assert result.resolution_source is ResolutionSource.MISS


def test_llm_cutoff_boundary_inclusive() -> None:
    stub_llm = _FakeLLM(LLMProposal(term_fqn="inventory.safety_stock", confidence=0.6))
    r = TermResolver(
        terms=[_SAFETY],
        llm_resolver=stub_llm,
        cutoffs=ResolutionCutoffs(llm=0.6),
        clock=lambda: _NOW,
    )
    result = r.resolve("unknown")
    assert result.resolution_source is ResolutionSource.LLM


def test_llm_skipped_when_embedding_hits() -> None:
    stub_emb = _FakeEmb(hits_by_query={"q": [SimHit(term_fqn="inventory.safety_stock", similarity=0.9)]})
    stub_llm = _FakeLLM(LLMProposal(term_fqn="inventory.safety_stock", confidence=0.99))
    r = TermResolver(
        terms=[_SAFETY],
        embedding_provider=stub_emb,
        llm_resolver=stub_llm,
        clock=lambda: _NOW,
    )
    r.resolve("q")
    assert stub_llm.calls == []


def test_llm_proposal_with_unknown_term_fqn_is_miss() -> None:
    """LLM 이 존재하지 않는 term 을 제안하면 받아들이지 않고 MISS."""
    stub_llm = _FakeLLM(LLMProposal(term_fqn="no.such.term", confidence=0.9))
    r = TermResolver(
        terms=[_SAFETY], llm_resolver=stub_llm, clock=lambda: _NOW
    )
    result = r.resolve("unknown")
    assert result.resolution_source is ResolutionSource.MISS


# ---------------------------------------------------------------------------
# No providers
# ---------------------------------------------------------------------------
def test_no_providers_configured_falls_through_to_miss() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("완전 모르는 용어")
    assert result.resolution_source is ResolutionSource.MISS
    assert result.matched_term_fqn is None
    assert result.confidence == 0.0
    assert result.candidates == []


def test_empty_terms_list_miss_on_any_query() -> None:
    r = TermResolver(terms=[], clock=lambda: _NOW)
    result = r.resolve("안전재고")
    assert result.resolution_source is ResolutionSource.MISS


# ---------------------------------------------------------------------------
# ResolutionAuditLog
# ---------------------------------------------------------------------------
def test_audit_log_captured_on_hit() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("SS")
    assert isinstance(result.audit_log, ResolutionAuditLog)
    assert result.audit_log.query_term == "SS"
    assert result.audit_log.resolved_term_fqn == "inventory.safety_stock"
    assert result.audit_log.resolution_source is ResolutionSource.ALIAS
    assert result.audit_log.confidence == 1.0
    assert result.audit_log.confirmed is True
    assert result.audit_log.timestamp == _NOW


def test_audit_log_captured_on_miss() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("잘 모르겠음")
    assert result.audit_log.resolved_term_fqn is None
    assert result.audit_log.resolution_source is ResolutionSource.MISS
    assert result.audit_log.confirmed is False


def test_audit_log_preserves_original_query_not_normalized() -> None:
    r = TermResolver(terms=[_SAFETY], clock=lambda: _NOW)
    result = r.resolve("  안전 재고  ")
    assert result.audit_log.query_term == "  안전 재고  "
    assert result.audit_log.resolved_term_fqn == "inventory.safety_stock"


# ---------------------------------------------------------------------------
# InMemoryEmbeddingProvider
# ---------------------------------------------------------------------------
def test_in_memory_provider_cosine_identical_vectors() -> None:
    p = InMemoryEmbeddingProvider(
        embeddings={"a": [1.0, 0.0, 0.0]},
        embed_fn=lambda s: [1.0, 0.0, 0.0] if s == "x" else [0.0, 1.0, 0.0],
    )
    hits = p.search_similar("x", top_k=1)
    assert hits[0].term_fqn == "a"
    assert hits[0].similarity == pytest.approx(1.0)


def test_in_memory_provider_cosine_orthogonal() -> None:
    p = InMemoryEmbeddingProvider(
        embeddings={"a": [1.0, 0.0]},
        embed_fn=lambda s: [0.0, 1.0],
    )
    hits = p.search_similar("y", top_k=1)
    assert hits[0].similarity == pytest.approx(0.0)


def test_in_memory_provider_top_k_sorted_desc() -> None:
    p = InMemoryEmbeddingProvider(
        embeddings={"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [0.7, 0.7]},
        embed_fn=lambda s: [1.0, 0.0],
    )
    hits = p.search_similar("q", top_k=3)
    assert [h.term_fqn for h in hits] == ["a", "c", "b"]
    sims = [h.similarity for h in hits]
    assert sims == sorted(sims, reverse=True)


def test_in_memory_provider_respects_top_k() -> None:
    p = InMemoryEmbeddingProvider(
        embeddings={"a": [1.0, 0.0], "b": [0.9, 0.4], "c": [0.7, 0.7]},
        embed_fn=lambda s: [1.0, 0.0],
    )
    assert len(p.search_similar("q", top_k=2)) == 2


def test_in_memory_provider_empty_returns_empty() -> None:
    p = InMemoryEmbeddingProvider(embeddings={}, embed_fn=lambda s: [1.0, 0.0])
    assert p.search_similar("q", top_k=3) == []


def test_in_memory_provider_index_adds_from_term_embedding() -> None:
    p = InMemoryEmbeddingProvider(
        embeddings={}, embed_fn=lambda s: [1.0, 0.0]
    )
    t = _term("t", "abc", embedding=[1.0, 0.0])
    p.index(t)
    hits = p.search_similar("q", top_k=1)
    assert hits[0].term_fqn == "t"


def test_in_memory_provider_index_computes_when_embedding_missing() -> None:
    """BusinessTerm.embedding 이 None 이면 embed_fn(canonical_label + description) 로 계산."""
    captured: list[str] = []

    def _embed(text: str) -> list[float]:
        captured.append(text)
        return [1.0, 0.0]

    p = InMemoryEmbeddingProvider(embeddings={}, embed_fn=_embed)
    t = _term("t", "안전재고", description="재고 하한선", embedding=None)
    p.index(t)
    # query 측 호출 전에 index 쪽 호출 기록
    assert any("안전재고" in c for c in captured)
    assert any("재고 하한선" in c for c in captured)


def test_in_memory_provider_zero_vector_returns_zero_similarity() -> None:
    """영벡터는 cosine 0 (ZeroDivision 방어)."""
    p = InMemoryEmbeddingProvider(
        embeddings={"a": [0.0, 0.0]},
        embed_fn=lambda s: [1.0, 0.0],
    )
    hits = p.search_similar("q", top_k=1)
    assert hits[0].similarity == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Integration — full chain with InMemoryEmbeddingProvider
# ---------------------------------------------------------------------------
def test_integration_full_chain_exact_alias_embedding_miss() -> None:
    safety = _term(
        "inventory.safety_stock",
        "안전재고",
        aliases=("Safety Stock", "SS"),
        embedding=[1.0, 0.0, 0.0],
    )
    stock_alert = _term(
        "inventory.stock_alert",
        "재고경고",
        embedding=[0.9, 0.4, 0.0],
    )

    def _embed(text: str) -> list[float]:
        table = {
            "안전재고": [1.0, 0.0, 0.0],
            "재고 낮음": [0.9, 0.4, 0.0],  # ~1.0 sim vs stock_alert (normalize)
            "unrelated": [0.0, 0.0, 1.0],
        }
        return table.get(text, [0.0, 0.0, 0.0])

    provider = InMemoryEmbeddingProvider(
        embeddings={
            "inventory.safety_stock": safety.embedding,  # type: ignore[arg-type]
            "inventory.stock_alert": stock_alert.embedding,  # type: ignore[arg-type]
        },
        embed_fn=_embed,
    )
    r = TermResolver(
        terms=[safety, stock_alert],
        embedding_provider=provider,
        clock=lambda: _NOW,
    )

    assert r.resolve("안전재고").resolution_source is ResolutionSource.EXACT
    assert r.resolve("SS").resolution_source is ResolutionSource.ALIAS

    emb_result = r.resolve("재고 낮음")
    assert emb_result.resolution_source is ResolutionSource.EMBEDDING
    assert emb_result.matched_term_fqn == "inventory.stock_alert"

    miss_result = r.resolve("unrelated")
    assert miss_result.resolution_source is ResolutionSource.MISS
