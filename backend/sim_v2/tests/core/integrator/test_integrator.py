"""Integrator 8-method API test — ADR-003 §1."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.sim_v2.core.integrator.integrator import (
    Integrator,
    InvalidTransitionError,
    ProposalNotFoundError,
    ProposalRefinement,
    ProposalStore,
)
from backend.sim_v2.core.integrator.proposal import (
    Proposal,
    UserFeedback,
)
from backend.sim_v2.core.integrator.revision import RevisionStore
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mocks
# ─────────────────────────────────────────────────────────────────────────────


class MockVerification:
    """Test double — controllable OracleResult."""
    def __init__(self, default_status: str = "PASS"):
        self.default_status = default_status
        self.last_request: OracleRequest | None = None

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        self.last_request = request
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture={
                fid: FixtureOracleResult(
                    fixture_id=fid,
                    java_baseline_output={"out": 1},
                    python_proposal_output={"out": 1},
                    output_diff=OutputDiff(is_equivalent=True),
                    trace_diff=TraceDiff(is_equivalent=True),
                    status="PASS" if self.default_status == "PASS" else "FAIL_OUTPUT",
                )
                for fid in request.fixture_subset
            },
            aggregate_status=self.default_status,
            summary=f"mock oracle ({self.default_status})",
        )


class MockRecommendation:
    def refine(self, proposal: Proposal, hints: dict) -> Proposal:
        return proposal


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def integrator() -> Integrator:
    return Integrator(
        verification=MockVerification(),
        recommendation=MockRecommendation(),
    )


@pytest.fixture
def integrator_failing() -> Integrator:
    return Integrator(
        verification=MockVerification(default_status="FAIL_BREAKING"),
        recommendation=MockRecommendation(),
    )


def _new_proposal(plugin: str = "v2-slab-design") -> Proposal:
    return Proposal(
        type="schema_change",
        description="Add audit_log table",
        schema_diff={"add_table": "audit_log"},
        plugin=plugin,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. submit_proposal
# ─────────────────────────────────────────────────────────────────────────────


def test_submit_proposal_transitions_to_proposed(integrator: Integrator):
    prop = _new_proposal()
    prop_id = integrator.submit_proposal(prop)
    assert prop_id == prop.id
    assert prop.state == "PROPOSED"


def test_submit_proposal_rejects_non_draft(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)  # → PROPOSED
    with pytest.raises(ValueError, match="DRAFT"):
        integrator.submit_proposal(prop)


def test_submit_proposal_records_history(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    assert len(prop.history) == 1
    assert prop.history[0].to_state == "PROPOSED"
    assert prop.history[0].actor == "recommendation_engine"


# ─────────────────────────────────────────────────────────────────────────────
# 2. request_oracle
# ─────────────────────────────────────────────────────────────────────────────


def test_request_oracle_attaches_result(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    result = integrator.request_oracle(prop.id, fixture_subset=["S1", "S2"])

    assert result.aggregate_status == "PASS"
    assert prop.state == "ORACLED"
    assert prop.oracle_result is not None
    assert prop.oracle_result.aggregate_status == "PASS"
    # Full result available via integrator
    full = integrator.get_full_oracle_result(prop.id)
    assert full is not None
    assert len(full.by_fixture) == 2


def test_request_oracle_forwards_diffs(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])

    verification: MockVerification = integrator._verification  # type: ignore[assignment]
    assert verification.last_request is not None
    assert verification.last_request.apply_schema_diff == {"add_table": "audit_log"}
    assert verification.last_request.fixture_subset == ["S1"]


def test_request_oracle_unknown_proposal(integrator: Integrator):
    with pytest.raises(ProposalNotFoundError):
        integrator.request_oracle("nonexistent", fixture_subset=["S1"])


def test_request_oracle_wrong_state(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])  # → ORACLED
    with pytest.raises(InvalidTransitionError):
        integrator.request_oracle(prop.id, fixture_subset=["S1"])  # already ORACLED


# ─────────────────────────────────────────────────────────────────────────────
# 3. refine_proposal
# ─────────────────────────────────────────────────────────────────────────────


def test_refine_proposal_applies_diff_update(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.refine_proposal(
        prop.id,
        ProposalRefinement(
            schema_diff_update={"add_index": "idx_audit_ts"},
            reason="add index for timestamp queries",
        ),
    )
    assert prop.state == "DRAFT"
    assert prop.schema_diff == {"add_table": "audit_log", "add_index": "idx_audit_ts"}


def test_refine_proposal_clears_stale_oracle(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])  # → ORACLED
    assert prop.oracle_result is not None

    integrator.refine_proposal(prop.id, ProposalRefinement(reason="rework"))
    assert prop.state == "DRAFT"
    assert prop.oracle_result is None
    assert integrator.get_full_oracle_result(prop.id) is None


def test_refine_proposal_from_terminal_rejected(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.reject_proposal(prop.id, reason="not needed")
    with pytest.raises(InvalidTransitionError):
        integrator.refine_proposal(prop.id, ProposalRefinement())


# ─────────────────────────────────────────────────────────────────────────────
# 3b. re_propose — DRAFT → PROPOSED (W28)
# ─────────────────────────────────────────────────────────────────────────────


def test_re_propose_promotes_drafted_proposal(integrator: Integrator):
    """Refine loop: after refine_proposal returns DRAFT, re_propose advances to PROPOSED."""
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])   # → ORACLED
    integrator.refine_proposal(prop.id, ProposalRefinement(reason="rework"))  # → DRAFT
    assert prop.state == "DRAFT"

    integrator.re_propose(prop.id)
    assert prop.state == "PROPOSED"


def test_re_propose_appends_history_event(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    integrator.refine_proposal(prop.id, ProposalRefinement(reason="x"))
    n_before = len(prop.history)

    integrator.re_propose(prop.id)
    assert len(prop.history) == n_before + 1
    last = prop.history[-1]
    assert last.from_state == "DRAFT"
    assert last.to_state == "PROPOSED"
    assert last.actor == "recommendation_engine"


def test_re_propose_rejects_non_draft(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)  # → PROPOSED
    with pytest.raises(InvalidTransitionError):
        integrator.re_propose(prop.id)


def test_re_propose_unknown_proposal(integrator: Integrator):
    with pytest.raises(ProposalNotFoundError):
        integrator.re_propose("nonexistent-id")


def test_re_propose_enables_request_oracle_again(integrator: Integrator):
    """End-to-end refine loop: submit → oracle → refine → re_propose → oracle (again)."""
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    first = integrator.request_oracle(prop.id, fixture_subset=["S1"])
    integrator.refine_proposal(prop.id, ProposalRefinement(reason="retry"))
    integrator.re_propose(prop.id)
    second = integrator.request_oracle(prop.id, fixture_subset=["S1"])
    assert prop.state == "ORACLED"
    assert first.proposal_id == second.proposal_id


def test_re_propose_custom_actor_and_notes(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    integrator.refine_proposal(prop.id, ProposalRefinement(reason="x"))

    integrator.re_propose(prop.id, actor="user", notes="manual re-propose")
    last = prop.history[-1]
    assert last.actor == "user"
    assert last.notes == "manual re-propose"


# ─────────────────────────────────────────────────────────────────────────────
# 4. review_proposal
# ─────────────────────────────────────────────────────────────────────────────


def _make_feedback(decision: str, comments: str = "") -> UserFeedback:
    return UserFeedback(
        decision=decision,
        timestamp=datetime.now(timezone.utc),
        user="jeensh",
        comments=comments,
    )


def test_review_proposal_accept(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    final = integrator.review_proposal(prop.id, _make_feedback("ACCEPT"))
    assert final == "ACCEPTED"
    assert prop.state == "ACCEPTED"


def test_review_proposal_reject(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    final = integrator.review_proposal(
        prop.id, _make_feedback("REJECT", "not needed for this sprint")
    )
    assert final == "REJECTED"


def test_review_proposal_change_request(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    final = integrator.review_proposal(
        prop.id, _make_feedback("CHANGE_REQUEST", "prefer NUMERIC(20,2)")
    )
    assert final == "DRAFT"
    assert prop.state == "DRAFT"


def test_review_proposal_partial_accept_phase2(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    final = integrator.review_proposal(
        prop.id,
        UserFeedback(
            decision="PARTIAL_ACCEPT",
            timestamp=datetime.now(timezone.utc),
            user="jeensh",
            comments="accept table, reject index",
            fields_to_change=["schema_diff.add_index"],
        ),
    )
    assert final == "DRAFT"
    assert prop.history[-1].artifacts["fields_to_change"] == ["schema_diff.add_index"]


def test_review_proposal_requires_oracled(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)  # PROPOSED, not ORACLED
    with pytest.raises(InvalidTransitionError):
        integrator.review_proposal(prop.id, _make_feedback("ACCEPT"))


# ─────────────────────────────────────────────────────────────────────────────
# 5. merge_proposal
# ─────────────────────────────────────────────────────────────────────────────


def test_merge_proposal_creates_revision(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    integrator.review_proposal(prop.id, _make_feedback("ACCEPT"))

    revision_id = integrator.merge_proposal(
        prop.id,
        ontology_revision="v2-slab-design@v2",
        code_revision="abc123",
        schema_revision="v2",
        created_by="jeensh",
    )
    assert prop.state == "MERGED"
    assert revision_id
    revision = integrator.revision_store.get(revision_id)
    assert revision is not None
    assert revision.proposal_id == prop.id


def test_merge_proposal_with_lineage(integrator: Integrator):
    # Setup parent revision
    prop1 = _new_proposal()
    integrator.submit_proposal(prop1)
    integrator.request_oracle(prop1.id, fixture_subset=["S1"])
    integrator.review_proposal(prop1.id, _make_feedback("ACCEPT"))
    r1 = integrator.merge_proposal(
        prop1.id, "v2@v1", "commit1", "v1", created_by="jeensh"
    )

    # Child revision
    prop2 = _new_proposal()
    integrator.submit_proposal(prop2)
    integrator.request_oracle(prop2.id, fixture_subset=["S1"])
    integrator.review_proposal(prop2.id, _make_feedback("ACCEPT"))
    r2 = integrator.merge_proposal(
        prop2.id, "v2@v2", "commit2", "v2",
        created_by="jeensh", parent_revision=r1,
    )

    lineage = integrator.revision_store.lineage(r2)
    assert len(lineage) == 2
    assert lineage[0].id == r2
    assert lineage[1].id == r1


def test_merge_proposal_requires_accepted(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])  # ORACLED, not ACCEPTED
    with pytest.raises(InvalidTransitionError):
        integrator.merge_proposal(
            prop.id, "v2@v1", "commit1", "v1", created_by="jeensh"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 6. reject_proposal
# ─────────────────────────────────────────────────────────────────────────────


def test_reject_proposal_from_draft(integrator: Integrator):
    prop = _new_proposal()
    integrator._proposals.add(prop)  # add to store (not submitted)
    integrator.reject_proposal(prop.id, reason="abandoned at draft")
    assert prop.state == "REJECTED"


def test_reject_proposal_from_oracled(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.request_oracle(prop.id, fixture_subset=["S1"])
    integrator.reject_proposal(prop.id, reason="risk too high")
    assert prop.state == "REJECTED"


def test_reject_terminal_proposal_fails(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    integrator.reject_proposal(prop.id, reason="r")
    with pytest.raises(InvalidTransitionError):
        integrator.reject_proposal(prop.id, reason="again")


# ─────────────────────────────────────────────────────────────────────────────
# 7-8. get_proposal / list_proposals
# ─────────────────────────────────────────────────────────────────────────────


def test_get_proposal(integrator: Integrator):
    prop = _new_proposal()
    integrator.submit_proposal(prop)
    fetched = integrator.get_proposal(prop.id)
    assert fetched is prop
    assert integrator.get_proposal("missing") is None


def test_list_proposals_filter_by_state(integrator: Integrator):
    p1 = _new_proposal()
    p2 = _new_proposal()
    integrator.submit_proposal(p1)
    integrator.submit_proposal(p2)
    integrator.request_oracle(p1.id, fixture_subset=["S1"])  # p1 → ORACLED

    proposed = integrator.list_proposals(state="PROPOSED")
    oracled = integrator.list_proposals(state="ORACLED")
    assert [p.id for p in proposed] == [p2.id]
    assert [p.id for p in oracled] == [p1.id]


def test_list_proposals_filter_by_plugin(integrator: Integrator):
    p_v2 = _new_proposal(plugin="v2-slab-design")
    p_broadleaf = _new_proposal(plugin="broadleaf")
    integrator.submit_proposal(p_v2)
    integrator.submit_proposal(p_broadleaf)

    v2_only = integrator.list_proposals(plugin="v2-slab-design")
    assert len(v2_only) == 1
    assert v2_only[0].id == p_v2.id


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_end_to_end_happy_path(integrator: Integrator):
    """DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED."""
    prop = _new_proposal()

    # submit
    integrator.submit_proposal(prop)
    assert prop.state == "PROPOSED"

    # oracle
    integrator.request_oracle(prop.id, fixture_subset=["S1", "S2"])
    assert prop.state == "ORACLED"

    # review accept
    integrator.review_proposal(prop.id, _make_feedback("ACCEPT"))
    assert prop.state == "ACCEPTED"

    # merge
    revision_id = integrator.merge_proposal(
        prop.id,
        ontology_revision="v2@v3",
        code_revision="def456",
        schema_revision="v3",
        created_by="jeensh",
    )
    assert prop.state == "MERGED"
    assert prop.is_terminal()

    # history audit
    states = [event.to_state for event in prop.history]
    assert states == ["PROPOSED", "ORACLED", "REVIEWED", "ACCEPTED", "MERGED"]

    revision = integrator.revision_store.get(revision_id)
    assert revision is not None
    assert revision.created_by == "jeensh"


def test_end_to_end_oracle_failure_path(integrator_failing: Integrator):
    """ORACLE FAIL → user rejects."""
    prop = _new_proposal()
    integrator_failing.submit_proposal(prop)
    result = integrator_failing.request_oracle(prop.id, fixture_subset=["S1"])

    assert result.aggregate_status == "FAIL_BREAKING"
    assert prop.state == "ORACLED"

    integrator_failing.review_proposal(
        prop.id, _make_feedback("REJECT", "oracle indicates breaking change")
    )
    assert prop.state == "REJECTED"
