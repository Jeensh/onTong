"""R4-T1.1 — synthetic 5K repo generator (안건 6 D, 안건 1 ELK spike 입력).

한 source repo (slab-design-real, 123 CodeType) 를 N 배 cloning 해서 ~5K CodeType 의
synthetic repo 생성. 패키지 hierarchy + relational graph 분포는 source 그대로 보존.

Usage:
    python scripts/synthesize_5k_repo.py \\
        --source slab-design-real \\
        --target synthetic-5k \\
        --target-count 5000

Then: GET /api/ontology/repos/synthetic-5k/graph 로 layout/응답 시간 측정.
또는 graph_api 의 mode=cluster 로 적정 collapse 테스트.

source 의 CodeType / BusinessTerm / TypeRealization / Action / Realization 모두 cloning.
새 fqn prefix 는 `syn{i}.{original_fqn}` (1-indexed). 충돌 방지.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

# import path 보정
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.modeling.code_layer import orm as _co  # noqa: F401
from backend.modeling.code_layer.schema import CodeMethod, CodeMethodAnchor, CodeMethodParam, CodeType
from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer import orm as _do  # noqa: F401
from backend.modeling.domain_layer.schema import BusinessTerm
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer import orm as _mo  # noqa: F401
from backend.modeling.mapping_layer.schema import (
    Action,
    Realization,
    TypeRealization,
)
from backend.modeling.mapping_layer.store import MappingLayerStore
from backend.modeling.persistence.database import bootstrap_database


def _prefix(fqn: str, idx: int) -> str:
    return f"syn{idx}.{fqn}"


def _clone_method(m: CodeMethod, idx: int) -> CodeMethod:
    new_parent = _prefix(m.parent_type_fqn, idx)
    new_fqn = _prefix(m.fqn, idx)
    new_anchors = [
        CodeMethodAnchor(
            method_fqn=new_fqn, kind=a.kind, locator=a.locator,
            line=a.line, snippet=a.snippet, extra=a.extra,
        )
        for a in m.anchors
    ]
    return m.model_copy(update={
        "fqn": new_fqn, "parent_type_fqn": new_parent, "anchors": new_anchors,
    })


def _clone_code_type(ct: CodeType, idx: int, target_repo: str) -> CodeType:
    new_fqn = _prefix(ct.fqn, idx)
    return ct.model_copy(update={
        "fqn": new_fqn,
        "package": _prefix(ct.package or "", idx) if ct.package else "",
        "extends": _prefix(ct.extends, idx) if ct.extends else None,
        "implements": [_prefix(x, idx) for x in ct.implements],
        "extends_interfaces": [_prefix(x, idx) for x in ct.extends_interfaces],
        "methods": [_clone_method(m, idx) for m in ct.methods],
        "repo_id": target_repo,
    })


def _clone_term(t: BusinessTerm, idx: int, target_repo: str) -> BusinessTerm:
    return t.model_copy(update={
        "fqn": _prefix(t.fqn, idx),
        "repo_id": target_repo,
    })


def _clone_action(a: Action, idx: int, target_repo: str) -> Action:
    new_realizations = [
        Realization(
            code_method_fqn=_prefix(r.code_method_fqn, idx),
            applies_to_code_type_fqn=(_prefix(r.applies_to_code_type_fqn, idx)
                                       if r.applies_to_code_type_fqn else None),
            is_override=r.is_override,
            dispatch_source=r.dispatch_source,
            confidence=r.confidence,
            scope=r.scope,
            confirmed=r.confirmed,
            rationale=r.rationale,
        )
        for r in a.realizations
    ]
    return a.model_copy(update={
        "fqn": _prefix(a.fqn, idx),
        "declared_on_term": (_prefix(a.declared_on_term, idx)
                              if a.declared_on_term else None),
        "realizations": new_realizations,
        "repo_id": target_repo,
    })


def _clone_type_realization(tr: TypeRealization, idx: int, target_repo: str) -> TypeRealization:
    return tr.model_copy(update={
        "code_type_fqn": _prefix(tr.code_type_fqn, idx),
        "term_fqn": _prefix(tr.term_fqn, idx),
        "repo_id": target_repo,
    })


def synthesize(source_repo: str, target_repo: str, target_count: int) -> dict:
    code_store = CodeLayerStore()
    domain_store = DomainLayerStore()
    mapping_store = MappingLayerStore()

    src_types = code_store.list_types(repo_id=source_repo)
    if not src_types:
        raise SystemExit(f"source repo '{source_repo}' has no CodeTypes — import first")
    src_terms = domain_store.list_terms(repo_id=source_repo)
    src_actions = mapping_store.list_actions(repo_id=source_repo)
    src_trs = mapping_store.list_type_realizations(repo_id=source_repo)

    src_count = len(src_types)
    n_copies = max(1, math.ceil(target_count / src_count))

    print(f"  source: {src_count} CodeTypes / {len(src_terms)} Terms / "
          f"{len(src_actions)} Actions / {len(src_trs)} TypeRealizations")
    print(f"  target_count={target_count} → {n_copies} copies = {n_copies * src_count} CodeTypes")
    print(f"  target_repo='{target_repo}'")

    # 1. clean target repo
    print("\n[1/4] target repo 비우기...")
    code_store.delete_repo(target_repo)
    domain_store.delete_repo(target_repo)
    mapping_store.delete_repo(target_repo)

    # 2. CodeTypes
    print(f"[2/4] CodeType cloning ({n_copies} × {src_count})...")
    t0 = time.time()
    all_types: list[CodeType] = []
    for idx in range(1, n_copies + 1):
        all_types.extend(_clone_code_type(ct, idx, target_repo) for ct in src_types)
    code_store.upsert_types(target_repo, all_types)
    print(f"   {len(all_types)} CodeTypes in {(time.time() - t0):.1f}s")

    # 3. Terms
    print(f"[3/4] BusinessTerm cloning ({n_copies} × {len(src_terms)})...")
    t0 = time.time()
    all_terms: list[BusinessTerm] = []
    for idx in range(1, n_copies + 1):
        all_terms.extend(_clone_term(t, idx, target_repo) for t in src_terms)
    if all_terms:
        domain_store.upsert_terms(target_repo, all_terms)
    print(f"   {len(all_terms)} Terms in {(time.time() - t0):.1f}s")

    # 4. TypeRealizations + Actions
    print(f"[4/4] TypeRealization + Action cloning...")
    t0 = time.time()
    all_trs: list[TypeRealization] = []
    for idx in range(1, n_copies + 1):
        all_trs.extend(_clone_type_realization(tr, idx, target_repo) for tr in src_trs)
    if all_trs:
        mapping_store.upsert_type_realizations(target_repo, all_trs)

    all_actions: list[Action] = []
    for idx in range(1, n_copies + 1):
        all_actions.extend(_clone_action(a, idx, target_repo) for a in src_actions)
    if all_actions:
        mapping_store.upsert_actions(target_repo, all_actions)
    print(f"   {len(all_trs)} TypeRealizations + {len(all_actions)} Actions in {(time.time() - t0):.1f}s")

    return {
        "code_types": len(all_types),
        "terms": len(all_terms),
        "actions": len(all_actions),
        "type_realizations": len(all_trs),
        "copies": n_copies,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="slab-design-real",
                        help="복제 source repo_id (default: slab-design-real)")
    parser.add_argument("--target", default="synthetic-5k",
                        help="대상 repo_id (default: synthetic-5k)")
    parser.add_argument("--target-count", type=int, default=5000,
                        help="대상 CodeType 수 (default: 5000)")
    args = parser.parse_args()

    bootstrap_database()

    print(f"=== Synthesize: {args.source} → {args.target} (target {args.target_count}) ===")
    t0 = time.time()
    result = synthesize(args.source, args.target, args.target_count)
    elapsed = time.time() - t0

    print(f"\n=== 완료 ({elapsed:.1f}s) ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
    print(f"\n다음: curl http://localhost:8788/api/ontology/repos/{args.target}/graph")


if __name__ == "__main__":
    main()
