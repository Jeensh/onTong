"""FastAPI router — /api/ontology/repos/{repo_id}/graph — 시각화용 그래프 데이터.

P3-5 — xyflow + dagre 가 한 번의 호출로 노드 + 엣지 다 받아서 layout. 5000+ class 대응을
위해 BFS k-hop subgraph 옵션 (focus_fqn + hops) 지원. focus 없으면 전체 (slab-design ~100노드
규모는 OK, 큰 repo 는 하드캡 적용).
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.modeling.code_layer.store import CodeLayerStore
from backend.modeling.domain_layer.store import DomainLayerStore
from backend.modeling.mapping_layer.store import MappingLayerStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology/repos", tags=["ontology-graph"])


GraphNodeKind = Literal["term", "code_type", "action", "domain"]
GraphEdgeKind = Literal[
    "extends", "implements",        # Inheritance
    "composition",                   # HAS_A
    "type_realization_primary",
    "type_realization_partial",      # CodeType ↔ Term
    "realization",                   # Action ↔ CodeMethod (parent CodeType 로 줄임)
    "contains",                      # Domain (Java 패키지) ↔ CodeType (R4-T3.1)
]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: GraphNodeKind
    role: str | None = None              # CodeType.role / Action.kind / Term kind
    domain: str | None = None
    confirmed: bool = False
    extra: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: GraphEdgeKind
    label: str | None = None


class GraphResponse(BaseModel):
    repo_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = False
    summary: dict[str, int] = Field(default_factory=dict)
    focus_fqn: str | None = None
    hops: int | None = None


_HARD_NODE_CAP = 600   # xyflow + dagre 가 부드럽게 처리하는 상한 추정치


@router.get("/{repo_id}/graph", response_model=GraphResponse)
def get_graph(
    repo_id: str,
    mode: str = Query(
        "neighborhood",
        pattern="^(neighborhood|path|cluster)$",
        description="neighborhood (focus 주변 importance-weighted) / path (A→B 최단경로) / cluster (패키지 supernode)",
    ),
    focus_fqn: str | None = Query(None, description="neighborhood mode 의 중심"),
    target_fqn: str | None = Query(None, description="path mode 의 도착 노드"),
    n_max: int = Query(60, ge=10, le=600, description="결과 노드 수 상한 (hops 대체)"),
    hops: int | None = Query(None, ge=1, le=6, description="(deprecated) BFS 반경 — n_max 권장"),
    include_kinds: str = Query(
        "term,code_type,action,domain",
        description="comma-separated subset of {term, code_type, action, domain}",
    ),
    connected_only: bool = Query(
        True,
        description="True 면 엣지가 1개도 없는 isolated 노드 제외 (가독성). focus 모드에서만 의미.",
    ),
) -> GraphResponse:
    kinds = {k.strip() for k in include_kinds.split(",") if k.strip()}
    if not kinds.issubset({"term", "code_type", "action", "domain"}):
        raise HTTPException(status_code=400, detail=f"invalid include_kinds: {include_kinds}")

    code_store = CodeLayerStore()
    domain_store = DomainLayerStore()
    mapping_store = MappingLayerStore()

    # 1. 모든 노드 수집 — 후에 BFS 로 줄일 수 있음
    nodes: dict[str, GraphNode] = {}
    if "code_type" in kinds:
        # R4-T1.1 perf — list_types_summary (methods/anchors 안 로드, ~10x faster)
        for s in code_store.list_types_summary(repo_id=repo_id):
            nodes[s["fqn"]] = GraphNode(
                id=s["fqn"], label=s["simple_name"],
                kind="code_type", role=s["role"], domain=s["package"] or None,
                extra={"kind_code": s["kind"], "is_abstract": s["is_abstract"]},
            )
    if "term" in kinds:
        for t in domain_store.list_terms(repo_id=repo_id):
            nodes[t.fqn] = GraphNode(
                id=t.fqn, label=t.label,
                kind="term", role=t.kind.value, domain=t.domain or None,
                confirmed=t.confirmed,
                extra={"is_root_entity": t.is_root_entity, "struct_like_hint": t.struct_like_hint},
            )
    if "action" in kinds:
        for a in mapping_store.list_actions(repo_id=repo_id):
            nodes[a.fqn] = GraphNode(
                id=a.fqn, label=a.label,
                kind="action", role=a.kind.value, domain=a.domain or None,
                confirmed=a.confirmed_by is not None,
                extra={
                    "verification": a.verification_level.value,
                    "declared_on_term": a.declared_on_term,
                },
            )

    # R4-T3.1: Domain (Java 패키지) 노드 — 직접 클래스 가진 패키지만 emit.
    # 패키지 hierarchy 의 모든 segment 가 아니라 leaf-direct 만 (5K 시 visual 부담 ↓).
    # id format: "pkg::{fqn}" — code_type id 와 충돌 방지.
    if "domain" in kinds and "code_type" in kinds:
        package_classes: dict[str, list[str]] = {}
        for s in code_store.list_types_summary(repo_id=repo_id):
            pkg = s["package"]
            if not pkg:
                continue
            package_classes.setdefault(pkg, []).append(s["fqn"])
        for pkg, members in package_classes.items():
            pkg_id = f"pkg::{pkg}"
            short = pkg.split(".")[-1]
            nodes[pkg_id] = GraphNode(
                id=pkg_id,
                label=short,
                kind="domain",
                role=None,
                domain=pkg,
                extra={
                    "package_full": pkg,
                    "class_count": len(members),
                    "members": members,
                },
            )

    # 2. 엣지 수집 — 양 끝이 nodes 안에 있을 때만 포함
    edges: list[GraphEdge] = []
    e_idx = 0

    def _add(src: str, dst: str, kind: GraphEdgeKind, label: str | None = None) -> None:
        nonlocal e_idx
        if src not in nodes or dst not in nodes:
            return
        edges.append(GraphEdge(
            id=f"e{e_idx}",
            source=src, target=dst, kind=kind, label=label,
        ))
        e_idx += 1

    # 2a. Inheritance / Composition (domain layer)
    if "term" in kinds:
        for inh in domain_store.list_inheritance(repo_id=repo_id):
            _add(inh.child_fqn, inh.parent_fqn, inh.kind.value)  # type: ignore[arg-type]
        for c in domain_store.list_composition(repo_id=repo_id):
            _add(c.parent_fqn, c.child_fqn, "composition", label=c.role_name)

    # 2b. TypeRealization — code_type ↔ term
    if "term" in kinds and "code_type" in kinds:
        for tr in mapping_store.list_type_realizations(repo_id=repo_id):
            kind: GraphEdgeKind = (
                "type_realization_partial" if tr.scope.value == "partial"
                else "type_realization_primary"
            )
            _add(tr.code_type_fqn, tr.term_fqn, kind)

    # 2c. Action realizations — action → code_type (parent of method)
    if "action" in kinds and "code_type" in kinds:
        for a in mapping_store.list_actions(repo_id=repo_id):
            for r in a.realizations:
                # method fqn → parent type fqn (signature 제거 + 마지막 segment 떨어트림)
                base = r.code_method_fqn.split("(", 1)[0].split("@line", 1)[0]
                if "." in base:
                    parent = base.rsplit(".", 1)[0]
                    _add(a.fqn, parent, "realization")

    # 2d. R4-T3.1: Domain → CodeType CONTAINS edges
    if "domain" in kinds and "code_type" in kinds:
        for n in list(nodes.values()):
            if n.kind != "domain":
                continue
            members = n.extra.get("members", []) if isinstance(n.extra, dict) else []
            for ct_fqn in members:
                _add(n.id, ct_fqn, "contains")

    # 3a. connected_only — focus/path 모드 아닐 때만 적용
    if focus_fqn is None and target_fqn is None and connected_only:
        connected: set[str] = set()
        for e in edges:
            connected.add(e.source)
            connected.add(e.target)
        nodes = {k: v for k, v in nodes.items() if k in connected}

    # 3b. mode 별 subgraph
    if mode == "path":
        if not focus_fqn or not target_fqn:
            raise HTTPException(status_code=400, detail="path mode requires focus_fqn + target_fqn")
        if focus_fqn not in nodes or target_fqn not in nodes:
            raise HTTPException(status_code=404, detail="focus or target not found")
        nodes, edges = _shortest_path(nodes, edges, focus_fqn, target_fqn)
    elif mode == "cluster":
        nodes, edges = _cluster_by_package(nodes, edges)
    else:
        # neighborhood
        if focus_fqn is not None:
            if focus_fqn not in nodes:
                raise HTTPException(status_code=404, detail=f"focus_fqn not found: {focus_fqn}")
            nodes, edges = _importance_neighborhood(
                nodes, edges, focus_fqn, n_max=n_max, hops_cap=(hops or 4),
            )
        else:
            # focus 없으면 importance-weighted top-N
            nodes, edges = _topn_by_importance(nodes, edges, n_max=n_max)

    # 4. final hard cap (안전망)
    truncated = False
    if len(nodes) > _HARD_NODE_CAP:
        truncated = True
        # 1) action / term root 우선, 2) 나머지 잘라냄
        keep: list[str] = []
        seen: set[str] = set()
        # priority: action workflow → term root → action effectful → term composite → 나머지
        priority_order = sorted(
            nodes.values(),
            key=lambda n: (
                0 if n.kind == "action" and n.role == "workflow" else
                1 if n.kind == "term" and n.extra.get("is_root_entity") else
                2 if n.kind == "action" and n.role == "effectful" else
                3 if n.kind == "term" else
                4,
            ),
        )
        for n in priority_order:
            if len(keep) >= _HARD_NODE_CAP:
                break
            keep.append(n.id)
            seen.add(n.id)
        nodes = {k: v for k, v in nodes.items() if k in seen}
        edges = [e for e in edges if e.source in seen and e.target in seen]

    summary = {
        "nodes_total": len(nodes),
        "edges_total": len(edges),
    }
    for k in ("term", "code_type", "action", "domain"):
        summary[f"nodes_{k}"] = sum(1 for n in nodes.values() if n.kind == k)

    return GraphResponse(
        repo_id=repo_id,
        nodes=list(nodes.values()),
        edges=edges,
        truncated=truncated,
        summary=summary,
        focus_fqn=focus_fqn,
        hops=hops if focus_fqn else None,
    )


# ---------------------------------------------------------------------------
# 헬퍼 (V7 — 3 mode)
# ---------------------------------------------------------------------------
def _build_adj(edges: list[GraphEdge]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    for e in edges:
        adj.setdefault(e.source, set()).add(e.target)
        adj.setdefault(e.target, set()).add(e.source)
    return adj


def _importance_score(node: GraphNode, degree: int) -> float:
    """노드 중요도 — degree + role/kind 가중. neighborhood 우선순위 정렬용."""
    base = float(degree)
    if node.kind == "term":
        if node.extra.get("is_root_entity"):
            base += 5
        base += 3
    elif node.kind == "action":
        if node.role == "workflow":
            base += 4
        elif node.role == "effectful":
            base += 2
        base += 1
    if node.confirmed:
        base += 2
    return base


def _importance_neighborhood(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    focus: str,
    *,
    n_max: int,
    hops_cap: int,
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """focus 에서 BFS 하면서 importance 높은 순으로 frontier expand. n_max 도달 시 중단.

    그냥 BFS 보다 더 의미있는 노드 (root term, workflow action, confirmed) 를 먼저 끌어옴.
    hops_cap 은 안전 상한 (≤4 권장).
    """
    adj = _build_adj(edges)
    deg = {k: len(adj.get(k, ())) for k in nodes}

    selected: set[str] = {focus}
    frontier_pool: dict[str, int] = {}  # candidate → hops_distance
    for nb in adj.get(focus, ()):
        frontier_pool[nb] = 1

    while frontier_pool and len(selected) < n_max:
        # importance score 기준 가장 높은 candidate 채택
        best = max(
            frontier_pool.items(),
            key=lambda kv: _importance_score(nodes[kv[0]], deg.get(kv[0], 0)) - 0.05 * kv[1],
        )
        cand, dist = best
        del frontier_pool[cand]
        selected.add(cand)
        if dist < hops_cap:
            for nb in adj.get(cand, ()):
                if nb not in selected and nb not in frontier_pool:
                    frontier_pool[nb] = dist + 1

    new_nodes = {k: v for k, v in nodes.items() if k in selected}
    new_edges = [e for e in edges if e.source in selected and e.target in selected]
    return new_nodes, new_edges


def _topn_by_importance(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    *,
    n_max: int,
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """focus 없을 때 — importance 상위 n_max 노드만 + 그들 사이 엣지."""
    adj = _build_adj(edges)
    deg = {k: len(adj.get(k, ())) for k in nodes}
    ranked = sorted(
        nodes.items(),
        key=lambda kv: -_importance_score(kv[1], deg.get(kv[0], 0)),
    )
    keep = {k for k, _ in ranked[:n_max]}
    new_nodes = {k: v for k, v in nodes.items() if k in keep}
    new_edges = [e for e in edges if e.source in keep and e.target in keep]
    return new_nodes, new_edges


def _shortest_path(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
    src: str,
    dst: str,
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """무방향 BFS shortest path. 경로 노드/엣지만 반환."""
    adj = _build_adj(edges)
    if src == dst:
        return {src: nodes[src]}, []

    parent: dict[str, str] = {src: ""}
    frontier = [src]
    found = False
    while frontier and not found:
        nxt: list[str] = []
        for n in frontier:
            for m in adj.get(n, ()):
                if m in parent:
                    continue
                parent[m] = n
                if m == dst:
                    found = True
                    break
                nxt.append(m)
            if found:
                break
        frontier = nxt
    if not found:
        return {src: nodes[src], dst: nodes[dst]}, []

    # path 복원
    path: list[str] = []
    cur = dst
    while cur:
        path.append(cur)
        cur = parent.get(cur, "")
    path.reverse()
    seen = set(path)

    new_nodes = {k: nodes[k] for k in path}
    edge_pairs = {(path[i], path[i + 1]) for i in range(len(path) - 1)}
    new_edges = [
        e for e in edges
        if e.source in seen and e.target in seen
        and ((e.source, e.target) in edge_pairs or (e.target, e.source) in edge_pairs)
    ]
    return new_nodes, new_edges


def _cluster_by_package(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
) -> tuple[dict[str, GraphNode], list[GraphEdge]]:
    """code_type 노드는 패키지 별로 supernode 하나로 collapse.
    term/action 노드는 그대로 유지 (이미 도메인 추상). 엣지는 supernode 로 redirect.
    """
    cluster_id: dict[str, str] = {}   # original node id → new (super)node id
    new_nodes: dict[str, GraphNode] = {}

    for nid, n in nodes.items():
        if n.kind == "code_type":
            pkg = n.domain or "(default)"
            super_id = f"pkg:{pkg}"
            cluster_id[nid] = super_id
            if super_id not in new_nodes:
                new_nodes[super_id] = GraphNode(
                    id=super_id,
                    label=pkg.split(".")[-1] or "(root)",
                    kind="code_type",
                    role="cluster",
                    domain=pkg,
                    extra={"cluster_size": 1, "cluster_path": pkg},
                )
            else:
                cur = new_nodes[super_id].extra.get("cluster_size", 1)
                new_nodes[super_id].extra["cluster_size"] = cur + 1
        else:
            cluster_id[nid] = nid
            new_nodes[nid] = n

    edge_seen: dict[tuple[str, str, str], int] = {}
    new_edges: list[GraphEdge] = []
    for e in edges:
        src = cluster_id.get(e.source, e.source)
        dst = cluster_id.get(e.target, e.target)
        if src == dst:
            continue
        key = (src, dst, e.kind)
        if key in edge_seen:
            edge_seen[key] += 1
            continue
        edge_seen[key] = 1
        new_edges.append(GraphEdge(
            id=f"cl{len(new_edges)}",
            source=src, target=dst, kind=e.kind, label=e.label,
        ))

    # cluster supernode label 에 사이즈 표시
    for n in new_nodes.values():
        if n.id.startswith("pkg:"):
            sz = n.extra.get("cluster_size", 1)
            n.label = f"{n.label} ({sz})"

    return new_nodes, new_edges
