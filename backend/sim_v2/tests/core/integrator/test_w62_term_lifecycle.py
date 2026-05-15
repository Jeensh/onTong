"""W62 — TermProposal → Integrator lifecycle tests."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.sim_v2.core.integrator.term_proposal_pipeline import (
    DEFAULT_SCHEMA_FIXTURES,
    LifecycleResult,
    SCHEMA_RULE_ALIASES,
    SCHEMA_RULE_FQN_UNIQUE,
    SCHEMA_RULE_NAMING,
    SCHEMA_RULE_NON_EMPTY,
    TermSchemaOracle,
    _ExistingTermSnapshot,
    auto_review_policy,
    make_integrator_for_term,
    run_term_lifecycle,
    term_to_draft_proposal,
)
from backend.sim_v2.core.recommendation.term_proposer import (
    BusinessTermProposal,
)
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────


def _term(
    *, fqn="term.scm.product.product_category",
    label="제품 카테고리", description="제품의 분류",
    aliases=("ProductCategory",), domain="scm", kind="enum",
    confidence=0.9, needs_review=False, target_class="ProductCategory",
):
    return BusinessTermProposal(
        fqn=fqn, label=label, description=description, aliases=tuple(aliases),
        domain=domain, kind=kind, confidence=confidence,
        needs_review=needs_review, target_class=target_class,
    )


# ─────────────────────────────────────────────────────────────────────────────
# term_to_draft_proposal
# ─────────────────────────────────────────────────────────────────────────────


def test_term_to_proposal_creates_draft_ontology_evolution():
    p = term_to_draft_proposal(_term())
    assert p.type == "ontology_evolution"
    assert p.state == "DRAFT"
    assert p.ontology_diff["fqn"] == "term.scm.product.product_category"
    assert p.ontology_diff["target_class"] == "ProductCategory"


def test_term_to_proposal_carries_full_payload():
    p = term_to_draft_proposal(_term(aliases=("X", "Y")))
    assert p.ontology_diff["aliases"] == ["X", "Y"]
    assert p.ontology_diff["operation"] == "ADD_BUSINESS_TERM"
    assert p.ontology_diff["confidence"] == 0.9


def test_term_to_proposal_uses_specified_plugin():
    p = term_to_draft_proposal(_term(), plugin="broadleaf")
    assert p.plugin == "broadleaf"


# ─────────────────────────────────────────────────────────────────────────────
# TermSchemaOracle — per rule
# ─────────────────────────────────────────────────────────────────────────────


def _run_rule(oracle: TermSchemaOracle, rule_id: str):
    return oracle.run_fixture(rule_id, plugin="term", apply_diffs={})


def test_oracle_fqn_unique_passes_when_novel():
    oracle = TermSchemaOracle(_term(), _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_FQN_UNIQUE)
    assert r.status == "PASS"


def test_oracle_fqn_unique_fails_when_collision():
    existing = _ExistingTermSnapshot(
        fqns=frozenset({"term.scm.product.product_category"}),
        aliases=frozenset(),
    )
    oracle = TermSchemaOracle(_term(), existing)
    r = _run_rule(oracle, SCHEMA_RULE_FQN_UNIQUE)
    assert r.status == "FAIL_OUTPUT"
    assert "collision" in r.output_diff.summary


def test_oracle_alias_rule_passes_for_novel_aliases():
    oracle = TermSchemaOracle(_term(), _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_ALIASES)
    assert r.status == "PASS"


def test_oracle_alias_rule_fails_on_collision():
    """Alias is already claimed by another term."""
    existing = _ExistingTermSnapshot(
        fqns=frozenset(),
        aliases=frozenset({"DifferentAlias"}),
    )
    term = _term(aliases=("ProductCategory", "DifferentAlias"))
    oracle = TermSchemaOracle(term, existing)
    r = _run_rule(oracle, SCHEMA_RULE_ALIASES)
    assert r.status == "FAIL_OUTPUT"
    assert "DifferentAlias" in r.output_diff.summary


def test_oracle_alias_rule_allows_target_class_already_claimed():
    """The target_class itself can match an existing alias (the same Java class
    was previously aliased to a stale term — this isn't a hard fail, it's
    surfaced as duplicate_of in W61)."""
    existing = _ExistingTermSnapshot(
        fqns=frozenset(),
        aliases=frozenset({"ProductCategory"}),
    )
    oracle = TermSchemaOracle(_term(), existing)
    r = _run_rule(oracle, SCHEMA_RULE_ALIASES)
    assert r.status == "PASS"


def test_oracle_naming_passes_for_valid_fqn():
    oracle = TermSchemaOracle(_term(), _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_NAMING)
    assert r.status == "PASS"


def test_oracle_naming_fails_on_uppercase_segment():
    bad = _term(fqn="term.Scm.X")
    oracle = TermSchemaOracle(bad, _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_NAMING)
    assert r.status == "FAIL_OUTPUT"


def test_oracle_naming_fails_on_missing_prefix():
    bad = _term(fqn="scm.x.y")
    oracle = TermSchemaOracle(bad, _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_NAMING)
    assert r.status == "FAIL_OUTPUT"


def test_oracle_non_empty_passes_when_all_filled():
    oracle = TermSchemaOracle(_term(), _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_NON_EMPTY)
    assert r.status == "PASS"


def test_oracle_non_empty_fails_when_label_blank():
    bad = _term(label="")
    oracle = TermSchemaOracle(bad, _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, SCHEMA_RULE_NON_EMPTY)
    assert r.status == "FAIL_OUTPUT"
    assert "label" in r.output_diff.summary


def test_oracle_unknown_rule_returns_error():
    oracle = TermSchemaOracle(_term(), _ExistingTermSnapshot.empty())
    r = _run_rule(oracle, "no.such.rule")
    assert r.status == "ERROR"


# ─────────────────────────────────────────────────────────────────────────────
# auto_review_policy
# ─────────────────────────────────────────────────────────────────────────────


def test_auto_review_accepts_clean_pass():
    assert auto_review_policy("PASS", _term(needs_review=False)) == "ACCEPT"


def test_auto_review_change_request_when_needs_review():
    assert auto_review_policy("PASS", _term(needs_review=True)) == "CHANGE_REQUEST"


def test_auto_review_rejects_fail_breaking():
    assert auto_review_policy("FAIL_BREAKING", _term()) == "REJECT"


def test_auto_review_rejects_fail_drift():
    assert auto_review_policy("FAIL_DRIFT", _term()) == "REJECT"


def test_auto_review_change_request_when_inconclusive():
    assert auto_review_policy("INCONCLUSIVE", _term()) == "CHANGE_REQUEST"


# ─────────────────────────────────────────────────────────────────────────────
# Full lifecycle — happy path → MERGED
# ─────────────────────────────────────────────────────────────────────────────


def test_lifecycle_clean_term_reaches_merged():
    r = run_term_lifecycle(_term())
    assert r.final_state == "MERGED"
    assert r.oracle_status == "PASS"
    assert r.revision_id is not None
    assert r.rejection_reason is None
    # state sequence: DRAFT → PROPOSED → ORACLED → REVIEWED → ACCEPTED → MERGED
    # We capture: initial DRAFT, after submit PROPOSED, after oracle ORACLED,
    # after review terminal (here ACCEPTED), after merge MERGED
    assert "MERGED" in r.states_visited
    assert "PROPOSED" in r.states_visited
    assert "ORACLED" in r.states_visited


def test_lifecycle_collision_term_is_rejected():
    """Term whose fqn collides with existing → oracle FAIL_BREAKING → REJECT."""
    existing = _ExistingTermSnapshot(
        fqns=frozenset({"term.scm.product.product_category"}),
        aliases=frozenset(),
    )
    r = run_term_lifecycle(_term(), existing=existing)
    assert r.final_state == "REJECTED"
    assert r.oracle_status == "FAIL_BREAKING"
    assert r.revision_id is None
    assert "FAIL_BREAKING" in (r.rejection_reason or "")


def test_lifecycle_needs_review_term_returns_to_draft():
    """oracle PASS but term.needs_review=True → CHANGE_REQUEST → DRAFT."""
    r = run_term_lifecycle(_term(needs_review=True))
    assert r.final_state == "DRAFT"
    assert r.oracle_status == "PASS"
    assert r.revision_id is None
    assert "change-requested" in (r.rejection_reason or "")


def test_lifecycle_invalid_fqn_pattern_rejected():
    """Naming rule fails → oracle FAIL_BREAKING → REJECT."""
    r = run_term_lifecycle(_term(fqn="not.a.term.pattern"))
    assert r.final_state == "REJECTED"


def test_lifecycle_empty_label_rejected():
    r = run_term_lifecycle(_term(label="   "))
    assert r.final_state == "REJECTED"


# ─────────────────────────────────────────────────────────────────────────────
# Integrator wiring
# ─────────────────────────────────────────────────────────────────────────────


def test_make_integrator_returns_wired_pair():
    integrator, oracle = make_integrator_for_term(_term())
    # Integrator can list proposals (empty initially)
    assert integrator.list_proposals() == []
    assert isinstance(oracle, TermSchemaOracle)


def test_lifecycle_stores_proposal_in_integrator():
    """After lifecycle runs, the proposal is retrievable via its id."""
    integrator, _oracle = make_integrator_for_term(_term())
    proposal = term_to_draft_proposal(_term())
    prop_id = integrator.submit_proposal(proposal)
    assert integrator.get_proposal(prop_id) is not None
    assert integrator.get_proposal(prop_id).state == "PROPOSED"


# ─────────────────────────────────────────────────────────────────────────────
# Existing snapshot — production accessor
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE business_terms (
                fqn TEXT, aliases_json TEXT, repo_id TEXT
            )
        """))
    yield engine
    engine.dispose()


