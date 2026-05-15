"""W78 — Hybrid search tier tests.

Tier 별 동작을 격리해서 검증:

    Tier 1: 기본 매칭 (W77 와 같음 → test_w77_*.py 에서 cover)
    Tier 2: static transliteration (이 파일)
    Tier 3: fuzzy edit-distance (이 파일)
    Tier 4: LLM assist callback (이 파일)

Tier 2 는 항상 1 패스에 통합되므로 hit 가 있어도 호출됨.
Tier 3 / 4 는 *상위 단계 0 hit 시* 에만 호출 (fallback chain).
"""
from __future__ import annotations

import pytest

from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
    TermRecord,
)
from backend.sim_v2.core.search.transliteration import (
    expand_transliteration,
    register_transliteration,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def resolver() -> KoreanTermResolver:
    """Resolver over a small synthetic corpus with 한↔영 imbalance.

    Term A 는 영문 label, alias 도 영문 only — 한국어 query 가 cross-match
    하려면 Tier 2 (transliteration) 가 반드시 필요.

    Term B 는 한국어 label, alias 도 한국어 only — 영문 query 가 cross-match
    하려면 Tier 2 의 역방향 (영 → 한) 매핑 필요.
    """
    return KoreanTermResolver([
        TermRecord(
            fqn="term.scm.edging_group",
            label="EdgingGroup",
            aliases=("EdgingGroupEntity",),
            description="Edge process grouping for slab",
            kind="entity",
            domain="scm",
        ),
        TermRecord(
            fqn="term.scm.order",
            label="주문번호",
            aliases=("주문 번호",),
            description="고객이 등록한 주문의 식별자",
            kind="value_object",
            domain="scm",
        ),
        TermRecord(
            fqn="term.common.validation_result",
            label="검증결과",
            aliases=("ValidationResult",),
            description="비즈니스 규칙 검증의 결과 데이터",
            kind="value_object",
            domain="common",
        ),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2: transliteration
# ─────────────────────────────────────────────────────────────────────────────


def test_transliteration_expand_known_korean() -> None:
    out = expand_transliteration("엣징")
    assert "엣징" in out
    assert "edging" in out


def test_transliteration_expand_known_english() -> None:
    out = expand_transliteration("edging")
    assert "edging" in out
    assert "엣징" in out


def test_transliteration_expand_unknown_returns_self() -> None:
    out = expand_transliteration("zzzqqq")
    assert out == {"zzzqqq"}


def test_transliteration_register_runtime() -> None:
    register_transliteration("주조", "casting")
    assert "casting" in expand_transliteration("주조")
    assert "주조" in expand_transliteration("casting")


def test_tier2_korean_query_finds_english_only_term(
    resolver: KoreanTermResolver,
) -> None:
    """한국어 '엣징' → 영문 EdgingGroup 도달 (Tier 2 활성)."""
    hits = resolver.resolve("엣징", use_transliteration=True)
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" in fqns


def test_tier2_disabled_fails_cross_language(
    resolver: KoreanTermResolver,
) -> None:
    """use_transliteration=False 면 한↔영 cross-match 안 됨."""
    hits = resolver.resolve("엣징", use_transliteration=False, use_fuzzy=False)
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" not in fqns


# ─────────────────────────────────────────────────────────────────────────────
# Tier 3: fuzzy edit-distance
# ─────────────────────────────────────────────────────────────────────────────


def test_tier3_fuzzy_corrects_typo(resolver: KoreanTermResolver) -> None:
    """'edgign' (typo of edging) → EdgingGroup 도달."""
    hits = resolver.resolve(
        "edgign",
        use_transliteration=False,  # Tier 2 끄고 fuzzy 만 발동시키기
        use_fuzzy=True,
    )
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" in fqns


def test_tier3_fuzzy_skipped_when_tier1_has_hit(
    resolver: KoreanTermResolver,
) -> None:
    """정확한 query 는 Tier 1 에서 hit → Tier 3 안 거침."""
    hits = resolver.resolve("EdgingGroup", use_fuzzy=True)
    assert any(h.term.fqn == "term.scm.edging_group" for h in hits)
    # 결과의 score 가 fuzzy-injected 토큰으로 인한 noise 없이 정확해야 함
    top = hits[0]
    assert top.score >= 3.0  # exact label match


def test_tier3_fuzzy_disabled(resolver: KoreanTermResolver) -> None:
    """use_fuzzy=False 면 typo 보정 안 됨."""
    hits = resolver.resolve(
        "edgign",
        use_transliteration=False,
        use_fuzzy=False,
    )
    assert hits == []


def test_tier3_fuzzy_short_token_skipped(
    resolver: KoreanTermResolver,
) -> None:
    """길이 < 3 토큰은 fuzzy false-match 가 많아서 skip."""
    # 'ab' 같은 짧은 token 은 fuzzy 처리 대상이 아님
    hits = resolver.resolve(
        "ab",
        use_transliteration=False,
        use_fuzzy=True,
    )
    assert hits == []


# ─────────────────────────────────────────────────────────────────────────────
# Tier 4: LLM assist callback
# ─────────────────────────────────────────────────────────────────────────────


def test_tier4_llm_inference_unknown_transliteration(
    resolver: KoreanTermResolver,
) -> None:
    """정적 table 에 없는 음역 '에징' → LLM 이 ["edging"] 추론."""

    def llm_assist(query: str) -> list[str]:
        # 실제 LLM 처럼 query 를 보고 음역 후보 반환
        if "에징" in query:
            return ["edging"]
        return []

    hits = resolver.resolve(
        "에징",
        use_transliteration=True,  # Tier 2 통과 (에징 매핑 없음)
        use_fuzzy=True,             # Tier 3 도 fail
        llm_assist=llm_assist,
    )
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" in fqns


def test_tier4_llm_not_called_when_upper_tier_has_hit(
    resolver: KoreanTermResolver,
) -> None:
    """상위 tier 에서 hit 가 있으면 LLM callback 호출되지 않음."""
    calls: list[str] = []

    def llm_assist(query: str) -> list[str]:
        calls.append(query)
        return ["edging"]

    # "엣징" 은 Tier 2 (static table) 에서 즉시 hit
    hits = resolver.resolve("엣징", llm_assist=llm_assist)
    assert any(h.term.fqn == "term.scm.edging_group" for h in hits)
    assert calls == []  # LLM 안 불림


def test_tier4_llm_exception_swallowed(
    resolver: KoreanTermResolver,
) -> None:
    """LLM callback 이 throw 해도 resolver 는 빈 결과만 반환 (crash X)."""

    def broken_llm(query: str) -> list[str]:
        raise RuntimeError("LLM API down")

    hits = resolver.resolve(
        "에징",
        use_transliteration=True,
        use_fuzzy=True,
        llm_assist=broken_llm,
    )
    assert hits == []  # 실패해도 crash 없이 0 hit


def test_tier4_llm_returns_non_string_filtered(
    resolver: KoreanTermResolver,
) -> None:
    """LLM 이 비-str 반환 (e.g. None, dict) 해도 안전하게 무시."""

    def odd_llm(query: str) -> list:  # type: ignore[type-arg]
        return [None, 123, {"key": "val"}, "edging"]  # type: ignore[list-item]

    hits = resolver.resolve(
        "에징",
        use_transliteration=True,
        use_fuzzy=True,
        llm_assist=odd_llm,
    )
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" in fqns
