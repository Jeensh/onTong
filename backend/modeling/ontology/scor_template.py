"""SCOR + ISA-95 default ontology template.

Provides a ready-made DomainOntology with:
- SCOR Level 1 & Level 2 processes
- ISA-95 levels nested under Make
- Common supply-chain entities and roles
- Structural (PART_OF) and semantic relations
"""

from __future__ import annotations

from backend.modeling.ontology.domain_models import (
    DomainNode,
    DomainNodeKind,
    DomainOntology,
    DomainRelation,
    DomainRelationKind,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _p(id: str, name: str, *, parent_id: str | None = None, description: str = "") -> DomainNode:
    """Create a process node."""
    return DomainNode(
        kind=DomainNodeKind.PROCESS,
        id=id,
        name=name,
        parent_id=parent_id,
        description=description,
    )


def _e(id: str, name: str, *, description: str = "") -> DomainNode:
    """Create an entity node."""
    return DomainNode(
        kind=DomainNodeKind.ENTITY,
        id=id,
        name=name,
        description=description,
    )


def _r(id: str, name: str, *, description: str = "") -> DomainNode:
    """Create a role node."""
    return DomainNode(
        kind=DomainNodeKind.ROLE,
        id=id,
        name=name,
        description=description,
    )


def _rel(kind: DomainRelationKind, source: str, target: str) -> DomainRelation:
    """Create a relation."""
    return DomainRelation(kind=kind, source_id=source, target_id=target)


# ---------------------------------------------------------------------------
# Template builder
# ---------------------------------------------------------------------------

def load_scor_template() -> DomainOntology:
    """Return the default SCOR + ISA-95 ontology template.

    The template contains 30+ nodes covering SCOR Level 1/2 processes,
    ISA-95 manufacturing hierarchy, common supply-chain entities, and roles.
    """
    nodes: list[DomainNode] = []
    relations: list[DomainRelation] = []

    # === SCOR Level 1 =======================================================
    level1 = [
        _p("SCOR/Plan", "Plan", description="Demand/supply planning and balancing"),
        _p("SCOR/Source", "Source", description="Procurement and supplier management"),
        _p("SCOR/Make", "Make", description="Production and manufacturing"),
        _p("SCOR/Deliver", "Deliver", description="Order fulfillment and logistics"),
        _p("SCOR/Return", "Return", description="Returns and reverse logistics"),
    ]
    nodes.extend(level1)

    # === SCOR Level 2 (sub-processes) ========================================

    # Plan sub-processes
    plan_children = [
        _p("SCOR/Plan/DemandPlanning", "Demand Planning", parent_id="SCOR/Plan",
           description="Forecast and demand signal aggregation"),
        _p("SCOR/Plan/SupplyPlanning", "Supply Planning", parent_id="SCOR/Plan",
           description="Supply capacity and constraint planning"),
        _p("SCOR/Plan/InventoryPlanning", "Inventory Planning", parent_id="SCOR/Plan",
           description="Safety stock and replenishment strategy"),
        _p("SCOR/Plan/SalesAndOperationsPlanning", "S&OP", parent_id="SCOR/Plan",
           description="Cross-functional demand-supply alignment"),
    ]
    nodes.extend(plan_children)

    # Source sub-processes
    source_children = [
        _p("SCOR/Source/SupplierSelection", "Supplier Selection", parent_id="SCOR/Source",
           description="Evaluate and select suppliers"),
        _p("SCOR/Source/Purchasing", "Purchasing", parent_id="SCOR/Source",
           description="Purchase order creation and management"),
        _p("SCOR/Source/ReceivingInspection", "Receiving & Inspection", parent_id="SCOR/Source",
           description="Inbound quality and receiving"),
    ]
    nodes.extend(source_children)

    # Make sub-processes
    make_children = [
        _p("SCOR/Make/ProductionScheduling", "Production Scheduling", parent_id="SCOR/Make",
           description="Sequencing and scheduling production orders"),
        _p("SCOR/Make/Manufacturing", "Manufacturing", parent_id="SCOR/Make",
           description="Execution of production processes"),
        _p("SCOR/Make/QualityControl", "Quality Control", parent_id="SCOR/Make",
           description="In-process and final quality assurance"),
    ]
    nodes.extend(make_children)

    # Deliver sub-processes
    deliver_children = [
        _p("SCOR/Deliver/OrderManagement", "Order Management", parent_id="SCOR/Deliver",
           description="Sales order processing and confirmation"),
        _p("SCOR/Deliver/Warehousing", "Warehousing", parent_id="SCOR/Deliver",
           description="Storage, pick, pack operations"),
        _p("SCOR/Deliver/Transportation", "Transportation", parent_id="SCOR/Deliver",
           description="Outbound shipping and freight"),
        _p("SCOR/Deliver/LastMileDelivery", "Last Mile Delivery", parent_id="SCOR/Deliver",
           description="Final delivery to customer"),
    ]
    nodes.extend(deliver_children)

    # Return sub-processes
    return_children = [
        _p("SCOR/Return/ReturnAuthorization", "Return Authorization", parent_id="SCOR/Return",
           description="RMA and return eligibility"),
        _p("SCOR/Return/ReturnProcessing", "Return Processing", parent_id="SCOR/Return",
           description="Inspect, restock, or dispose returned goods"),
        _p("SCOR/Return/Refurbishment", "Refurbishment", parent_id="SCOR/Return",
           description="Repair and repackage returned products"),
    ]
    nodes.extend(return_children)

    # === ISA-95 levels under Make ============================================
    isa95_nodes = [
        _p("SCOR/Make/ISA95/Level4", "Business Planning & Logistics",
           parent_id="SCOR/Make",
           description="ISA-95 Level 4: ERP-level business planning"),
        _p("SCOR/Make/ISA95/Level3", "Manufacturing Operations Management",
           parent_id="SCOR/Make",
           description="ISA-95 Level 3: MES/MOM work-flow management"),
        _p("SCOR/Make/ISA95/Level2", "Supervisory Control",
           parent_id="SCOR/Make",
           description="ISA-95 Level 2: SCADA / supervisory layer"),
        _p("SCOR/Make/ISA95/Level1", "Direct Control",
           parent_id="SCOR/Make",
           description="ISA-95 Level 1: PLC / sensor-actuator control"),
    ]
    nodes.extend(isa95_nodes)

    # === Common Entities =====================================================
    entities = [
        _e("Entity/SafetyStock", "Safety Stock",
           description="Buffer inventory to protect against variability"),
        _e("Entity/BOM", "Bill of Materials",
           description="Component and raw-material structure of a product"),
        _e("Entity/PurchaseOrder", "Purchase Order",
           description="Document authorizing procurement from a supplier"),
        _e("Entity/ProductionOrder", "Production Order",
           description="Work order to manufacture a specific quantity"),
        _e("Entity/SalesOrder", "Sales Order",
           description="Customer order for goods or services"),
        _e("Entity/Inventory", "Inventory",
           description="Stock on hand across locations"),
        _e("Entity/LeadTime", "Lead Time",
           description="Duration from order to receipt or completion"),
    ]
    nodes.extend(entities)

    # === Common Roles ========================================================
    roles = [
        _r("Role/Planner", "Planner",
           description="Responsible for demand/supply planning activities"),
        _r("Role/Buyer", "Buyer",
           description="Handles procurement and supplier negotiations"),
        _r("Role/ProductionManager", "Production Manager",
           description="Oversees manufacturing operations"),
        _r("Role/WarehouseManager", "Warehouse Manager",
           description="Manages warehousing and distribution"),
        _r("Role/QualityEngineer", "Quality Engineer",
           description="Ensures product and process quality standards"),
    ]
    nodes.extend(roles)

    # === Relations ============================================================

    # PART_OF: Level-2 -> Level-1
    for child in plan_children:
        relations.append(_rel(DomainRelationKind.PART_OF, child.id, "SCOR/Plan"))
    for child in source_children:
        relations.append(_rel(DomainRelationKind.PART_OF, child.id, "SCOR/Source"))
    for child in make_children:
        relations.append(_rel(DomainRelationKind.PART_OF, child.id, "SCOR/Make"))
    for child in deliver_children:
        relations.append(_rel(DomainRelationKind.PART_OF, child.id, "SCOR/Deliver"))
    for child in return_children:
        relations.append(_rel(DomainRelationKind.PART_OF, child.id, "SCOR/Return"))

    # PART_OF: ISA-95 -> Make
    for isa in isa95_nodes:
        relations.append(_rel(DomainRelationKind.PART_OF, isa.id, "SCOR/Make"))

    # USES relations
    relations.extend([
        _rel(DomainRelationKind.USES, "SCOR/Plan/DemandPlanning", "Entity/SalesOrder"),
        _rel(DomainRelationKind.USES, "SCOR/Plan/InventoryPlanning", "Entity/SafetyStock"),
        _rel(DomainRelationKind.USES, "SCOR/Plan/InventoryPlanning", "Entity/LeadTime"),
        _rel(DomainRelationKind.USES, "SCOR/Source/Purchasing", "Entity/PurchaseOrder"),
        _rel(DomainRelationKind.USES, "SCOR/Make/Manufacturing", "Entity/BOM"),
        _rel(DomainRelationKind.USES, "SCOR/Make/ProductionScheduling", "Entity/ProductionOrder"),
        _rel(DomainRelationKind.USES, "SCOR/Deliver/Warehousing", "Entity/Inventory"),
    ])

    # PRODUCES relations
    relations.extend([
        _rel(DomainRelationKind.PRODUCES, "SCOR/Plan/DemandPlanning", "Entity/SafetyStock"),
        _rel(DomainRelationKind.PRODUCES, "SCOR/Source/Purchasing", "Entity/PurchaseOrder"),
        _rel(DomainRelationKind.PRODUCES, "SCOR/Deliver/OrderManagement", "Entity/SalesOrder"),
        _rel(DomainRelationKind.PRODUCES, "SCOR/Make/ProductionScheduling", "Entity/ProductionOrder"),
    ])

    # RESPONSIBLE_FOR relations
    relations.extend([
        _rel(DomainRelationKind.RESPONSIBLE_FOR, "Role/Planner", "SCOR/Plan"),
        _rel(DomainRelationKind.RESPONSIBLE_FOR, "Role/Buyer", "SCOR/Source"),
        _rel(DomainRelationKind.RESPONSIBLE_FOR, "Role/ProductionManager", "SCOR/Make"),
        _rel(DomainRelationKind.RESPONSIBLE_FOR, "Role/WarehouseManager", "SCOR/Deliver/Warehousing"),
        _rel(DomainRelationKind.RESPONSIBLE_FOR, "Role/QualityEngineer", "SCOR/Make/QualityControl"),
    ])

    return DomainOntology(nodes=nodes, relations=relations)
