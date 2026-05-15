"""UC6 — 3-system schema evolution: banking + v2 + broadleaf (W29).

Validates that the Schema Layer pattern (W25/G4) is **system-agnostic** — all 3
plugin domains (banking / v2-slab-design / broadleaf) flow through the same:
  - JpaAnnotationExtractor (one extractor handles all 3 JPA dialects)
  - Schema Layer ORM (SchemaTableRow/Column/Constraint/Migration)
  - SchemaVerificationEngine (same R3 + R4 fixtures)
  - Integrator (single instance carrying 3 schema_change proposals)
  - Revision store (3 revisions, one per system)

Each system contributes its own JPA baseline + additive DDL diff. `repo_id`
isolates each system's schema rows in the same ontology DB — proving multi-
tenant ontology support (ADR-004 §3.4).

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc6_3system_schema.run
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.persistence.database import Base
from backend.sim_v2.core.integrator.integrator import Integrator
from backend.sim_v2.core.integrator.proposal import (
    OracleResult as ProposalOracleResult,
    Proposal,
    UserFeedback,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaColumnRow,
    SchemaConstraintRow,
    SchemaMigrationRow,
    SchemaTableRow,
)
from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import RecommendationEngine
from backend.sim_v2.core.verification.oracle import (
    FixtureOracleResult,
    OracleRequest,
    OracleResult,
    OutputDiff,
    TraceDiff,
    aggregate_status_from_fixtures,
)
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import (
    SchemaVerificationEngine,
    apply_forward,
    seed_baseline_schema as _seed_banking_baseline,
)
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import BANKING_BASELINE_JPA
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import SCHEMA_DIFF_V1_TO_V2 as BANKING_DIFF
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import REPO_ID as BANKING_REPO_ID
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import (
    baseline_columns,
)
from backend.sim_v2.demos.uc3_g3_correction_loop.run import ScriptedFixProvider


# ─────────────────────────────────────────────────────────────────────────────
# System 2 — v2-slab-design baseline (slab + order)
# ─────────────────────────────────────────────────────────────────────────────


V2_REPO_ID = "v2-slab-design"


V2_BASELINE_JPA: list[dict[str, Any]] = [
    {
        "class_fqn":  "com.posco.slabdesign.SlabEntity",
        "table_name": "slab",
        "schema_name": "public",
        "description": "v2 slab — primary mill artifact",
        "columns": [
            {"column_name": "id",              "data_type": "BIGINT",        "nullable": False, "primary_key": True},
            {"column_name": "slab_no",         "data_type": "VARCHAR(40)",   "nullable": False},
            {"column_name": "second_wgt_high", "data_type": "NUMERIC(15,3)", "nullable": False},
            {"column_name": "status_cd",       "data_type": "VARCHAR(8)",    "nullable": False, "default_value": "'NEW'"},
        ],
    },
    {
        "class_fqn":  "com.posco.slabdesign.OrderEntity",
        "table_name": "sd_order",
        "schema_name": "public",
        "description": "v2 order — downstream demand spec",
        "columns": [
            {"column_name": "id",              "data_type": "BIGINT",        "nullable": False, "primary_key": True},
            {"column_name": "order_no",        "data_type": "VARCHAR(40)",   "nullable": False},
            {"column_name": "order_wgt_high",  "data_type": "NUMERIC(15,3)", "nullable": False},
            {"column_name": "productivity",    "data_type": "NUMERIC(10,4)", "nullable": False},
        ],
    },
]


V2_DIFF = {
    "migration_version": "v2_add_slab_revision",
    "forward_ddl": """\
ALTER TABLE slab ADD COLUMN version_no INT NOT NULL DEFAULT 1;
CREATE TABLE slab_revision_log (
    id BIGINT PRIMARY KEY,
    slab_id BIGINT NOT NULL REFERENCES slab(id),
    from_status VARCHAR(8) NOT NULL,
    to_status   VARCHAR(8) NOT NULL,
    changed_at  TIMESTAMP  NOT NULL
);
""",
    "backward_ddl": """\
