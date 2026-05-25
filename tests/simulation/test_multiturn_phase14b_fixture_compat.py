"""Phase 14B (MVP) — fixture compatibility check.

Phase 13c 의 verdict 는 heuristic 만 — fixture 실행 안 함. 페르소나 시니어 / PM
검증에서 "verdict 가 실제 실행 결과 아닌 추론" 이라는 한계가 지적됨.

Full fixture invoke (sim_v2 fixture run) 는 multi-day. **MVP scope**:
  - conditions 의 var 가 target method 의 param 명/타입과 매칭하는지 사전 체크
  - 매칭 → "fixture-ready" 시그널 (verdict 강화)
  - 미매칭 → "param-incompat" 경고 (likely_no 약한 신호)

이는 실 fixture 실행 없이도 "이 hypothesis 가 실제로 테스트 가능한가" 의 가치
surface.
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase14b.db"
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
# (1) _check_fixture_compat — conditions × method params
# ─────────────────────────────────────────────────────────────────────────────


def test_compat_when_var_matches_param_name() -> None:
    """condition.var 가 method param 이름 substring 매칭 시 compat=True."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        params=[
            {"name": "margin", "type": "double"},
            {"name": "id", "type": "long"},
        ],
    )
    assert result["compat"] is True
    assert result["matched_params"] == ["margin"]


def test_compat_when_var_korean_substring_param() -> None:
    """condition.var 가 한국어인데 param name 도 한국어 매칭."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    # 한국어 param 명 가능 (예: 한국어 Python 변수)
    result = _check_fixture_compat(
        conditions=[{"var": "주문 수량", "op": "=", "value": "0", "unit": ""}],
        params=[
            {"name": "주문수량", "type": "int"},
        ],
    )
    assert result["compat"] is True


def test_incompat_when_no_param_matches() -> None:
    """condition var 가 어떤 param 도 매칭 X → compat=False."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        params=[
            {"name": "orderId", "type": "long"},
            {"name": "name", "type": "String"},
        ],
    )
    assert result["compat"] is False
    assert result["mismatch_reason"]


def test_value_type_incompat_with_param_type() -> None:
    """var 매칭 하지만 value 의 type 이 param type 과 불일치 → compat=False."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    # value="0.1" 인데 param type 이 "int" 면 incompat
    result = _check_fixture_compat(
        conditions=[{"var": "qty", "op": "=", "value": "0.1", "unit": ""}],
        params=[
            {"name": "qty", "type": "int"},
        ],
    )
    assert result["compat"] is False
    assert "type" in result["mismatch_reason"].lower()


def test_value_type_compat_decimal_to_double() -> None:
    """value 가 decimal 인데 param 이 double → compat=True."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "rate", "op": ">", "value": "0.95", "unit": ""}],
        params=[{"name": "rate", "type": "double"}],
    )
    assert result["compat"] is True


def test_empty_params_treated_as_unknown_not_incompat() -> None:
    """method 가 param 없음 (getter 등) → compat=None (모름)."""
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(
        conditions=[{"var": "x", "op": "<", "value": "1", "unit": ""}],
        params=[],
    )
    assert result["compat"] is None   # unknown — verdict 영향 없음


def test_empty_conditions_treated_as_unknown() -> None:
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _check_fixture_compat,
    )
    result = _check_fixture_compat(conditions=[], params=[{"name": "x", "type": "int"}])
    assert result["compat"] is None


# ─────────────────────────────────────────────────────────────────────────────
# (2) build_gate_hypothesis 가 fixture_compat 결과를 sources / reasoning 에 반영
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_surfaces_fixture_compat_in_sources(
    fresh_db,
) -> None:
    """compat 결과가 Provenance sources 에 surface (DB 시드 후)."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow

    # CodeType + CodeMethod 시드 (params_json 포함)
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.A", simple_name="A", kind="class",
            source_file="A.java", role="domain", repo_id="r",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.A.b", name="b", parent_type_fqn="com.x.A",
            return_type="void",
            params_json='[{"name":"margin","type":"double"}]',
            body_text="if (margin < 1.0) throw new Ex();",
            role="business",
            line_start=1, line_end=10, repo_id="r",
        ))

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation,
    )

    body = "void f(double margin) { if (margin < 1.0) throw new Ex(); }"
    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.A.b": body},
    })
    target = ActionRef(
        action_id="a", code_method_fqn="com.x.A.b", repo_id="r",
        location=CodeLocation(file_path="A.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )
    detail_str = " ".join(p.detail for p in payload.sources)
    assert "fixture" in detail_str.lower() or "compat" in detail_str.lower(), (
        f"sources 에 fixture_compat 신호가 surface 되어야. "
        f"sources={[p.detail for p in payload.sources]}"
    )
