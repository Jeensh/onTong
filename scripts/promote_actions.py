"""draft 상태 actions 의 params_json 을 채우고 SIGNATURE_LOCKED 진급.

For each Action (verification_level='draft', has realizations):
  1. Get primary realization's method_fqn
  2. Get code_method.params (Java side: [{name, type}, ...])
  3. Convert each param's type:
     - String → 'string'
     - int / Integer → 'int'
     - long / Long → 'int'  (BigDecimal-related primitives)
     - BigDecimal / float / double → 'float'
     - boolean / Boolean → 'bool'
     - other (Java class) → 'object_ref' + object_ref_term (TypeRealization lookup)
  4. Save back to action.params_json
  5. Set verification_level='signature_locked'

usage:
  python3 scripts/promote_actions.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology.db"
REPO_ID = "slab-design-real"


PRIMITIVE_MAP = {
    "String": "string",
    "string": "string",
    "char": "string",
    "Character": "string",
    "int": "int",
    "Integer": "int",
    "long": "int",
    "Long": "int",
    "short": "int",
    "Short": "int",
    "byte": "int",
    "Byte": "int",
    "BigInteger": "int",
    "BigDecimal": "float",
    "double": "float",
    "Double": "float",
    "float": "float",
    "Float": "float",
    "Number": "float",
    "boolean": "bool",
    "Boolean": "bool",
}


def normalize_java_type(java_type: str) -> str:
    """Java type 의 generic (List<X>, Optional<X>) 을 unwrap, simple_name 만 반환."""
    t = java_type.strip()
    # Optional<X> / List<X> 등은 inner 로 unwrap
    if "<" in t:
        prefix = t.split("<", 1)[0].strip()
        if prefix in ("Optional", "List", "Set", "Collection", "Iterable"):
            inner = t[len(prefix) + 1:].rsplit(">", 1)[0]
            return normalize_java_type(inner)
    # `array[]` → element
    if t.endswith("[]"):
        return normalize_java_type(t[:-2])
    return t


def java_to_action_param(param: dict, type_realizations: dict[str, str]) -> dict:
    """Java param -> ActionParam dict.

    type_realizations: Java simple_name (or fqn) -> BusinessTerm.fqn.
    """
    name = param.get("name", "p")
    java_type = normalize_java_type(param.get("type", ""))

    if java_type in PRIMITIVE_MAP:
        return {"name": name, "type": PRIMITIVE_MAP[java_type]}

    # object_ref — TypeRealization 으로 BusinessTerm 찾기
    term_fqn = type_realizations.get(java_type)
    if term_fqn is None:
        # fallback — 매칭 안 되면 string 으로 처리 (보수적)
        return {"name": name, "type": "string"}
    return {
        "name": name,
        "type": "object_ref",
        "object_ref_term": term_fqn,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. type_realizations — Java simple_name (마지막 segment) → BusinessTerm.fqn
    type_realizations: dict[str, str] = {}
    for row in cur.execute(
        "SELECT code_type_fqn, term_fqn FROM type_realizations WHERE repo_id=? AND scope='primary'",
        (REPO_ID,),
    ):
        code_fqn, term_fqn = row
        # simple_name: Java fqn 의 마지막 segment
        simple = code_fqn.rsplit(".", 1)[-1] if "." in code_fqn else code_fqn
        type_realizations[simple] = term_fqn
        # 또한 fqn 자체도 키로 등록 (보수적)
        type_realizations[code_fqn] = term_fqn

    # 2. draft action 수집 (realization 있는 것만)
    cur.execute("""
        SELECT a.fqn, a.params_json
        FROM actions a
        WHERE a.repo_id = ? AND a.verification_level = 'draft'
          AND EXISTS (SELECT 1 FROM realizations r WHERE r.action_fqn = a.fqn AND r.repo_id = ?)
    """, (REPO_ID, REPO_ID))
    drafts = list(cur.fetchall())
    print(f"draft actions with realization: {len(drafts)}")

    promoted = 0
    skipped = 0
    for action_fqn, current_params in drafts:
        # 3. primary realization 의 method
        cur.execute("""
            SELECT r.code_method_fqn FROM realizations r
            WHERE r.action_fqn = ? AND r.repo_id = ?
            ORDER BY (r.scope = 'primary') DESC, r.confidence DESC LIMIT 1
        """, (action_fqn, REPO_ID))
        row = cur.fetchone()
        if row is None:
            skipped += 1
            continue
        method_fqn = row[0]

        # 4. method.params
        cur.execute("SELECT params_json FROM code_methods WHERE fqn=?", (method_fqn,))
        m = cur.fetchone()
        if m is None or not m[0]:
            # method 없거나 params 없음 — params_json=[] 유지하되 진급
            new_params = []
        else:
            method_params = json.loads(m[0])
            new_params = [
                java_to_action_param(p, type_realizations)
                for p in method_params
            ]

        new_params_json = json.dumps(new_params, ensure_ascii=False)

        if args.dry_run:
            print(f"  [would promote] {action_fqn}: {len(new_params)} params via {method_fqn}")
            promoted += 1
            continue

        cur.execute("""
            UPDATE actions SET params_json=?, verification_level='signature_locked',
                              confirmed_by='user'
            WHERE fqn=? AND repo_id=?
        """, (new_params_json, action_fqn, REPO_ID))
        promoted += 1
        print(f"  [+] {action_fqn} ({len(new_params)} params)")

    if not args.dry_run:
        conn.commit()

    # 5. 카운트 검증
    cur.execute("SELECT verification_level, count(*) FROM actions WHERE repo_id=? GROUP BY verification_level", (REPO_ID,))
    print("\n=== verification_level distribution ===")
    for level, n in cur.fetchall():
        print(f"  {level}: {n}")
    print(f"\n{'[DRY-RUN] ' if args.dry_run else ''}promoted={promoted}, skipped={skipped}")

    conn.close()


if __name__ == "__main__":
    main()
