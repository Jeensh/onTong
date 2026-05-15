"""W77 — Korean term resolver tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.search.korean_term_resolver import (
    KoreanTermResolver,
    TermRecord,
    tokenize,
)


# ─────────────────────────────────────────────────────────────────────────────
# Tokenizer
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("input_str,expected", [
    ("EdgingGroupEntity",      ["edging", "group", "entity"]),
    ("term.scm.edging_group",  ["term", "scm", "edging", "group"]),
    ("HR최대중량",              ["hr", "최대중량"]),
    ("실수율표준",              ["실수율표준"]),
    ("엣징 사양 룩업 룰",        ["엣징", "사양", "룩업", "룰"]),
    ("",                       []),
    ("SDOrderPK",              ["sd", "order", "pk"]),
    ("camelCaseWord99",        ["camel", "case", "word", "99"]),
])
def test_tokenize(input_str, expected):
    assert tokenize(input_str) == expected


def test_tokenize_lowercases_ascii_only():
    """Hangul preserved as-is, latin lowercased."""
    toks = tokenize("Edging엣징")
    assert "edging" in toks
    assert "엣징" in toks


# ─────────────────────────────────────────────────────────────────────────────
# Resolver — basic matching
# ─────────────────────────────────────────────────────────────────────────────


def _term(fqn, label, aliases=(), description="", kind="composite",
          domain="scm"):
    return TermRecord(fqn=fqn, label=label, aliases=tuple(aliases),
                      description=description, kind=kind, domain=domain)


@pytest.fixture
def resolver():
    return KoreanTermResolver([
        _term("term.scm.edging_group", "EDGING그룹",
              aliases=("EdgingGroupEntity",)),
        _term("term.scm.shared.edging_group_cd", "엣징그룹코드",
              aliases=("엣징그룹코드", "edgingGroupCd")),
        _term("term.scm.product.productivity_std", "실수율표준",
              aliases=("SdProductivityStdEntity",),
              description="실수율 표준 - cumulativeProductivity 계산 baseline"),
        _term("term.scm.error_code", "에러코드",
              aliases=("SdErrorCode",)),
        _term("term.scm.validation_result", "검증결과",
              aliases=("ValidationResult",)),
        _term("term.scm.product.unit_weight", "주문단중",
              aliases=("UnitWeight",),
              description="주문단중 = 슬랩 한 본의 weight"),
    ])


def test_korean_query_finds_via_label(resolver):
    """'엣징' 검색 시 label 에 '엣징' substring 이 있는 term 매칭.
    EDGING그룹 label 의 영문 'EDGING' 은 한글 '엣징' 과는 다른 표기이므로
    label 자체로는 매칭 안 됨 (별도 한↔영 매핑 table 필요)."""
    hits = resolver.resolve("엣징")
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.shared.edging_group_cd" in fqns


def test_korean_query_finds_via_alias(resolver):
    """'엣징' 검색이 한국어 label 의 term 까지 도달 — Section 3 보고서의 실패 케이스 close."""
    hits = resolver.resolve("엣징")
    assert len(hits) >= 1
    # 가장 점수 높은 hit 는 한국어 label 이 정확히 매칭되는 것 (엣징그룹코드)
    assert hits[0].term.fqn == "term.scm.shared.edging_group_cd"


def test_english_query_finds_via_alias(resolver):
    """영문 'edging' → 같은 term 의 alias 매칭."""
    hits = resolver.resolve("edging")
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.edging_group" in fqns


def test_korean_compound_word_prefix(resolver):
    """'단중' → '주문단중' substring 매칭."""
    hits = resolver.resolve("단중")
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.product.unit_weight" in fqns


def test_korean_word_in_description(resolver):
    """description 에만 있는 토큰도 hit."""
    hits = resolver.resolve("실수율")
    fqns = {h.term.fqn for h in hits}
    assert "term.scm.product.productivity_std" in fqns


def test_multiple_keyword_query(resolver):
    """'엣징 사양' 다 토큰 쪼개기 + 각각 매칭."""
    hits = resolver.resolve("엣징 사양")
    assert len(hits) >= 1


def test_no_match_returns_empty(resolver):
    hits = resolver.resolve("zzz존재안하는단어zzz")
    assert hits == []


def test_empty_query_returns_empty(resolver):
    assert resolver.resolve("") == []
    assert resolver.resolve("   ") == []


def test_matched_tokens_surfaced(resolver):
    hits = resolver.resolve("엣징")
    assert hits
    assert "엣징" in hits[0].matched_tokens


def test_matched_fields_surfaced(resolver):
    hits = resolver.resolve("ValidationResult")
    # 영문 alias 매칭 → 'aliases' field 가 matched_fields 에 있어야
    assert any("aliases" in h.matched_fields for h in hits)


def test_top_n_caps_results(resolver):
    hits = resolver.resolve("엣징", top_n=1)
    assert len(hits) == 1


def test_min_score_filters_weak_hits(resolver):
    """description 의 일부 단어만 매칭되는 약한 hit 는 min_score 로 제외 가능."""
    weak = resolver.resolve("baseline")  # productivity_std 의 description 일부
    if weak:
        assert all(h.score >= 0.5 for h in weak)
    high_threshold = resolver.resolve("baseline", min_score=10.0)
    assert high_threshold == []


def test_score_ordering(resolver):
    """label 정확 매칭이 description 매칭보다 높은 점수."""
    hits = resolver.resolve("검증결과")
    assert hits[0].term.fqn == "term.scm.validation_result"


def test_case_insensitive_english(resolver):
    """'EDGING' / 'edging' / 'Edging' 모두 같은 결과."""
    h1 = {h.term.fqn for h in resolver.resolve("EDGING")}
    h2 = {h.term.fqn for h in resolver.resolve("edging")}
    h3 = {h.term.fqn for h in resolver.resolve("Edging")}
    assert h1 == h2 == h3


# ─────────────────────────────────────────────────────────────────────────────
# from_session — SQL 입력
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_with_terms():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, label TEXT, aliases_json TEXT,
                description TEXT, kind TEXT, domain TEXT, repo_id TEXT
            )
        """))
        sample = [
            {"fqn": "term.scm.edging", "label": "엣징그룹",
             "aliases_json": '["EdgingGroupEntity"]', "description": "엣징 그룹",
             "kind": "composite", "domain": "scm", "repo_id": "v2"},
            {"fqn": "term.scm.unit", "label": "주문단중",
             "aliases_json": '["UnitWeight"]', "description": "단중",
             "kind": "composite", "domain": "scm", "repo_id": "v2"},
            {"fqn": "term.banking.tx", "label": "거래",
             "aliases_json": '["Transaction"]', "description": "은행 거래",
             "kind": "composite", "domain": "banking", "repo_id": "other"},
        ]
        for r in sample:
            conn.execute(text(
                "INSERT INTO business_terms"
                "(fqn, label, aliases_json, description, kind, domain, repo_id) "
                "VALUES (:fqn, :label, :aliases_json, :description, :kind, :domain, :repo_id)"
            ), r)
    yield engine
    engine.dispose()