DROP TABLE slab_revision_log;
ALTER TABLE slab DROP COLUMN version_no;
""",
    "new_columns": [
        {
            "table_fqn":   "public.slab",
            "column_name": "version_no",
            "data_type":   "INT",
            "nullable":    False,
            "position":    4,
            "default_value": "1",
            "description": "slab record version counter (v2 evolution)",
        },
    ],
    "new_tables": [
        {
            "class_fqn":  "com.posco.slabdesign.SlabRevisionLog",
            "table_name": "slab_revision_log",
            "schema_name": "public",
            "description": "v2 slab status change audit",
            "columns": [
                {"column_name": "id",          "data_type": "BIGINT",      "nullable": False, "primary_key": True},
                {"column_name": "slab_id",     "data_type": "BIGINT",      "nullable": False},
                {"column_name": "from_status", "data_type": "VARCHAR(8)",  "nullable": False},
                {"column_name": "to_status",   "data_type": "VARCHAR(8)",  "nullable": False},
                {"column_name": "changed_at",  "data_type": "TIMESTAMP",   "nullable": False},
            ],
            "fks": [
                {"name": "fk_slab_revision_slab", "column": "slab_id",
                 "ref_table": "slab", "ref_column": "id"},
            ],
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# System 3 — broadleaf baseline (product + category)
# ─────────────────────────────────────────────────────────────────────────────


BROADLEAF_REPO_ID = "broadleaf"


BROADLEAF_BASELINE_JPA: list[dict[str, Any]] = [
    {
        "class_fqn":  "org.broadleafcommerce.catalog.Product",
        "table_name": "blc_product",
        "schema_name": "public",
        "description": "Broadleaf product entity",
        "columns": [
            {"column_name": "product_id",  "data_type": "BIGINT",        "nullable": False, "primary_key": True},
            {"column_name": "name",        "data_type": "VARCHAR(200)",  "nullable": False},
            {"column_name": "base_price",  "data_type": "NUMERIC(15,2)", "nullable": False},
            {"column_name": "category_id", "data_type": "BIGINT",        "nullable": True},
        ],
        "fks": [
            {"name": "fk_product_category", "column": "category_id",
             "ref_table": "blc_category", "ref_column": "category_id"},
        ],
    },
    {
        "class_fqn":  "org.broadleafcommerce.catalog.Category",
        "table_name": "blc_category",
        "schema_name": "public",
        "description": "Broadleaf category entity",
        "columns": [
            {"column_name": "category_id", "data_type": "BIGINT",       "nullable": False, "primary_key": True},
            {"column_name": "name",        "data_type": "VARCHAR(120)", "nullable": False},
            {"column_name": "url",         "data_type": "VARCHAR(255)", "nullable": True},
        ],
    },
]


BROADLEAF_DIFF = {
    "migration_version": "v2_add_product_change_log",
    "forward_ddl": """\
ALTER TABLE blc_product ADD COLUMN last_modified TIMESTAMP NULL;
CREATE TABLE blc_product_change_log (
    id BIGINT PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES blc_product(product_id),
    field_name VARCHAR(80) NOT NULL,
    old_value  TEXT,
    new_value  TEXT,
    changed_at TIMESTAMP NOT NULL
);
""",
    "backward_ddl": """\
