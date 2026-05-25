"""Phase 16G — alias source 확장: CodeField @Column + Action.aliases_json.

시니어 16B 권고 #3. 현재 `_expand_var_to_aliases` 는 business_terms.aliases_json
한 source 만 본다. 데이터 갱신 없이 즉시 활용 가능한 추가 source 2개:

1. `CodeFieldRow.annotations_json` — `@Column(name=XXX)` 패턴이 Java field name ↔
   DB column name 직접 bridge. e.g., field `orderNo` + `@Column(name=ORDER_NO)` →
   "orderNo" ↔ "ORDER_NO" alias.

2. `ActionRow.aliases_json` — 129 action rows 이미 aliases 보유. BusinessTerm 에
   미커버된 alias 도 Action 단계에서 surface.

backward compat: BusinessTerm 우선, repo_id=None 동작 무변동.
"""
from __future__ import annotations

import pytest

from backend.modeling.persistence import database as db_mod


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase16g.db"
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


def _seed_code_type(*, fqn: str, name: str, kind: str = "entity", repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeTypeRow
    with session_scope() as s:
        s.add(CodeTypeRow(
            fqn=fqn,
            simple_name=name,
            kind=kind,
            package="",
            repo_id=repo_id,
        ))


def _seed_code_field(*, type_fqn: str, name: str, ftype: str = "String", ann_json: str = "[]"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.code_layer.orm import CodeFieldRow
    with session_scope() as s:
        s.add(CodeFieldRow(
            type_fqn=type_fqn,
            name=name,
            type=ftype,
            annotations_json=ann_json,
        ))


def _seed_action(*, fqn: str, label: str, aliases_json: str, repo_id: str = "r"):
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.mapping_layer.orm import ActionRow
    with session_scope() as s:
        s.add(ActionRow(
            fqn=fqn,
            label=label,
            aliases_json=aliases_json,
            domain="scm",
            kind="atomic",
            repo_id=repo_id,
        ))


# ─────────────────────────────────────────────────────────────────────────────
# (1) CodeField @Column(name=XXX) → bridge field name ↔ DB column name
# ─────────────────────────────────────────────────────────────────────────────


def test_code_field_column_annotation_bridges_alias(fresh_db) -> None:
    """field=orderNo + @Column(name=ORDER_NO) → var=orderNo 가 ORDER_NO 도 반환."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_code_type(fqn="com.x.SdOrderJpo", name="SdOrderJpo")
    _seed_code_field(
        type_fqn="com.x.SdOrderJpo",
        name="orderNo",
        ann_json='["@Column(name=ORDER_NO,length=20)"]',
    )

    aliases = _expand_var_to_aliases(var="orderNo", repo_id="r")
    assert any(a == "ORDER_NO" for a in aliases), (
        f"@Column(name=ORDER_NO) 가 alias bridge 되어야. aliases={aliases}"
    )


def test_code_field_column_reverse_lookup(fresh_db) -> None:
    """var=ORDER_NO 로 검색 시 field=orderNo 도 alias 로 반환."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_code_type(fqn="com.x.SdOrderJpo", name="SdOrderJpo")
    _seed_code_field(
        type_fqn="com.x.SdOrderJpo",
        name="orderNo",
        ann_json='["@Column(name=ORDER_NO,length=20)"]',
    )

    aliases = _expand_var_to_aliases(var="ORDER_NO", repo_id="r")
    assert any(a == "orderNo" for a in aliases), (
        f"ORDER_NO 가 field orderNo 와 양방향 bridge 되어야. aliases={aliases}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (2) ActionRow.aliases_json — strict 매칭 시 label + aliases 반환
# ─────────────────────────────────────────────────────────────────────────────


def test_action_aliases_json_picks_up_match(fresh_db) -> None:
    """Action label='thickness check' aliases=['두께검증'] → var='두께검증' alias bridge."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_action(
        fqn="action.scm.thickness_validate",
        label="thickness check",
        aliases_json='["두께검증", "thickness validate"]',
    )

    aliases = _expand_var_to_aliases(var="두께검증", repo_id="r")
    # action 의 label + aliases 모두 후보로
    assert "thickness check" in aliases, (
        f"Action label 이 alias 로 surface 되어야. aliases={aliases}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# (3) Union — BusinessTerm + Action + CodeField 동시 매칭
# ─────────────────────────────────────────────────────────────────────────────


def test_union_of_all_sources(fresh_db) -> None:
    """BusinessTerm + Action + CodeField 모두 thickness 관련 시 alias 합집합."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases
    from backend.modeling.persistence.database import session_scope
    from backend.modeling.domain_layer.orm import BusinessTermRow

    with session_scope() as s:
        s.add(BusinessTermRow(
            fqn="term.scm.thickness",
            label="두께",
            aliases_json='["thickness", "thick"]',
            kind="atomic",
            domain="scm",
            description="",
            confirmed=True,
            repo_id="r",
            source="user",
        ))
    _seed_action(
        fqn="action.scm.thick_op",
        label="thickness operation",
        aliases_json='["두께작업"]',
    )
    _seed_code_type(fqn="com.x.Slab", name="Slab")
    _seed_code_field(
        type_fqn="com.x.Slab",
        name="thickness",
        ann_json='["@Column(name=THICKNESS,precision=6,scale=2)"]',
    )

    aliases = _expand_var_to_aliases(var="thickness", repo_id="r")
    # 최소 BusinessTerm 의 두께 + CodeField 의 THICKNESS 가 surface
    aliases_lower = {a.lower() for a in aliases}
    assert "두께" in aliases, f"BusinessTerm 두께 surface. aliases={aliases}"
    assert "thickness" in aliases_lower, f"variant 의 thickness surface. aliases={aliases}"
    assert "THICKNESS" in aliases, f"CodeField @Column THICKNESS surface. aliases={aliases}"


# ─────────────────────────────────────────────────────────────────────────────
# (4) Backward compat — repo_id=None 동작 무변동
# ─────────────────────────────────────────────────────────────────────────────


def test_backward_compat_no_repo_id(fresh_db) -> None:
    """repo_id=None → 원본만 (BusinessTerm/Action/CodeField 모두 조회 안 함)."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_code_type(fqn="com.x.SdOrderJpo", name="SdOrderJpo")
    _seed_code_field(
        type_fqn="com.x.SdOrderJpo",
        name="orderNo",
        ann_json='["@Column(name=ORDER_NO,length=20)"]',
    )
    _seed_action(
        fqn="action.x",
        label="something",
        aliases_json='["orderNo"]',
    )

    aliases = _expand_var_to_aliases(var="orderNo", repo_id=None)
    assert aliases == ["orderNo"], f"repo_id=None 이면 원본만. aliases={aliases}"


# ─────────────────────────────────────────────────────────────────────────────
# (5) Graceful — DB miss / 매칭 0 → 원본만
# ─────────────────────────────────────────────────────────────────────────────


def test_no_match_returns_base(fresh_db) -> None:
    """DB 에 매칭 없으면 var 자체만 반환."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    aliases = _expand_var_to_aliases(var="unknown_var_xyz", repo_id="r")
    assert aliases == ["unknown_var_xyz"]


# ─────────────────────────────────────────────────────────────────────────────
# (6) @Column 부분 패턴 — name= 외 다른 속성 무시
# ─────────────────────────────────────────────────────────────────────────────


def test_column_other_attrs_ignored(fresh_db) -> None:
    """@Column(length=20) 처럼 name= 없으면 alias 추출 안 함."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_code_type(fqn="com.x.T", name="T")
    _seed_code_field(
        type_fqn="com.x.T",
        name="someField",
        ann_json='["@Column(length=20,nullable=false)"]',  # name= 없음
    )
    aliases = _expand_var_to_aliases(var="someField", repo_id="r")
    # 원본만
    assert aliases == ["someField"]


# ─────────────────────────────────────────────────────────────────────────────
# (7) Wrong repo isolation
# ─────────────────────────────────────────────────────────────────────────────


def test_repo_id_isolation(fresh_db) -> None:
    """다른 repo_id 의 entry 는 alias source 가 되지 않아야."""
    from backend.section3.agents.multiturn.gate_hypothesis import _expand_var_to_aliases

    _seed_code_type(fqn="com.x.T", name="T", repo_id="other_repo")
    _seed_code_field(
        type_fqn="com.x.T",
        name="orderNo",
        ann_json='["@Column(name=ORDER_NO,length=20)"]',
    )
    aliases = _expand_var_to_aliases(var="orderNo", repo_id="r")
    # other_repo 의 entry 는 보이지 않음 → 원본만
    assert aliases == ["orderNo"], f"repo isolation 위반. aliases={aliases}"
