"""Tests for ontology graph validation + Rule sub-DSL AST parser."""

from __future__ import annotations

import pytest

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
from backend.modeling.ontology.validator import (
    OntologyValidationError,
    parse_arithmetic,
    parse_boolean,
    validate_ontology,
)


def _port(pid: str) -> IOPort:
    return IOPort(id=pid, name=pid, type=ValueType.FLOAT)


def _minimal_process(pid: str = "P") -> Process:
    return Process(
        id=pid,
        name=pid,
        inputs=[_port("a"), _port("b")],
        outputs=[_port("c")],
        formula=Formula(expression="a + b"),
    )


def _wrap(process: Process, *, terms: list[Term] | None = None, bindings: dict[str, CodeBinding] | None = None) -> Ontology:
    return Ontology(
        ontology=OntologyHeader(id="test-v1"),
        processes=[process],
        terms=terms or [],
        code_bindings=bindings or {},
    )


# ---------- parse_arithmetic ----------


def test_parse_arithmetic_basic() -> None:
    parse_arithmetic("a + b * 2", {"a", "b"})


def test_parse_arithmetic_with_whitelist_function() -> None:
    parse_arithmetic("sqrt(a) + round(b, 2)", {"a", "b"})


def test_parse_arithmetic_reject_unknown_function() -> None:
    with pytest.raises(OntologyValidationError):
        parse_arithmetic("unknown_fn(a)", {"a"})


def test_parse_arithmetic_reject_unknown_identifier() -> None:
    with pytest.raises(OntologyValidationError):
        parse_arithmetic("a + z", {"a"})


def test_parse_arithmetic_reject_bitwise_op() -> None:
    with pytest.raises(OntologyValidationError):
        parse_arithmetic("a | b", {"a", "b"})


def test_parse_arithmetic_reject_syntax_error() -> None:
    with pytest.raises(OntologyValidationError):
        parse_arithmetic("a +", {"a"})


# ---------- parse_boolean ----------


def test_parse_boolean_simple_compare() -> None:
    parse_boolean("a > 0", {"a"})


def test_parse_boolean_uppercase_and_or_not() -> None:
    parse_boolean("a > 0 AND NOT b < 0 OR c == 1", {"a", "b", "c"})


def test_parse_boolean_with_arithmetic_inside() -> None:
    parse_boolean("a + b > sqrt(c)", {"a", "b", "c"})


def test_parse_boolean_reject_disallowed_function() -> None:
    with pytest.raises(OntologyValidationError):
        parse_boolean("danger(a) > 0", {"a"})


def test_parse_boolean_reject_unknown_id() -> None:
    with pytest.raises(OntologyValidationError):
        parse_boolean("a > z", {"a"})


# ---------- validate_ontology: graph ----------


def test_validate_ontology_happy() -> None:
    validate_ontology(_wrap(_minimal_process()))


def test_validate_ontology_duplicate_process_id() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="dup"),
        processes=[_minimal_process("A"), _minimal_process("A")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("중복 프로세스 id" in msg for msg in e.value.errors)


def test_validate_ontology_duplicate_input_id() -> None:
    bad = Process(
        id="P",
        name="P",
        inputs=[_port("a"), _port("a")],
        outputs=[_port("b")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(bad))
    assert any("중복 input id" in msg for msg in e.value.errors)


def test_validate_ontology_depends_on_cycle() -> None:
    p1 = Process(id="P1", name="P1", inputs=[_port("a")], outputs=[_port("b")], depends_on=["P2"])
    p2 = Process(id="P2", name="P2", inputs=[_port("a")], outputs=[_port("b")], depends_on=["P1"])
    ont = Ontology(ontology=OntologyHeader(id="cycle"), processes=[p1, p2])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("순환 참조" in msg for msg in e.value.errors)


def test_validate_ontology_depends_on_missing() -> None:
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("b")], depends_on=["Ghost"])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("미정의 프로세스" in msg for msg in e.value.errors)


def test_validate_ontology_term_refers_to_ok() -> None:
    ont = _wrap(
        _minimal_process(),
        terms=[Term(canonical="A", aliases=["a"], refers_to="P.inputs.a")],
    )
    validate_ontology(ont)