DROP TABLE blc_product_change_log;
ALTER TABLE blc_product DROP COLUMN last_modified;
""",
    "new_columns": [
        {
            "table_fqn":   "public.blc_product",
            "column_name": "last_modified",
            "data_type":   "TIMESTAMP",
            "nullable":    True,
            "position":    4,
            "description": "product last-modified timestamp (v2 evolution)",
        },
    ],
    "new_tables": [
        {
            "class_fqn":  "org.broadleafcommerce.catalog.ProductChangeLog",
            "table_name": "blc_product_change_log",
            "schema_name": "public",
            "description": "broadleaf product field-change audit",
            "columns": [
                {"column_name": "id",         "data_type": "BIGINT",      "nullable": False, "primary_key": True},
                {"column_name": "product_id", "data_type": "BIGINT",      "nullable": False},
                {"column_name": "field_name", "data_type": "VARCHAR(80)", "nullable": False},
                {"column_name": "old_value",  "data_type": "TEXT",        "nullable": True},
                {"column_name": "new_value",  "data_type": "TEXT",        "nullable": True},
                {"column_name": "changed_at", "data_type": "TIMESTAMP",   "nullable": False},
            ],
            "fks": [
                {"name": "fk_change_log_product", "column": "product_id",
                 "ref_table": "blc_product", "ref_column": "product_id"},
            ],
        },
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# System manifest — drives the loop
# ─────────────────────────────────────────────────────────────────────────────


SYSTEMS = [
    {
        "name":       "banking",
        "repo_id":    BANKING_REPO_ID,
        "baseline":   BANKING_BASELINE_JPA,
        "diff":       BANKING_DIFF,
        "tables":     ["public.account", "public.transaction"],
        "added_table": "public.audit_log",
    },
    {
        "name":       "v2-slab-design",
        "repo_id":    V2_REPO_ID,
        "baseline":   V2_BASELINE_JPA,
        "diff":       V2_DIFF,
        "tables":     ["public.slab", "public.sd_order"],
        "added_table": "public.slab_revision_log",
    },
    {
        "name":       "broadleaf",
        "repo_id":    BROADLEAF_REPO_ID,
        "baseline":   BROADLEAF_BASELINE_JPA,
        "diff":       BROADLEAF_DIFF,
        "tables":     ["public.blc_product", "public.blc_category"],
        "added_table": "public.blc_product_change_log",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo seed/apply helpers (reuse uc4 internal functions but parameterized)
# ─────────────────────────────────────────────────────────────────────────────


def _build_shared_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        SchemaTableRow.__table__,
        SchemaColumnRow.__table__,
        SchemaConstraintRow.__table__,
        SchemaMigrationRow.__table__,
    ])
    return Session(engine)


def seed_baseline_for(session: Session, system: dict) -> None:
    """Seed a system's baseline schema using the shared JpaAnnotationExtractor.

    We monkey-patch the W25 helper's REPO_ID — instead, call the underlying
    persistence routine directly with the system's repo_id.
    """
    from backend.sim_v2.core.ontology.schema_layer.extractor import (
        SchemaSource,
        get_extractor,
    )
    import json as _json
    import hashlib as _hashlib

    extractor = get_extractor("jpa_annotation")
    model = extractor.extract(SchemaSource(
        kind="jpa_annotation",
        payload=system["baseline"],
        repo_id=system["repo_id"],
    ))
    # Persist with system-specific repo_id
    for t in model.tables:
        session.add(SchemaTableRow(
            fqn=t.fqn, table_name=t.table_name, schema_name=t.schema_name,
            description=t.description, source="jpa_annotation", repo_id=system["repo_id"],
        ))
    for c in model.columns:
        session.add(SchemaColumnRow(
            fqn=c.fqn, table_fqn=c.table_fqn, column_name=c.column_name,
            data_type=c.data_type, nullable=c.nullable, default_value=c.default_value,
            description=c.description, position=c.position, repo_id=system["repo_id"],
        ))
    for k in model.constraints:
        session.add(SchemaConstraintRow(
            table_fqn=k.table_fqn,
            constraint_name=k.constraint_name,
            kind=k.kind,
            columns_json=_json.dumps(k.columns),
            expression=k.expression,
            referenced_table_fqn=k.referenced_table_fqn,
            referenced_columns_json=_json.dumps(k.referenced_columns) if k.referenced_columns else None,
            repo_id=system["repo_id"],
        ))
    session.add(SchemaMigrationRow(
        system=system["name"],
        version="v1_initial",
        sha256=_hashlib.sha256(str(system["baseline"]).encode()).hexdigest()[:16],
        applied_at=datetime.now(timezone.utc).isoformat(),
        rollback_sql=None,
        description=f"{system['name']} baseline",
        repo_id=system["repo_id"],
    ))
    session.commit()


def apply_forward_for(session: Session, system: dict) -> None:
    """Apply a system's additive diff with system-specific repo_id."""
    from backend.sim_v2.core.ontology.schema_layer.extractor import (
        SchemaSource,
        get_extractor,
    )
    import json as _json
    import hashlib as _hashlib

    diff = system["diff"]
    for col in diff["new_columns"]:
        col_fqn = f"{col['table_fqn']}.{col['column_name']}"
        session.add(SchemaColumnRow(
            fqn=col_fqn,
            table_fqn=col["table_fqn"],
            column_name=col["column_name"],
            data_type=col["data_type"],
            nullable=col["nullable"],
            default_value=col.get("default_value"),
            description=col["description"],
            position=col["position"],
            repo_id=system["repo_id"],
        ))
    if diff.get("new_tables"):
        extractor = get_extractor("jpa_annotation")
        model = extractor.extract(SchemaSource(
            kind="jpa_annotation",
            payload=diff["new_tables"],
            repo_id=system["repo_id"],
        ))
        for t in model.tables:
            session.add(SchemaTableRow(
                fqn=t.fqn, table_name=t.table_name, schema_name=t.schema_name,
                description=t.description, source="jpa_annotation", repo_id=system["repo_id"],
            ))
        for c in model.columns:
            session.add(SchemaColumnRow(
                fqn=c.fqn, table_fqn=c.table_fqn, column_name=c.column_name,
                data_type=c.data_type, nullable=c.nullable, default_value=c.default_value,
                description=c.description, position=c.position, repo_id=system["repo_id"],
            ))
        for k in model.constraints:
            session.add(SchemaConstraintRow(
                table_fqn=k.table_fqn,
                constraint_name=k.constraint_name,
                kind=k.kind,
                columns_json=_json.dumps(k.columns),
                expression=k.expression,
                referenced_table_fqn=k.referenced_table_fqn,
                referenced_columns_json=_json.dumps(k.referenced_columns) if k.referenced_columns else None,
                repo_id=system["repo_id"],
            ))
    session.add(SchemaMigrationRow(
        system=system["name"],
        version=diff["migration_version"],
        sha256=_hashlib.sha256(str(diff).encode()).hexdigest()[:16],
        applied_at=datetime.now(timezone.utc).isoformat(),
        rollback_sql=diff["backward_ddl"],
        description=f"{system['name']} v1→v2 additive",
        repo_id=system["repo_id"],
    ))
    session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Per-repo VerificationEngine
