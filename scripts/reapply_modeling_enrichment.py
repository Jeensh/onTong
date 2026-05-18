"""Re-apply modeling enrichment snapshot after a fresh re-import.

Uses natural keys (FQN, composite tuples) to be ID-independent. Safe to run
on a freshly imported DB: untouched rows stay as imported, matched rows
gain the enriched fields.

Strategy per table:
- business_terms (PK fqn+repo_id): UPSERT description, aliases_json,
  confirmed, source (preserve other fields if any)
- business_rules (PK fqn+repo_id): UPSERT
- actions (PK fqn+repo_id): UPSERT description, effects_json, params_json,
  preconditions_json, postconditions_json, confirmed_by, verification_level,
  signature_locked_at
- realizations (natural key action_fqn+code_method_fqn+applies_to_code_type_fqn):
  upsert by natural key (re-import may regenerate IDs)
- type_realizations (natural key code_type_fqn+term_fqn+scope): upsert
- anchor_bindings (PK id is FQN-like, preserve): upsert all fields
- call_sites_user_confirmed (natural key caller+callee+line): upsert
  user_confirmed_type, analysis_source, confidence, needs_user_confirm
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def upsert_business_terms(c, repo_id, items, *, dry_run=False):
    n = 0
    for it in items:
        fqn = it["fqn"]
        # try update first
        row = c.execute("SELECT 1 FROM business_terms WHERE fqn=? AND repo_id=?", (fqn, repo_id)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE business_terms
                    SET description=?, aliases_json=?, confirmed=?, source=?
                    WHERE fqn=? AND repo_id=?
                """, (it.get("description"), it.get("aliases_json"), it.get("confirmed"), it.get("source"), fqn, repo_id))
            n += 1
    return n


def upsert_business_rules(c, repo_id, items, *, dry_run=False):
    n = 0
    for it in items:
        fqn = it["fqn"]
        row = c.execute("SELECT 1 FROM business_rules WHERE fqn=? AND repo_id=?", (fqn, repo_id)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE business_rules
                    SET statement=?, severity=?, terms_ref_json=?, source=?, confirmed=?,
                        enforced_by_json=?, violated_at_call_json=?, operational_history_json=?
                    WHERE fqn=? AND repo_id=?
                """, (
                    it.get("statement"), it.get("severity"), it.get("terms_ref_json"),
                    it.get("source"), it.get("confirmed"),
                    it.get("enforced_by_json", "[]"), it.get("violated_at_call_json", "[]"),
                    it.get("operational_history_json", "[]"),
                    fqn, repo_id,
                ))
            n += 1
    return n


def upsert_actions(c, repo_id, items, *, dry_run=False):
    n = 0
    for it in items:
        fqn = it["fqn"]
        row = c.execute("SELECT 1 FROM actions WHERE fqn=? AND repo_id=?", (fqn, repo_id)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE actions
                    SET description=?, params_json=?, output_json=?, effects_json=?,
                        preconditions_json=?, postconditions_json=?, sub_actions_json=?,
                        verification_level=?, signature_locked_at=?, confirmed_by=?,
                        declared_on_term=?
                    WHERE fqn=? AND repo_id=?
                """, (
                    it.get("description"), it.get("params_json", "[]"),
                    it.get("output_json"), it.get("effects_json", "[]"),
                    it.get("preconditions_json", "[]"), it.get("postconditions_json", "[]"),
                    it.get("sub_actions_json", "[]"), it.get("verification_level"),
                    it.get("signature_locked_at"), it.get("confirmed_by"),
                    it.get("declared_on_term"),
                    fqn, repo_id,
                ))
            n += 1
    return n


def upsert_realizations(c, repo_id, items, *, dry_run=False):
    """Natural key: (action_fqn, code_method_fqn, applies_to_code_type_fqn)."""
    n = 0
    for it in items:
        af = it["action_fqn"]
        cm = it["code_method_fqn"]
        ac = it.get("applies_to_code_type_fqn")
        # match
        row = c.execute("""
            SELECT id FROM realizations
            WHERE action_fqn=? AND code_method_fqn=? AND repo_id=?
              AND (applies_to_code_type_fqn IS ? OR applies_to_code_type_fqn=?)
        """, (af, cm, repo_id, ac, ac)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE realizations
                    SET is_override=?, dispatch_source=?, confidence=?, scope=?,
                        confirmed=?, rationale=?
                    WHERE id=?
                """, (
                    it.get("is_override", 0), it.get("dispatch_source"),
                    it.get("confidence", 1.0), it.get("scope", "primary"),
                    it.get("confirmed", 1), it.get("rationale"),
                    row["id"] if hasattr(row, "__getitem__") else row[0],
                ))
            n += 1
        else:
            # insert (fresh re-import might not have this row)
            if not dry_run:
                c.execute("""
                    INSERT INTO realizations
                    (action_fqn, code_method_fqn, applies_to_code_type_fqn, is_override,
                     dispatch_source, confidence, scope, confirmed, rationale, repo_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    af, cm, ac, it.get("is_override", 0),
                    it.get("dispatch_source"), it.get("confidence", 1.0),
                    it.get("scope", "primary"), it.get("confirmed", 1),
                    it.get("rationale"), repo_id,
                ))
            n += 1
    return n


