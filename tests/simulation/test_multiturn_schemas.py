"""Step 1b TDD — multiturn agent schemas.

3 gates + Provenance + sub-models. Pydantic v2 discriminator unions.

차용 원본: `backend/application/authoring/capabilities/hypothesis.py:210-213`
(Annotated[Union[...], Field(discriminator="kind")] 패턴).
"""
from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError


# ─────────────────────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────────────────────


def test_provenance_basic() -> None:
    from backend.section3.agents.multiturn.schemas import Provenance
    p = Provenance(
        source="ontology",
        detail="ontology.get_action_detail(action_id=42)",
        confidence=1.0,
    )
    assert p.source == "ontology"
    assert p.confidence == 1.0


def test_provenance_confidence_optional() -> None:
    from backend.section3.agents.multiturn.schemas import Provenance
    p = Provenance(source="user_input", detail="user typed: 주문 검증")
    assert p.confidence is None


def test_provenance_rejects_unknown_source() -> None:
    from backend.section3.agents.multiturn.schemas import Provenance
    with pytest.raises(ValidationError):
        Provenance(source="elasticsearch", detail="x")  # type: ignore[arg-type]


def test_provenance_confidence_range() -> None:
    from backend.section3.agents.multiturn.schemas import Provenance
    with pytest.raises(ValidationError):
        Provenance(source="sim_v2", detail="x", confidence=1.5)
    with pytest.raises(ValidationError):
        Provenance(source="sim_v2", detail="x", confidence=-0.1)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models (ActionCandidate / ActionRef / CodeLocation / IdiomDiff / FixtureRow)
# ─────────────────────────────────────────────────────────────────────────────


def test_action_candidate_minimal() -> None:
    from backend.section3.agents.multiturn.schemas import ActionCandidate
    c = ActionCandidate(
        action_id="action.scm.order.validate",
        label="주문 검증",
        score=0.87,
        code_method_fqn="com.ontong.scm.OrderService.validateOrder",
    )
    assert c.score == 0.87


def test_action_ref_carries_repo() -> None:
    from backend.section3.agents.multiturn.schemas import (
        ActionRef, CodeLocation,
    )
    r = ActionRef(
        action_id="action.scm.order.validate",
        code_method_fqn="com.ontong.scm.OrderService.validateOrder",
        repo_id="slab-design-real-v2",
        location=CodeLocation(
            file_path="src/main/java/.../OrderService.java",
            line_start=42, line_end=87,
        ),
    )
    assert r.repo_id == "slab-design-real-v2"
    assert r.location.line_start == 42


def test_idiom_diff() -> None:
    from backend.section3.agents.multiturn.schemas import IdiomDiff
    d = IdiomDiff(
        idiom_name="List.add",
        java_snippet="list.add(item)",
        python_snippet="list.append(item)",
    )
    assert d.idiom_name == "List.add"


def test_fixture_row_args_dict() -> None:
    from backend.section3.agents.multiturn.schemas import FixtureRow
    f = FixtureRow(
        fixture_id="f-1",
        args={"order_id": "ABC-001", "qty": 5, "weight": 1.2},
    )
    assert f.args["qty"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# GatePayload outer discriminator
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_payload_discriminates_target_selected() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GatePayload, GateTarget,
    )
    adapter = TypeAdapter(GatePayload)
    parsed = adapter.validate_python({
        "kind": "target_selected",
        "intent": "simulate",
        "user_query": "주문 검증 시뮬",
        "candidates": [
            {
                "action_id": "action.scm.order.validate",
                "label": "주문 검증",
                "score": 0.9,
                "code_method_fqn": "OrderService.validateOrder",
            }
        ],
        "recommended_index": 0,
        "selected": None,
        "sources": [{"source": "sim_v2", "detail": "find_action_candidates", "confidence": 0.9}],
    })
    assert isinstance(parsed, GateTarget)
    assert parsed.intent == "simulate"


