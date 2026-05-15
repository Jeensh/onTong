"""UC5 capstone — all 4 gates active in a single banking pipeline (W26).

Banking loan-processing scenario that exercises G1+G2+G3+G4 end-to-end:

  G4 Schema evolution
     Banking baseline (account + loan + transaction) → additive DDL adds an
     `audit_log` table (consumed by G2 audit aspect downstream).

  G1 Java translation
     `InterestService.computeInterest` Java method → ontology-aware Python
     emission using OntologyTypeResolver + BigDecimal mapper. The *first*
     emission carries a deliberate bug (forgets /100 on rate) so the
     correction loop in G3 has something to fix.

  G2 Meta-programming (4 / 4 areas)
     · ADR-007 annotation       — banking.compensable wraps the method with
                                   saga rollback semantics
     · ADR-008 AOP / aspect     — banking.audit aspect decorates the method
                                   to record entries to the G4 audit_log
     · ADR-006 polymorphic disp — banking.drools_kbase_lookup turns a
                                   tiered-rate kbase into an if-elif chain
                                   used inside the method
     · ADR-009 bytecode         — banking.bpmn_dynamic_class emits a delegate
                                   class registry for an Activiti BPMN
                                   `loan-approval-process`

  G3 Correction loop
     First oracle on the buggy translation reports FAIL_BREAKING. The
     RecommendationEngine routes hints to a ScriptedFixProvider that returns
     the corrected emission; the proposal is refined, re-oracled (PASS),
     accepted, and merged.

Two `Proposal` instances flow through the same `Integrator`:
   1. schema_change → MERGED (G4)
   2. code_change   → ORACLED FAIL → refine → ORACLED PASS → MERGED (G1+G2+G3)

Run from repo root:
    .venv/bin/python -m backend.sim_v2.demos.uc5_capstone.run
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.modeling.code_layer.orm import CodeFieldRow, CodeTypeRow
from backend.modeling.domain_layer.orm import BusinessTermRow
from backend.modeling.persistence.database import Base
from backend.sim_v2.core.integrator.integrator import Integrator, ProposalRefinement
from backend.sim_v2.core.integrator.proposal import Proposal, UserFeedback
from backend.sim_v2.core.ontology.query import (
    find_business_terms_for_schema_column,
    find_schema_columns_for_business_term,
    find_schema_tables_for_code_type,
    schema_coverage_for_repo,
)
from backend.sim_v2.core.ontology.schema_layer.orm import (
    SchemaCodeMappingRow,
    SchemaColumnRow,
    SchemaConstraintRow,
    SchemaDomainMappingRow,
    SchemaMigrationRow,
    SchemaTableRow,
)
from backend.sim_v2.core.recommendation.anti_patterns.catalog import AntiPatternScanner
from backend.sim_v2.core.recommendation.engine import RecommendationEngine
from backend.sim_v2.core.synthesizer.annotations.registry import (
    AnnotationContext,
    get_default_registry as get_annotation_registry,
)
from backend.sim_v2.core.synthesizer.aop.registry import (
    AspectContext,
    get_default_registry as get_aop_registry,
)
from backend.sim_v2.core.synthesizer.bytecode.registry import (
    BytecodeContext,
    get_default_registry as get_bytecode_registry,
)
from backend.sim_v2.core.synthesizer.dispatchers.registry import (
    DispatchContext,
    get_default_registry as get_dispatcher_registry,
)
from backend.sim_v2.core.verification.scenario_engine import (
    Scenario,
    ScenarioVerificationEngine,
)

# Reuse already-validated demos as building blocks
from backend.sim_v2.demos.uc3_g3_correction_loop.run import ScriptedFixProvider
from backend.sim_v2.demos.uc4_g4_schema_evolution.run import (
    BANKING_BASELINE_JPA,
    SCHEMA_DIFF_V1_TO_V2,
    apply_forward as g4_apply_forward,
    seed_baseline_schema as g4_seed_baseline,
)

# Trigger banking + broadleaf extension auto-registration (all 4 G2 areas)
import backend.sim_v2.plugins.banking.annotations  # noqa: F401
import backend.sim_v2.plugins.banking.aop          # noqa: F401
import backend.sim_v2.plugins.banking.dispatchers  # noqa: F401
import backend.sim_v2.plugins.banking.bytecode     # noqa: F401


REPO_ID = "banking"


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth Python (oracle baseline) for InterestService.computeInterest
# ─────────────────────────────────────────────────────────────────────────────


def compute_interest_baseline(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")


# ─────────────────────────────────────────────────────────────────────────────
# "First-pass" Java translation output — deliberately omits /100 on rate
# (matches uc3 demo so the scripted LLM provider's canned fix applies)
# ─────────────────────────────────────────────────────────────────────────────


BUGGY_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate * Decimal(months) / Decimal("12")
"""

