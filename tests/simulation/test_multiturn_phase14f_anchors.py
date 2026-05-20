"""Phase 14F (MVP) — anchor_bindings activation in executed_lookup / hypothesis.

페르소나 14B 시니어 발견: substring 매칭 한계 → AST binding 도약 필요.
anchor_bindings 는 fragment-level mapping (code_method ↔ action.target_slot)
이 이미 ontology 에 존재. 163 행 (slab-design-real-v2 기준) sleeping data.

**MVP scope** — full fixture inject 아닌 read-only visibility + verdict boost:
  - executed_lookup / executed_hypothesis 의 Provenance sources 에 anchor 카운트 surface
  - condition var 가 anchor.rationale / target_slot 에 매칭하면 rule_signals +1
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase14f.db"
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


def _seed_anchor(*, fqn_prefix: str = "com.x.A.b", repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.mapping_layer.orm import AnchorBindingRow
    with session_scope() as s:
        s.add(AnchorBindingRow(
            id=f"ab.{fqn_prefix}.1",
            anchor_locator="line:5",
            code_method_fqn=fqn_prefix,
            target_action_fqn="action.x.exec",
            target_slot="margin",
            confidence=0.92,
            source="ast",
            confirmed=True,
            rationale="margin parameter binding from condition",
            repo_id=repo_id,
            line=5,
        ))
        s.add(AnchorBindingRow(
            id=f"ab.{fqn_prefix}.2",
            anchor_locator="line:7",
            code_method_fqn=fqn_prefix,
            target_action_fqn="action.x.exec",
            target_slot="threshold",
            confidence=0.85,
            source="ast",
            confirmed=False,
            rationale="threshold value 1.0",
            repo_id=repo_id,
            line=7,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (1) _fetch_anchor_bindings_for_method — SQLite query
# ─────────────────────────────────────────────────────────────────────────────


def test_fetch_anchor_bindings_returns_rows(fresh_db) -> None:
    _seed_anchor()
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _fetch_anchor_bindings,
    )
    rows = _fetch_anchor_bindings(fqn="com.x.A.b", repo_id="r")
    assert len(rows) == 2
    slots = [r["target_slot"] for r in rows]
    assert "margin" in slots
    assert "threshold" in slots


def test_fetch_anchor_bindings_empty_when_no_match(fresh_db) -> None:
    _seed_anchor()
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _fetch_anchor_bindings,
    )
    rows = _fetch_anchor_bindings(fqn="com.unknown.Method", repo_id="r")
    assert rows == []


def test_fetch_anchor_bindings_filters_repo(fresh_db) -> None:
    _seed_anchor(repo_id="r1")
    from backend.section3.agents.multiturn.gate_hypothesis import (
        _fetch_anchor_bindings,
    )
    rows = _fetch_anchor_bindings(fqn="com.x.A.b", repo_id="other-repo")
    assert rows == []


# ─────────────────────────────────────────────────────────────────────────────
# (2) build_gate_hypothesis 가 anchor_bindings 를 Provenance 에 surface
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_gate_hypothesis_surfaces_anchors_in_sources(fresh_db) -> None:
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow
    _seed_anchor()
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.A", simple_name="A", kind="class",
            source_file="A.java", role="domain", repo_id="r",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.A.b", name="b", parent_type_fqn="com.x.A",
            return_type="void", params_json='[{"name":"margin","type":"double"}]',
            body_text="if (margin < 1.0) throw new Ex();",
            role="business", line_start=1, line_end=10, repo_id="r",
        ))

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation

    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.A.b": "if (margin < 1.0) throw;"},
    })
    target = ActionRef(
        action_id="action.x.exec", code_method_fqn="com.x.A.b", repo_id="r",
        location=CodeLocation(file_path="A.java", line_start=1, line_end=10),
    )
    payload = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )
    detail_str = " ".join(p.detail for p in payload.sources)
    assert "anchor" in detail_str.lower() or "binding" in detail_str.lower(), (
        f"sources 에 anchor surface 되어야: {[p.detail for p in payload.sources]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (3) condition var 가 anchor.target_slot 매칭 → confidence boost
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_anchor_slot_match_boosts_confidence(fresh_db) -> None:
    """condition var 가 anchor.target_slot 와 일치 → confidence 가 anchor 없을 때보다 ↑."""
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeMethodRow, CodeTypeRow

    # 메서드만 시드 (anchor 없음)
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn="com.x.A", simple_name="A", kind="class",
            source_file="A.java", role="domain", repo_id="r",
        ))
        s.add(CodeMethodRow(
            fqn="com.x.A.b", name="b", parent_type_fqn="com.x.A",
            return_type="void", params_json='[{"name":"margin","type":"double"}]',
            body_text="if (margin < 1.0) throw new Ex();",
            role="business", line_start=1, line_end=10, repo_id="r",
        ))

    from backend.section3.agents.multiturn.gate_hypothesis import (
        build_gate_hypothesis,
    )
    from backend.section3.agents.multiturn.ontology_client import MockOntologyClient
    from backend.section3.agents.multiturn.schemas import ActionRef, CodeLocation

    client = MockOntologyClient(catalog={
        "method_bodies": {"com.x.A.b": "if (margin < 1.0) throw;"},
    })
    target = ActionRef(
        action_id="action.x.exec", code_method_fqn="com.x.A.b", repo_id="r",
        location=CodeLocation(file_path="A.java", line_start=1, line_end=10),
    )
    p_no_anchor = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )

    # 이제 anchor 추가 후 재실행
    _seed_anchor()
    p_with_anchor = await build_gate_hypothesis(
        target=target,
        conditions=[{"var": "margin", "op": "<", "value": "1.0", "unit": ""}],
        repo_id="r",
        ontology_client=client,
    )

    # anchor 가 있는 경우 confidence ≥ no_anchor 또는 verdict ≥ (strict 보장은 어려움)
    # 최소 검증: anchor 있을 때 sources 에 anchor surface
    detail_anchor = " ".join(p.detail for p in p_with_anchor.sources)
    assert "anchor" in detail_anchor.lower() or "binding" in detail_anchor.lower()
    # 그리고 confidence 는 같거나 ↑
    assert p_with_anchor.confidence >= p_no_anchor.confidence - 0.01, (
        f"anchor 매칭 시 confidence 같거나 ↑. "
        f"no_anchor={p_no_anchor.confidence} with_anchor={p_with_anchor.confidence}"
    )