def test_gate_payload_discriminates_bundle() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GatePayload, GateBundle,
    )
    adapter = TypeAdapter(GatePayload)
    parsed = adapter.validate_python({
        "kind": "bundle_prepared",
        "target": {
            "action_id": "x",
            "code_method_fqn": "OrderService.validateOrder",
            "repo_id": "slab-design-real-v2",
            "location": {"file_path": "X.java", "line_start": 1, "line_end": 5},
        },
        "java_source": "void validateOrder(){}",
        "python_source": "def validate_order():\n    pass",
        "idiom_diffs": [],
        "fixtures": [],
        "schema_summary": {"entity_name": "Order", "fields": []},
        "sources": [],
        "confidence": 0.9,
    })
    assert isinstance(parsed, GateBundle)
    assert parsed.confidence == 0.9


# ─────────────────────────────────────────────────────────────────────────────
# GateExecuted inner discriminator (mode = simulate / impact)
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_executed_simulation_variant() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GatePayload, GateExecutedSimulation,
    )
    adapter = TypeAdapter(GatePayload)
    parsed = adapter.validate_python({
        "kind": "executed_simulation",
        "results": [
            {
                "fixture_id": "f-1", "status": "PASS",
                "output": {"valid": True}, "error_class": None,
            }
        ],
        "invariant_status": "clean",
        "baseline_diff": None,
        "sources": [],
    })
    assert isinstance(parsed, GateExecutedSimulation)
    assert parsed.mode == "simulate"
    assert parsed.results[0].status == "PASS"


def test_gate_executed_impact_variant() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GatePayload, GateExecutedImpact,
    )
    adapter = TypeAdapter(GatePayload)
    parsed = adapter.validate_python({
        "kind": "executed_impact",
        "affected_methods": [
            {
                "fqn": "ProductivityService.cumulativeProductivity",
                "distance": 1,
                "via": "direct_caller",
            }
        ],
        "sim_v2_findings": [],
        "confidence": 0.7,
        "sources": [],
    })
    assert isinstance(parsed, GateExecutedImpact)
    assert parsed.mode == "impact"
    assert parsed.affected_methods[0].distance == 1


def test_gate_executed_unknown_kind_rejected() -> None:
    from backend.section3.agents.multiturn.schemas import GatePayload
    adapter = TypeAdapter(GatePayload)
    with pytest.raises(ValidationError):
        adapter.validate_python({
            "kind": "executed_diagnose",  # not in known kinds
            "sources": [],
        })


# ─────────────────────────────────────────────────────────────────────────────
# JSON round-trip
# ─────────────────────────────────────────────────────────────────────────────


def test_gate_target_json_roundtrip() -> None:
    from backend.section3.agents.multiturn.schemas import (
        GatePayload, GateTarget, ActionCandidate, Provenance,
    )
    original = GateTarget(
        intent="impact",
        user_query="cumulativeProductivity 영향",
        candidates=[
            ActionCandidate(
                action_id="x", label="x", score=0.5,
                code_method_fqn="X.cumulativeProductivity",
            ),
        ],
        recommended_index=0,
        selected=None,
        sources=[Provenance(source="llm_inference", detail="intent=impact", confidence=0.8)],
    )
    payload_json = original.model_dump_json()
    adapter = TypeAdapter(GatePayload)
    rehydrated = adapter.validate_json(payload_json)
    assert isinstance(rehydrated, GateTarget)
    assert rehydrated.intent == "impact"
    assert rehydrated.candidates[0].action_id == "x"


# ─────────────────────────────────────────────────────────────────────────────
# Sources field always present
# ─────────────────────────────────────────────────────────────────────────────


def test_all_gate_payloads_have_sources_field() -> None:
    """Q5 비전: 모든 카드에 provenance surface — 어떤 gate payload 도 sources 누락 X."""
    from backend.section3.agents.multiturn.schemas import (
        GateTarget, GateBundle, GateExecutedSimulation, GateExecutedImpact,
    )
    for cls in (GateTarget, GateBundle, GateExecutedSimulation, GateExecutedImpact):
        assert "sources" in cls.model_fields, f"{cls.__name__} missing 'sources' field"
