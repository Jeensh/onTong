"""Phase 13c — hypothesis intent + boundary value extraction + verdict.

최QA 페르소나 마찰 해결:
  - "엣징 마진이 1.0 미만이면 어떻게 처리되나?" → Phase 13b 는 explain 으로 분류 + boundary 숫자 누락
  - "두께 0.1mm 일 때 검증 실패하나?" → 조건 → 결과 추론 못함

해결책:
  (a) `hypothesis` intent 6 번째 카테고리 신설 — boundary / edge case 질의
  (b) IntentDecision 에 `conditions: list[Condition]` (var/op/value/unit)
  (c) GateExecutedHypothesis payload — body + verdict (yes/no/likely_*/unknown) + 근거
  (d) router turn 3 → hypothesis intent → build_gate_hypothesis 라우팅
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
    db_path = tmp_path / "phase13c.db"
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
# (1) IntentDecision 에 conditions
# ─────────────────────────────────────────────────────────────────────────────


def test_intent_decision_accepts_hypothesis() -> None:
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(
        intent="hypothesis",
        confidence=0.85,
        reasoning="boundary 검증",
    )
    assert d.intent == "hypothesis"


def test_intent_decision_supports_conditions() -> None:
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(
        intent="hypothesis",
        confidence=0.85,
        reasoning="boundary",
        conditions=[
            {"var": "엣징 마진", "op": "<", "value": "1.0", "unit": ""},
        ],
    )
    assert d.conditions[0]["var"] == "엣징 마진"
    assert d.conditions[0]["op"] == "<"


def test_intent_decision_conditions_default_empty() -> None:
    from backend.section3.agents.multiturn.intent import IntentDecision
    d = IntentDecision(intent="simulate", confidence=0.9, reasoning="x")
    assert d.conditions == []


def test_llm_prompt_has_hypothesis_and_conditions_guidance() -> None:
    from backend.section3.agents.multiturn import intent as intent_mod
    p = intent_mod._SYSTEM_PROMPT
    assert "hypothesis" in p
    assert "conditions" in p


def test_classify_with_llm_parses_conditions() -> None:
    from backend.section3.agents.multiturn.intent import classify_with_llm

    class _FakeLLM:
        def chat_json(self, messages, **kw):
            return {
                "intent": "hypothesis",
                "confidence": 0.9,
                "reasoning": "boundary 조건",
                "search_terms": ["엣징", "마진"],
                "conditions": [
                    {"var": "엣징 마진", "op": "<", "value": "1.0", "unit": ""},
                ],
            }
    out = classify_with_llm("엣징 마진이 1.0 미만이면?", llm=_FakeLLM())
    assert out.intent == "hypothesis"
    assert out.conditions == [
        {"var": "엣징 마진", "op": "<", "value": "1.0", "unit": ""},
    ]


def test_stub_classifier_supports_forced_conditions() -> None:
    from backend.section3.agents.multiturn.intent import StubIntentClassifier
    c = StubIntentClassifier(
        forced_intent="hypothesis",
        forced_conditions=[
            {"var": "두께", "op": "=", "value": "0.1", "unit": "mm"},
        ],
    )
    d = c.classify("아무거나")
    assert d.intent == "hypothesis"
    assert d.conditions[0]["unit"] == "mm"


# ─────────────────────────────────────────────────────────────────────────────
# (2) GateTarget.intent extends + GateExecutedHypothesis schema
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_target_accepts_hypothesis_intent() -> None:
    from backend.section3.agents.multiturn.schemas import GateTarget
    t = GateTarget(
        intent="hypothesis",
        user_query="엣징 마진 1.0 미만",
        candidates=[], recommended_index=None, selected=None, sources=[],
    )
    assert t.intent == "hypothesis"


def test_gate_executed_hypothesis_schema_exists() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GateExecutedHypothesis,
        ActionRef,
        CodeLocation,
        BusinessRuleEvidence,
        Provenance,
    )
    payload = GateExecutedHypothesis(
        target=ActionRef(
            action_id="a", code_method_fqn="A.b", repo_id="r",
            location=CodeLocation(file_path="x.java", line_start=1, line_end=10),
        ),
        conditions=[
            {"var": "엣징 마진", "op": "<", "value": "1.0", "unit": ""},
        ],
        body_text="if (margin < 1.0) fail('EDG_001');",
        file_path="x.java",
        line_start=1, line_end=10,
        verdict="likely_yes",
        reasoning="body 의 if 분기가 매개변수와 1.0 비교",
        evidence=[
            BusinessRuleEvidence(
                fqn="rule.edg_001",
                statement="엣징 마진은 1.0 이상이어야",
                severity="hard",
            ),
        ],
        confidence=0.7,
        sources=[],
    )
    assert payload.kind == "executed_hypothesis"
    assert payload.mode == "hypothesis"
    assert payload.verdict == "likely_yes"


def test_gate_payload_discriminator_includes_hypothesis() -> None:
    from pydantic import TypeAdapter
    from backend.section3.agents.multiturn.schemas import GatePayload

    raw = {
        "kind": "executed_hypothesis",
        "mode": "hypothesis",
        "target": {
            "action_id": "a", "code_method_fqn": "A.b", "repo_id": "r",
            "location": {"file_path": "x.java", "line_start": 1, "line_end": 10},
        },
        "conditions": [{"var": "x", "op": "<", "value": "1", "unit": ""}],
        "body_text": "if (x < 1) fail;",
        "file_path": "x.java", "line_start": 1, "line_end": 10,
        "verdict": "likely_yes",
        "reasoning": "분기 발견",
        "evidence": [],
        "confidence": 0.6,
        "sources": [],
    }
    obj = TypeAdapter(GatePayload).validate_python(raw)
    assert obj.kind == "executed_hypothesis"


# ─────────────────────────────────────────────────────────────────────────────
# (3) build_gate_hypothesis — body + conditions → verdict
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_returns_payload() -> None:
    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation,
    )

    client = MockOntologyClient(catalog={})
    target = ActionRef(
        action_id="a.test", code_method_fqn="A.b", repo_id="r",
        location=CodeLocation(file_path="x.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )
    assert payload.kind == "executed_hypothesis"
    assert payload.conditions == [
        {"var": "margin", "op": "<", "value": "1.0", "unit": ""},
    ]


@pytest.mark.asyncio
async def test_build_gate_hypothesis_detects_inline_boundary_in_body() -> None:
    """body 에 `if (margin < 1.0)` 가 있으면 verdict=likely_yes (정확한 LLM 추론은 stub)."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation,
    )

    body = "void check() { if (margin < 1.0) throw new EdgException('EDG_001'); }"
    client = MockOntologyClient(catalog={
        "method_bodies": {"A.b": body},
    })

    target = ActionRef(
        action_id="a.test", code_method_fqn="A.b", repo_id="r",
        location=CodeLocation(file_path="x.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )
    assert "margin" in payload.body_text
    # heuristic 적어도 verdict 가 "unknown" 이면 안 됨 (body 에 분기 발견)
    assert payload.verdict in ("likely_yes", "yes", "likely_no")


# ─────────────────────────────────────────────────────────────────────────────
# (4) router — turn 3 hypothesis intent → build_gate_hypothesis
# ─────────────────────────────────────────────────────────────────────────────


def test_respond_turn3_hypothesis_intent_routes_to_gate_hypothesis(
    fresh_db, monkeypatch,
) -> None:
    """turn 3 가 hypothesis intent 면 executed_hypothesis 응답."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow

    # seed: a CodeType + CodeMethod with body
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.OrderValidator",
            simple_name="OrderValidator",
            kind="class",
            source_file="src/com/x/OrderValidator.java",
            role="domain",
            repo_id="r1",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.OrderValidator.check",
            name="check",
            parent_type_fqn="com.x.OrderValidator",
            return_type="void",
            params_json="[]",
            body_text="if (margin < 1.0) throw new EdgException('EDG_001');",
            role="business",
            line_start=10, line_end=20,
            repo_id="r1",
        ))

    # mock sim_v2 with a match
    from backend.section3 import sim_v2_bridge as sb

    class _S:
        def close(self): pass

    monkeypatch.setattr(sb, "open_sim_v2_session", lambda: _S())
    monkeypatch.setattr(
        sb, "find_action_candidates",
        lambda s, q, r, *, top_n=3: [
            {"code_method_fqn": "com.x.OrderValidator.check",
             "fqn": "action.x.check",
             "label": "Check",
             "score": 10.0},
        ],
    )

    from backend.section3.api import multiturn_router as router_mod
    app = FastAPI()
    app.include_router(router_mod.router)
    app.dependency_overrides[router_mod.get_classifier] = lambda: (
        StubIntentClassifier(
            forced_intent="hypothesis",
            forced_search_terms=["margin"],
            forced_conditions=[
                {"var": "margin", "op": "<", "value": "1.0", "unit": ""},
            ],
        )
    )
    app.dependency_overrides[router_mod.get_ontology_client] = lambda: (
        MockOntologyClient(catalog={
            "method_bodies": {
                "com.x.OrderValidator.check": (
                    "if (margin < 1.0) throw new EdgException('EDG_001');"
                ),
            },
        })
    )
    client = TestClient(app)

    start = client.post("/api/section3/multiturn/start", json={
        "user_query": "margin 이 1.0 미만이면?",
        "repo_id": "r1",
    })
    sid = start.json()["session_id"]
    turn2 = client.post(f"/api/section3/multiturn/respond/{sid}",
                        json={"message": "margin 이 1.0 미만이면?"})
    assert turn2.status_code == 200
    assert turn2.json()["payload"]["intent"] == "hypothesis"

    # confirm 후 turn 3
    confirm = client.post(
        f"/api/section3/multiturn/confirm/{sid}/2",
        json={"action": "confirm", "user_response": {"selected_index": 0}},
    )
    assert confirm.status_code == 200, confirm.text

    turn3 = client.post(f"/api/section3/multiturn/respond/{sid}",
                        json={"message": ""})
    assert turn3.status_code == 200, turn3.text
    payload = turn3.json()["payload"]
    assert payload["kind"] == "executed_hypothesis"
    assert payload["mode"] == "hypothesis"
    assert payload["conditions"][0]["var"] == "margin"
    assert payload["verdict"] in (
        "yes", "no", "likely_yes", "likely_no", "unknown",
    )


def test_next_gate_kind_returns_executed_hypothesis() -> None:
    from backend.section3.api.multiturn_router import _next_gate_kind

    class _Dec:
        gate_kind = "target_selected"
        payload = {"intent": "hypothesis"}

    # confirm 후 hypothesis → executed_hypothesis
    out = _next_gate_kind(_Dec(), action="confirm")
    assert out == "executed_hypothesis"