def upsert_type_realizations(c, repo_id, items, *, dry_run=False):
    """Natural key: (code_type_fqn, term_fqn, scope)."""
    n = 0
    for it in items:
        ct = it["code_type_fqn"]
        tm = it["term_fqn"]
        sc = it.get("scope", "primary")
        row = c.execute("""
            SELECT id FROM type_realizations
            WHERE code_type_fqn=? AND term_fqn=? AND scope=? AND repo_id=?
        """, (ct, tm, sc, repo_id)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE type_realizations
                    SET confidence=?, source=?, confirmed=?, confirmed_by=?, rationale=?
                    WHERE id=?
                """, (
                    it.get("confidence", 1.0), it.get("source"),
                    it.get("confirmed", 1), it.get("confirmed_by"),
                    it.get("rationale"),
                    row["id"] if hasattr(row, "__getitem__") else row[0],
                ))
            n += 1
        else:
            if not dry_run:
                c.execute("""
                    INSERT INTO type_realizations
                    (code_type_fqn, term_fqn, scope, confidence, source, confirmed,
                     confirmed_by, rationale, repo_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ct, tm, sc, it.get("confidence", 1.0), it.get("source"),
                    it.get("confirmed", 1), it.get("confirmed_by"),
                    it.get("rationale"), repo_id,
                ))
            n += 1
    return n


def upsert_anchor_bindings(c, repo_id, items, *, dry_run=False):
    """PK is anchor_bindings.id (FQN-like string), preserve."""
    n = 0
    for it in items:
        aid = it["id"]
        row = c.execute("SELECT 1 FROM anchor_bindings WHERE id=?", (aid,)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE anchor_bindings
                    SET anchor_locator=?, code_method_fqn=?, target_action_fqn=?,
                        target_slot=?, confidence=?, source=?, confirmed=?, rationale=?,
                        line=?
                    WHERE id=?
                """, (
                    it.get("anchor_locator"), it.get("code_method_fqn"),
                    it.get("target_action_fqn"), it.get("target_slot"),
                    it.get("confidence", 1.0), it.get("source"),
                    it.get("confirmed", 1), it.get("rationale"),
                    it.get("line"),
                    aid,
                ))
            n += 1
        else:
            if not dry_run:
                c.execute("""
                    INSERT INTO anchor_bindings
                    (id, anchor_locator, code_method_fqn, target_action_fqn, target_slot,
                     confidence, source, confirmed, rationale, repo_id, line)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    aid, it.get("anchor_locator"), it.get("code_method_fqn"),
                    it.get("target_action_fqn"), it.get("target_slot"),
                    it.get("confidence", 1.0), it.get("source"),
                    it.get("confirmed", 1), it.get("rationale"), repo_id, it.get("line"),
                ))
            n += 1
    return n


def upsert_call_sites(c, repo_id, items, *, dry_run=False):
    """Natural key: (caller_method_fqn, callee_simple_name, line)."""
    n_match = 0
    n_miss = 0
    for it in items:
        cm = it["caller_method_fqn"]
        cn = it["callee_simple_name"]
        ln = it.get("line")
        row = c.execute("""
            SELECT id FROM call_sites
            WHERE caller_method_fqn=? AND callee_simple_name=? AND repo_id=?
              AND (line IS ? OR line=?)
        """, (cm, cn, repo_id, ln, ln)).fetchone()
        if row:
            if not dry_run:
                c.execute("""
                    UPDATE call_sites
                    SET user_confirmed_type=?, analysis_source=?, confidence=?,
                        needs_user_confirm=?, user_confirmed_at=?, callee_receiver_static_type=?
                    WHERE id=?
                """, (
                    it.get("user_confirmed_type"), it.get("analysis_source"),
                    it.get("confidence", 0.5), it.get("needs_user_confirm", 0),
                    it.get("user_confirmed_at"), it.get("callee_receiver_static_type", ""),
                    row["id"] if hasattr(row, "__getitem__") else row[0],
                ))
            n_match += 1
        else:
            n_miss += 1
    return n_match, n_miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/ontology.db")
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.snapshot) as f:
        snap = json.load(f)

    repo_id = snap["meta"]["repo_id"]
    print(f"Applying snapshot for repo_id={repo_id} (dry_run={args.dry_run})")

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row
    try:
        n_t = upsert_business_terms(c, repo_id, snap["business_terms"], dry_run=args.dry_run)
        n_r = upsert_business_rules(c, repo_id, snap["business_rules"], dry_run=args.dry_run)
        n_a = upsert_actions(c, repo_id, snap["actions"], dry_run=args.dry_run)
        n_re = upsert_realizations(c, repo_id, snap["realizations"], dry_run=args.dry_run)
        n_tr = upsert_type_realizations(c, repo_id, snap["type_realizations"], dry_run=args.dry_run)
        n_ab = upsert_anchor_bindings(c, repo_id, snap["anchor_bindings"], dry_run=args.dry_run)
        n_cs_match, n_cs_miss = upsert_call_sites(c, repo_id, snap["call_sites_user_confirmed"], dry_run=args.dry_run)
        if not args.dry_run:
            c.commit()
    finally:
        c.close()

    print("Re-applied counts:")
    print(f"  business_terms: {n_t}")
    print(f"  business_rules: {n_r}")
    print(f"  actions: {n_a}")
    print(f"  realizations: {n_re}")
    print(f"  type_realizations: {n_tr}")
    print(f"  anchor_bindings: {n_ab}")
    print(f"  call_sites: matched {n_cs_match}, missed {n_cs_miss}")


if __name__ == "__main__":
    main()