def test_validate_ontology_term_refers_to_wrong_port() -> None:
    ont = _wrap(
        _minimal_process(),
        terms=[Term(canonical="A", aliases=[], refers_to="P.outputs.ghost")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("ghost" in msg for msg in e.value.errors)


def test_validate_ontology_term_refers_to_bad_format() -> None:
    ont = _wrap(
        _minimal_process(),
        terms=[Term(canonical="A", aliases=[], refers_to="not_dotted")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("형식 불일치" in msg for msg in e.value.errors)


def test_validate_ontology_code_bindings_unknown_process() -> None:
    ont = _wrap(
        _minimal_process(),
        bindings={
            "Ghost": CodeBinding(implementations=[CodeBindingImplementation(entity="x")])
        },
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("code_bindings" in msg and "Ghost" in msg for msg in e.value.errors)


# ---------- validate_ontology: rules ----------


def test_validate_ontology_rule_warning_with_target_rejected() -> None:
    bad_rule = Rule(
        id="R", condition="a > 0", action_type="warning", action_message="x", target="c"
    )
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("c")], rules=[bad_rule])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("target" in msg for msg in e.value.errors)


def test_validate_ontology_rule_assign_missing_target() -> None:
    bad_rule = Rule(id="R", condition="a > 0", action_type="assign", expression="a + 1")
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("c")], rules=[bad_rule])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("target 필수" in msg for msg in e.value.errors)


def test_validate_ontology_rule_assign_target_not_in_ports() -> None:
    bad_rule = Rule(
        id="R",
        condition="a > 0",
        action_type="assign",
        target="not_a_port",
        expression="a + 1",
    )
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("c")], rules=[bad_rule])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("not_a_port" in msg for msg in e.value.errors)


def test_validate_ontology_rule_assign_bad_expression() -> None:
    bad_rule = Rule(
        id="R",
        condition="a > 0",
        action_type="assign",
        target="c",
        expression="unknown_fn(a)",
    )
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("c")], rules=[bad_rule])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("unknown_fn" in msg for msg in e.value.errors)


def test_validate_ontology_rule_condition_unknown_id() -> None:
    bad_rule = Rule(id="R", condition="ghost > 0", action_type="warning", action_message="x")
    p = Process(id="P", name="P", inputs=[_port("a")], outputs=[_port("c")], rules=[bad_rule])
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("ghost" in msg for msg in e.value.errors)


def test_validate_ontology_formula_uses_derived_param() -> None:
    p = Process(
        id="P",
        name="P",
        inputs=[_port("a")],
        outputs=[_port("c")],
        formula=Formula(expression="z * a", derived_params={"z": "sqrt(a)"}),
    )
    validate_ontology(_wrap(p))


def test_validate_ontology_formula_unknown_identifier() -> None:
    p = Process(
        id="P",
        name="P",
        inputs=[_port("a")],
        outputs=[_port("c")],
        formula=Formula(expression="a + ghost"),
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(_wrap(p))
    assert any("ghost" in msg for msg in e.value.errors)


def test_validate_ontology_rule_constraint_shape() -> None:
    p = Process(
        id="P",
        name="P",
        inputs=[_port("a")],
        outputs=[_port("c")],
        rules=[Rule(id="R", condition="a > 0", action_type="constraint", expression="a < 100")],
    )
    validate_ontology(_wrap(p))


# ---------------------------------------------------------------------------
# Entity / Role / Relation / parent_id validation
# ---------------------------------------------------------------------------


def test_validate_entities_duplicate_id() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        entities=[Entity(id="E1", name="One"), Entity(id="E1", name="Two")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("중복 entity id" in msg for msg in e.value.errors)


def test_validate_roles_duplicate_id() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        roles=[Role(id="R1", name="One"), Role(id="R1", name="Two")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("중복 role id" in msg for msg in e.value.errors)


def test_validate_namespace_collision_process_entity() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[Process(id="Shared", name="P")],
        entities=[Entity(id="Shared", name="E")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("id 충돌" in msg for msg in e.value.errors)


def test_validate_process_parent_id_missing() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[Process(id="P", name="P", parent_id="Ghost")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("parent_id" in msg and "Ghost" in msg for msg in e.value.errors)


def test_validate_process_parent_id_cycle() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[
            Process(id="A", name="A", parent_id="B"),
            Process(id="B", name="B", parent_id="A"),
        ],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("parent_id 순환" in msg for msg in e.value.errors)


def test_validate_process_parent_id_ok() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[
            Process(id="Plan", name="Plan"),
            Process(id="Plan/Demand", name="Demand", parent_id="Plan"),
        ],
    )
    validate_ontology(ont)


def test_validate_relation_unknown_source() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[Process(id="P", name="P")],
        entities=[Entity(id="E", name="E")],
        relations=[Relation(kind="uses", source="Ghost", target="E")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("source" in msg and "Ghost" in msg for msg in e.value.errors)


def test_validate_relation_unknown_target() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[Process(id="P", name="P")],
        relations=[Relation(kind="produces", source="P", target="GhostEntity")],
    )
    with pytest.raises(OntologyValidationError) as e:
        validate_ontology(ont)
    assert any("target" in msg and "GhostEntity" in msg for msg in e.value.errors)


def test_validate_relations_happy_mix() -> None:
    ont = Ontology(
        ontology=OntologyHeader(id="t"),
        processes=[Process(id="Plan", name="Plan")],
        entities=[Entity(id="Entity/BOM", name="BOM")],
        roles=[Role(id="Role/Planner", name="Planner")],
        relations=[
            Relation(kind="uses", source="Plan", target="Entity/BOM"),
            Relation(kind="responsible_for", source="Role/Planner", target="Plan"),
        ],
    )
    validate_ontology(ont)
