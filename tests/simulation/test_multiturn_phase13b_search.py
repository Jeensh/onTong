"""Phase 13b — search keyword extraction + 0-cand fallback + ranking 강화.

페르소나 검증 잔여 마찰 해결:
  - 김PM "엣징 마진 변경하면 어디 영향?" → 0 cand (search 풀 query 던짐)
  - 박주니어 "validateOrder" → 무관 매칭

해결책:
  (a) LLM intent classifier 가 `search_terms` 도 추출 → ontology/sim_v2 검색에 전달
  (b) 0-cand 시 `business_terms.aliases_json` 인접어 추천 surface
  (c) GateTarget 의 suggestions 필드 신설
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modeling.persistence import database as db_mod
from backend.section3.agents.multiturn.intent import StubIntentClassifier
from backend.section3.agents.multiturn.ontology_client import MockOntologyClient


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase13b.db"
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


# ─────────────────────────────────────────────────────────────────────────────
# (1) IntentDecision.search_terms — LLM 이 추출하는 검색 키워드
# ─────────────────────────────────────────────────────────────────────────────


def test_intent_decision_supports_search_terms() -> None:
    """이전: intent + confidence + reasoning 만. 이후: search_terms (optional)."""
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(
        intent="impact",
        confidence=0.9,
        reasoning="변경 영향 의도",
        search_terms=["엣징", "마진"],
    )
    assert d.search_terms == ["엣징", "마진"]


def test_intent_decision_search_terms_default_empty() -> None:
    """기존 코드가 search_terms 없이 만들어도 깨지지 않아야."""
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(intent="simulate", confidence=0.8, reasoning="x")
    assert d.search_terms == []


def test_classify_with_llm_parses_search_terms() -> None:
    """LLM JSON 응답에 search_terms 들어오면 IntentDecision 에 mapping."""
    from backend.section3.agents.multiturn.intent import classify_with_llm

    class _FakeLLM:
        def chat_json(self, messages, **kw):
            return {
                "intent": "impact",
                "confidence": 0.9,
                "reasoning": "변경 영향",
                "search_terms": ["엣징", "마진"],
            }
    out = classify_with_llm("엣징 마진 변경하면 어디 영향?", llm=_FakeLLM())
    assert out.intent == "impact"
    assert out.search_terms == ["엣징", "마진"]


def test_classify_with_llm_handles_missing_search_terms() -> None:
    """LLM 이 search_terms 빠뜨려도 기본값 [] (backward compat)."""
    from backend.section3.agents.multiturn.intent import classify_with_llm

    class _FakeLLM:
        def chat_json(self, messages, **kw):
            return {"intent": "simulate", "confidence": 0.9, "reasoning": "x"}
    out = classify_with_llm("query", llm=_FakeLLM())
    assert out.search_terms == []


def test_llm_prompt_has_search_terms_extraction_guidance() -> None:
    from backend.section3.agents.multiturn import intent as intent_mod
    p = intent_mod._SYSTEM_PROMPT
    assert "search_terms" in p


def test_stub_classifier_supports_per_query_search_terms() -> None:
    """StubIntentClassifier 도 search_terms 강제 지원 (테스트 용)."""
    from backend.section3.agents.multiturn.intent import StubIntentClassifier
    c = StubIntentClassifier(
        forced_intent="impact",
        forced_search_terms=["엣징"],
    )
    d = c.classify("아무거나")
    assert d.search_terms == ["엣징"]


# ─────────────────────────────────────────────────────────────────────────────
# (2) gate_i — search_terms 가 ontology/sim_v2 검색에 전달
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_i_uses_search_terms_when_present(fresh_db, monkeypatch) -> None:
    """LLM 이 search_terms 추출하면 그걸로 검색 (풀 query 대신)."""
    from backend.section3 import sim_v2_bridge as sb

    captured_queries: list[str] = []

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())

    def _find(s, q, r, *, top_n=3):
        captured_queries.append(q)
        return []

    monkeypatch.setattr(sb, "find_action_candidates", _find)

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(
            forced_intent="impact",
            forced_search_terms=["엣징", "마진"],
        )
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "엣징 마진 변경하면 어디 영향?",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "엣징 마진 변경하면 어디 영향?"})

    # search_terms 가 있으면 그 토큰들이 ontology/sim_v2 검색에 사용
    assert captured_queries, "sim_v2.find_action_candidates 가 호출되어야"
    used = " ".join(captured_queries)
    assert "엣징" in used or "마진" in used, (
        f"search_terms ({['엣징', '마진']}) 가 sim_v2 검색 query 에 반영되어야. "
        f"실제 호출: {captured_queries}"
    )


def test_gate_i_falls_back_to_user_query_when_no_search_terms(fresh_db, monkeypatch) -> None:
    """LLM 이 search_terms 빠뜨리면 user_query 그대로 사용 (backward compat)."""
    from backend.section3 import sim_v2_bridge as sb
    captured_queries: list[str] = []

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())

    def _find(s, q, r, *, top_n=3):
        captured_queries.append(q)
        return []

    monkeypatch.setattr(sb, "find_action_candidates", _find)

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="simulate")   # search_terms 안 줌
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})
    )
    client = TestClient(app)
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "주문 검증"})

    assert captured_queries == ["주문 검증"], (
        f"search_terms 없으면 user_query 사용. 실제: {captured_queries}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (3) 0-cand fallback — business_terms.aliases_json 인접어 suggestion
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_suggestions_returns_nearby_terms(fresh_db) -> None:
    """`business_terms.aliases_json` 의 인접 키워드 추천."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions

    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn="term.scm.edging_group",
            label="엣징그룹",
            aliases_json='["엣징 그룹", "EDGING_GROUP", "EdgingGroupEntity"]',
            kind="concept",
            repo_id="r1",
        ))
        s.add(BusinessTermRow(
            fqn="term.scm.thickness",
            label="두께",
            aliases_json='["thickness", "두께 마진"]',
            kind="concept",
            repo_id="r1",
        ))
        s.add(BusinessTermRow(
            fqn="term.other.x",
            label="다른 repo 거",
            aliases_json='["엣징"]',
            kind="concept",
            repo_id="other-repo",
        ))

    # "엣징 마진" 검색 → 엣징그룹 / 두께 마진 surface
    suggestions = _fetch_suggestions(
        query="엣징 마진",
        search_terms=["엣징", "마진"],
        repo_id="r1",
    )
    assert len(suggestions) >= 1
    # 다른 repo 의 결과는 제외
    assert not any("다른 repo" in s for s in suggestions)


