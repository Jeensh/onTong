"""OD-11-C2 TDD — Round 2 concept-bridge DTOs.

`backend/modeling/mapping/mapping_models.py` 의 Pydantic DTO 4종 검증:

- `BusinessTerm` (노드)
- `BusinessRule` (노드)
- `ConceptBinding` (REALIZES 엣지 DTO)
- `ConceptBindingSet` (primary 유일성 검증 집합)
- `ResolutionAuditLog` (Term Resolution 감사 로그)

Spec: `toClaude/modeling/round2-concept-bridge.html` rev.2 §2, §3-1, §4.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.modeling.mapping.mapping_models import (
    BindingScope,
    BindingSource,
    BusinessProcess,
    BusinessRule,
    BusinessTerm,
    BusinessTermSource,
    ConceptBinding,
    ConceptBindingSet,
    ParentProcessBinding,
    ParentProcessBindingSet,
    PartOfBinding,
    ResolutionAuditLog,
    ResolutionSource,
    ResponsibilityKind,
    Role,
    RoleBinding,
    RoleKind,
    RuleSeverity,
)

_NOW = datetime(2026, 4, 20, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
def test_enum_values() -> None:
    assert BusinessTermSource.MANUAL.value == "manual"
    assert BusinessTermSource.EXTRACTED.value == "extracted"
    assert BusinessTermSource.LLM_PROPOSED.value == "llm_proposed"

    assert BindingSource.MANUAL.value == "manual"
    assert BindingSource.NAME_MATCH.value == "name_match"
    assert BindingSource.EMBEDDING.value == "embedding"
    assert BindingSource.LLM.value == "llm"

    assert BindingScope.PRIMARY.value == "primary"
    assert BindingScope.PARTIAL.value == "partial"

    assert RuleSeverity.HARD.value == "hard"
    assert RuleSeverity.SOFT.value == "soft"

    assert ResolutionSource.EXACT.value == "exact"
    assert ResolutionSource.ALIAS.value == "alias"
    assert ResolutionSource.EMBEDDING.value == "embedding"
    assert ResolutionSource.LLM.value == "llm"
    assert ResolutionSource.MISS.value == "miss"


# ---------------------------------------------------------------------------
# BusinessTerm
# ---------------------------------------------------------------------------
def _term(qn: str = "inventory.safety_stock", **over: object) -> BusinessTerm:
    base: dict[str, object] = {
        "qualified_name": qn,
        "canonical_label": "안전재고",
        "domain": "inventory",
        "source": BusinessTermSource.MANUAL,
        "created_at": _NOW,
    }
    base.update(over)
    return BusinessTerm(**base)  # type: ignore[arg-type]


def test_business_term_defaults() -> None:
    t = _term()
    assert t.aliases == []
    assert t.description == ""
    assert t.embedding is None
    assert t.confirmed is False


def test_business_term_accepts_aliases_and_embedding() -> None:
    t = _term(aliases=["Safety Stock", "SS"], embedding=[0.1, 0.2, 0.3])
    assert t.aliases == ["Safety Stock", "SS"]
    assert t.embedding == [0.1, 0.2, 0.3]


def test_business_term_alias_duplicates_case_insensitive_rejected() -> None:
    with pytest.raises(ValidationError):
        _term(aliases=["SS", "ss"])


def test_business_term_alias_empty_string_rejected() -> None:
    with pytest.raises(ValidationError):
        _term(aliases=["SS", "   "])


def test_business_term_qualified_name_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _term(qn="")


def test_business_term_canonical_label_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _term(canonical_label="")


def test_business_term_source_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _term(source="bogus")  # type: ignore[arg-type]


def test_business_term_json_round_trip() -> None:
    t = _term(aliases=["SS"], confirmed=True, description="재고 하한선")
    s = t.model_dump_json()
    u = BusinessTerm.model_validate_json(s)
    assert u == t


# ---------------------------------------------------------------------------
# BusinessRule
# ---------------------------------------------------------------------------
def _rule(**over: object) -> BusinessRule:
    base: dict[str, object] = {
        "qualified_name": "inventory.rule.below_safety_stock_triggers_order",
        "statement": "현재 재고 < 안전재고 이면 자동 발주",
        "terms_ref": ["inventory.safety_stock"],
        "severity": RuleSeverity.HARD,
        "source": "기준서 §3.2",
        "created_at": _NOW,
    }
    base.update(over)
    return BusinessRule(**base)  # type: ignore[arg-type]


def test_business_rule_defaults() -> None:
    r = _rule()
    assert r.confirmed is False


def test_business_rule_severity_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _rule(severity="warning")  # type: ignore[arg-type]


def test_business_rule_terms_ref_can_be_empty_for_draft() -> None:
    r = _rule(terms_ref=[])
    assert r.terms_ref == []


def test_business_rule_statement_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _rule(statement="")


# ---------------------------------------------------------------------------
# ConceptBinding
# ---------------------------------------------------------------------------
def _binding(
    term_fqn: str = "inventory.safety_stock",
    code_fqn: str = "com.acme.inventory.SafetyStockCalculator.compute",
    scope: BindingScope = BindingScope.PRIMARY,
    **over: object,
) -> ConceptBinding:
    base: dict[str, object] = {
        "term_fqn": term_fqn,
        "code_fqn": code_fqn,
        "scope": scope,
        "confidence": 1.0,
        "source": BindingSource.MANUAL,
        "confirmed": True,
        "confirmed_by": "leader@acme",
        "created_at": _NOW,
    }
    base.update(over)
    return ConceptBinding(**base)  # type: ignore[arg-type]


def test_concept_binding_basic_construction() -> None:
    b = _binding()
    assert b.scope is BindingScope.PRIMARY
    assert b.confidence == 1.0


def test_concept_binding_confidence_range() -> None:
    with pytest.raises(ValidationError):
        _binding(confidence=-0.01)
    with pytest.raises(ValidationError):
        _binding(confidence=1.01)
    _binding(confidence=0.0)
    _binding(confidence=1.0)


def test_concept_binding_scope_and_source_enums_validate() -> None:
    with pytest.raises(ValidationError):
        _binding(scope="main")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        _binding(source="fuzzy")  # type: ignore[arg-type]


def test_concept_binding_unconfirmed_allows_null_confirmer() -> None:
    b = _binding(confirmed=False, confirmed_by=None, source=BindingSource.LLM, confidence=0.4)
    assert b.confirmed is False
    assert b.confirmed_by is None


# ---------------------------------------------------------------------------
# ConceptBindingSet — primary uniqueness invariant
# ---------------------------------------------------------------------------
def test_concept_binding_set_empty_ok() -> None:
    ConceptBindingSet(bindings=[])


def test_concept_binding_set_single_primary_ok() -> None:
    s = ConceptBindingSet(bindings=[_binding()])
    assert len(s.bindings) == 1


def test_concept_binding_set_multiple_partials_same_code_ok() -> None:
    code = "com.acme.order.OrderService.place"
    bindings = [
        _binding(term_fqn="order.placement", code_fqn=code, scope=BindingScope.PRIMARY),
        _binding(term_fqn="credit.check", code_fqn=code, scope=BindingScope.PARTIAL, confidence=0.88),
        _binding(term_fqn="inventory.allocation", code_fqn=code, scope=BindingScope.PARTIAL, confidence=0.82),
    ]
    s = ConceptBindingSet(bindings=bindings)
    assert len(s.bindings) == 3


def test_concept_binding_set_primary_for_different_codes_ok() -> None:
    bindings = [
        _binding(term_fqn="inventory.safety_stock", code_fqn="a.b.C.m1"),
        _binding(term_fqn="inventory.safety_stock", code_fqn="a.b.C.m2"),
        _binding(term_fqn="inventory.safety_stock", code_fqn="a.b.C.m3"),
    ]
    s = ConceptBindingSet(bindings=bindings)
    assert len(s.bindings) == 3


def test_concept_binding_set_two_primaries_same_code_rejected() -> None:
    code = "com.acme.order.OrderService.place"
    bindings = [
        _binding(term_fqn="order.placement", code_fqn=code, scope=BindingScope.PRIMARY),
        _binding(term_fqn="credit.check", code_fqn=code, scope=BindingScope.PRIMARY),
    ]
    with pytest.raises(ValidationError) as ei:
        ConceptBindingSet(bindings=bindings)
    assert "primary" in str(ei.value).lower()


def test_concept_binding_set_duplicate_term_code_pair_rejected() -> None:
    """같은 (term, code) pair 2회는 중복 — partial 이어도 모호성 유발."""
    pair = {"term_fqn": "x", "code_fqn": "a.b.C.m"}
    bindings = [
        _binding(scope=BindingScope.PARTIAL, confidence=0.5, **pair),
        _binding(scope=BindingScope.PARTIAL, confidence=0.9, **pair),
    ]
    with pytest.raises(ValidationError):
        ConceptBindingSet(bindings=bindings)


def test_concept_binding_set_json_round_trip_preserves_invariant() -> None:
    code = "a.b.C.m"
    s = ConceptBindingSet(
        bindings=[
            _binding(term_fqn="t1", code_fqn=code, scope=BindingScope.PRIMARY),
            _binding(term_fqn="t2", code_fqn=code, scope=BindingScope.PARTIAL, confidence=0.7),
        ]
    )
    raw = s.model_dump_json()
    restored = ConceptBindingSet.model_validate_json(raw)
    assert restored == s


# ---------------------------------------------------------------------------
# ResolutionAuditLog
# ---------------------------------------------------------------------------
def test_resolution_audit_log_hit() -> None:
    log = ResolutionAuditLog(
        query_term="안전재고",
        resolved_term_fqn="inventory.safety_stock",
        resolution_source=ResolutionSource.EXACT,
        confidence=1.0,
        confirmed=True,
        timestamp=_NOW,
    )
    assert log.resolution_source is ResolutionSource.EXACT


def test_resolution_audit_log_miss_allows_null_fqn() -> None:
    log = ResolutionAuditLog(
        query_term="Slab 폭 조정",
        resolved_term_fqn=None,
        resolution_source=ResolutionSource.MISS,
        confidence=0.0,
        confirmed=False,
        timestamp=_NOW,
    )
    assert log.resolved_term_fqn is None


def test_resolution_audit_log_confidence_bounded() -> None:
    with pytest.raises(ValidationError):
        ResolutionAuditLog(
            query_term="x",
            resolved_term_fqn=None,
            resolution_source=ResolutionSource.MISS,
            confidence=1.5,
            confirmed=False,
            timestamp=_NOW,
        )


def test_resolution_audit_log_enum_validates() -> None:
    with pytest.raises(ValidationError):
        ResolutionAuditLog(
            query_term="x",
            resolved_term_fqn="y",
            resolution_source="guess",  # type: ignore[arg-type]
            confidence=0.5,
            confirmed=False,
            timestamp=_NOW,
        )


# ===========================================================================
# OD-11-D1.5 — Phase D Layer A (organization) DTOs
# ---------------------------------------------------------------------------
# 결정 근거:
#   Q1=C : PARENT_PROCESS 는 엣지 (BusinessProcess 노드에 parent 필드 없음)
#   Q2=A : Role kind="team" 고정, qualified_name 은 "team." 으로 시작
# ===========================================================================
def test_org_enum_values() -> None:
    assert RoleKind.TEAM.value == "team"

    assert ResponsibilityKind.OWNER.value == "owner"
    assert ResponsibilityKind.APPROVER.value == "approver"
    assert ResponsibilityKind.REVIEWER.value == "reviewer"
    assert ResponsibilityKind.NOTIFY.value == "notify"


# ---------------------------------------------------------------------------
# BusinessProcess
# ---------------------------------------------------------------------------
def _process(qn: str = "proc.inventory.safety_stock_management", **over: object) -> BusinessProcess:
    base: dict[str, object] = {
        "qualified_name": qn,
        "canonical_label": "안전재고 관리",
        "created_at": _NOW,
    }
    base.update(over)
    return BusinessProcess(**base)  # type: ignore[arg-type]


def test_business_process_defaults() -> None:
    p = _process()
    assert p.description == ""


def test_business_process_requires_non_empty_qualified_name() -> None:
    with pytest.raises(ValidationError):
        _process(qn="")


def test_business_process_requires_non_empty_label() -> None:
    with pytest.raises(ValidationError):
        _process(canonical_label="")


def test_business_process_has_no_parent_field() -> None:
    """Q1=C: 계층은 엣지로 표현. parent_process_fqn 같은 필드는 존재하면 안 됨."""
    p = _process()
    assert not hasattr(p, "parent_process_fqn")
    assert not hasattr(p, "parent_fqn")


def test_business_process_json_round_trip() -> None:
    p = _process(description="재고 하한선 관리 프로세스")
    raw = p.model_dump_json()
    u = BusinessProcess.model_validate_json(raw)
    assert u == p


# ---------------------------------------------------------------------------
# Role (Q2=A team-only)
# ---------------------------------------------------------------------------
def _role(qn: str = "team.inventory_mgmt", **over: object) -> Role:
    base: dict[str, object] = {
        "qualified_name": qn,
        "kind": RoleKind.TEAM,
        "canonical_label": "재고관리팀",
        "created_at": _NOW,
    }
    base.update(over)
    return Role(**base)  # type: ignore[arg-type]


def test_role_defaults() -> None:
    r = _role()
    assert r.kind is RoleKind.TEAM
    assert r.description == ""
    assert r.contact == ""


def test_role_accepts_contact() -> None:
    r = _role(contact="#inventory-ops", description="재고 입출고 운영")
    assert r.contact == "#inventory-ops"


def test_role_qualified_name_must_start_with_team_dot() -> None:
    """Q2=A: 조직 레이어는 팀 단위로만 시작. 개인/직함 FQN 거부."""
    with pytest.raises(ValidationError):
        _role(qn="person.hong_gildong")
    with pytest.raises(ValidationError):
        _role(qn="title.inventory_manager")
    with pytest.raises(ValidationError):
        _role(qn="inventory_mgmt")


def test_role_qualified_name_team_prefix_accepted() -> None:
    r1 = _role(qn="team.inventory_mgmt")
    r2 = _role(qn="team.production_ops", canonical_label="생산관리팀")
    r3 = _role(qn="team.qa", canonical_label="품질관리팀")
    assert r1.qualified_name == "team.inventory_mgmt"
    assert r2.canonical_label == "생산관리팀"
    assert r3.qualified_name == "team.qa"


def test_role_kind_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _role(kind="person")  # type: ignore[arg-type]


def test_role_json_round_trip() -> None:
    r = _role(contact="#ops", description="x")
    raw = r.model_dump_json()
    u = Role.model_validate_json(raw)
    assert u == r


# ---------------------------------------------------------------------------
# PartOfBinding
# ---------------------------------------------------------------------------
def _part_of(**over: object) -> PartOfBinding:
    base: dict[str, object] = {
        "code_fqn": "com.acme.inventory.SafetyStockCalculator.compute",
        "process_fqn": "proc.inventory.safety_stock_management",
        "created_at": _NOW,
    }
    base.update(over)
    return PartOfBinding(**base)  # type: ignore[arg-type]


def test_part_of_binding_basic() -> None:
    b = _part_of()
    assert b.code_fqn.startswith("com.acme")
    assert b.process_fqn.startswith("proc.")


def test_part_of_binding_fqns_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _part_of(code_fqn="")
    with pytest.raises(ValidationError):
        _part_of(process_fqn="")


def test_part_of_binding_json_round_trip() -> None:
    b = _part_of()
    raw = b.model_dump_json()
    u = PartOfBinding.model_validate_json(raw)
    assert u == b


# ---------------------------------------------------------------------------
# RoleBinding
# ---------------------------------------------------------------------------
def _role_binding(**over: object) -> RoleBinding:
    base: dict[str, object] = {
        "role_fqn": "team.inventory_mgmt",
        "target_fqn": "proc.inventory.safety_stock_management",
        "responsibility_kind": ResponsibilityKind.OWNER,
        "created_at": _NOW,
    }
    base.update(over)
    return RoleBinding(**base)  # type: ignore[arg-type]


def test_role_binding_basic_owner() -> None:
    b = _role_binding()
    assert b.responsibility_kind is ResponsibilityKind.OWNER


def test_role_binding_accepts_all_responsibility_kinds() -> None:
    for rk in (
        ResponsibilityKind.OWNER,
        ResponsibilityKind.APPROVER,
        ResponsibilityKind.REVIEWER,
        ResponsibilityKind.NOTIFY,
    ):
        b = _role_binding(responsibility_kind=rk)
        assert b.responsibility_kind is rk


def test_role_binding_responsibility_kind_enum_validates() -> None:
    with pytest.raises(ValidationError):
        _role_binding(responsibility_kind="observer")  # type: ignore[arg-type]


def test_role_binding_rejects_non_team_role_fqn() -> None:
    """Q2=A: 조직 레이어는 팀만. 개인/직함 role_fqn 거부."""
    with pytest.raises(ValidationError):
        _role_binding(role_fqn="person.hong")
    with pytest.raises(ValidationError):
        _role_binding(role_fqn="title.manager")
    with pytest.raises(ValidationError):
        _role_binding(role_fqn="inventory_mgmt")


def test_role_binding_target_fqn_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _role_binding(target_fqn="")


def test_role_binding_json_round_trip() -> None:
    b = _role_binding(responsibility_kind=ResponsibilityKind.APPROVER)
    raw = b.model_dump_json()
    u = RoleBinding.model_validate_json(raw)
    assert u == b


# ---------------------------------------------------------------------------
# ParentProcessBinding (Q1=C self-ref 금지 + cycle 금지)
# ---------------------------------------------------------------------------
def _pp(parent_fqn: str = "proc.inventory.root", child_fqn: str = "proc.inventory.ops", **over: object) -> ParentProcessBinding:
    base: dict[str, object] = {
        "parent_fqn": parent_fqn,
        "child_fqn": child_fqn,
        "created_at": _NOW,
    }
    base.update(over)
    return ParentProcessBinding(**base)  # type: ignore[arg-type]


def test_parent_process_binding_basic() -> None:
    b = _pp()
    assert b.parent_fqn == "proc.inventory.root"
    assert b.child_fqn == "proc.inventory.ops"


def test_parent_process_binding_rejects_self_reference() -> None:
    """Q1=C: 자기 자신을 부모로 지정 금지."""
    with pytest.raises(ValidationError):
        _pp(parent_fqn="proc.x.y", child_fqn="proc.x.y")


def test_parent_process_binding_fqns_required_nonempty() -> None:
    with pytest.raises(ValidationError):
        _pp(parent_fqn="")
    with pytest.raises(ValidationError):
        _pp(child_fqn="")


# ---------------------------------------------------------------------------
# ParentProcessBindingSet — cycle detection at graph level
# ---------------------------------------------------------------------------
def test_parent_process_set_empty_ok() -> None:
    s = ParentProcessBindingSet(bindings=[])
    assert len(s.bindings) == 0


def test_parent_process_set_single_edge_ok() -> None:
    s = ParentProcessBindingSet(bindings=[_pp()])
    assert len(s.bindings) == 1


def test_parent_process_set_tree_ok() -> None:
    """root → a → b, root → c (트리 — 사이클 없음)."""
    bindings = [
        _pp(parent_fqn="proc.root", child_fqn="proc.a"),
        _pp(parent_fqn="proc.a", child_fqn="proc.b"),
        _pp(parent_fqn="proc.root", child_fqn="proc.c"),
    ]
    s = ParentProcessBindingSet(bindings=bindings)
    assert len(s.bindings) == 3


def test_parent_process_set_dag_ok() -> None:
    """다이아몬드 DAG (A→B, A→C, B→D, C→D) — 사이클 아님."""
    bindings = [
        _pp(parent_fqn="proc.A", child_fqn="proc.B"),
        _pp(parent_fqn="proc.A", child_fqn="proc.C"),
        _pp(parent_fqn="proc.B", child_fqn="proc.D"),
        _pp(parent_fqn="proc.C", child_fqn="proc.D"),
    ]
    s = ParentProcessBindingSet(bindings=bindings)
    assert len(s.bindings) == 4


def test_parent_process_set_direct_cycle_rejected() -> None:
    """A→B, B→A — 2노드 사이클."""
    bindings = [
        _pp(parent_fqn="proc.A", child_fqn="proc.B"),
        _pp(parent_fqn="proc.B", child_fqn="proc.A"),
    ]
    with pytest.raises(ValidationError) as ei:
        ParentProcessBindingSet(bindings=bindings)
    assert "cycle" in str(ei.value).lower()


def test_parent_process_set_indirect_cycle_rejected() -> None:
    """A→B→C→A — 3노드 간접 사이클."""
    bindings = [
        _pp(parent_fqn="proc.A", child_fqn="proc.B"),
        _pp(parent_fqn="proc.B", child_fqn="proc.C"),
        _pp(parent_fqn="proc.C", child_fqn="proc.A"),
    ]
    with pytest.raises(ValidationError) as ei:
        ParentProcessBindingSet(bindings=bindings)
    assert "cycle" in str(ei.value).lower()


def test_parent_process_set_duplicate_edge_rejected() -> None:
    """같은 (parent, child) 쌍 2회 — 중복 엣지."""
    pair = {"parent_fqn": "proc.A", "child_fqn": "proc.B"}
    bindings = [_pp(**pair), _pp(**pair)]
    with pytest.raises(ValidationError):
        ParentProcessBindingSet(bindings=bindings)


def test_parent_process_set_json_round_trip() -> None:
    bindings = [
        _pp(parent_fqn="proc.root", child_fqn="proc.a"),
        _pp(parent_fqn="proc.a", child_fqn="proc.b"),
    ]
    s = ParentProcessBindingSet(bindings=bindings)
    raw = s.model_dump_json()
    restored = ParentProcessBindingSet.model_validate_json(raw)
    assert restored == s
