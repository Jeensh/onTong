"""Phase 14E — 한·영 alias gap (cross-lingual term expansion).

페르소나 검증 (시니어) 발견:
  - "두께" 입력 → SdOrderValidator (한국어 "검증" 매칭) top-1
  - SdThicknessAction (영문 fqn `thickness`) 는 매칭 실패
  - silent wrong target 가 (Phase 13c 가 verdict 로는 surface 하지만) 본질 미해결

해결책: `business_terms.aliases_json` 으로 양방향 lookup:
  - "두께" → term `term.scm.thickness` + aliases `["thickness", ...]` → search 에 추가
  - "thickness" → 같은 term → aliases `["두께", ...]` → search 에 추가
  - declared_on_term 매칭 후보들에 추가 ranking boost
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase14e.db"
    monkeypatch.setenv("ONTONG_DB_PATH", str(db_path))
    db_mod.reset_engine_for_tests()

    from backend.modeling.code_layer import orm as _code_orm  # noqa: F401
    from backend.modeling.domain_layer import orm as _domain_orm  # noqa: F401
    from backend.modeling.mapping_layer import orm as _mapping_orm  # noqa: F401
    from backend.modeling.view_layer import orm as _view_orm  # noqa: F401
    from backend.application.authoring import orm as _authoring_orm  # noqa: F401
    from backend.section3.agents.multiturn import orm as _multiturn_orm  # noqa: F401

    db_mod.bootstrap_database()
    yield db_path
    db_mod.reset_engine_for_tests()


def _seed_thickness_term(repo_id: str = "r1") -> None:
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn="term.scm.thickness",
            label="두께",
            aliases_json='["thickness", "Thickness", "thk", "두께값"]',
            kind="concept",
            repo_id=repo_id,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (1) _expand_search_terms — 한·영 양방향 alias lookup
# ─────────────────────────────────────────────────────────────────────────────


def test_expand_search_terms_korean_to_english(fresh_db) -> None:
    """입력 한국어 → 영문 aliases 추가."""
    _seed_thickness_term()
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms

    expanded = _expand_search_terms(
        search_terms=["두께"], repo_id="r1",
    )
    # 원본 + 영문 aliases 가 포함되어야
    assert "두께" in expanded
    assert "thickness" in expanded


def test_expand_search_terms_english_to_korean(fresh_db) -> None:
    """입력 영문 → 한국어 label 추가."""
    _seed_thickness_term()
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms

    expanded = _expand_search_terms(
        search_terms=["thickness"], repo_id="r1",
    )
    assert "thickness" in expanded
    assert "두께" in expanded


def test_expand_search_terms_unknown_word_returns_original(fresh_db) -> None:
    """alias 매칭 없으면 원본만 반환."""
    _seed_thickness_term()
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms

    expanded = _expand_search_terms(
        search_terms=["zzzunknownzzz"], repo_id="r1",
    )
    assert expanded == ["zzzunknownzzz"]


def test_expand_search_terms_other_repo_ignored(fresh_db) -> None:
    """다른 repo 의 alias 는 무시."""
    _seed_thickness_term(repo_id="other-repo")
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms

    expanded = _expand_search_terms(
        search_terms=["두께"], repo_id="r1",
    )
    assert "thickness" not in expanded


def test_expand_search_terms_empty(fresh_db) -> None:
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms
    assert _expand_search_terms(search_terms=[], repo_id="r1") == []


def test_expand_search_terms_cap_per_token(fresh_db) -> None:
    """한 토큰 당 expansion 토큰 수 cap (UX/검색 정확도)."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        # 10 aliases — cap 동작 검증
        s.add(BusinessTermRow(
            fqn="term.test",
            label="테스트",
            aliases_json=(
                '["a1","a2","a3","a4","a5","a6","a7","a8","a9","a10"]'
            ),
            kind="concept",
            repo_id="r1",
        ))
    from backend.section3.agents.multiturn.gate_i import _expand_search_terms

    expanded = _expand_search_terms(
        search_terms=["테스트"], repo_id="r1",
    )
    # 원본 + cap (예: 5) — 정확히 N 까지만
    assert "테스트" in expanded
    # 총 길이는 합리적이어야 (12 미만)
    assert len(expanded) < 12


# ─────────────────────────────────────────────────────────────────────────────
# (2) gate_i 가 expansion 결과로 검색
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_i_uses_expanded_search_terms(fresh_db, monkeypatch) -> None:
    """gate_i 가 한국어 입력을 expansion 후 영문 alias 까지 검색에 사용."""
    _seed_thickness_term()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.section3 import sim_v2_bridge as sb
    from backend.section3.agents.multiturn.intent import StubIntentClassifier
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient

    captured: list[str] = []

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: captured.append(q) or [])

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(
            forced_intent="impact",
            forced_search_terms=["두께"],
        )
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "두께 변경 영향", "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
               json={"message": "두께 변경 영향"})

    used = " ".join(captured)
    assert "thickness" in used, (
        f"한·영 alias 가 검색 query 에 포함되어야. captured={captured}"
    )
    assert "두께" in used


# ─────────────────────────────────────────────────────────────────────────────
# (3) ranking — declared_on_term 매칭 후보에 추가 boost
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_ranking_boost_with_declared_on_term_match(fresh_db) -> None:
    """후보의 declared_on_term 이 expansion 의 term FQN 과 일치 시 boost."""
    from backend.section3.agents.multiturn.gate_i import _apply_ranking_boost
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    c1 = ActionCandidate(
        action_id="a1", label="thickness exec", score=10.0,
        code_method_fqn="com.x.SdThicknessAction.execute",
        declared_on_term="term.scm.thickness",
    )
    c2 = ActionCandidate(
        action_id="a2", label="order validator", score=12.0,
        code_method_fqn="com.x.SdOrderValidator.validate",
        declared_on_term=None,
    )
    # query 토큰 "두께" 가 c1 의 declared_on_term term 의 label 이면 c1 우선되어야
    ranked = _apply_ranking_boost(
        [c2, c1],
        user_query="두께 변경",
        term_fqns_in_query={"term.scm.thickness"},
    )
    assert ranked[0].action_id == "a1", (
        f"declared_on_term 매칭 후보가 top-1. 실제: {ranked[0]}"
    )


def test_apply_ranking_boost_term_fqns_optional(fresh_db) -> None:
    """기존 호출 (term_fqns_in_query 없이) 도 동작 (backward compat)."""
    from backend.section3.agents.multiturn.gate_i import _apply_ranking_boost
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    c = ActionCandidate(
        action_id="a", label="x", score=5.0,
        code_method_fqn="A.b",
    )
    out = _apply_ranking_boost([c], user_query="x")
    assert out[0].action_id == "a"
