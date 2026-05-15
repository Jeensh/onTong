"""UC16 — Composite production pipeline demo verification — W46.

Smoke-tests the entire 6-stage production pipeline. Skips cleanly if production
DB missing. Each stage's invariants are asserted on the orchestrator output.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc16_production_pipeline.run import (
    DEFAULT_REPOS,
    PipelineResult,
    RepoPipelineResult,
    main,
    run_full_pipeline,
    run_pipeline_for_repo,
)


requires_production_db = pytest.mark.skipif(
    not PRODUCTION_DB_PATH.exists(),
    reason=f"production data/ontology.db missing at {PRODUCTION_DB_PATH}",
)


@pytest.fixture
def scratch_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Demo entry point
# ─────────────────────────────────────────────────────────────────────────────


def test_main_returns_zero_without_db(monkeypatch):
    from backend.sim_v2.demos.uc16_production_pipeline import run as runmod
    monkeypatch.setattr(runmod, "open_readonly_session", lambda *_a, **_kw: None)
    assert main() == 0


@requires_production_db
def test_main_returns_zero():
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo pipeline — each stage produces non-empty result
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_pipeline_for_real_repo_produces_per_stage_results(scratch_session):
    prod = open_readonly_session()
    try:
        r = run_pipeline_for_repo(
            prod, scratch_session, "slab-design-real", translate_sample=20,
        )
        assert isinstance(r, RepoPipelineResult)
        assert r.repo_id == "slab-design-real"
        # Stage 1
        assert r.method_count > 0
        # Stage 2
        assert r.translate_pass + r.translate_locked >= 0
        assert r.sample_size > 0
        # Stage 3+4
        assert r.entity_count > 0
        assert r.table_count > 0
        assert r.column_count > 0
        assert r.mapping_count > 0
        # Stage 5
        assert (r.drift_added_cols + r.drift_removed_cols + r.drift_changed_cols) > 0
        # Stage 6
        assert r.term_count > 0
        assert r.action_count > 0
        assert r.sample_term_actions > 0
    finally:
        prod.close()


@requires_production_db
def test_pipeline_translate_pass_rate_on_real_repo_is_100(scratch_session):
    """Real-repo translator pass rate should be 100% (post-W41)."""
    prod = open_readonly_session()
    try:
        r = run_pipeline_for_repo(
            prod, scratch_session, "slab-design-real", translate_sample=50,
        )
        # Allow a tiny margin in case future production data introduces a new
        # locked construct; current state is 100%
        assert r.translate_pass_rate >= 0.99
    finally:
        prod.close()


@requires_production_db
def test_pipeline_synthetic_repo_has_no_bindings_but_many_actions(scratch_session):
    """synthetic-5k characteristic: 0 anchor bindings but many actions."""
    prod = open_readonly_session()
    try:
        r = run_pipeline_for_repo(
            prod, scratch_session, "synthetic-5k", translate_sample=20,
        )
        assert r.binding_count == 0
        assert r.action_count > 1000
    finally:
        prod.close()


@requires_production_db
def test_pipeline_unknown_repo_yields_zero_counts(scratch_session):
    prod = open_readonly_session()
    try:
        r = run_pipeline_for_repo(
            prod, scratch_session, "no-such-repo-xyz", translate_sample=10,
        )
        assert r.method_count == 0
        assert r.entity_count == 0
        assert r.table_count == 0
        assert r.term_count == 0
    finally:
        prod.close()


# ─────────────────────────────────────────────────────────────────────────────
# Full pipeline — aggregate across DEFAULT_REPOS
# ─────────────────────────────────────────────────────────────────────────────


@requires_production_db
def test_full_pipeline_aggregates_across_three_repos(scratch_session):
    prod = open_readonly_session()
    try:
        result = run_full_pipeline(prod, scratch_session, DEFAULT_REPOS)
        assert isinstance(result, PipelineResult)
        assert len(result.per_repo) == len(DEFAULT_REPOS)
        # Aggregate invariants
        assert result.total_methods >= 39_000  # ~39,282 in current production
        assert result.total_entities >= 500    # ~602 in current production
        assert result.total_tables >= 30       # 14+14+14 = 42 (deduped)
        assert result.total_terms >= 1000      # ~1,277 in current production
        assert result.total_actions >= 1000    # ~1,552 in current production
        assert result.total_bindings >= 100    # 9+163+0 = 172
        # Drift detection ran on every repo
        total_drift = (result.total_drift_added
                       + result.total_drift_removed
                       + result.total_drift_changed)
        assert total_drift > 0
    finally:
        prod.close()


@requires_production_db
def test_full_pipeline_aggregate_equals_sum_of_per_repo(scratch_session):
    """The aggregate fields must be exact sums of per_repo entries."""
    prod = open_readonly_session()
    try:
        result = run_full_pipeline(prod, scratch_session, DEFAULT_REPOS)
        assert result.total_methods == sum(r.method_count for r in result.per_repo)
        assert result.total_entities == sum(r.entity_count for r in result.per_repo)
        assert result.total_tables == sum(r.table_count for r in result.per_repo)
        assert result.total_mappings == sum(r.mapping_count for r in result.per_repo)
        assert result.total_terms == sum(r.term_count for r in result.per_repo)
        assert result.total_actions == sum(r.action_count for r in result.per_repo)
    finally:
        prod.close()


@requires_production_db
def test_full_pipeline_handles_subset_of_repos(scratch_session):
    """Caller can restrict the repo list — orchestrator should run only those."""
    prod = open_readonly_session()
    try:
        result = run_full_pipeline(prod, scratch_session, ("slab-design-real",))
        assert len(result.per_repo) == 1
        assert result.per_repo[0].repo_id == "slab-design-real"
    finally:
        prod.close()
