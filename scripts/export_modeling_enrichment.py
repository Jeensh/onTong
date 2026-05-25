"""Export all modeling enrichment for `slab-design-real-v2` to a single JSON.

Used as safety-net before re-importing the repo with a boosted parser.
After re-import, `reapply_modeling_enrichment.py` restores all the manual
domain content (descriptions, effects, rationale, confirmations) without
relying on auto-generated PKs (uses natural keys: fqn / composite tuples).

Output: data/enrichment_snapshot_<repo_id>_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def export_repo(db_path: str, repo_id: str) -> dict:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row

    snapshot = {
        "meta": {
            "repo_id": repo_id,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "db_path": db_path,
        },
        "business_terms": [],
        "business_rules": [],
        "actions": [],
        "realizations": [],
        "type_realizations": [],
        "anchor_bindings": [],
        "call_sites_user_confirmed": [],
    }

    # business_terms — key: fqn
    for row in c.execute("SELECT * FROM business_terms WHERE repo_id=?", (repo_id,)):
        snapshot["business_terms"].append(dict(row))

    # business_rules — key: fqn
    for row in c.execute("SELECT * FROM business_rules WHERE repo_id=?", (repo_id,)):
        snapshot["business_rules"].append(dict(row))

    # actions — key: fqn
    for row in c.execute("SELECT * FROM actions WHERE repo_id=?", (repo_id,)):
        snapshot["actions"].append(dict(row))

    # realizations — natural key: (action_fqn, code_method_fqn, applies_to_code_type_fqn)
    for row in c.execute("SELECT * FROM realizations WHERE repo_id=?", (repo_id,)):
        d = dict(row)
        d.pop("id", None)  # autoinc, drop
        snapshot["realizations"].append(d)

    # type_realizations — natural key: (code_type_fqn, term_fqn, scope)
    for row in c.execute("SELECT * FROM type_realizations WHERE repo_id=?", (repo_id,)):
        d = dict(row)
        d.pop("id", None)
        snapshot["type_realizations"].append(d)

    # anchor_bindings — natural key: (target_action_fqn, code_method_fqn, anchor_locator, target_slot)
    for row in c.execute("SELECT * FROM anchor_bindings WHERE repo_id=?", (repo_id,)):
        d = dict(row)
        snapshot["anchor_bindings"].append(d)

    # call_sites — only export user-confirmed ones with natural key
    # natural key: (caller_method_fqn, callee_simple_name, line)
    for row in c.execute("""
        SELECT * FROM call_sites
        WHERE repo_id=?
          AND (user_confirmed_type IS NOT NULL OR analysis_source != 'static_unresolved')
    """, (repo_id,)):
        d = dict(row)
        d.pop("id", None)
        snapshot["call_sites_user_confirmed"].append(d)

    c.close()
    return snapshot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/ontology.db")
    ap.add_argument("--repo-id", required=True)
    ap.add_argument("--out", default=None, help="output path (default: data/enrichment_snapshot_<repo_id>_<ts>.json)")
    args = ap.parse_args()

    snap = export_repo(args.db, args.repo_id)

    out = args.out or f"data/enrichment_snapshot_{args.repo_id.replace('-','_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)

    print(f"Exported to: {out}")
    print(f"Counts:")
    for k, v in snap.items():
        if k == "meta":
            continue
        print(f"  {k}: {len(v)}")


if __name__ == "__main__":
    main()