def test_fetch_suggestions_empty_when_no_terms_match(fresh_db) -> None:
    from backend.section3.agents.multiturn.gate_i import _fetch_suggestions
    sugg = _fetch_suggestions(query="zzz", search_terms=["zzz"], repo_id="r1")
    assert sugg == []


# ─────────────────────────────────────────────────────────────────────────────
# (4) GateTarget.suggestions 필드
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_target_has_suggestions_field() -> None:
    from backend.section3.agents.multiturn.schemas import GateTarget
    t = GateTarget(
        intent="impact",
        user_query="엣징 마진",
        candidates=[],
        recommended_index=None,
        selected=None,
        sources=[],
        suggestions=["엣징 그룹", "두께 마진"],
    )
    assert t.suggestions == ["엣징 그룹", "두께 마진"]


def test_gate_target_suggestions_default_empty() -> None:
    """기존 GateTarget 생성 시 suggestions 없어도 깨지지 않아야."""
    from backend.section3.agents.multiturn.schemas import GateTarget
    t = GateTarget(
        intent="impact", user_query="x", candidates=[],
        recommended_index=None, selected=None, sources=[],
    )
    assert t.suggestions == []


def test_gate_i_surfaces_suggestions_on_zero_candidates(fresh_db, monkeypatch) -> None:
    """0-cand 발생 시 GateTarget.suggestions 에 인접 term 추천."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow

    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn="term.edging_group", label="엣징그룹",
            aliases_json='["엣징 그룹", "edging"]',
            kind="concept", repo_id="r1",
        ))

    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates",
                       lambda s, q, r, *, top_n=3: [])

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(
            forced_intent="impact",
            forced_search_terms=["엣징", "마진"],
        )
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={})  # 비어있어서 후보 0
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "엣징 마진 변경하면 어디 영향?",
        "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    r = client.post(f"/api/section3/multiturn/respond/{sid}",
                    json={"message": "엣징 마진 변경하면 어디 영향?"})
    payload = r.json()["payload"]
    assert len(payload["candidates"]) == 0
    assert len(payload["suggestions"]) >= 1, (
        f"0-cand 시 suggestions 있어야. 실제: {payload['suggestions']}"
    )