def test_from_session_loads_only_target_repo(db_with_terms):
    with Session(db_with_terms) as s:
        r = KoreanTermResolver.from_session(s, "v2")
    assert len(r) == 2


def test_from_session_resolves_korean(db_with_terms):
    with Session(db_with_terms) as s:
        r = KoreanTermResolver.from_session(s, "v2")
    hits = r.resolve("엣징")
    assert hits and hits[0].term.fqn == "term.scm.edging"


def test_from_session_handles_empty_aliases_json(db_with_terms):
    # aliases_json 이 '[]' 인 row 도 정상 처리
    with db_with_terms.begin() as conn:
        conn.execute(text(
            "INSERT INTO business_terms"
            "(fqn, label, aliases_json, description, kind, domain, repo_id) "
            "VALUES ('term.x.no_alias', '별칭없음', '[]', '', 'composite', 'x', 'v2')"
        ))
    with Session(db_with_terms) as s:
        r = KoreanTermResolver.from_session(s, "v2")
    hits = r.resolve("별칭없음")
    assert hits and hits[0].term.fqn == "term.x.no_alias"


def test_from_session_handles_bad_json(db_with_terms):
    """aliases_json 이 깨진 경우 → 빈 aliases 로 처리, crash 안 함."""
    with db_with_terms.begin() as conn:
        conn.execute(text(
            "INSERT INTO business_terms"
            "(fqn, label, aliases_json, description, kind, domain, repo_id) "
            "VALUES ('term.x.bad', '깨진별칭', '{not json}', '', 'composite', 'x', 'v2')"
        ))
    with Session(db_with_terms) as s:
        r = KoreanTermResolver.from_session(s, "v2")
    # v2 repo 의 3 row (sample 2 + bad 1) 모두 load 됨
    assert len(r) == 3
