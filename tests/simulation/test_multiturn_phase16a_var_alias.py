"""Phase 16A — Korean↔English var-alias bridge in `_check_fixture_compat`.

Phase 14B 시니어 검증에서 발견된 잔여 (즉시 fix 후에도 underlying):
  - condition var ("주문 수량") 가 영문 param name ("order") 와 substring 매칭 실패
  - 14B 응급 fix 는 "var miss → verdict 영향 X" 로 false negative 차단했으나, 본질은
    한·영 alias 미커버
  - Phase 14E 의 `_expand_search_terms` 메커니즘 (business_terms.aliases_json 정확
    매칭) 을 fixture_compat 에도 재사용

MVP:
  - `_check_fixture_compat(conditions, params, repo_id=None)` repo_id 옵셔널
  - repo_id 가 있으면 각 condition var 의 한·영 alias 확장 후 param 매칭 시도
  - 매칭 성공 → compat=True (이전엔 var miss false negative)
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase16a.db"
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


def _seed_term(*, fqn: str, label: str, aliases_json: str, repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn=fqn,
            label=label,
            aliases_json=aliases_json,
            kind="atomic",        # Schema constraint: atomic|composite
            domain="scm",
            description="",
            confirmed=True,
            repo_id=repo_id,
            source="user",        # Schema constraint: manual|auto|llm|user
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (1) repo_id 없으면 기존 substring 매칭 그대로 (backward compat)
# ─────────────────────────────────────────────────────────────────────────────


def test_compat_backward_compat_without_repo_id(fresh_db) -> None:
    """repo_id 없으면 기존 14B 동작 — substring 매칭만."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        params=[{"name": "order", "type": "long"}],
        # repo_id 미전달 — alias 확장 안 함
    )
    # 14B 동작: var miss → compat=False (한·영 substring 매칭 안 됨)
    assert result["compat"] is False


# ─────────────────────────────────────────────────────────────────────────────
# (2) repo_id 전달 + alias 매칭으로 compat=True
# ─────────────────────────────────────────────────────────────────────────────


def test_compat_with_alias_bridge_korean_to_english(fresh_db) -> None:
    """condition var (Korean) ↔ alias → param name (English) 매칭."""
    _seed_term(
        fqn="term.scm.order_qty",
        label="주문 수량",
        aliases_json='["order", "orderQty", "order count"]',
    )
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        params=[{"name": "order", "type": "long"}],
        repo_id="r",
    )
    # alias "order" 가 term 의 aliases 에 있음 → param "order" 매칭 성공
    assert result["compat"] is True
    assert "order" in result["matched_params"]


def test_compat_with_alias_bridge_english_to_korean(fresh_db) -> None:
    """condition var (English) ↔ alias → param name (Korean)."""
    _seed_term(
        fqn="term.scm.thickness",
        label="두께",
        aliases_json='["thickness", "thk"]',
    )
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "thickness", "op": "<", "value": "0.1", "unit": "mm"}],
        params=[{"name": "두께", "type": "double"}],
        repo_id="r",
    )
    assert result["compat"] is True


def test_compat_alias_bridge_no_term_falls_back_to_substring(fresh_db) -> None:
    """term 없으면 14B substring 매칭으로 fallback (그래도 OK 케이스 통과)."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        params=[{"name": "margin", "type": "double"}],
        repo_id="r",
    )
    assert result["compat"] is True


def test_compat_alias_bridge_other_repo_ignored(fresh_db) -> None:
    """다른 repo 의 alias 는 무시."""
    _seed_term(
        fqn="term.scm.order_qty",
        label="주문 수량",
        aliases_json='["order"]',
        repo_id="other-repo",
    )
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        params=[{"name": "order", "type": "long"}],
        repo_id="r",  # different repo
    )
    # repo 불일치 → alias 매칭 안 됨 → compat=False
    assert result["compat"] is False


# ─────────────────────────────────────────────────────────────────────────────
# (3) type compat 결합 — alias 매칭 후 type 도 체크
# ─────────────────────────────────────────────────────────────────────────────


def test_compat_alias_matched_but_type_incompat(fresh_db) -> None:
    """alias 매칭 성공 + type 불일치 → compat=False (type incompat)."""
    _seed_term(
        fqn="term.scm.order_qty",
        label="주문 수량",
        aliases_json='["order"]',
    )
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    # value="0.5" (decimal) 인데 param type="int" → type incompat
    result = _check_fixture_compat(
        conditions=[{"var": "주문 수량", "op": "=", "value": "0.5", "unit": ""}],
        params=[{"name": "order", "type": "int"}],
        repo_id="r",
    )
    assert result["compat"] is False
    assert "type" in result["mismatch_reason"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# (4) build_gate_hypothesis 가 repo_id 를 _check_fixture_compat 에 전달
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_passes_repo_id_to_compat(fresh_db) -> None:
    """build_gate_hypothesis 가 repo_id 를 fixture_compat 에 전달 → alias 활용."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow

    # 시드: term + method (params=[{name:"order"}], condition var="주문 수량")
    _seed_term(
        fqn="term.scm.order_qty",
        label="주문 수량",
        aliases_json='["order", "orderQty"]',
    )
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.OrderSvc", simple_name="OrderSvc", kind="class",
            source_file="X.java", role="domain", repo_id="r",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.OrderSvc.check", name="check",
            parent_type_fqn="com.x.OrderSvc",
            return_type="void",
            params_json='[{"name":"order","type":"long"}]',
            body_text="if (order == 0) throw new Ex();",
            role="business",
            line_start=1, line_end=10, repo_id="r",
        ))

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation

    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.OrderSvc.check": "if (order == 0) throw;"},
    })
    target = ActionRef(
        action_id="a", code_method_fqn="com.x.OrderSvc.check", repo_id="r",
        location=CodeLocation(file_path="X.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )

    detail = " ".join(p.detail for p in payload.sources)
    # alias bridge 효과: fixture_compat=ok 또는 matched_params 에 'order' surface
    assert "fixture_compat=ok" in detail or "matched_params=['order']" in detail, (
        f"alias bridge 활성 시 fixture_compat=ok 또는 matched_params=['order']. "
        f"sources={[p.detail for p in payload.sources]}"
    )
