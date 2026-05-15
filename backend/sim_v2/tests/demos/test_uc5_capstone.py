"""UC5 capstone demo verification — W26.3.

Validates the framework end-to-end with all 4 gates active in a single flow:
  - G4 schema_change proposal reaches MERGED with revision
  - G2 all 4 meta-programming areas (annotation/AOP/dispatch/bytecode) emit
  - G1 Java translation produces buggy emission (intentional)
  - G3 correction loop: FAIL_BREAKING → refine → PASS → ACCEPT → MERGED
  - Code revision's parent_revision points at the schema revision (lineage)
"""
from __future__ import annotations

import importlib

import pytest

from backend.sim_v2.demos.uc5_capstone.run import (
    BPMN_DELEGATES,
    BPMN_PROCESS_ID,
    BUGGY_EMISSION,
    CORRECTED_EMISSION,
    RATE_TIER_KBASE_NAME,
    RATE_TIER_RULES,
    activate_all_meta_programming,
    main,
    run_capstone,
)


@pytest.fixture(autouse=True)
def _ensure_banking_extensions_registered():
    """Reload banking extension modules to recover from cross-test registry resets.

    test_banking_extensions.py uses an autouse fixture that calls reset_*() on
    annotation/dispatcher/aop/bytecode registries. Re-import here so all 4
    handlers are available for the capstone.
    """
    import backend.sim_v2.plugins.banking.annotations as ann
    import backend.sim_v2.plugins.banking.aop          as aop
    import backend.sim_v2.plugins.banking.dispatchers  as disp
    import backend.sim_v2.plugins.banking.bytecode     as byte
    importlib.reload(ann)
    importlib.reload(aop)
    importlib.reload(disp)
    importlib.reload(byte)
    yield


@pytest.fixture
def capstone_state():
    return run_capstone()


# ─────────────────────────────────────────────────────────────────────────────
# Demo main
# ─────────────────────────────────────────────────────────────────────────────


def test_demo_main_returns_zero():
    """The W26 capstone main() exits 0 — all 4 gates pass."""
    assert main() == 0


# ─────────────────────────────────────────────────────────────────────────────
# G4 — schema migration MERGED
# ─────────────────────────────────────────────────────────────────────────────


def test_g4_baseline_then_post_migration_table_count(capstone_state):
    assert capstone_state["baseline_table_count"] == 2
    assert capstone_state["post_migration_table_count"] == 3