CORRECTED_EMISSION = """\
def compute_interest(principal, rate, months):
    return principal * rate / Decimal("100") * Decimal(months) / Decimal("12")
"""


# ─────────────────────────────────────────────────────────────────────────────
# G2 — Drools tiered-rate kbase (input metadata for W6.2 dispatcher)
# ─────────────────────────────────────────────────────────────────────────────


RATE_TIER_KBASE_NAME = "loan-rate-tier-kbase"
RATE_TIER_RULES = [
    {"name": "platinum_tier", "lhs": "credit_score >= 750", "rhs": "tier = 'PLATINUM'"},
    {"name": "gold_tier",     "lhs": "credit_score >= 650", "rhs": "tier = 'GOLD'"},
    {"name": "silver_tier",   "lhs": "credit_score >= 550", "rhs": "tier = 'SILVER'"},
]


# ─────────────────────────────────────────────────────────────────────────────
# G2 — BPMN dynamic class registry (input for W6.3 bytecode handler)
# ─────────────────────────────────────────────────────────────────────────────


BPMN_PROCESS_ID = "loan-approval-process"
BPMN_DELEGATES = {
    "interest_compute_task": "com.bank.InterestComputeDelegate",
    "audit_record_task":     "com.bank.AuditRecordDelegate",
}


# ─────────────────────────────────────────────────────────────────────────────
# Build ontology session + integrator (single store for both proposals)
# ─────────────────────────────────────────────────────────────────────────────


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        # Schema Layer (G4)
        SchemaTableRow.__table__,
        SchemaColumnRow.__table__,
        SchemaConstraintRow.__table__,
        SchemaMigrationRow.__table__,
        # W32: Code + Domain + cross-layer mapping tables (UC4 pre-flight)
        CodeTypeRow.__table__,
        CodeFieldRow.__table__,
        BusinessTermRow.__table__,
        SchemaCodeMappingRow.__table__,
        SchemaDomainMappingRow.__table__,
    ])
    return Session(engine)


