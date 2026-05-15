"""UC16 — Composite production pipeline (W46).

Final stage of the production-wiring storyline. UC10-15 each demonstrate one
capability against the production DB; UC16 runs all six in sequence within a
single demo, aggregating per-stage counts and per-repo cross-references.

Stages (per repo):
    1. Inspect       — count code methods that have body_text
    2. Translate     — translate a sample of methods, classify each PASS/LOCKED/etc.
    3. Schema onboard — JPA annotations → SchemaModel
    4. Persist + map  — persist into scratch ORM, count code↔schema mappings
    5. Drift detect  — synthetic mutation → diff
    6. Domain query  — read business_terms / actions / anchor_bindings + sample
                       one cross-layer resolution

The orchestrator returns a `PipelineResult` carrying per-stage metrics.

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc16_production_pipeline.run
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.ontology.domain_layer.production_domain_loader import (
    load_actions,
    load_anchor_bindings,
    load_business_terms,
)
from backend.sim_v2.core.ontology.schema_layer.extractor import (
    JpaAnnotationExtractor,
    SchemaSource,
)
from backend.sim_v2.core.ontology.schema_layer.persistence import persist_schema_model
from backend.sim_v2.core.ontology.schema_layer.production_jpa_loader import (
    load_entity_dicts,
)
from backend.sim_v2.core.ontology.schema_layer.schema_diff import compute_diff
from backend.sim_v2.demos.uc10_production_inspector.run import (
    PRODUCTION_DB_PATH,
    open_readonly_session,
)
from backend.sim_v2.demos.uc11_production_translator.run import (
    fetch_methods,
    run_translation_survey,
)
from backend.sim_v2.demos.uc14_production_schema_drift.run import mutate_entities


DEFAULT_REPOS: tuple[str, ...] = (
    "synthetic-5k",
    "slab-design-real-v2",
    "slab-design-real",
)
TRANSLATE_SAMPLE_SIZE = 100


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RepoPipelineResult:
    repo_id:              str

    # Stage 1 — inspect
    method_count:         int

    # Stage 2 — translate
    sample_size:          int
    translate_pass:       int
    translate_locked:     int
    translate_pass_rate:  float

    # Stage 3+4 — schema onboard + persist
    entity_count:         int
    table_count:          int
    column_count:         int
    mapping_count:        int

    # Stage 5 — drift
    drift_added_cols:     int
    drift_removed_cols:   int
    drift_changed_cols:   int

    # Stage 6 — domain
    term_count:           int
    action_count:         int
    binding_count:        int
    sample_term_actions:  int = 0


@dataclass(frozen=True)
class PipelineResult:
    per_repo:                  tuple[RepoPipelineResult, ...]
    total_methods:             int
    total_translate_pass:      int
    total_translate_locked:    int
    total_entities:            int
    total_tables:              int
    total_columns:             int
    total_mappings:            int
    total_drift_added:         int
    total_drift_removed:       int
    total_drift_changed:       int
    total_terms:               int
    total_actions:             int
    total_bindings:            int


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo orchestration
# ─────────────────────────────────────────────────────────────────────────────


def run_pipeline_for_repo(
    prod_session: Session,
    scratch_session: Session,
    repo_id: str,
    *,
    translate_sample: int = TRANSLATE_SAMPLE_SIZE,
) -> RepoPipelineResult:
    """Run all 6 stages on `repo_id`. `scratch_session` is a writable in-memory
    ORM session used by stage 4. `prod_session` is read-only."""

    # Stage 1 — inspect (just count methods with body_text)
    methods = fetch_methods(prod_session, repo_id, limit=10_000_000)
    method_count = len(methods)

    # Stage 2 — translate a sample
    translate_report = run_translation_survey(
        prod_session, repo_id, sample_size=translate_sample,
    )
    pass_rate = translate_report.pass_rate

    # Stage 3 — schema onboard
    entities = load_entity_dicts(prod_session, repo_id)
    schema_model = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=entities, repo_id=repo_id)
    )

    # Stage 4 — persist
    counts = persist_schema_model(schema_model, scratch_session, repo_id)
    scratch_session.commit()

    # Stage 5 — drift via synthetic mutation
    mutated = mutate_entities(entities)
    schema_model_v2 = JpaAnnotationExtractor().extract(
        SchemaSource(kind="jpa_annotation", payload=mutated, repo_id=repo_id)
    )
    diff = compute_diff(schema_model, schema_model_v2)

    # Stage 6 — domain query
    terms = load_business_terms(prod_session, repo_id)
    actions = load_actions(prod_session, repo_id)
    bindings = load_anchor_bindings(prod_session, repo_id)
    sample_term_actions = 0
    if actions:
        by_term: dict[str, int] = {}
        for a in actions:
            if a.declared_on_term:
                by_term[a.declared_on_term] = by_term.get(a.declared_on_term, 0) + 1
        if by_term:
            sample_term_actions = max(by_term.values())

    return RepoPipelineResult(
        repo_id=repo_id,
        method_count=method_count,
        sample_size=translate_report.sample_size,
        translate_pass=translate_report.pass_count,
        translate_locked=translate_report.locked_count,
        translate_pass_rate=pass_rate,
        entity_count=len(entities),
        table_count=counts.tables,
        column_count=counts.columns,
        mapping_count=counts.code_mappings,
        drift_added_cols=len(diff.added_columns),
        drift_removed_cols=len(diff.removed_columns),
        drift_changed_cols=len(diff.changed_columns),
        term_count=len(terms),
        action_count=len(actions),
        binding_count=len(bindings),
        sample_term_actions=sample_term_actions,
    )


def run_full_pipeline(
    prod_session: Session,
    scratch_session: Session,
    repos: tuple[str, ...] = DEFAULT_REPOS,
) -> PipelineResult:
    per_repo: list[RepoPipelineResult] = []
    for repo_id in repos:
        per_repo.append(
            run_pipeline_for_repo(prod_session, scratch_session, repo_id)
        )
    return PipelineResult(
        per_repo=tuple(per_repo),
        total_methods=sum(r.method_count for r in per_repo),
        total_translate_pass=sum(r.translate_pass for r in per_repo),
        total_translate_locked=sum(r.translate_locked for r in per_repo),
        total_entities=sum(r.entity_count for r in per_repo),
        total_tables=sum(r.table_count for r in per_repo),
        total_columns=sum(r.column_count for r in per_repo),
        total_mappings=sum(r.mapping_count for r in per_repo),
        total_drift_added=sum(r.drift_added_cols for r in per_repo),
        total_drift_removed=sum(r.drift_removed_cols for r in per_repo),
        total_drift_changed=sum(r.drift_changed_cols for r in per_repo),
        total_terms=sum(r.term_count for r in per_repo),
        total_actions=sum(r.action_count for r in per_repo),
        total_bindings=sum(r.binding_count for r in per_repo),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text_line: str) -> None:
    print("─" * 78)
    print(text_line)
    print("─" * 78)


def main(repos: tuple[str, ...] = DEFAULT_REPOS) -> int:
    print("=" * 78)
    print("UC16 — Composite production pipeline (W46)")
    print("=" * 78)
    print()

    prod_session = open_readonly_session()
    if prod_session is None:
        print(f"  {PRODUCTION_DB_PATH} not found — skipping (CI / fresh checkout)")
        return 0

    scratch_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(scratch_engine)

    try:
        with Session(scratch_engine) as scratch_session:
            result = run_full_pipeline(prod_session, scratch_session, repos)

        for r in result.per_repo:
            _banner(f"Repo: {r.repo_id}")
            print(f"  1. Inspect       : {r.method_count:7d} methods with body_text")
            print(f"  2. Translate     : {r.translate_pass}/{r.sample_size} sample = "
                  f"{r.translate_pass_rate * 100:.1f}% PASS")
            print(f"  3. Schema onboard: {r.entity_count:4d} entities → {r.table_count:4d} tables")
            print(f"  4. Persist+map   : {r.column_count:5d} cols / {r.mapping_count:5d} mappings")
            print(f"  5. Drift detect  : +{r.drift_added_cols} / -{r.drift_removed_cols} / "
                  f"~{r.drift_changed_cols} (synthetic mutation)")
            print(f"  6. Domain query  : {r.term_count:5d} terms / {r.action_count:5d} actions / "
                  f"{r.binding_count:4d} bindings (sample term→{r.sample_term_actions} actions)")
            print()

        _banner("Aggregate (all repos)")
        print(f"  Methods inspected  : {result.total_methods}")
        print(f"  Translate PASS     : {result.total_translate_pass} "
              f"(LOCKED {result.total_translate_locked})")
        print(f"  Entities / tables  : {result.total_entities} / {result.total_tables}")
        print(f"  Columns / mappings : {result.total_columns} / {result.total_mappings}")
        print(f"  Drift +/-/~        : {result.total_drift_added} / "
              f"{result.total_drift_removed} / {result.total_drift_changed}")
        print(f"  Terms / actions    : {result.total_terms} / {result.total_actions}")
        print(f"  Anchor bindings    : {result.total_bindings}")
        print()
        print("✓ Full 6-stage production pipeline operational end-to-end on real data")
        return 0
    finally:
        prod_session.close()
        scratch_engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