def test_snapshot_from_session_collects_fqns_and_aliases(fixture_db):
    with fixture_db.begin() as conn:
        conn.execute(text("INSERT INTO business_terms VALUES "
                          "('term.a', :a, 'r')"), {"a": json.dumps(["A", "AClass"])})
        conn.execute(text("INSERT INTO business_terms VALUES "
                          "('term.b', :a, 'r')"), {"a": json.dumps(["B"])})
    with Session(fixture_db) as session:
        snap = _ExistingTermSnapshot.from_session(session, "r")
    assert "term.a" in snap.fqns
    assert "term.b" in snap.fqns
    assert "A" in snap.aliases
    assert "AClass" in snap.aliases
    assert "B" in snap.aliases


def test_snapshot_empty_when_repo_unknown(fixture_db):
    with Session(fixture_db) as session:
        snap = _ExistingTermSnapshot.from_session(session, "no-repo")
    assert snap.fqns == frozenset()
    assert snap.aliases == frozenset()


# ─────────────────────────────────────────────────────────────────────────────
# Production smoke
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_production_snapshot_carries_validation_result_term():
    session = open_readonly_session()
    try:
        snap = _ExistingTermSnapshot.from_session(session, "slab-design-real")
        assert "term.scm.validation_result" in snap.fqns
        assert "ValidationResult" in snap.aliases
    finally:
        session.close()