# ─────────────────────────────────────────────────────────────────────────────


class _ScopedSchemaEngine:
    """Snapshot baseline at construction, then evaluate R3/R4 against migrated state."""

    def __init__(self, session: Session, repo_id: str) -> None:
        self.session = session
        self.repo_id = repo_id
        self.baseline = self._snapshot()

    def _snapshot(self) -> dict[str, list[str]]:
        rows = self.session.query(SchemaTableRow).filter_by(repo_id=self.repo_id).all()
        return {
            r.fqn: [
                col.column_name
                for col in self.session.query(SchemaColumnRow)
                    .filter_by(table_fqn=r.fqn, repo_id=self.repo_id)
                    .order_by(SchemaColumnRow.position, SchemaColumnRow.column_name)
                    .all()
            ]
            for r in rows
        }

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        results: dict[str, FixtureOracleResult] = {}
        for fid in request.fixture_subset:
            results[fid] = self._one(fid)
        agg = aggregate_status_from_fixtures(results)
        return OracleResult(
            proposal_id=request.proposal_id,
            by_fixture=results,
            aggregate_status=agg,
            summary=f"{len(results)} fixture(s) — aggregate={agg}",
        )

    def _one(self, fid: str) -> FixtureOracleResult:
        if fid.startswith("R3_"):
            table_fqn = fid[len("R3_"):]
            baseline = self.baseline.get(table_fqn, [])
            current = [
                c.column_name
                for c in self.session.query(SchemaColumnRow)
                    .filter_by(table_fqn=table_fqn, repo_id=self.repo_id)
                    .order_by(SchemaColumnRow.position, SchemaColumnRow.column_name)
                    .all()
            ]
            ok = all(col in current for col in baseline)
            return _result(fid, {"columns": baseline}, {"columns": current}, ok,
                           f"R3 {table_fqn}: baseline subset preserved={ok}")
        if fid == "R4_table_count_monotone":
            baseline_n = len(self.baseline)
            current_n = self.session.query(SchemaTableRow).filter_by(repo_id=self.repo_id).count()
            ok = current_n >= baseline_n
            return _result(fid, {"table_count": baseline_n}, {"table_count": current_n}, ok,
                           f"table count monotone: {baseline_n} → {current_n}")
        return _result(fid, None, None, False, f"unknown fixture {fid!r}")


