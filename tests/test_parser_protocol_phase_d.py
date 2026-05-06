"""OD-11-D1.6 TDD — Round 3 (Phase D) entity/relation kind 등록.

`backend/modeling/code_analysis/parser_protocol.py` 의 기본 레지스트리에
Round 3 Phase D 항목이 category="concept" 으로 추가됐는지 검증.

추가 엔티티 5종 :
- business_process / role / manual_document / manual_section / manual_fragment

추가 관계 6종 :
- part_of / responsible_for / parent_process / described_in / conflicts_with / missing_in

Spec :
- `toClaude/modeling/round3-manual-gap.html` rev.2 §2, §3
- Q1=C (PARENT_PROCESS 엣지), Q2=A (team-only), Q3=C (Section+Fragment 양쪽).
"""
from __future__ import annotations

import pytest

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity,
    CodeRelation,
    EntityKindRegistry,
    EntityKinds,
    EntityKindSpec,
    RelationKindRegistry,
    RelationKinds,
    RelationKindSpec,
)


# ---------------------------------------------------------------------------
# Entity kinds — Phase D Layer A & B
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind",
    [
        "business_process",
        "role",
        "manual_document",
        "manual_section",
        "manual_fragment",
    ],
)
def test_phase_d_entity_kind_registered_with_concept_category(kind: str) -> None:
    spec = EntityKindRegistry.get(kind)
    assert spec is not None, f"entity kind {kind!r} not registered"
    assert isinstance(spec, EntityKindSpec)
    assert spec.kind == kind
    assert spec.category == "concept"
    assert spec.description != ""


def test_phase_d_entity_kind_count_in_concept_category() -> None:
    """Round 2 (2) + Round 3 (5) = 총 7."""
    concept_entities = set(EntityKindRegistry.of_category("concept"))
    assert concept_entities >= {
        "business_term",
        "business_rule",
        "business_process",
        "role",
        "manual_document",
        "manual_section",
        "manual_fragment",
    }


# ---------------------------------------------------------------------------
# Relation kinds — Phase D
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind",
    [
        "part_of",
        "responsible_for",
        "parent_process",
        "described_in",
        "conflicts_with",
        "missing_in",
    ],
)
def test_phase_d_relation_kind_registered_with_concept_category(kind: str) -> None:
    spec = RelationKindRegistry.get(kind)
    assert spec is not None, f"relation kind {kind!r} not registered"
    assert isinstance(spec, RelationKindSpec)
    assert spec.kind == kind
    assert spec.category == "concept"
    assert spec.description != ""


def test_phase_d_relation_kind_count_in_concept_category() -> None:
    """Round 2 (3) + Round 3 (6) = 총 9."""
    concept_relations = set(RelationKindRegistry.of_category("concept"))
    assert concept_relations >= {
        "realizes",
        "validates",
        "derived_from",
        "part_of",
        "responsible_for",
        "parent_process",
        "described_in",
        "conflicts_with",
        "missing_in",
    }


# ---------------------------------------------------------------------------
# Convenience string constants (EntityKinds / RelationKinds)
# ---------------------------------------------------------------------------
def test_phase_d_entity_constants_match_registry() -> None:
    assert EntityKinds.BUSINESS_PROCESS == "business_process"
    assert EntityKinds.ROLE == "role"
    assert EntityKinds.MANUAL_DOCUMENT == "manual_document"
    assert EntityKinds.MANUAL_SECTION == "manual_section"
    assert EntityKinds.MANUAL_FRAGMENT == "manual_fragment"


def test_phase_d_relation_constants_match_registry() -> None:
    assert RelationKinds.PART_OF == "part_of"
    assert RelationKinds.RESPONSIBLE_FOR == "responsible_for"
    assert RelationKinds.PARENT_PROCESS == "parent_process"
    assert RelationKinds.DESCRIBED_IN == "described_in"
    assert RelationKinds.CONFLICTS_WITH == "conflicts_with"
    assert RelationKinds.MISSING_IN == "missing_in"


# ---------------------------------------------------------------------------
# End-to-end : CodeEntity / CodeRelation 생성 가능 확인
# ---------------------------------------------------------------------------
def test_business_process_entity_instantiable() -> None:
    e = CodeEntity(
        kind=EntityKinds.BUSINESS_PROCESS,
        qualified_name="proc.inventory.safety_stock_management",
        name="safety_stock_management",
        file_path="<concept>",
        line_start=0,
        line_end=0,
    )
    assert e.kind == "business_process"


def test_role_entity_instantiable() -> None:
    e = CodeEntity(
        kind=EntityKinds.ROLE,
        qualified_name="team.inventory_mgmt",
        name="inventory_mgmt",
        file_path="<concept>",
        line_start=0,
        line_end=0,
    )
    assert e.kind == "role"


def test_manual_entities_instantiable() -> None:
    doc = CodeEntity(
        kind=EntityKinds.MANUAL_DOCUMENT,
        qualified_name="manual.inventory.safety_stock_policy",
        name="safety_stock_policy",
        file_path="/manuals/inventory/safety_stock_policy.md",
        line_start=0,
        line_end=0,
    )
    sec = CodeEntity(
        kind=EntityKinds.MANUAL_SECTION,
        qualified_name="manual.inventory.safety_stock_policy#3.2",
        name="3.2",
        file_path="/manuals/inventory/safety_stock_policy.md",
        line_start=0,
        line_end=0,
    )
    frag = CodeEntity(
        kind=EntityKinds.MANUAL_FRAGMENT,
        qualified_name="manual.inventory.safety_stock_policy#3.2:f0",
        name="f0",
        file_path="/manuals/inventory/safety_stock_policy.md",
        line_start=0,
        line_end=0,
    )
    assert (doc.kind, sec.kind, frag.kind) == ("manual_document", "manual_section", "manual_fragment")


@pytest.mark.parametrize(
    "kind",
    [
        RelationKinds.PART_OF,
        RelationKinds.RESPONSIBLE_FOR,
        RelationKinds.PARENT_PROCESS,
        RelationKinds.DESCRIBED_IN,
        RelationKinds.CONFLICTS_WITH,
        RelationKinds.MISSING_IN,
    ],
)
def test_phase_d_relation_instantiable_via_code_relation(kind: str) -> None:
    r = CodeRelation(
        kind=kind,
        source="proc.x",
        target="proc.y",
    )
    assert r.kind == kind