def test_g4_schema_proposal_merged(capstone_state):
    assert capstone_state["schema_proposal"].state == "MERGED"
    assert capstone_state["schema_revision_id"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# G2 — all 4 meta-prog handlers emitted
# ─────────────────────────────────────────────────────────────────────────────


def test_g2_all_four_overlays_emitted(capstone_state):
    meta = capstone_state["meta_outputs"]
    assert set(meta.keys()) == {"annotation", "aspect", "dispatch", "bytecode"}
    for kind, src in meta.items():
        assert src.strip(), f"{kind} overlay is empty"


def test_g2_annotation_overlay_contains_compensable_signature():
    """ADR-007 — @Compensable produces a wrapper with the compensation method baked in."""
    meta = activate_all_meta_programming()
    src = meta["annotation"]
    assert "_compensable_wrap" in src
    assert "refundInterest" in src


def test_g2_aspect_overlay_carries_audit_table():
    """ADR-008 — audit aspect emits a decorator that records audit_log entries."""
    meta = activate_all_meta_programming()
    assert "audit_log" in meta["aspect"]


def test_g2_dispatch_overlay_renders_rate_tier_rules():
    """ADR-006 — Drools kbase renders into a Python if-elif decision tree."""
    meta = activate_all_meta_programming()
    src = meta["dispatch"]
    for rule in RATE_TIER_RULES:
        assert rule["name"] in src
    assert "platinum_tier" in src
    assert RATE_TIER_KBASE_NAME in src


def test_g2_bytecode_overlay_renders_bpmn_delegates():
    """ADR-009 — BPMN handler emits a class registry + lookup function."""
    meta = activate_all_meta_programming()
    src = meta["bytecode"]
    for task_id in BPMN_DELEGATES:
        assert f"'{task_id}'" in src
    assert BPMN_PROCESS_ID in src
    assert "lookup_bpmn_delegate" in src


# ─────────────────────────────────────────────────────────────────────────────
# G1 + G3 — translation + correction loop
# ─────────────────────────────────────────────────────────────────────────────


def test_g1_buggy_emission_diverges_then_corrected(capstone_state):
    # First oracle fails on the buggy translation
    assert capstone_state["first_oracle"].aggregate_status == "FAIL_BREAKING"
    # Refined source equals the corrected emission (scripted-provider determinism)
    assert capstone_state["refined_source"] == CORRECTED_EMISSION


def test_g3_correction_loop_one_llm_call_then_pass(capstone_state):
    assert capstone_state["provider_calls"] == 1
    assert capstone_state["second_oracle"].aggregate_status == "PASS"


def test_g3_code_proposal_merged_with_lineage(capstone_state):
    code_prop = capstone_state["code_proposal"]
    assert code_prop.state == "MERGED"
    integrator = capstone_state["integrator"]
    code_rev = integrator.revision_store.get(capstone_state["code_revision_id"])
    schema_rev_id = capstone_state["schema_revision_id"]
    # Lineage chain: code revision's parent IS the schema revision
    assert code_rev is not None
    assert code_rev.parent_revision == schema_rev_id


def test_g3_code_lifecycle_has_eight_events(capstone_state):
    transitions = [
        (e.from_state, e.to_state)
        for e in capstone_state["code_proposal"].history
    ]
    assert transitions == [
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "DRAFT"),
        ("DRAFT",    "PROPOSED"),
        ("PROPOSED", "ORACLED"),
        ("ORACLED",  "REVIEWED"),
        ("REVIEWED", "ACCEPTED"),
        ("ACCEPTED", "MERGED"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Integration — single integrator carries both proposals
# ─────────────────────────────────────────────────────────────────────────────


def test_integrator_holds_both_proposals(capstone_state):
    integrator = capstone_state["integrator"]
    schema = integrator.get_proposal(capstone_state["schema_prop_id"])
    code   = integrator.get_proposal(capstone_state["code_proposal"].id)
    assert schema is not None
    assert code   is not None
    assert schema.type == "schema_change"
    assert code.type   == "code_change"
    assert schema.plugin == "banking"
    assert code.plugin   == "banking"


def test_revision_store_has_two_revisions(capstone_state):
    integrator = capstone_state["integrator"]
    schema_rev = integrator.revision_store.get(capstone_state["schema_revision_id"])
    code_rev   = integrator.revision_store.get(capstone_state["code_revision_id"])
    assert schema_rev is not None
    assert code_rev   is not None


# ─────────────────────────────────────────────────────────────────────────────
# UC4 cross-layer pre-flight (W32)
# ─────────────────────────────────────────────────────────────────────────────


def test_uc4_preflight_payload_present(capstone_state):
    """W32 — capstone state carries a preflight payload with all 4 query results."""
    pf = capstone_state["preflight"]
    assert set(pf.keys()) == {
        "code_to_schema_for_account",
        "schema_to_terms_for_balance",
        "terms_to_schema_for_balance",
        "coverage",
    }


def test_uc4_preflight_code_to_schema_for_account(capstone_state):
    """com.bank.Account class maps to both the account table and balance column."""
    hits = capstone_state["preflight"]["code_to_schema_for_account"]
    tables = {h.schema_table_fqn for h in hits if h.schema_table_fqn}
    columns = {h.schema_column_fqn for h in hits if h.schema_column_fqn}
    assert "public.account"         in tables
    assert "public.account.balance" in columns


def test_uc4_preflight_schema_to_terms_for_balance(capstone_state):
    """public.account.balance maps to its own term + parent table's term."""
    hits = capstone_state["preflight"]["schema_to_terms_for_balance"]
    terms = {h.business_term_fqn for h in hits}
    assert "banking.account.balance" in terms
    assert "banking.account"         in terms


def test_uc4_preflight_terms_to_schema_for_balance(capstone_state):
    """banking.account.balance term resolves back to its schema column."""
    hits = capstone_state["preflight"]["terms_to_schema_for_balance"]
    assert any(h.column_fqn == "public.account.balance" and h.confirmed for h in hits)


def test_uc4_preflight_coverage_sanity(capstone_state):
    """Coverage stats reflect the seeded cross-layer mappings."""
    cov = capstone_state["preflight"]["coverage"]
    # 3 tables (account + transaction + audit_log) after G4 migration
    assert cov.table_count == 3
    # At least the seeded mappings should be visible
    assert cov.confirmed_domain_mappings >= 1
    assert cov.confirmed_code_mappings   >= 1


# ─────────────────────────────────────────────────────────────────────────────
# All-gates marker
# ─────────────────────────────────────────────────────────────────────────────


def test_all_four_gates_active_in_single_flow():
    """Framework completion marker — G1+G2+G3+G4 + UC4 in one Integrator session."""
    assert main() == 0