def _result(fid, baseline_value, proposal_value, ok, summary) -> FixtureOracleResult:
    return FixtureOracleResult(
        fixture_id=fid,
        java_baseline_output=baseline_value,
        python_proposal_output=proposal_value,
        output_diff=OutputDiff(
            is_equivalent=ok,
            baseline_value=baseline_value,
            proposal_value=proposal_value,
            summary=summary,
        ),
        trace_diff=TraceDiff(is_equivalent=True, summary="schema R4 stable"),
        status="PASS" if ok else "FAIL_OUTPUT",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub recommendation (no LLM needed for pure schema_change)
# ─────────────────────────────────────────────────────────────────────────────


class _NoopRecommendation:
    def refine(self, proposal, hints):
        return proposal


# ─────────────────────────────────────────────────────────────────────────────
# Driver — process all 3 systems through a single Integrator
# ─────────────────────────────────────────────────────────────────────────────


class MultiSystemSchemaEngine:
    """VerificationEngine that holds per-repo `_ScopedSchemaEngine` snapshots.

    On run_oracle the engine looks up the proposal_id → repo_id mapping and
    delegates to the right scoped engine. The Integrator stays agnostic — same
    API, same proposal lifecycle, regardless of which system the proposal
    belongs to.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self._scoped: dict[str, _ScopedSchemaEngine] = {}
        self._prop_to_repo: dict[str, str] = {}

    def register_proposal(self, prop_id: str, repo_id: str) -> None:
        """Tie a proposal to its system. Snapshot the baseline now."""
        if repo_id not in self._scoped:
            self._scoped[repo_id] = _ScopedSchemaEngine(self.session, repo_id)
        self._prop_to_repo[prop_id] = repo_id

    def run_oracle(self, request: OracleRequest) -> OracleResult:
        repo_id = self._prop_to_repo.get(request.proposal_id)
        if repo_id is None:
            raise KeyError(f"Proposal {request.proposal_id!r} not registered with any repo")
        return self._scoped[repo_id].run_oracle(request)


def run_3system_schema_evolution() -> dict[str, Any]:
    session = _build_shared_session()
    multi_engine = MultiSystemSchemaEngine(session)
    integrator = Integrator(
        verification=multi_engine,
        recommendation=_NoopRecommendation(),
    )

    system_results: list[dict[str, Any]] = []

    for system in SYSTEMS:
        # 1) Seed baseline (with system's repo_id) — must precede engine.register
        #    because the scoped engine snapshots baseline shape on construction.
        seed_baseline_for(session, system)

        # 2) Create proposal in DRAFT
        prop = Proposal(
            type="schema_change",
            description=f"{system['name']} v1→v2 additive",
            plugin=system["name"],
            schema_diff={
                "migration_version": system["diff"]["migration_version"],
                "forward_ddl":       system["diff"]["forward_ddl"],
                "backward_ddl":      system["diff"]["backward_ddl"],
            },
        )
        # 3) Register the proposal with the multi-engine BEFORE submitting —
        #    this is when the baseline shape is snapshotted for this repo.
        multi_engine.register_proposal(prop.id, system["repo_id"])

        # 4) Apply forward DDL — mutates the ontology AFTER baseline snapshot
        apply_forward_for(session, system)

        # 5) Lifecycle via Integrator (same API for all 3 systems)
        prop_id = integrator.submit_proposal(prop)
        fixtures = [f"R3_{t}" for t in system["tables"]] + ["R4_table_count_monotone"]
        oracle_result = integrator.request_oracle(prop_id, fixtures)

        if oracle_result.aggregate_status == "PASS":
            integrator.review_proposal(prop_id, UserFeedback(
                decision="ACCEPT",
                timestamp=datetime.now(timezone.utc),
                user="dba",
                comments=f"{system['name']} additive — R3+R4 hold",
            ))
            rev_id = integrator.merge_proposal(
                prop_id=prop_id,
                ontology_revision=f"{system['name']}@2026-05-14",
                code_revision=f"git:{system['name']}-schema",
                schema_revision=system["diff"]["migration_version"],
                created_by="dba",
            )
        else:
            rev_id = None

        system_results.append({
            "system":     system["name"],
            "repo_id":    system["repo_id"],
            "prop_id":    prop_id,
            "oracle":     oracle_result,
            "rev_id":     rev_id,
            "proposal":   integrator.get_proposal(prop_id),
        })

    return {
        "session":     session,
        "integrator":  integrator,
        "multi_engine": multi_engine,
        "systems":     system_results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 78)
    print("UC6 — 3-system schema evolution (banking + v2 + broadleaf, W29)")
    print("=" * 78)
    print()

    state = run_3system_schema_evolution()
    session = state["session"]

    print(f"  Single Integrator carries {len(state['systems'])} schema_change proposals")
    print(f"  All systems share the same ontology session (repo_id-isolated)")
    print()

    all_pass = True
    for sys_state in state["systems"]:
        name = sys_state["system"]
        oracle = sys_state["oracle"]
        prop = sys_state["proposal"]
        rev_id = sys_state["rev_id"]
        print(f"── {name} ─────────────────────────────────────────────────────────")
        print(f"  repo_id              : {sys_state['repo_id']}")
        print(f"  oracle status        : {oracle.aggregate_status}")
        for fid, r in oracle.by_fixture.items():
            print(f"    {fid:<40} {r.status:<6} {r.output_diff.summary}")
        print(f"  proposal state       : {prop.state}")
        print(f"  revision id          : {rev_id}")
        print()
        if prop.state != "MERGED" or rev_id is None:
            all_pass = False

    # Per-system table count check (cross-tenant isolation)
    print("── Cross-tenant isolation check ──────────────────────────────────────")
    for sys_state in state["systems"]:
        n_tables = session.query(SchemaTableRow).filter_by(repo_id=sys_state["repo_id"]).count()
        print(f"  {sys_state['system']:<16} repo_id={sys_state['repo_id']:<20} tables={n_tables}")
    print()

    integrator = state["integrator"]
    print(f"  Total proposals merged    : {len(integrator.list_proposals(state='MERGED'))}")
    print(f"  Total revisions in store  : {integrator.revision_store.count()}")
    print()

    if all_pass and integrator.revision_store.count() == len(SYSTEMS):
        print("✓ Final verdict: PASS — 3 systems same framework, same Integrator")
        print("  G4 Schema Layer evolution validated across all 3 plugin systems")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
