"""UC41 — Korean term search demo tests."""
from __future__ import annotations

import pytest

from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc41_korean_term_search.run import (
    TARGET_REPO,
    UC41Report,
    main,
    run_korean_search_demo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc41_korean_term_search import run as r
    monkeypatch.setattr(r, "open_readonly_session", lambda *a, **kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


@requires_production_db
def test_v2_korean_search_high_hit_rate():
    """Section 3 §2.4 의 실패 케이스 close 검증.
    10 query 중 최소 8개가 ≥1 hit 도달 (≥80%).
    "단중" 은 현재 v2 DB 에 해당 term 없음 → 0 hit 정답.
    """
    s = open_readonly_session()
    try:
        r = run_korean_search_demo(s)
        assert isinstance(r, UC41Report)
        with_hit = sum(1 for q in r.queries if q.hit_count > 0)
        assert with_hit >= 8
    finally:
        s.close()


@requires_production_db
def test_v2_edging_korean_to_alias_match():
    """'엣징' (한국어) → 'EdgingGroupEntity' / 'edgingGroupCd' (영문 alias)
    cross-match. 보고서가 명시한 *바로 그* 실패 케이스 close."""
    s = open_readonly_session()
    try:
        r = run_korean_search_demo(s)
        edging = next(q for q in r.queries if q.query == "엣징")
        assert edging.hit_count >= 1
        fqns = {h.term.fqn for h in edging.hits}
        assert "term.scm.shared.edging_group_cd" in fqns
    finally:
        s.close()


@requires_production_db
def test_v2_english_query_finds_korean_label():
    """역방향: 영문 'ValidationResult' → 한국어 label '검증결과' term 도달."""
    s = open_readonly_session()
    try:
        r = run_korean_search_demo(s)
        vr = next(q for q in r.queries if q.query == "ValidationResult")
        assert vr.hit_count >= 1
        top = vr.hits[0]
        assert top.term.fqn == "term.scm.validation_result"
        assert top.term.label == "검증결과"
    finally:
        s.close()


@requires_production_db
def test_v2_case_insensitive_english():
    """'EDGING' / 'edging' 모두 같은 top hit."""
    s = open_readonly_session()
    try:
        r = run_korean_search_demo(s)
        upper = next(q for q in r.queries if q.query == "EDGING")
        lower = next(q for q in r.queries if q.query == "edging")
        assert {h.term.fqn for h in upper.hits} == {h.term.fqn for h in lower.hits}
    finally:
        s.close()


def test_target_repo_is_v2():
    assert TARGET_REPO == "slab-design-real-v2"
