"""P2.2 — BusinessTermRegistry tests.

repo_id 단위로 사용자 정의 BusinessTerm 보관. RuleRegistry 와 같은 패턴.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.modeling.mapping.business_term_registry import (
    BusinessTermRegistry,
    InMemoryBusinessTermRegistry,
)
from backend.modeling.mapping.mapping_models import (
    BusinessTerm,
    BusinessTermSource,
)


def _term(
    fqn: str = "term.품종코드",
    canonical: str = "품종코드",
    aliases: list[str] | None = None,
    source: BusinessTermSource = BusinessTermSource.MANUAL,
) -> BusinessTerm:
    return BusinessTerm(
        qualified_name=fqn,
        canonical_label=canonical,
        aliases=aliases or [],
        domain="slab-design",
        source=source,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
class TestProtocol:
    def test_in_memory_conforms_to_protocol(self) -> None:
        assert isinstance(InMemoryBusinessTermRegistry(), BusinessTermRegistry)


# ---------------------------------------------------------------------------
# 기본 동작
# ---------------------------------------------------------------------------
class TestBasic:
    def test_put_then_get(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        t = _term()
        reg.put("repo-a", t)
        assert reg.get("repo-a", t.qualified_name) is t

    def test_put_many(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        terms = [_term(fqn=f"term.t{i}") for i in range(3)]
        reg.put_many("repo-a", terms)
        listed = list(reg.list_by_repo("repo-a"))
        assert len(listed) == 3

    def test_idempotent_upsert(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        t1 = _term(canonical="원본")
        t2 = _term(canonical="갱신")
        reg.put("repo-a", t1)
        reg.put("repo-a", t2)
        assert reg.get("repo-a", t1.qualified_name).canonical_label == "갱신"
        assert len(list(reg.list_by_repo("repo-a"))) == 1

    def test_multi_repo_isolation(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        reg.put("a", _term(canonical="A"))
        reg.put("b", _term(canonical="B"))
        assert reg.get("a", "term.품종코드").canonical_label == "A"
        assert reg.get("b", "term.품종코드").canonical_label == "B"

    def test_clear_specific_repo(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        reg.put("a", _term())
        reg.put("b", _term(fqn="term.x"))
        reg.clear("a")
        assert list(reg.list_by_repo("a")) == []
        assert len(list(reg.list_by_repo("b"))) == 1
        assert reg.repos() == {"b"}

    def test_get_unknown_returns_none(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        assert reg.get("ghost", "term.x") is None

    def test_list_by_unknown_repo_empty(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        assert list(reg.list_by_repo("ghost")) == []


# ---------------------------------------------------------------------------
# 시나리오 1·2 시드 시뮬레이션 (사용자 답변 그대로)
# ---------------------------------------------------------------------------
class TestSlabDemoSeeds:
    def test_seed_품종코드_and_열연공장코드(self) -> None:
        reg = InMemoryBusinessTermRegistry()
        # 사용자 답변에서 받은 시드
        reg.put("slab-design-real", _term(
            fqn="term.품종코드",
            canonical="품종코드",
            aliases=["품종", "품명", "product_type", "product_name", "prod_kind"],
        ))
        reg.put("slab-design-real", _term(
            fqn="term.열연공장코드",
            canonical="열연공장코드",
            aliases=["열연", "hr_plant", "hr_cd"],
        ))
        terms = list(reg.list_by_repo("slab-design-real"))
        assert len(terms) == 2
        names = {t.canonical_label for t in terms}
        assert names == {"품종코드", "열연공장코드"}
