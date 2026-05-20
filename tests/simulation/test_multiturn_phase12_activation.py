"""Phase 12 Activation — 기존 ontology 데이터를 agent 가 활용하도록 재배선.

스코프 (5 항목):
  1. SimV2BackedOntologyClient.get_caller_graph — return [] → SQLite store 직접 query
  2. Gate III impact confidence — caller_count 0 시 자동 confidence 떨어뜨림
  3. ActionCandidate schema — role / parent_role / annotations 7+ 필드 확장
  4. 랭킹 boost — role/annotations/FQN substring 시그널 활용
  5. business_rules evidence — Gate I/II 응답 sources 에 자연어 statement

이 테스트는 1번, 2번, 3번 시작점.
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase12_activation.db"
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


def _seed_caller_data(repo_id: str = "r1") -> None:
    """callee 1 개 + caller 3 개 (receiver_exact / name_only / 미매칭) 시드."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeTypeRow, CodeMethodRow, CallSiteRow
    callee_class = "com.x.CalleeService"
    caller_class = "com.x.CallerService"
    other_class  = "com.y.OtherService"

    with session_scope() as s:
        for fqn, name, pkg in [
            (callee_class, "CalleeService", "com.x"),
            (caller_class, "CallerService", "com.x"),
            (other_class,  "OtherService",  "com.y"),
        ]:
            s.add(CodeTypeRow(
                fqn=fqn, simple_name=name, package=pkg,
                kind="class", repo_id=repo_id,
            ))
        s.flush()
        # callee method
        s.add(CodeMethodRow(
            fqn=f"{callee_class}.execute()",
            name="execute",
            parent_type_fqn=callee_class,
            repo_id=repo_id,
        ))
        # 3 caller methods
        s.add(CodeMethodRow(
            fqn=f"{caller_class}.callA()",
            name="callA",
            parent_type_fqn=caller_class,
            repo_id=repo_id,
        ))
        s.add(CodeMethodRow(
            fqn=f"{other_class}.callB()",
            name="callB",
            parent_type_fqn=other_class,
            repo_id=repo_id,
        ))
        s.flush()
        # CallSites — caller -> callee
        s.add(CallSiteRow(
            id="cs1",
            caller_method_fqn=f"{caller_class}.callA()",
            callee_simple_name="execute",
            callee_receiver_static_type=callee_class,   # exact match
            analysis_source="static_method_invocation",
            repo_id=repo_id,
        ))
        s.add(CallSiteRow(
            id="cs2",
            caller_method_fqn=f"{other_class}.callB()",
            callee_simple_name="execute",
            callee_receiver_static_type="",   # parser 가 못 잡음 → name_only
            analysis_source="ambiguous_invocation",
            repo_id=repo_id,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# Item 1 — SimV2BackedOntologyClient.get_caller_graph activation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sim_v2_backed_get_caller_graph_returns_callers(fresh_db) -> None:
    """이전: stub `return []`. 이후: SQLite store 직접 query → AffectedMethod[] 반환."""
    from backend.section3.agents.multiturn.ontology_client import (
        SimV2BackedOntologyClient,
    )
    _seed_caller_data(repo_id="r1")

    c = SimV2BackedOntologyClient()
    result = await c.get_caller_graph(
        "com.x.CalleeService.execute()", repo_id="r1",
    )

    assert len(result) >= 1, "caller 가 surface 되어야 (이전 stub 은 빈 배열)"
    fqns = [r.fqn for r in result]
    assert "com.x.CallerService.callA()" in fqns
    # match_kind / strength 가 채워져야
    exact = next(r for r in result if r.fqn == "com.x.CallerService.callA()")
    assert exact.match_kind == "receiver_exact"
    assert exact.strength == 0.95


@pytest.mark.asyncio
async def test_sim_v2_backed_get_caller_graph_repo_filter(fresh_db) -> None:
    """다른 repo 는 빈 배열 — 같은 callee 이름이라도."""
    from backend.section3.agents.multiturn.ontology_client import (
        SimV2BackedOntologyClient,
    )
    _seed_caller_data(repo_id="r1")

    c = SimV2BackedOntologyClient()
    result = await c.get_caller_graph(
        "com.x.CalleeService.execute()", repo_id="other-repo",
    )
    assert result == []


@pytest.mark.asyncio
async def test_sim_v2_backed_get_caller_graph_name_only_match(fresh_db) -> None:
    """parser 가 receiver type 못 잡은 caller 도 name_only 로 surface 되어야."""
    from backend.section3.agents.multiturn.ontology_client import (
        SimV2BackedOntologyClient,
    )
    _seed_caller_data(repo_id="r1")

    c = SimV2BackedOntologyClient()
    result = await c.get_caller_graph(
        "com.x.CalleeService.execute()", repo_id="r1",
    )
    fqns = [r.fqn for r in result]
    assert "com.y.OtherService.callB()" in fqns
    other = next(r for r in result if r.fqn == "com.y.OtherService.callB()")
    assert other.match_kind == "name_only"
    assert other.strength == 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Item 2 — Gate III impact confidence — caller_count blind 수정
# ─────────────────────────────────────────────────────────────────────────────


def test_impact_confidence_drops_when_no_callers() -> None:
    """이전: caller 0 이어도 fixture 만 통과하면 confidence 1.0.
    이후: caller=0 면 confidence 0.0 ~ 0.5 사이로 떨어져 "변경 안전" 오해 방지.
    """
    from backend.section3.agents.multiturn.gate_iii_impact import _impact_confidence

    diag_full_pass = {"ok": True, "fixtures": 12, "passing": 12, "stubs": 3}
    # 이전: caller_count blind → 1.0
    # 이후: caller_count 0 → 0.5 이하
    conf_no_caller = _impact_confidence(diag_full_pass, caller_count=0)
    conf_one_caller = _impact_confidence(diag_full_pass, caller_count=1)
    conf_many_caller = _impact_confidence(diag_full_pass, caller_count=5)

    assert conf_no_caller <= 0.5, (
        f"caller=0 인데 confidence={conf_no_caller} — 이전 1.0 버그 미수정"
    )
    assert conf_one_caller > conf_no_caller
    assert conf_many_caller >= conf_one_caller


def test_impact_confidence_diag_blocked_returns_low() -> None:
    """diagnose 가 blocked / not ok 면 confidence 낮음 (기존 동작 유지)."""
    from backend.section3.agents.multiturn.gate_iii_impact import _impact_confidence

    conf = _impact_confidence({"ok": False, "fixtures": 0}, caller_count=2)
    assert conf <= 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Item 3 — ActionCandidate schema 확장
# ─────────────────────────────────────────────────────────────────────────────


def test_action_candidate_has_role_and_annotations_fields() -> None:
    """ActionCandidate 가 ontology 의 풍부 데이터를 surface 할 수 있는 필드 보유."""
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    c = ActionCandidate(
        action_id="a1",
        label="주문 검증",
        score=10.0,
        code_method_fqn="com.x.OrderValidator.validate",
        aliases=[],
        role="business",
        parent_role="domain",
        annotations=["@Service"],
        declared_on_term="term.order.validation",
    )
    assert c.role == "business"
    assert c.parent_role == "domain"
    assert c.annotations == ["@Service"]
    assert c.declared_on_term == "term.order.validation"


def test_action_candidate_new_fields_optional_backward_compat() -> None:
    """기존 코드가 새 필드 없이 ActionCandidate 만들 때 깨지지 않아야."""
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    c = ActionCandidate(
        action_id="a1", label="x", score=1.0,
        code_method_fqn="x.y", aliases=[],
    )
    # 신규 필드는 None / 빈 기본값
    assert c.role is None
    assert c.parent_role is None
    assert c.annotations == []
    assert c.declared_on_term is None


# ─────────────────────────────────────────────────────────────────────────────
# Item 4 — 랭킹 boost (role / annotations / FQN substring)
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_ranking_boost_lifts_domain_business_methods() -> None:
    """role=business + parent_role=domain → score 부스트.
    role=helper / adapter → 패널티.
    """
    from backend.section3.agents.multiturn.gate_i import _apply_ranking_boost
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    helper = ActionCandidate(
        action_id="h1", label="ValidationResult.pass", score=9.0,
        code_method_fqn="com.x.ValidationResult.pass",
        aliases=[], role="helper", parent_role="unknown",
    )
    domain_action = ActionCandidate(
        action_id="a1", label="thickness 검증", score=3.0,
        code_method_fqn="com.x.SdThicknessAction.execute",
        aliases=[], role="business", parent_role="domain",
        annotations=["@Service"],
    )
    boosted = _apply_ranking_boost(
        [helper, domain_action], user_query="thickness 검증",
    )
    # 도메인 액션이 helper 위로 올라와야
    assert boosted[0].action_id == "a1"
    assert boosted[1].action_id == "h1"


def test_apply_ranking_boost_fqn_substring() -> None:
    """쿼리에 FQN 일부 (`.` 포함 또는 PascalCase Class) 있으면 일치 후보 부스트."""
    from backend.section3.agents.multiturn.gate_i import _apply_ranking_boost
    from backend.section3.agents.multiturn.schemas import ActionCandidate

    matching = ActionCandidate(
        action_id="m1", label="validate", score=3.0,
        code_method_fqn="com.slab.SdOrderValidator.validate",
        aliases=[],
    )
    other = ActionCandidate(
        action_id="o1", label="design", score=17.0,
        code_method_fqn="com.slab.SdDesigner.design",
        aliases=[],
    )
    boosted = _apply_ranking_boost(
        [other, matching], user_query="SdOrderValidator.validate 시뮬",
    )
    # 사용자가 콕 찍은 FQN 매칭 후보가 1위
    assert boosted[0].action_id == "m1"


# ─────────────────────────────────────────────────────────────────────────────
# Item 5 — business_rules evidence 노출
# ─────────────────────────────────────────────────────────────────────────────


def test_find_related_business_rules_by_term(fresh_db) -> None:
    """candidate 의 declared_on_term 으로 연결된 business_rules statement 수집."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessRuleRow
    from backend.section3.agents.multiturn.gate_i import _find_related_business_rules

    with session_scope() as s:
        s.add(BusinessRuleRow(
            fqn="rule.scm.productivity_range",
            statement="실수율 범위 (0.5 ≤ p ≤ 1.0)",
            severity="WARNING",
            terms_ref_json='["term.scm.productivity"]',
            repo_id="r1",
        ))
        s.add(BusinessRuleRow(
            fqn="rule.scm.stock_order_excluded",
            statement="재고주문은 설계 대상 아님 (DG001)",
            severity="ERROR",
            terms_ref_json='["term.scm.order"]',
            repo_id="r1",
        ))
        s.add(BusinessRuleRow(
            fqn="rule.other.something",
            statement="다른 repo 의 룰 (잡혀선 안 됨)",
            severity="INFO",
            terms_ref_json='["term.scm.productivity"]',
            repo_id="other",
        ))

    rules = _find_related_business_rules(
        terms=["term.scm.productivity"], repo_id="r1",
    )
    statements = [r.statement for r in rules]
    assert "실수율 범위 (0.5 ≤ p ≤ 1.0)" in statements
    assert all("다른 repo" not in s for s in statements)


def test_find_related_business_rules_empty_when_no_terms(fresh_db) -> None:
    from backend.section3.agents.multiturn.gate_i import _find_related_business_rules

    rules = _find_related_business_rules(terms=[], repo_id="r1")
    assert rules == []
