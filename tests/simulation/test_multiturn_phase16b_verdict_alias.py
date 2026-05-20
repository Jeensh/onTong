"""Phase 16B — alias bridge in `_infer_verdict` body matching.

Phase 16A 시니어 발견: `_check_fixture_compat` 만 alias bridge 활성, `_infer_verdict`
의 body matching 은 raw var 만 검색.

예: "두께" var + body 가 "slabThickness" 사용 → "두께" substring 매칭 실패 → likely_no.
해결: var 의 한·영 alias 도 함께 body lookup. 단일 alias 라도 body 에 hit 하면 var
match counted.
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase16b.db"
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


def _seed_thickness_term(repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow
    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn="term.scm.thickness",
            label="두께",
            aliases_json='["thickness", "Thickness", "thk", "slabThickness"]',
            kind="atomic",
            domain="scm",
            description="",
            confirmed=True,
            repo_id=repo_id,
            source="user",
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (1) _infer_verdict 가 var_aliases 인자 받아 body match 에 활용
# ─────────────────────────────────────────────────────────────────────────────


def test_infer_verdict_with_var_aliases_matches_body() -> None:
    """var="두께" + var_aliases=["thickness"] → body 의 "if (thickness < 0.1)" 매칭."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "void check(double thickness) { if (thickness < 0.1) throw new Ex(); }"
    verdict, _, body_sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        evidence=[],
        var_aliases_per_cond=[["두께", "thickness"]],
    )
    # body 안에 "thickness" 가 있어 var match counted
    # + value "0.1" word-boundary match → body_signals 강함
    # + expression pattern `thickness\s*<\s*0.1` 매칭 → has_expression_match=True
    assert verdict in ("yes", "likely_yes"), (
        f"alias 활용 시 body match → likely_yes 이상. v={verdict} sig={body_sig}"
    )


def test_infer_verdict_without_aliases_misses_body_match() -> None:
    """var="두께" + var_aliases=None (16B 비활성) → 'thickness' body 매칭 X (regression baseline)."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "void check(double thickness) { if (thickness < 0.1) throw new Ex(); }"
    verdict, _, body_sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        evidence=[],
        # var_aliases_per_cond 미전달 (None)
    )
    # 14D 동작: var="두께" 가 body 와 매칭 안 됨. var miss false positive 강등
    assert verdict in ("likely_no", "unknown"), (
        f"alias 없으면 body match X → likely_no/unknown 회귀 OK. v={verdict}"
    )


def test_infer_verdict_aliases_with_expression_match() -> None:
    """alias 가 매칭하고 expression pattern (alias op value) 까지 매칭 → verdict=likely_yes/yes."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (thickness < 0.1) throw 'TOO_THIN';"
    # rule_signals=0 면 likely_yes, ≥1 면 yes (verdict logic)
    verdict, reasoning, body_sig, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        evidence=[],
        var_aliases_per_cond=[["두께", "thickness"]],
    )
    assert verdict in ("yes", "likely_yes"), (
        f"alias + expression match → likely_yes (rule 없으면) 또는 yes. "
        f"v={verdict} body_sig={body_sig}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (2) build_gate_hypothesis 가 var_aliases 를 _infer_verdict 에 전달
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_uses_alias_in_verdict(fresh_db) -> None:
    """end-to-end: "두께" var + body 가 "thickness" 사용 → verdict=likely_yes/yes."""
    _seed_thickness_term()

    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.SdT", simple_name="SdT", kind="class",
            source_file="x.java", role="domain", repo_id="r",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.SdT.exec", name="exec",
            parent_type_fqn="com.x.SdT", return_type="void",
            params_json='[{"name":"thickness","type":"double"}]',
            body_text="if (thickness < 0.1) throw new Ex();",
            role="business",
            line_start=1, line_end=10, repo_id="r",
        ))

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation

    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.SdT.exec": "if (thickness < 0.1) throw new Ex();"},
    })
    target = ActionRef(
        action_id="a", code_method_fqn="com.x.SdT.exec", repo_id="r",
        location=CodeLocation(file_path="x.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "두께", "op": "<", "value": "0.1", "unit": "mm"}],
        repo_id="r",
        ontology_client=client,
    )

    # 16B 효과: alias "thickness" body match → verdict=yes/likely_yes
    assert payload.verdict in ("yes", "likely_yes"), (
        f"alias bridge 활용 verdict={payload.verdict}, reasoning={payload.reasoning!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (3) backward compat — var_aliases_per_cond=None 이면 기존 동작
# ─────────────────────────────────────────────────────────────────────────────


def test_infer_verdict_backward_compat_no_aliases_arg() -> None:
    """기존 호출 (var_aliases_per_cond 없이) 도 작동."""
    from backend.section3.agents.multiturn.gate_hypothesis import _infer_verdict

    body = "if (margin < 1.0) throw;"
    verdict, _, _, _ = _infer_verdict(
        body_text=body,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        evidence=[],
    )
    # margin 영문 → body match → likely_yes/yes
    assert verdict in ("yes", "likely_yes")
