"""Seed data API — load SCM demo project with pre-configured mappings."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/modeling/seed", tags=["modeling-seed"])
logger = logging.getLogger(__name__)

_java_parser = None
_graph_writer = None
_onto_store = None
_mapping_svc = None

SAMPLE_REPO_ID = "scm-demo"

# Pre-configured mappings: code entity -> domain node
PRESET_MAPPINGS = [
    ("com.ontong.scm.order.OrderService", "SCOR/Plan/DemandPlanning", "class"),
    ("com.ontong.scm.inventory.InventoryManager", "SCOR/Plan/InventoryPlanning", "class"),
    ("com.ontong.scm.inventory.SafetyStockCalculator", "SCOR/Plan/InventoryPlanning", "class"),
    ("com.ontong.scm.production.ProductionPlanner", "SCOR/Make/Manufacturing", "class"),
    ("com.ontong.scm.production.WorkOrderProcessor", "SCOR/Make/Manufacturing", "class"),
    ("com.ontong.scm.procurement.PurchaseOrderService", "SCOR/Source/Purchasing", "class"),
    ("com.ontong.scm.procurement.SupplierEvaluator", "SCOR/Source/SupplierSelection", "class"),
    ("com.ontong.scm.logistics.ShipmentTracker", "SCOR/Deliver/Transportation", "class"),
    ("com.ontong.scm.logistics.WarehouseController", "SCOR/Deliver/Warehousing", "class"),
]


def init(java_parser, graph_writer, onto_store, mapping_svc):
    global _java_parser, _graph_writer, _onto_store, _mapping_svc
    _java_parser = java_parser
    _graph_writer = graph_writer
    _onto_store = onto_store
    _mapping_svc = mapping_svc


def _find_sample_repo() -> Path:
    """Locate sample-repos/scm-demo relative to project root."""
    # Walk up from this file to find project root
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "sample-repos" / "scm-demo"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("sample-repos/scm-demo not found")


@router.post("/scm-demo")
async def seed_scm_demo():
    """Load the SCM demo: parse sample Java project, load SCOR ontology, create preset mappings."""
    if _java_parser is None:
        raise HTTPException(status_code=503, detail="Modeling not initialized")

    sample_dir = _find_sample_repo()
    java_dir = sample_dir / "src" / "main" / "java"

    # 1. Parse Java files
    java_files = sorted(java_dir.rglob("*.java"))
    if not java_files:
        raise HTTPException(status_code=500, detail="No Java files found in sample project")

    _graph_writer.clear_repo(SAMPLE_REPO_ID)

    total_entities = 0
    total_relations = 0
    for java_file in java_files:
        content = java_file.read_text(encoding="utf-8")
        rel_path = java_file.relative_to(sample_dir)
        result = _java_parser.parse_file(rel_path, content)
        _graph_writer.write_parse_result(result, repo_id=SAMPLE_REPO_ID)
        total_entities += len(result.entities)
        total_relations += len(result.relations)

    # 2. Load SCOR ontology (idempotent)
    ontology_count = _onto_store.load_template()

    # 3. Create preset mappings
    from backend.modeling.mapping.mapping_models import (
        Mapping,
        MappingFile,
        MappingGranularity,
        MappingStatus,
    )
    mf_path = Path("/tmp/ontong-repos") / SAMPLE_REPO_ID / ".ontology" / "mapping.yaml"
    mf = MappingFile(repo_id=SAMPLE_REPO_ID, mappings=[])

    for code, domain, granularity in PRESET_MAPPINGS:
        mf.mappings.append(
            Mapping(
                code=code,
                domain=domain,
                granularity=MappingGranularity(granularity),
                owner="system",
                status=MappingStatus.CONFIRMED,
            )
        )

    from backend.modeling.mapping.yaml_store import save_mapping_yaml
    save_mapping_yaml(mf_path, mf)

    # 4. Sync mappings to Neo4j
    _mapping_svc.sync_to_neo4j(mf)

    # 5. Register simulation parameters (sim_registry is pre-loaded with demo data)
    from backend.modeling.simulation.sim_registry import SimRegistry
    sim_entity_ids = SimRegistry.all_entity_ids()
    sim_count = len([eid for eid in sim_entity_ids if any(m.code == eid for m in mf.mappings)])

    return {
        "status": "ok",
        "repo_id": SAMPLE_REPO_ID,
        "files_parsed": len(java_files),
        "entities_count": total_entities,
        "relations_count": total_relations,
        "ontology_nodes": ontology_count,
        "mappings_created": len(PRESET_MAPPINGS),
        "sim_entities": sim_count,
    }
