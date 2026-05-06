"""Tests for backend/modeling/ontology/schema.py Pydantic DSL."""

import pytest
from pydantic import ValidationError

from backend.modeling.ontology.schema import (
    CodeBinding,
    CodeBindingImplementation,
    Entity,
    Formula,
    IOPort,
    Ontology,
    OntologyHeader,
    Process,
    Relation,
    Role,
    Rule,
    Term,
    ValueType,
)


def test_ioport_minimal() -> None:
    port = IOPort(id="x", name="X", type=ValueType.FLOAT)
    assert port.id == "x"
    assert port.range is None


def test_ioport_reject_empty_id() -> None:
    with pytest.raises(ValidationError):
        IOPort(id="", name="X", type=ValueType.FLOAT)


def test_rule_warning_shape() -> None:
    rule = Rule(
        id="R1",
        condition="x > 0",
        action_type="warning",
        action_message="x is positive",
    )
    assert rule.action_message == "x is positive"
    assert rule.target is None


def test_rule_assign_shape() -> None:
    rule = Rule(
        id="R2",
        condition="x > 10",
        action_type="assign",
        target="y",
        expression="y * 2",
    )
    assert rule.target == "y"


def test_process_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Process(
            id="P1",
            name="P1",
            extra_field="nope",  # type: ignore[call-arg]
        )


def test_ontology_minimal_roundtrip() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="test-v1"),
        processes=[
            Process(
                id="P",
                name="P",
                inputs=[IOPort(id="a", name="A", type=ValueType.FLOAT)],
                outputs=[IOPort(id="b", name="B", type=ValueType.FLOAT)],
                formula=Formula(expression="a + 1"),
                rules=[
                    Rule(
                        id="R",
                        condition="a > 0",
                        action_type="warning",
                        action_message="ok",
                    )
                ],
            ),
        ],
        terms=[Term(canonical="A", aliases=["a"], refers_to="P.inputs.a")],
        code_bindings={
            "P": CodeBinding(
                implementations=[CodeBindingImplementation(entity="com.Foo")]
            )
        },
    )
    dumped = ont.model_dump()
    reloaded = Ontology.model_validate(dumped)
    assert reloaded == ont


def test_entity_minimal() -> None:
    e = Entity(id="Entity/SafetyStock", name="Safety Stock")
    assert e.aliases == []


def test_role_minimal() -> None:
    r = Role(id="Role/Planner", name="Planner")
    assert r.description is None


def test_relation_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Relation(kind="uses", source="P", target="E", foo="bar")  # type: ignore[call-arg]


def test_relation_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        Relation(kind="unknown_kind", source="P", target="E")  # type: ignore[arg-type]


def test_process_parent_id() -> None:
    parent = Process(id="SCOR/Plan", name="Plan")
    child = Process(id="SCOR/Plan/Demand", name="Demand", parent_id="SCOR/Plan")
    assert child.parent_id == parent.id


def test_ontology_with_entities_roles_relations() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="scor-mini"),
        processes=[
            Process(id="Plan", name="Plan"),
            Process(id="Plan/Demand", name="Demand Planning", parent_id="Plan"),
        ],
        entities=[Entity(id="Entity/BOM", name="Bill of Materials")],
        roles=[Role(id="Role/Planner", name="Planner")],
        relations=[
            Relation(kind="part_of", source="Plan/Demand", target="Plan"),
            Relation(kind="uses", source="Plan/Demand", target="Entity/BOM"),
            Relation(kind="responsible_for", source="Role/Planner", target="Plan"),
        ],
    )
    dumped = ont.model_dump()
    reloaded = Ontology.model_validate(dumped)
    assert reloaded == ont
    assert len(reloaded.relations) == 3
