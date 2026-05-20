"""Phase 13a — locate / explain intent + executed_lookup payload.

방안 C 점진적 첫 단계: intent 3 종 (simulate/impact/ambiguous) 에 locate/explain 추가.
박주니어 페르소나 ("validateOrder 뭐함?" / "어디서 계산?") 즉시 해결.

새 단계 흐름:
  start (turn 1) → respond turn 2 (Gate I, intent=locate/explain) →
  confirm turn 2 + respond turn 3 → executed_lookup (session done)

executed_lookup 응답 = body + file_path + callers + linked_term + business_rules.
Gate II / III 우회.
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
    db_path = tmp_path / "phase13a.db"
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
# (1) Intent — locate / explain enum 추가
# ─────────────────────────────────────────────────────────────────────────────


def test_intent_decision_accepts_locate() -> None:
    """이전: simulate/impact/ambiguous 3 종만. 이후: locate + explain 추가."""
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(intent="locate", confidence=0.8, reasoning="어디서 계산 패턴")
    assert d.intent == "locate"


def test_intent_decision_accepts_explain() -> None:
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(intent="explain", confidence=0.85, reasoning="X 뭐함 패턴")
    assert d.intent == "explain"


def test_intent_decision_rejects_invalid_still() -> None:
    """기존 검증은 유지."""
    from backend.section3.agents.multiturn.intent import IntentDecision
    with pytest.raises(ValueError, match="intent must be one of"):
        IntentDecision(intent="bogus", confidence=0.5, reasoning="")


def test_llm_system_prompt_has_locate_and_explain_examples() -> None:
    """prompt 본문에 두 신규 intent 의 한국어 예시 명시 (LLM 분류 정확도 확보)."""
    from backend.section3.agents.multiturn import intent as intent_mod
    prompt = intent_mod._SYSTEM_PROMPT
    assert "locate" in prompt
    assert "explain" in prompt
    # 한국어 자연어 trigger 예시 — "어디" / "뭐" / "위치" 가 있어야 LLM 이 분류 가능
    assert any(k in prompt for k in ("어디", "위치", "뭐함"))


# ─────────────────────────────────────────────────────────────────────────────
# (2) Schemas — BusinessRuleEvidence + GateExecutedLookup
# ─────────────────────────────────────────────────────────────────────────────


def test_business_rule_evidence_schema() -> None:
    from backend.section3.agents.multiturn.schemas import BusinessRuleEvidence
    e = BusinessRuleEvidence(
        fqn="rule.scm.dg001",
        statement="재고주문은 설계 대상 아님 (DG001)",
        severity="hard",
    )
    assert e.fqn == "rule.scm.dg001"
    assert "DG001" in e.statement


def test_gate_executed_lookup_schema() -> None:
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation, GateExecutedLookup, BusinessRuleEvidence,
        AffectedMethod, Provenance,
    )
    target = ActionRef(
        action_id="a1",
        code_method_fqn="com.x.OrderValidator.validate",
        repo_id="r",
        location=CodeLocation(file_path="OrderValidator.java", line_start=10, line_end=30),
    )
    p = GateExecutedLookup(
        mode="explain",
        target=target,
        body_text="public Result validate(...)",
        file_path="OrderValidator.java",
        line_start=10, line_end=30,
        return_type="ValidationResult",
        linked_action_label="주문 정합성 검증",
        linked_term="term.scm.order.validation",
        callers=[AffectedMethod(
            fqn="com.x.SdOrderService.process", distance=1, via="direct_caller",
            match_kind="receiver_exact", strength=0.95,
        )],
        business_rules=[BusinessRuleEvidence(
            fqn="rule.dg001", statement="재고주문 제외", severity="hard",
        )],
        sources=[],
    )
    assert p.kind == "executed_lookup"
    assert p.mode == "explain"
    assert "Result" in p.body_text


def test_gate_executed_lookup_supports_locate_mode() -> None:
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation, GateExecutedLookup,
    )
    target = ActionRef(
        action_id="a1", code_method_fqn="x.y", repo_id="r",
        location=CodeLocation(file_path="", line_start=0, line_end=0),
    )
    p = GateExecutedLookup(
        mode="locate", target=target, body_text="",
        file_path="OrderValidator.java", line_start=12, line_end=48,
        return_type="", linked_action_label=None, linked_term=None,
        callers=[], business_rules=[], sources=[],
    )
    assert p.mode == "locate"


# ─────────────────────────────────────────────────────────────────────────────
# (3) State machine — confirm 후 다음 게이트
# ─────────────────────────────────────────────────────────────────────────────


def _gate_i_catalog():
    fqn = "com.slab.SdOrderValidator.validate(SDOrderEntity)"
    return {
        "actions": [{
            "action_id": "action.scm.order.정합성_검증",
            "label": "주문 검증",
            "code_method_fqn": fqn,
            "aliases": ["주문검증", "validateOrder"],
            "repo_id": "slab-design-real-v2",
            "location": {"file_path": "OrderValidator.java",
                         "line_start": 12, "line_end": 48},
        }],
        "method_bodies": {
            fqn: "public Result validate(SDOrderEntity o) { return Result.OK; }",
        },
        "entity_schemas": {},
    }


def _client_with_intent(monkeypatch, intent_label: str):
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [],
    )
    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent=intent_label, forced_confidence=0.9)
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog=_gate_i_catalog())
    )
    return TestClient(app)


def test_state_machine_locate_confirm_returns_executed_lookup(fresh_db, monkeypatch):
    client = _client_with_intent(monkeypatch, "locate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "validateOrder 어디 있나?",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "validateOrder 어디 있나?"})
    r = client.post(f"/api/section3/multiturn/confirm/{sid}/2",
                    json={"action": "confirm", "user_response": {"selected_index": 0}})
    assert r.status_code == 200
    assert r.json()["next_gate_kind"] == "executed_lookup"


def test_state_machine_explain_confirm_returns_executed_lookup(fresh_db, monkeypatch):
    client = _client_with_intent(monkeypatch, "explain")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "validateOrder 뭐함?",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "validateOrder 뭐함?"})
    r = client.post(f"/api/section3/multiturn/confirm/{sid}/2",
                    json={"action": "confirm", "user_response": {"selected_index": 0}})
    assert r.status_code == 200
    assert r.json()["next_gate_kind"] == "executed_lookup"


# ─────────────────────────────────────────────────────────────────────────────
# (4) /respond turn 3 with intent=locate/explain → executed_lookup
# ─────────────────────────────────────────────────────────────────────────────


def test_respond_turn_3_locate_runs_executed_lookup(fresh_db, monkeypatch):
    client = _client_with_intent(monkeypatch, "locate")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "validateOrder 위치", "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "validateOrder 위치"})
    client.post(f"/api/section3/multiturn/confirm/{sid}/2",
                json={"action": "confirm", "user_response": {"selected_index": 0}})
    r = client.post(f"/api/section3/multiturn/respond/{sid}",
                    json={"message": "보여줘"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_no"] == 3
    payload = body["payload"]
    assert payload["kind"] == "executed_lookup"
    assert payload["mode"] == "locate"
    # 핵심 필드 surface
    assert payload["file_path"]   # 채워졌어야
    assert "body_text" in payload
    assert "callers" in payload
    assert "business_rules" in payload

    # session done
    sess = client.get(f"/api/section3/multiturn/session/{sid}").json()
    assert sess["session"]["status"] == "done"


def test_respond_turn_3_explain_runs_executed_lookup(fresh_db, monkeypatch):
    client = _client_with_intent(monkeypatch, "explain")
    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "validateOrder 뭐함",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "validateOrder 뭐함"})
    client.post(f"/api/section3/multiturn/confirm/{sid}/2",
                json={"action": "confirm", "user_response": {"selected_index": 0}})
    r = client.post(f"/api/section3/multiturn/respond/{sid}",
                    json={"message": "설명"})
    assert r.status_code == 200, r.text
    payload = r.json()["payload"]
    assert payload["kind"] == "executed_lookup"
    assert payload["mode"] == "explain"
    # explain 모드는 body_text 채워져야 (mock catalog 가 body 제공)
    assert "validate" in payload["body_text"]


# ─────────────────────────────────────────────────────────────────────────────
# (5) SimV2BackedOntologyClient.get_method_meta — locate payload fix
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sim_v2_backed_get_method_meta_returns_file_line_return(fresh_db):
    """이전: SimV2-only client 에 get_method_meta 부재 → executed_lookup 의
    file_path / line_start / line_end / return_type 빈 값.
    이후: SQLite 직접 query 로 채움.
    """
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeTypeRow, CodeMethodRow
    from backend.section3.agents.multiturn.ontology_client import (
        SimV2BackedOntologyClient,
    )

    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.Service", simple_name="Service", package="com.x",
            kind="class", source_file="com/x/Service.java",
            repo_id="r1",
        ))
        s.flush()
        s.add(CodeMethodRow(
            fqn="com.x.Service.process()",
            name="process",
            parent_type_fqn="com.x.Service",
            return_type="ValidationResult",
            line_start=12, line_end=48,
            repo_id="r1",
        ))

    c = SimV2BackedOntologyClient()
    meta = await c.get_method_meta("com.x.Service.process()", repo_id="r1")
    assert meta is not None
    assert meta["file_path"] == "com/x/Service.java"
    assert meta["line_start"] == 12
    assert meta["line_end"] == 48
    assert meta["return_type"] == "ValidationResult"


@pytest.mark.asyncio
async def test_sim_v2_backed_get_method_meta_unknown_returns_none(fresh_db):
    from backend.section3.agents.multiturn.ontology_client import (
        SimV2BackedOntologyClient,
    )
    c = SimV2BackedOntologyClient()
    meta = await c.get_method_meta("nonexistent.fqn()", repo_id="r1")
    assert meta is None


def test_executed_lookup_surfaces_business_rules(fresh_db, monkeypatch):
    """linked_term 으로 연결된 business_rule statement 가 surface 되어야.

    실 sec3 운영 흐름: ActionRow.declared_on_term + BusinessRuleRow.terms_ref_json
    매칭. catalog (mock ontology) 의 declared_on_term 만으론 부족 — DB seed 필요.
    """
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessRuleRow
    from backend.modeling.mapping_layer.orm import ActionRow

    # rule + action 시드 (executed_lookup 빌더가 DB 직접 query)
    with session_scope() as s:
        s.add(ActionRow(
            fqn="action.scm.order.정합성_검증",
            label="주문 검증",
            kind="business",
            declared_on_term="term.scm.order",
            repo_id="slab-design-real-v2",
        ))
        s.add(BusinessRuleRow(
            fqn="rule.scm.order.dg001",
            statement="재고주문 (STOCK_CODE=1) 은 설계 대상 아님",
            severity="hard",
            terms_ref_json='["term.scm.order"]',
            repo_id="slab-design-real-v2",
        ))

    # explain intent + action 의 declared_on_term 매핑된 term
    from backend.section3 import sim_v2_bridge as sb
    from backend.section3.api import multiturn_router as router_mod

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(sb, "find_action_candidates", lambda s, q, r, *, top_n=3: [])

    catalog = _gate_i_catalog()
    catalog["actions"][0]["declared_on_term"] = "term.scm.order"
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(forced_intent="explain", forced_confidence=0.9)
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog=catalog)
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "주문 검증 뭐함",
        "repo_id": "slab-design-real-v2",
    })
    sid = start.json()["session_id"]
    client.post(f"/api/section3/multiturn/respond/{sid}",
                json={"message": "주문 검증 뭐함"})
    client.post(f"/api/section3/multiturn/confirm/{sid}/2",
                json={"action": "confirm", "user_response": {"selected_index": 0}})
    r = client.post(f"/api/section3/multiturn/respond/{sid}",
                    json={"message": "go"})
    assert r.status_code == 200
    rules = r.json()["payload"]["business_rules"]
    assert len(rules) >= 1
    assert "DG001" in rules[0]["statement"] or "재고주문" in rules[0]["statement"]
