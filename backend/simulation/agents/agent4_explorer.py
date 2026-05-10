"""Agent 4 — 온톨로지 익스플로러.

노드 검색, 1-2 hop 이웃 expand, 두 노드 간 path finding을 제공한다.
모든 응답은 OntologySubgraphView가 그릴 수 있는 nodes/edges 형태.

Slab 설계 시뮬레이션은 Agent 1의 'order' target_type으로 흡수됨.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from backend.modeling.ontology.client import get_client

logger = logging.getLogger(__name__)


# 그래프 라벨 매핑 — Neo4j label → frontend group
LABEL_TO_GROUP = {
    "Term": "term",
    "TermCategory": "term",
    "Step": "step",
    "Standard": "standard",
    "Variable": "variable",
    "ErrorCode": "errorcode",
    "Class": "class",
    "Method": "method",
    "Table": "table",
}


# ─────────────────────────────────────────────────────────────


class NodeSearchHit(BaseModel):
    id: str
    label: str
    group: str
    snippet: str | None = None


class NodeSearchResult(BaseModel):
    nodes: list[NodeSearchHit]


def search_nodes(query: str, groups: list[str] | None = None) -> NodeSearchResult:
    """라벨/이름/그룹 기반 자유 검색."""
    client = get_client()
    q = query.strip()
    if not q:
        return NodeSearchResult(nodes=[])

    cypher = (
        "MATCH (n) "
        "WHERE n.korean_name CONTAINS $q "
        "   OR n.english_name CONTAINS $q "
        "   OR n.name CONTAINS $q "
        "   OR n.code CONTAINS $q "
        "   OR n.id CONTAINS $q "
        "RETURN labels(n) AS labels, "
        "       coalesce(n.korean_name, n.name, n.code, n.id) AS label, "
        "       coalesce(n.id, n.code, n.name) AS id, "
        "       coalesce(n.description, n.korean_name, '') AS snippet "
        "LIMIT 30"
    )
    rows = client.query(cypher, q=q)
    hits: list[NodeSearchHit] = []
    for r in rows:
        labels = r.get("labels", [])
        # 가장 도메인 의미있는 라벨 선택
        primary = next((lab for lab in labels if lab in LABEL_TO_GROUP), labels[0] if labels else "Node")
        group = LABEL_TO_GROUP.get(primary, "default")
        prefix = primary.lower()
        node_id = f"{prefix}:{r['id']}"
        hits.append(
            NodeSearchHit(
                id=node_id,
                label=r["label"],
                group=group,
                snippet=r.get("snippet"),
            )
        )
    return NodeSearchResult(nodes=hits)


# ─────────────────────────────────────────────────────────────


class ExpandRequest(BaseModel):
    node_id: str  # "step:2" / "term:term_edging" / "method:Foo.bar" 등
    hops: Literal[1, 2] = 1


class ExpandResult(BaseModel):
    node_id: str
    trace: dict = Field(default_factory=dict)


def _parse_node_id(node_id: str) -> tuple[str, str]:
    """'step:2' → ('Step', '2'). 알 수 없으면 ('', node_id)."""
    if ":" not in node_id:
        return "", node_id
    prefix, rest = node_id.split(":", 1)
    label_map = {
        "step": "Step",
        "term": "Term",
        "termcategory": "TermCategory",
        "standard": "Standard",
        "variable": "Variable",
        "errorcode": "ErrorCode",
        "class": "Class",
        "method": "Method",
        "table": "Table",
    }
    return label_map.get(prefix, ""), rest


def _node_dict(label: str, props: dict) -> dict:
    group = LABEL_TO_GROUP.get(label, "default")
    if label == "Step":
        nid = f"step:{props.get('step_number')}"
        text = f"Step {props.get('step_number')}\n{props.get('korean_name', '')}"
    elif label == "Standard":
        nid = f"standard:{props.get('code')}"
        text = f"{props.get('code')}\n{props.get('korean_name', '')}"
    elif label == "Method":
        nid = f"method:{props.get('id')}"
        # props에 class 정보 없을 수 있음 → name만
        text = f".{props.get('name')}()"
    elif label == "Class":
        nid = f"class:{props.get('id', props.get('name'))}"
        text = props.get("name", "")
    elif label == "Term":
        nid = f"term:{props.get('id')}"
        text = props.get("korean_name", "")
    elif label == "Table":
        nid = f"table:{props.get('id', props.get('name'))}"
        text = props.get("name", "")
    elif label == "Variable":
        nid = f"variable:{props.get('id')}"
        text = props.get("korean_name", props.get("name", ""))
    elif label == "ErrorCode":
        nid = f"errorcode:{props.get('code')}"
        text = f"{props.get('code')} {props.get('korean_message', '')}"
    else:
        nid = f"{label.lower()}:{props.get('id', props.get('name'))}"
        text = props.get("name", str(props.get("id", "?")))
    return {"id": nid, "label": text, "group": group}


def expand(req: ExpandRequest) -> ExpandResult:
    """seed 노드 주변 1~2 hop 이웃 추출."""
    client = get_client()
    label, raw_id = _parse_node_id(req.node_id)
    if not label:
        return ExpandResult(node_id=req.node_id, trace={"nodes": [], "edges": [], "cypher": ""})

    # WHERE 조건: Step은 step_number, 나머지는 id/code/name
    where_clauses = {
        "Step": "n.step_number = $val",
        "Standard": "n.code = $val OR n.id = $val",
        "Term": "n.id = $val",
        "Method": "n.id = $val OR n.name = $val",
        "Class": "n.id = $val OR n.name = $val",
        "Table": "n.id = $val OR n.name = $val",
        "Variable": "n.id = $val",
        "ErrorCode": "n.code = $val",
    }
    where = where_clauses.get(label, "n.id = $val")

    # Step의 경우 raw_id를 int로
    val: int | str
    val = int(raw_id) if label == "Step" and raw_id.isdigit() else raw_id

    hops = req.hops
    cypher = (
        f"MATCH (n:{label}) WHERE {where} "
        f"OPTIONAL MATCH (n)-[r1]-(m1) "
        + ("OPTIONAL MATCH (m1)-[r2]-(m2) " if hops == 2 else "")
        + "RETURN n, "
        "       collect(DISTINCT {rel: type(r1), node: m1, labels: labels(m1)}) AS first, "
        + ("collect(DISTINCT {rel: type(r2), src: m1, node: m2, labels: labels(m2)}) AS second " if hops == 2 else "[] AS second ")
    )

    rows = client.query(cypher, val=val)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()

    if not rows:
        return ExpandResult(
            node_id=req.node_id,
            trace={"nodes": [], "edges": [], "seed_ids": [req.node_id], "cypher": cypher},
        )

    r = rows[0]
    seed_node = r["n"]
    seed_d = _node_dict(label, dict(seed_node))
    nodes.append(seed_d)
    seen_ids.add(seed_d["id"])
    seed_id = seed_d["id"]

    for hop in r.get("first", []):
        m_props = hop.get("node")
        if not m_props:
            continue
        m_labels = hop.get("labels", [])
        m_label = next((lab for lab in m_labels if lab in LABEL_TO_GROUP), m_labels[0] if m_labels else "Node")
        m_d = _node_dict(m_label, dict(m_props))
        if m_d["id"] not in seen_ids:
            nodes.append(m_d)
            seen_ids.add(m_d["id"])
        edges.append({"from": seed_id, "to": m_d["id"], "label": hop.get("rel", "")})

    if hops == 2:
        for hop in r.get("second", []):
            m_props = hop.get("node")
            src_props = hop.get("src")
            if not m_props or not src_props:
                continue
            m_labels = hop.get("labels", [])
            m_label = next((lab for lab in m_labels if lab in LABEL_TO_GROUP), m_labels[0] if m_labels else "Node")
            m_d = _node_dict(m_label, dict(m_props))
            if m_d["id"] not in seen_ids:
                nodes.append(m_d)
                seen_ids.add(m_d["id"])
            # src의 node id 결정 어려움 → 첫 hop edge에 의해 이미 노드 등록됐다고 가정
            # 단순히 seed와의 거리는 알 수 있고 자기 자신 edge 빼고 추가
            edges.append(
                {"from": _node_dict(_pick_primary_label(src_props), dict(src_props))["id"],
                 "to": m_d["id"],
                 "label": hop.get("rel", "")}
            )

    return ExpandResult(
        node_id=req.node_id,
        trace={
            "nodes": nodes,
            "edges": edges,
            "seed_ids": [seed_id],
            "cypher": cypher,
        },
    )


def _pick_primary_label(props: dict) -> str:
    # props로부터 label 추정 — heuristic
    if "step_number" in props:
        return "Step"
    if "code" in props and "korean_name" in props:
        return "Standard"
    if "korean_name" in props and "category" in props:
        return "Term"
    if "name" in props and "fqn" in props:
        return "Class"
    if "name" in props and "return_type" in props:
        return "Method"
    return "Node"


# ─────────────────────────────────────────────────────────────


class PathRequest(BaseModel):
    from_id: str
    to_id: str
    max_hops: int = 4


class PathResult(BaseModel):
    from_id: str
    to_id: str
    found: bool
    trace: dict = Field(default_factory=dict)


def find_path(req: PathRequest) -> PathResult:
    """두 노드 간 shortest path 추출. 그래프로 path 만 진하게 반환."""
    client = get_client()
    fr_label, fr_raw = _parse_node_id(req.from_id)
    to_label, to_raw = _parse_node_id(req.to_id)
    if not fr_label or not to_label:
        return PathResult(from_id=req.from_id, to_id=req.to_id, found=False)

    fr_val: int | str = int(fr_raw) if fr_label == "Step" and fr_raw.isdigit() else fr_raw
    to_val: int | str = int(to_raw) if to_label == "Step" and to_raw.isdigit() else to_raw

    where_clauses = {
        "Step": "step_number",
        "Standard": "code",
        "Term": "id",
        "Method": "id",
        "Class": "id",
        "Table": "name",
        "Variable": "id",
        "ErrorCode": "code",
    }
    fr_field = where_clauses.get(fr_label, "id")
    to_field = where_clauses.get(to_label, "id")

    cypher = (
        f"MATCH (a:{fr_label} {{{fr_field}: $fr}}), "
        f"      (b:{to_label} {{{to_field}: $to}}), "
        f"      p = shortestPath((a)-[*..{req.max_hops}]-(b)) "
        "RETURN [n IN nodes(p) | {props: properties(n), labels: labels(n)}] AS ns, "
        "       [r IN relationships(p) | {rel: type(r), startId: id(startNode(r)), endId: id(endNode(r))}] AS rs"
    )
    rows = client.query(cypher, fr=fr_val, to=to_val)
    if not rows:
        return PathResult(
            from_id=req.from_id,
            to_id=req.to_id,
            found=False,
            trace={"nodes": [], "edges": [], "cypher": cypher},
        )

    r = rows[0]
    nodes: list[dict] = []
    edges: list[dict] = []
    path_keys: list[str] = []
    seen_ids: set[str] = set()
    node_id_list: list[str] = []

    for n_info in r.get("ns", []):
        labels = n_info.get("labels", [])
        primary = next((lab for lab in labels if lab in LABEL_TO_GROUP), labels[0] if labels else "Node")
        nd = _node_dict(primary, dict(n_info.get("props", {})))
        if nd["id"] not in seen_ids:
            nodes.append(nd)
            seen_ids.add(nd["id"])
        node_id_list.append(nd["id"])

    for i, r_info in enumerate(r.get("rs", [])):
        if i + 1 < len(node_id_list):
            from_id = node_id_list[i]
            to_id = node_id_list[i + 1]
            edges.append({"from": from_id, "to": to_id, "label": r_info.get("rel", "")})
            path_keys.append(f"{from_id}->{to_id}")

    return PathResult(
        from_id=req.from_id,
        to_id=req.to_id,
        found=True,
        trace={
            "nodes": nodes,
            "edges": edges,
            "seed_ids": [req.from_id, req.to_id],
            "path_edge_keys": path_keys,
            "cypher": cypher,
        },
    )
