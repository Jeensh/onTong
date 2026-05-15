"""UC1 Integrator pipeline demo verification — W15.2/W15.3.

Verifies the demo wires the Proposal lifecycle correctly end-to-end:
  DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED + Revision.
"""
from __future__ import annotations

from backend.sim_v2.demos.uc1_integrator_pipeline.run import main


def test_demo_main_returns_zero():
    """The demo's main() exits with code 0 — full lifecycle reaches MERGED."""
    assert main() == 0


def test_demo_proposal_reaches_merged_state():
    """Re-run the demo's lifecycle inline and inspect proposal state."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from backend.sim_v2.core.integrator.integrator import Integrator
    from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
    from backend.sim_v2.core.verification.scenario_engine import (
        Scenario,
        ScenarioVerificationEngine,
    )
    from backend.sim_v2.demos.uc1_integrator_pipeline.run import (
        _ground_truth_execute,
        _StubRecommendationEngine,
    )
    from backend.sim_v2.demos.uc1_real_file.run import (
        SDOrderEntity,
        SDSlabEntity,
        build_ontology_session,
        compile_to_callable,
        translate_real_file,
    )

    session = build_ontology_session()
    py_source, meta = translate_real_file(session)
    assert not meta["locked"]

    translated_fn = compile_to_callable(py_source)

    fixtures = {
        "S1_normal": Scenario(
            "S1_normal",
            inputs={
                "order": SDOrderEntity(orderWgtHigh=Decimal("20"), productivity=Decimal("0.5")),
                "slab":  SDSlabEntity(secondWgtHigh=Decimal("100")),
            },
            expected_output=None,
        ),
    }
    engine = ScenarioVerificationEngine(
        translated_fn=translated_fn,
        baseline_fn=_ground_truth_execute,
        fixtures=fixtures,
    )
    integrator = Integrator(engine, _StubRecommendationEngine())

    prop = Proposal(
        type="code_change",
        description="test SdMaxSplitCountAction translation",
        plugin="v2-slab-design",
        code_diff={"method": "execute"},
    )
    prop_id = integrator.submit_proposal(prop)
    assert integrator.get_proposal(prop_id).state == "PROPOSED"

    oracle = integrator.request_oracle(prop_id, ["S1_normal"])
    assert oracle.aggregate_status == "PASS"
    assert integrator.get_proposal(prop_id).state == "ORACLED"

    final_state = integrator.review_proposal(prop_id, UserFeedback(
        decision="ACCEPT",
        timestamp=datetime.now(timezone.utc),
        user="test",
    ))
    assert final_state == "ACCEPTED"

    rev_id = integrator.merge_proposal(
        prop_id=prop_id,
        ontology_revision="v2@test",
        code_revision="git:test",
        schema_revision="alembic:test",
        created_by="test",
    )
    final = integrator.get_proposal(prop_id)
    assert final.state == "MERGED"

    revision = integrator.revision_store.get(rev_id)
    assert revision is not None
    assert revision.proposal_id == prop_id

    # 5 transitions recorded: DRAFT→PROPOSED→ORACLED→REVIEWED→ACCEPTED→MERGED
    assert len(final.history) == 5
    states = [(e.from_state, e.to_state) for e in final.history]
    assert states == [
        ("DRAFT", "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED", "REVIEWED"),
        ("REVIEWED", "ACCEPTED"),
        ("ACCEPTED", "MERGED"),
    ]


def test_demo_oracle_result_attached_to_proposal():
    """request_oracle should attach a placeholder OracleResult to the proposal."""
    from datetime import datetime, timezone
    from decimal import Decimal

    from backend.sim_v2.core.integrator.integrator import Integrator
    from backend.sim_v2.core.integrator.proposal import Proposal
    from backend.sim_v2.core.verification.scenario_engine import (
        Scenario,
        ScenarioVerificationEngine,
    )
    from backend.sim_v2.demos.uc1_integrator_pipeline.run import (
        _ground_truth_execute,
        _StubRecommendationEngine,
    )
    from backend.sim_v2.demos.uc1_real_file.run import (
        SDOrderEntity,
        SDSlabEntity,
        build_ontology_session,
        compile_to_callable,
        translate_real_file,
    )

    session = build_ontology_session()
    py_source, _ = translate_real_file(session)
    translated_fn = compile_to_callable(py_source)

    fixtures = {
        "F": Scenario(
            "F",
            inputs={
                "order": SDOrderEntity(orderWgtHigh=Decimal("1"), productivity=Decimal("1")),
                "slab":  SDSlabEntity(secondWgtHigh=Decimal("0.3")),
            },
            expected_output=None,
        ),
    }
    engine = ScenarioVerificationEngine(translated_fn, _ground_truth_execute, fixtures)
    integrator = Integrator(engine, _StubRecommendationEngine())

    prop = Proposal(
        type="code_change", description="test", plugin="v2-slab-design",
        code_diff={"method": "execute"},
    )
    prop_id = integrator.submit_proposal(prop)
    integrator.request_oracle(prop_id, ["F"])

    p = integrator.get_proposal(prop_id)
    assert p.oracle_result is not None
    assert p.oracle_result.aggregate_status == "PASS"

    # Full oracle result also stored
    full = integrator.get_full_oracle_result(prop_id)
    assert full is not None
    assert "F" in full.by_fixture