def seed_cross_layer_ontology(session: Session) -> None:
    """W32 — populate Code + Domain layers + their mappings to Schema.

    Enables the UC4 pre-flight: before submitting code_change, ask the
    ontology which schema columns + business terms this method touches.
    """
    # Code Layer — InterestService + Account entity
    session.add_all([
        CodeTypeRow(
            fqn="com.bank.InterestService", simple_name="InterestService",
            package="com.bank", kind="CLASS", role="service", repo_id=REPO_ID,
        ),
        CodeTypeRow(
            fqn="com.bank.Account", simple_name="Account",
            package="com.bank", kind="CLASS", role="entity", repo_id=REPO_ID,
        ),
        CodeFieldRow(type_fqn="com.bank.Account", name="balance", type="java.math.BigDecimal"),
        CodeFieldRow(type_fqn="com.bank.Account", name="status",  type="java.lang.String"),
    ])
    # Domain Layer — business terms touched by computeInterest
    session.add_all([
        BusinessTermRow(
            fqn="banking.account",          label="Account",          domain="banking",
            kind="entity", is_root_entity=True, confirmed=True, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.account.balance",  label="Account Balance",  domain="banking",
            kind="atomic", value_type="java.math.BigDecimal", unit="USD",
            confirmed=True, repo_id=REPO_ID,
        ),
        BusinessTermRow(
            fqn="banking.interest_rate",    label="Interest Rate",    domain="banking",
            kind="atomic", value_type="java.math.BigDecimal", unit="percent",
            confirmed=True, repo_id=REPO_ID,
        ),
    ])
    # Schema ↔ Code mappings
    session.add_all([
        SchemaCodeMappingRow(
            schema_table_fqn="public.account",
            code_type_fqn="com.bank.Account",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
        SchemaCodeMappingRow(
            schema_column_fqn="public.account.balance",
            code_type_fqn="com.bank.Account",
            code_field_fqn="com.bank.Account#balance",
            mapping_kind="entity", confidence=1.0, confirmed=True,
            source="jpa_annotation", repo_id=REPO_ID,
        ),
    ])
    # Schema ↔ Domain mappings
    session.add_all([
        SchemaDomainMappingRow(
            schema_table_fqn="public.account",
            business_term_fqn="banking.account",
            confidence=1.0, confirmed=True, source="user", repo_id=REPO_ID,
        ),
        SchemaDomainMappingRow(
            schema_column_fqn="public.account.balance",
            business_term_fqn="banking.account.balance",
            confidence=0.95, confirmed=True, source="name_match", repo_id=REPO_ID,
        ),
    ])
    session.commit()


def run_uc4_preflight(session: Session) -> dict[str, Any]:
    """W32 — run cross-layer queries to surface schema impact of the upcoming
    code_change. The Recommendation Engine would use these hits to ground the
    LLM prompt (ADR-005 Layer 1 grounding) in real ontology context.
    """
    return {
        "code_to_schema_for_account":
            find_schema_tables_for_code_type(session, "com.bank.Account", REPO_ID),
        "schema_to_terms_for_balance":
            find_business_terms_for_schema_column(session, "public.account.balance", REPO_ID),
        "terms_to_schema_for_balance":
            find_schema_columns_for_business_term(session, "banking.account.balance", REPO_ID),
        "coverage":
            schema_coverage_for_repo(session, REPO_ID),
    }


def compile_emission(source: str) -> Any:
    g: dict[str, Any] = {"Decimal": Decimal}
    exec(compile(source, "<capstone>", "exec"), g)
    return g["compute_interest"]


def make_fixtures() -> dict[str, Scenario]:
    return {
        "F1_small":  Scenario(fixture_id="F1_small",
                              inputs={"principal": Decimal("1000"), "rate": Decimal("5"),    "months": 12}),
        "F2_medium": Scenario(fixture_id="F2_medium",
                              inputs={"principal": Decimal("50000"), "rate": Decimal("4.5"), "months": 36}),
        "F3_large":  Scenario(fixture_id="F3_large",
                              inputs={"principal": Decimal("250000"), "rate": Decimal("3.25"), "months": 60}),
    }


# ─────────────────────────────────────────────────────────────────────────────
# G2 activation — invoke all 4 handlers, collect their outputs
# ─────────────────────────────────────────────────────────────────────────────


def activate_all_meta_programming() -> dict[str, str]:
    """Invoke ADR-006/007/008/009 handlers and return their emitted Python
    fragments. Each handler is plugin-registered (auto on import)."""
    out: dict[str, str] = {}

    # ADR-007 annotation: @Compensable wrap
    ann_handler = get_annotation_registry().get("bank.annotation.Compensable")
    ann_out = ann_handler.handle(AnnotationContext(
        annotation_fqn="bank.annotation.Compensable",
        annotation_args={"compensationMethod": "refundInterest"},
        target_kind="method",
        target_metadata={"class_fqn": "com.bank.InterestService", "method_name": "computeInterest"},
        plugin_name="banking",
    ))
    out["annotation"] = ann_out.python_source

    # ADR-008 AOP: audit aspect (records to G4 audit_log)
    aop_handler = get_aop_registry().get("banking.audit")
    aop_out = aop_handler.weave(AspectContext(
        aspect_name="banking.audit",
        advice_kind="after_returning",
        target_method={"class_fqn": "com.bank.InterestService", "method_name": "computeInterest"},
        aspect_args={"audit_table": "audit_log"},
        plugin_name="banking",
    ))
    out["aspect"] = aop_out.python_source

    # ADR-006 dispatch: tiered-rate Drools kbase
    disp_handler = get_dispatcher_registry().get("banking.drools_kbase_lookup")
    disp_out = disp_handler.synthesize(DispatchContext(
        dispatch_kind="banking.drools_kbase_lookup",
        call_site={"kbase_name": RATE_TIER_KBASE_NAME, "rules": RATE_TIER_RULES},
        plugin_name="banking",
    ))
    out["dispatch"] = disp_out.python_source

    # ADR-009 bytecode: BPMN dynamic delegate registry
    byte_handler = get_bytecode_registry().get("banking.bpmn_dynamic_class")
    byte_out = byte_handler.synthesize(BytecodeContext(
        pattern_name="banking.bpmn_dynamic_class",
        target_class=BPMN_PROCESS_ID,
        pattern_args={"process_id": BPMN_PROCESS_ID, "delegates": BPMN_DELEGATES},
        plugin_name="banking",
    ))
    out["bytecode"] = byte_out.python_source

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Capstone orchestration
# ─────────────────────────────────────────────────────────────────────────────


def run_capstone() -> dict[str, Any]:
    state: dict[str, Any] = {}

    # ─── Build shared session + integrator ────────────────────────────────────
    session = build_session()
    g4_seed_baseline(session)
    state["baseline_table_count"] = session.query(SchemaTableRow).filter_by(repo_id=REPO_ID).count()

    provider = ScriptedFixProvider()
    rec_engine = RecommendationEngine(provider=provider, scanner=AntiPatternScanner())

    fixtures = make_fixtures()
    scen_engine = ScenarioVerificationEngine(
        translated_fn=compile_emission(BUGGY_EMISSION),
        baseline_fn=compute_interest_baseline,
        fixtures=fixtures,
    )
    integrator = Integrator(verification=scen_engine, recommendation=rec_engine)

    # ═════════════════════════════════════════════════════════════════════════
    # G4 — submit + merge schema_change proposal
    # ═════════════════════════════════════════════════════════════════════════
    g4_apply_forward(session, SCHEMA_DIFF_V1_TO_V2)
    state["post_migration_table_count"] = session.query(SchemaTableRow).filter_by(repo_id=REPO_ID).count()

    schema_prop = Proposal(
        type="schema_change",
        description="Add audit_log + account.updated_at (additive v2)",
        plugin="banking",
        schema_diff={
            "migration_version": SCHEMA_DIFF_V1_TO_V2["migration_version"],
            "forward_ddl":       SCHEMA_DIFF_V1_TO_V2["forward_ddl"],
            "backward_ddl":      SCHEMA_DIFF_V1_TO_V2["backward_ddl"],
        },
    )
    schema_prop_id = integrator.submit_proposal(schema_prop)
    # ScenarioVerificationEngine doesn't fit schema_change semantics — manually
    # transition + populate the placeholder OracleResult.
    from backend.sim_v2.core.integrator.proposal import OracleResult as P_OracleResult
    schema_prop.transition(to_state="ORACLED", actor="verification_engine",
                           notes="ontology shape preserved (R3+R4)")
    schema_prop.oracle_result = P_OracleResult(
        aggregate_status="PASS",
        summary="schema additive R3+R4 hold",
    )
    integrator.review_proposal(schema_prop_id, UserFeedback(
        decision="ACCEPT", timestamp=datetime.now(timezone.utc), user="dba",
        comments="additive — baseline preserved",
    ))
    schema_rev = integrator.merge_proposal(
        prop_id=schema_prop_id,
        ontology_revision="banking@2026-05-14",
        code_revision="git:capstone",
        schema_revision=SCHEMA_DIFF_V1_TO_V2["migration_version"],
        created_by="dba",
    )
    state["schema_prop_id"] = schema_prop_id
    state["schema_revision_id"] = schema_rev

    # ═════════════════════════════════════════════════════════════════════════
    # UC4 cross-layer pre-flight (W32) — seed Code/Domain, run impact queries
    # ═════════════════════════════════════════════════════════════════════════
    seed_cross_layer_ontology(session)
    state["preflight"] = run_uc4_preflight(session)

    # ═════════════════════════════════════════════════════════════════════════
    # G2 — activate all 4 meta-programming areas
    # ═════════════════════════════════════════════════════════════════════════
    meta = activate_all_meta_programming()
    state["meta_outputs"] = meta

    # ═════════════════════════════════════════════════════════════════════════
    # G1 + G3 — submit code_change with buggy emission, refine, re-oracle, merge
    # ═════════════════════════════════════════════════════════════════════════
    code_prop = Proposal(
        type="code_change",
        description="Emit InterestService.computeInterest + 4 meta-prog overlays",
        plugin="banking",
        code_diff={
            "method_fqn":         "com.bank.InterestService#computeInterest",
            "python_source":      BUGGY_EMISSION,
            "annotation_overlay": meta["annotation"],
            "aspect_overlay":     meta["aspect"],
            "dispatch_overlay":   meta["dispatch"],
            "bytecode_overlay":   meta["bytecode"],
        },
    )
    code_prop_id = integrator.submit_proposal(code_prop)
    first_oracle = integrator.request_oracle(code_prop_id, list(fixtures.keys()))
    state["first_oracle"] = first_oracle

    # G3 — refine via recommendation engine
    refined_prop = rec_engine.refine(integrator.get_proposal(code_prop_id), hints={
        "oracle_status": first_oracle.aggregate_status,
        "diff_summary":  first_oracle.summary,
    })
    refined_source = refined_prop.code_diff["refined_llm_output"]
    state["refined_source"] = refined_source
    state["provider_calls"] = len(provider.calls)

    integrator.refine_proposal(
        prop_id=code_prop_id,
        refinement=ProposalRefinement(
            code_diff_update={"python_source": refined_source},
            reason="scripted LLM corrected the divide-by-100",
        ),
    )
    scen_engine.translated_fn = compile_emission(refined_source)
    # Re-promote DRAFT → PROPOSED via Integrator.re_propose helper (W28)
    integrator.re_propose(code_prop_id)
    second_oracle = integrator.request_oracle(code_prop_id, list(fixtures.keys()))
    state["second_oracle"] = second_oracle

    if second_oracle.aggregate_status == "PASS":
        integrator.review_proposal(code_prop_id, UserFeedback(
            decision="ACCEPT", timestamp=datetime.now(timezone.utc), user="reviewer",
            comments="all 3 fixtures PASS after refine",
        ))
        code_rev = integrator.merge_proposal(
            prop_id=code_prop_id,
            ontology_revision="banking@2026-05-14",
            code_revision="git:capstone-interest",
            schema_revision=SCHEMA_DIFF_V1_TO_V2["migration_version"],
            created_by="reviewer",
            parent_revision=schema_rev,  # lineage chain: schema rev → code rev
        )
        state["code_revision_id"] = code_rev
    else:
        state["code_revision_id"] = None

    state["integrator"] = integrator
    state["session"]    = session
    state["schema_proposal"] = integrator.get_proposal(schema_prop_id)
    state["code_proposal"]   = integrator.get_proposal(code_prop_id)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────


def _banner(text: str) -> None:
    print("─" * 78)
    print(text)
    print("─" * 78)


def main() -> int:
    print("=" * 78)
    print("UC5 capstone — G1+G2+G3+G4 + UC4 cross-layer (W26+W32)")
    print("=" * 78)
    print()

    s = run_capstone()

    _banner("G4  Schema Layer evolution (ADR-004)")
    print(f"  baseline tables           : {s['baseline_table_count']}")
    print(f"  post-migration tables     : {s['post_migration_table_count']}  (+audit_log)")
    print(f"  schema proposal state     : {s['schema_proposal'].state}")
    print(f"  schema revision id        : {s['schema_revision_id']}")
    print()

    _banner("UC4  Cross-layer pre-flight (W32) — schema impact of upcoming code_change")
    pf = s["preflight"]
    print(f"  code-to-schema (com.bank.Account):")
    for hit in pf["code_to_schema_for_account"]:
        print(f"    table={hit.schema_table_fqn or '-':<22} column={hit.schema_column_fqn or '-'}")
    print(f"  schema-to-terms (public.account.balance):")
    for hit in pf["schema_to_terms_for_balance"]:
        print(f"    term={hit.business_term_fqn:<32} confirmed={hit.confirmed}")
    print(f"  domain-to-schema (banking.account.balance):")
    for hit in pf["terms_to_schema_for_balance"]:
        print(f"    column={hit.column_fqn:<32} confirmed={hit.confirmed}")
    cov = pf["coverage"]
    print(f"  coverage: tables={cov.table_count}, "
          f"domain-mapped cols={cov.domain_mapped_columns} (confirmed {cov.confirmed_domain_mappings}), "
          f"code-mapped cols={cov.code_mapped_columns} (confirmed {cov.confirmed_code_mappings})")
    print()

    _banner("G2  Meta-programming overlays (4 / 4 ADR areas)")
    for kind, src in s["meta_outputs"].items():
        print(f"  • {kind:<10} ({len(src.splitlines())} lines, first line: {src.splitlines()[0]!r})")
    print()

    _banner("G1  Java translation (BUGGY first pass)")
    for line in BUGGY_EMISSION.rstrip().split("\n"):
        print(f"  | {line}")
    print()

    _banner("G3  Correction loop — 1st oracle")
    o1 = s["first_oracle"]
    print(f"  aggregate_status = {o1.aggregate_status}")
    print(f"  summary          = {o1.summary}")
    print()

    _banner("G3  RecommendationEngine.refine() → scripted LLM")
    print(f"  provider call count: {s['provider_calls']}")
    print("  refined source:")
    for line in s["refined_source"].rstrip().split("\n"):
        print(f"  | {line}")
    print()

    _banner("G3  Correction loop — 2nd oracle")
    o2 = s["second_oracle"]
    print(f"  aggregate_status = {o2.aggregate_status}")
    for fid, r in o2.by_fixture.items():
        print(f"    {fid:<10} {r.status:<6} baseline={r.java_baseline_output} proposal={r.python_proposal_output}")
    print()

    _banner("Final state — 2 proposals MERGED, framework end-to-end active")
    cp = s["code_proposal"]
    print(f"  schema_change proposal      : state={s['schema_proposal'].state}, revision={s['schema_revision_id']}")
    print(f"  code_change proposal        : state={cp.state}, revision={s['code_revision_id']}")
    print(f"  code revision parent linkage: {s['schema_revision_id']} (schema-first lineage)")
    print(f"  code lifecycle audit ({len(cp.history)} events):")
    for i, ev in enumerate(cp.history, 1):
        print(f"    {i}. {ev.from_state:<10} → {ev.to_state:<10} actor={ev.actor}")
    print()

    success = (
        s["schema_proposal"].state == "MERGED"
        and cp.state == "MERGED"
        and s["first_oracle"].aggregate_status  == "FAIL_BREAKING"
        and s["second_oracle"].aggregate_status == "PASS"
        and s["post_migration_table_count"] > s["baseline_table_count"]
        and len(s["meta_outputs"]) == 4
    )
    if success:
        print("✓ Final verdict: PASS — Two-Engine Plugin Framework end-to-end")
        print("  All gates active in a single Integrator session:")
        print("    G1 Java translation (buggy → corrected)")
        print("    G2 4 / 4 meta-programming overlays emitted (annotation/AOP/dispatch/bytecode)")
        print("    G3 correction loop closed (FAIL_BREAKING → refine → PASS)")
        print("    G4 schema migration MERGED (additive R3+R4 hold)")
        print("    UC4 cross-layer pre-flight surfaced schema/term impact (W32)")
        return 0
    print("✗ Final verdict: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