@requires_production_db
def test_production_lifecycle_for_product_category_term():
    """Run a real BusinessTermProposal (like UC27 emits) through the lifecycle
    against a production snapshot."""
    session = open_readonly_session()
    try:
        snap = _ExistingTermSnapshot.from_session(session, "slab-design-real")
        term = _term()   # ProductCategory term
        # ProductCategory should be novel (UC23 surfaces it as new)
        result = run_term_lifecycle(term, existing=snap)
        # Should pass — no existing term covers ProductCategory
        assert result.final_state == "MERGED"
        assert result.oracle_status == "PASS"
    finally:
        session.close()


@requires_production_db
def test_production_lifecycle_for_already_existing_term_rejected():
    """ValidationResult term DOES exist in production → fqn collision → REJECT."""
    session = open_readonly_session()
    try:
        snap = _ExistingTermSnapshot.from_session(session, "slab-design-real")
        clash = BusinessTermProposal(
            fqn="term.scm.validation_result",
            label="검증결과 (재안)",
            description="이미 존재하는 term 과 fqn 충돌",
            aliases=("ValidationResult",),
            domain="scm",
            kind="composite",
            confidence=0.9,
            needs_review=False,
            target_class="ValidationResult",
        )
        result = run_term_lifecycle(clash, existing=snap)
        assert result.final_state == "REJECTED"
        assert result.oracle_status == "FAIL_BREAKING"
    finally:
        session.close()
