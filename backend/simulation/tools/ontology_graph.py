"""NetworkX-based mock ontology graph for Slab design simulation.

Replaces Section 2 (Modeling) until real integration is available.
Swap build_mock_graph() with build_graph_from_section2() when Section 2 is ready.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


def _load_ontology() -> dict:
    with open(_DATA_DIR / "mock_ontology.json", encoding="utf-8") as f:
        return json.load(f)


def build_mock_graph() -> nx.DiGraph:
    """Load mock_ontology.json and build a NetworkX directed graph."""
    data = _load_ontology()
    G = nx.DiGraph()
    for node in data["nodes"]:
        G.add_node(node["id"], **node)
    for edge in data["edges"]:
        G.add_edge(edge["from"], edge["to"], relation=edge["relation"])
    logger.debug(f"Built mock ontology graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def get_graph_data() -> dict:
    """Return graph as JSON-serializable dict for frontend rendering."""
    data = _load_ontology()
    return {
        "nodes": data["nodes"],
        "edges": [
            {"from": e["from"], "to": e["to"], "relation": e["relation"]}
            for e in data["edges"]
        ],
    }


def find_edging_specs_for_order(G: nx.DiGraph, order_id: str) -> list[dict]:
    """Traverse: Order → ROLLED_BY → HotRollingMill → HAS_EDGING_SPEC → EdgeSpec."""
    rolling_mills = [
        v for _, v, d in G.edges(order_id, data=True)
        if d.get("relation") == "ROLLED_BY"
    ]
    traversal = [order_id] + rolling_mills

    edging_specs = []
    for mill in rolling_mills:
        specs = [
            v for _, v, d in G.edges(mill, data=True)
            if d.get("relation") == "HAS_EDGING_SPEC"
        ]
        traversal.extend(specs)
        edging_specs.extend([{**G.nodes[s], "id": s} for s in specs])

    highlighted_edges = (
        [(order_id, m) for m in rolling_mills]
        + [(m, s) for m in rolling_mills
           for _, s, d in G.edges(m, data=True) if d.get("relation") == "HAS_EDGING_SPEC"]
    )
    return edging_specs, traversal, highlighted_edges


def find_orders_by_rolling_line(G: nx.DiGraph, rolling_id: str) -> tuple[list[dict], list[str], list[tuple]]:
    """Find all orders assigned to a rolling line (reverse traversal)."""
    order_ids = [
        u for u, v, d in G.edges(data=True)
        if v == rolling_id and d.get("relation") == "ROLLED_BY"
    ]
    traversal = [rolling_id] + order_ids
    highlighted_edges = [(o, rolling_id) for o in order_ids]
    return [G.nodes[o] for o in order_ids], traversal, highlighted_edges


def find_slab_for_order(G: nx.DiGraph, order_id: str) -> dict | None:
    """Find the Slab node produced by an order."""
    slabs = [
        v for _, v, d in G.edges(order_id, data=True)
        if d.get("relation") == "PRODUCES"
    ]
    if slabs:
        return {**G.nodes[slabs[0]], "id": slabs[0]}
    return None
