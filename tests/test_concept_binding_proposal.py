"""P2.1 — ConceptBindingStore 보강 : 승인 큐 + repo_id keying.

`ConceptBindingProposal` wrapper (`{id, repo_id, binding, status, ...}`) +
새 store API (`put_proposal` / `get_proposal` / `list_proposals` / `confirm` /
`reject`). 기존 `list_by_term` 은 backward-compat 유지 (reverse_lookup_api 사용 중).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.mapping.concept_store import (
    ConceptBindingStore,
    InMemoryConceptBindingStore,
)
from backend.modeling.mapping.mapping_models import (
    BindingScope,
    BindingSource,
    ConceptBinding,
    ConceptBindingProposal,
    ProposalStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _b(
    term: str = "term.품종코드",
    code: str = "com.x.OrderOmJpo.productTypeCd",
    scope: BindingScope = BindingScope.PRIMARY,
    source: BindingSource = BindingSource.EMBEDDING,
    confidence: float = 0.85,
) -> ConceptBinding:
    return ConceptBinding(
        term_fqn=term,
        code_fqn=code,
        scope=scope,
        confidence=confidence,
        source=source,
        created_at=datetime.now(timezone.utc),
    )


def _p(
    repo: str = "slab-design-real",
    binding: ConceptBinding | None = None,
) -> ConceptBindingProposal:
    return ConceptBindingProposal.from_binding(
        repo_id=repo,
        binding=binding or _b(),
        proposed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# DTO — ConceptBindingProposal
# ---------------------------------------------------------------------------
class TestProposalDto:
    def test_id_is_stable_hash(self) -> None:
        b = _b()
        p1 = ConceptBindingProposal.from_binding(repo_id="r", binding=b, proposed_at=datetime.now(timezone.utc))
        p2 = ConceptBindingProposal.from_binding(repo_id="r", binding=b, proposed_at=datetime.now(timezone.utc))
        # 같은 (repo, term, code) → 같은 id (timestamp 무관)
        assert p1.id == p2.id
        assert len(p1.id) >= 8  # 의미있는 길이

    def test_id_differs_per_repo(self) -> None:
        b = _b()
        p_a = ConceptBindingProposal.from_binding(repo_id="repo-a", binding=b, proposed_at=datetime.now(timezone.utc))
        p_b = ConceptBindingProposal.from_binding(repo_id="repo-b", binding=b, proposed_at=datetime.now(timezone.utc))
        assert p_a.id != p_b.id

    def test_default_status_is_proposed(self) -> None:
        p = _p()
        assert p.status is ProposalStatus.PROPOSED

    def test_proposal_is_frozen(self) -> None:
        from pydantic import ValidationError
        p = _p()
        with pytest.raises((TypeError, AttributeError, ValidationError)):
            p.status = ProposalStatus.CONFIRMED  # type: ignore


# ---------------------------------------------------------------------------
# Store — put / get / list / confirm / reject
# ---------------------------------------------------------------------------
class TestProposalStore:
    def setup_method(self) -> None:
        self.store = InMemoryConceptBindingStore([])

    def test_put_then_get(self) -> None:
        p = _p()
        self.store.put_proposal(p)
        assert self.store.get_proposal(p.id) is not None
        assert self.store.get_proposal(p.id).id == p.id

    def test_put_idempotent_same_id(self) -> None:
        p = _p()
        self.store.put_proposal(p)
        self.store.put_proposal(p)  # 같은 id 재 put — 중복 X
        proposals = list(self.store.list_proposals(repo_id="slab-design-real"))
        assert len(proposals) == 1

    def test_list_by_repo(self) -> None:
        self.store.put_proposal(_p(repo="r1"))
        self.store.put_proposal(_p(repo="r2", binding=_b(code="com.x.A.b")))
        r1 = list(self.store.list_proposals(repo_id="r1"))
        r2 = list(self.store.list_proposals(repo_id="r2"))
        assert len(r1) == 1 and len(r2) == 1
        assert r1[0].repo_id == "r1"

    def test_list_by_status(self) -> None:
        p_proposed = _p(binding=_b(code="com.x.A.a"))
        p_confirmed = _p(binding=_b(code="com.x.A.b"))
        self.store.put_proposal(p_proposed)
        self.store.put_proposal(p_confirmed)
        self.store.confirm(p_confirmed.id, by="user")

        proposed_only = list(self.store.list_proposals(
            repo_id="slab-design-real", status=ProposalStatus.PROPOSED
        ))
        confirmed_only = list(self.store.list_proposals(
            repo_id="slab-design-real", status=ProposalStatus.CONFIRMED
        ))
        assert len(proposed_only) == 1 and proposed_only[0].id == p_proposed.id
        assert len(confirmed_only) == 1 and confirmed_only[0].id == p_confirmed.id

    def test_confirm_changes_status_and_records_decider(self) -> None:
        p = _p()
        self.store.put_proposal(p)
        confirmed = self.store.confirm(p.id, by="alice")
        assert confirmed.status is ProposalStatus.CONFIRMED
        assert confirmed.decided_by == "alice"
        assert confirmed.decided_at is not None

    def test_reject_changes_status(self) -> None:
        p = _p()
        self.store.put_proposal(p)
        rejected = self.store.reject(p.id, by="bob")
        assert rejected.status is ProposalStatus.REJECTED
        assert rejected.decided_by == "bob"

    def test_confirm_unknown_id_raises(self) -> None:
        with pytest.raises(KeyError):
            self.store.confirm("missing", by=None)

    def test_reject_unknown_id_raises(self) -> None:
        with pytest.raises(KeyError):
            self.store.reject("missing", by=None)


# ---------------------------------------------------------------------------
# Backward compat — list_by_term still works
# ---------------------------------------------------------------------------
class TestBackwardCompat:
    def test_list_by_term_returns_confirmed_bindings_only(self) -> None:
        # reverse_lookup_api 가 의존하는 기존 동작 — confirmed 만 노출.
        store = InMemoryConceptBindingStore([])
        b1 = _b(term="t.x", code="com.x.A.f1")
        b2 = _b(term="t.x", code="com.x.A.f2")
        p1 = ConceptBindingProposal.from_binding(repo_id="r", binding=b1, proposed_at=datetime.now(timezone.utc))
        p2 = ConceptBindingProposal.from_binding(repo_id="r", binding=b2, proposed_at=datetime.now(timezone.utc))
        store.put_proposal(p1)
        store.put_proposal(p2)
        store.confirm(p1.id, by="u")

        # list_by_term 은 confirmed 만 반환 — proposed 는 제외.
        bindings = store.list_by_term("t.x")
        assert len(bindings) == 1
        assert bindings[0].code_fqn == "com.x.A.f1"

    def test_legacy_constructor_still_seeds(self) -> None:
        # 기존 InMemoryConceptBindingStore(bindings=...) 생성 패턴 — confirmed 로 시드.
        b = _b(term="t.x", code="com.x.A.f")
        store = InMemoryConceptBindingStore([b])
        bindings = store.list_by_term("t.x")
        assert len(bindings) == 1


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_in_memory_conforms_to_protocol(self) -> None:
        store = InMemoryConceptBindingStore([])
        assert isinstance(store, ConceptBindingStore)


# ---------------------------------------------------------------------------
# 회귀 (2026-04-26) — list_by_term 의 confirmed patch
# ---------------------------------------------------------------------------
class TestConfirmedPatchRegression:
    """`confirm()` 은 proposal.status 만 갱신, 내부 binding.confirmed 는 별도.
    `list_by_term` 이 confirmed=True 로 patch 해서 반환해야 reverse_lookup 의
    confirmed-only 게이트가 차단하지 않음.
    """

    def test_list_by_term_patches_confirmed_after_confirm(self):
        from datetime import datetime, timezone
        from backend.modeling.mapping.concept_store import (
            InMemoryConceptBindingStore,
        )
        from backend.modeling.mapping.mapping_models import (
            BindingScope, BindingSource, ConceptBinding, ConceptBindingProposal,
        )
        ts = datetime.now(timezone.utc)
        store = InMemoryConceptBindingStore()
        binding = ConceptBinding(
            term_fqn="term.x", code_fqn="com.x.A.f",
            scope=BindingScope.PRIMARY, confidence=1.0,
            source=BindingSource.NAME_MATCH,
            confirmed=False,  # 일부러 False 시작
            created_at=ts,
        )
        proposal = ConceptBindingProposal.from_binding(
            repo_id="repo", binding=binding, proposed_at=ts,
        )
        store.put_proposal(proposal)
        store.confirm(proposal.id, by="user")

        results = store.list_by_term("term.x")
        assert len(results) == 1
        # 핵심 회귀 체크: confirmed True 로 patch 됐는지
        assert results[0].confirmed is True
        assert results[0].confirmed_by == "user"

    def test_unconfirmed_proposal_not_returned(self):
        from datetime import datetime, timezone
        from backend.modeling.mapping.concept_store import (
            InMemoryConceptBindingStore,
        )
        from backend.modeling.mapping.mapping_models import (
            BindingScope, BindingSource, ConceptBinding, ConceptBindingProposal,
        )
        ts = datetime.now(timezone.utc)
        store = InMemoryConceptBindingStore()
        binding = ConceptBinding(
            term_fqn="term.x", code_fqn="com.x.A.f",
            scope=BindingScope.PRIMARY, confidence=1.0,
            source=BindingSource.NAME_MATCH, created_at=ts,
        )
        proposal = ConceptBindingProposal.from_binding(
            repo_id="repo", binding=binding, proposed_at=ts,
        )
        store.put_proposal(proposal)
        # confirm 안 함
        results = store.list_by_term("term.x")
        # CONFIRMED 가 아니라서 list_by_term 에 안 나옴
        assert results == []
