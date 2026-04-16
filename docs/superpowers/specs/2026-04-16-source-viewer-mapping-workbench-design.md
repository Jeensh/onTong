# Source Code Viewer + Mapping Workbench Design

**Date:** 2026-04-16
**Author:** donghae + Claude
**Status:** Approved
**Scope:** Section 2 Modeling — Phase 2a

---

## Goal

Build a commercial-grade code-to-domain mapping verification workflow. Users browse actual source code side-by-side with an interactive domain ontology graph, visually create and validate mappings, and verify that automated mappings are correct.

This is the core differentiator: legacy code modeling tools that only show parsed entity names are insufficient. Seeing the actual source code while mapping is essential for accuracy.

## Product Context

onTong is a legacy code modeling and simulation solution. The target user is a domain expert or architect who needs to:

1. Upload a Java project (git clone)
2. Parse code into entities and relations (existing: java_parser + Neo4j)
3. **Verify mappings by reading actual source code** (NEW: this phase)
4. Run impact analysis and simulations (existing: engine APIs)
5. Edit code and test in sandbox (FUTURE: separate phase)

Phase 2a addresses step 3 — the mapping verification gap.

## Architecture

Two new frontend components + one new backend API module, integrated into the existing ModelingSection via a new "Mapping Workbench" tab.

No new databases or infrastructure. Uses existing:
- Filesystem: cloned repos at `sample-repos/{repo_id}/`
- Neo4j: code entities with line position data
- YAML store: code-to-domain mappings
- Neo4j: SCOR/ISA-95 ontology nodes

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Source viewer mode | Read-only (Monaco Editor) | Editor extension planned for sandbox phase. Monaco gives free upgrade path. |
| Mapping visualization | React Flow interactive graph | Drag-and-drop mapping, zoom/pan, minimap. Industry standard for node graphs. |
| Layout | Split panel (canvas left + viewer right) | User said "both sides visible for verification". Desktop-only is acceptable for commercial tool. |
| Graph layout algorithm | Dagre (hierarchical) | SCOR ontology is inherently hierarchical (Plan → DemandPlanning → ...) |
| File serving | Direct filesystem read | No new storage needed. Path traversal protection required. |
| Existing tabs | Keep as-is under Settings | "Code Analysis", "Domain Ontology", "Mapping Management" remain for data input/management. Workbench is the visual integration layer. |

---

## Component Design

### 1. Source Code Viewer (Right Panel)

Two sub-areas: file tree (collapsible top) + code display (main).

#### 1.1 File Tree

- Renders actual directory structure from cloned repo
- Folder expand/collapse, file click opens in code display
- File type filter: `.java` default, toggleable for `.xml`, `.properties`, etc.
- Search/filter by filename or path
- Mapping status icon per file:
  - Green dot: all entities in file are mapped
  - Yellow dot: some entities mapped
  - No dot: no parsed entities (config files, etc.)

#### 1.2 Code Display

- Monaco Editor in read-only mode
- Java syntax highlighting, line numbers
- Entity highlight: when a domain node is clicked in canvas, auto-scroll to the mapped entity's class/method and apply background highlight color
- Gutter markers: colored bars on line ranges that have domain mappings (color per domain)
- Inline badges on class/method declarations: `[SCOR/Plan/InventoryPlanning]` showing current mapping
- Click on class/method declaration: highlight connected domain node in canvas

#### 1.3 Source Viewer API

```
GET /api/modeling/source/tree/{repo_id}
Response:
{
  "name": "src",
  "type": "directory",
  "path": "src",
  "children": [
    {
      "name": "main",
      "type": "directory",
      "path": "src/main",
      "children": [...]
    }
  ]
}

GET /api/modeling/source/file/{repo_id}?path=src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java
Response:
{
  "path": "src/main/java/.../SafetyStockCalculator.java",
  "language": "java",
  "content": "package com.ontong.scm.inventory;\n\nimport...",
  "entities": [
    {
      "fqn": "com.ontong.scm.inventory.SafetyStockCalculator",
      "kind": "class",
      "start_line": 5,
      "end_line": 89,
      "mapping": {
        "domain_path": "SCOR/Plan/InventoryPlanning",
        "status": "confirmed",
        "granularity": "class"
      }
    },
    {
      "fqn": "com.ontong.scm.inventory.SafetyStockCalculator.calculateSafetyStock",
      "kind": "method",
      "start_line": 23,
      "end_line": 45,
      "mapping": null
    }
  ]
}
```

**Security:** Path traversal guard — resolve path, verify it's within `sample-repos/{repo_id}/`. Reject `..`, symlinks outside repo, binary files.

---

### 2. Mapping Canvas (Left Panel)

React Flow-based interactive graph with code entity side panel.

#### 2.1 Domain Ontology Graph (Center)

- SCOR/ISA-95 nodes rendered as a directed acyclic graph
- Dagre layout algorithm for hierarchical positioning
- Node visual:
  - Green fill: has confirmed mappings
  - Yellow fill: has draft/review mappings
  - Gray fill: no mappings (gap)
  - Node label: domain name (e.g., "InventoryPlanning")
  - Badge: number of connected code entities
- Edge: parent-child domain relationships (part_of)
- Interactions:
  - Click node: show connected code entities, trigger source viewer highlight
  - Hover node: tooltip with full domain path + entity count
  - Zoom/pan: React Flow built-in
  - Minimap: bottom-right corner for orientation

#### 2.2 Code Entity Panel (Bottom or Left Side of Canvas)

- List of parsed code entities (classes, methods) from Neo4j
- Searchable, filterable by kind (class/method/package)
- Visual indicators:
  - Red dot: unmapped entity
  - Green dot: mapped entity (with domain name label)
  - Connection line to its domain node in the graph
- Drag-and-drop: drag entity onto a domain node to create mapping
- Click entity: open its source in the viewer (right panel)

#### 2.3 Mapping Lines

- Curved bezier lines connecting code entities to domain nodes
- Line style by granularity:
  - Package: thick solid line
  - Class: medium solid line
  - Method: dashed line
- Click on line: popover with mapping details (status, granularity, delete button)
- Line color matches domain node color

#### 2.4 Mapping CRUD

- **Create**: drag entity to domain node, or right-click entity → "Map to..." dropdown
- **Read**: visual connections + click for details
- **Update**: drag mapped entity to different domain node (re-map)
- **Delete**: click connection line → delete button, or right-click → remove mapping
- All operations call existing `mapping_service.py` APIs

---

### 3. Mapping Workbench (Integration)

Container component that combines canvas and viewer.

#### 3.1 Layout

```
┌─────────────────────────────────────────────────────────────┐
│                    Mapping Workbench                         │
├─────────────────────────────┬───────────────────────────────┤
│                             │  ┌─ File Tree ────────────┐   │
│   Mapping Canvas            │  │ > src/main/java/com/   │   │
│                             │  │   > inventory/          │   │
│   ┌─ Domain Graph ────────┐│  │     SafetyStock...java  │   │
│   │  [Plan]───[InvPlan]   ││  │     InventoryMgr.java   │   │
│   │  [Source]──[Procure]  ││  └─────────────────────────┘   │
│   └────────────────────────┘│  ┌─ Code Display ─────────┐   │
│                             │  │  1 │ package com.ontong │   │
│   ┌─ Code Entities ───────┐│  │  2 │ import java.util   │   │
│   │ ● SafetyStockCalc     ││  │  3 │                     │   │
│   │ ○ OrderService        ││  │  4 │ @Component          │   │
│   │ ○ ProductionPlanner   ││  │  5 │ public class Safe.. │   │
│   └────────────────────────┘│  └─────────────────────────┘   │
├─────────────────────────────┴───────────────────────────────┤
│  ◀═══ resizable divider ═══▶                                │
└─────────────────────────────────────────────────────────────┘
```

- Resizable vertical divider between canvas and viewer
- Default split: 55% canvas / 45% viewer
- Minimum width constraints to prevent collapsing

#### 3.2 Bidirectional Linking

**Canvas → Viewer:**
1. Click domain node in graph
2. Connected code entities highlighted in entity panel
3. Click one entity → viewer opens that file, scrolls to entity, highlights lines

**Viewer → Canvas:**
1. Click class/method declaration in source code
2. If mapped: corresponding domain node highlights in canvas, connection line pulses
3. If unmapped: floating "Add Mapping" button appears near the declaration

#### 3.3 Navigation Integration

- New "Mapping Workbench" entry in ModelingSection MAIN_NAV (between "Simulation" and Settings divider)
- Icon: Network or GitBranch from lucide-react
- From AnalysisConsole: "View Source" button on query results → opens workbench with entity pre-selected

---

## Sidebar Structure (Updated)

```
MAIN_NAV:
  - Analysis Console (default)
  - Simulation
  - Mapping Workbench (NEW)

SETTINGS_NAV:
  - Code Analysis (Step 1)
  - Domain Ontology (Step 2)
  - Mapping Management (Step 3)
  - Approval List
```

---

## Backend Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `backend/modeling/api/source_api.py` | File tree + file content + entity position API |

### Modified Files

| File | Change |
|------|--------|
| `backend/modeling/api/modeling.py` | Wire source_api router |
| `backend/modeling/code_analysis/graph_writer.py` | Ensure start_line/end_line stored in Neo4j entity nodes |
| `backend/modeling/mapping/mapping_service.py` | Add `get_mappings_for_file(repo_id, file_path)` method |

### No Changes Needed

| File | Reason |
|------|--------|
| `java_parser.py` | Already extracts line positions |
| `ontology_store.py` | Already serves ontology tree |
| `sim_registry.py` / `sim_engine.py` | Simulation layer unchanged |

---

## Frontend Changes Summary

### New Files

| File | Purpose | Estimated LOC |
|------|---------|---------------|
| `frontend/src/components/sections/modeling/SourceViewer.tsx` | File tree + Monaco code display | ~300 |
| `frontend/src/components/sections/modeling/MappingCanvas.tsx` | React Flow graph + entity panel | ~400 |
| `frontend/src/components/sections/modeling/MappingWorkbench.tsx` | Split panel container + linking logic | ~150 |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/components/sections/ModelingSection.tsx` | Add "Mapping Workbench" to MAIN_NAV, wire component |
| `frontend/src/lib/api/modeling.ts` | Add `getSourceTree()`, `getSourceFile()` API functions |

### New Dependencies

| Package | Purpose |
|---------|---------|
| `@xyflow/react` (React Flow v12) | Interactive node graph |
| `@dagrejs/dagre` | Hierarchical graph layout |
| `@monaco-editor/react` | Code editor component (read-only mode) |

---

## Implementation Order

### Step 1: Source Code Viewer (standalone)

- Backend: `source_api.py` with file tree + content endpoints
- Frontend: `SourceViewer.tsx` with file tree + Monaco display
- Temporary tab in sidebar for independent testing
- Verify: demo load → browse file tree → view Java source with syntax highlighting

### Step 2: Mapping Canvas

- React Flow domain graph from ontology data
- Code entity panel with search/filter
- Drag-and-drop mapping creation
- Mapping line visualization with status colors
- Verify: drag entity to node → mapping created → visual connection shown

### Step 3: Integration — Mapping Workbench

- `MappingWorkbench.tsx` split panel layout
- Bidirectional linking (canvas ↔ viewer)
- Entity highlighting in source code
- "Add Mapping" floating button for unmapped entities
- Sidebar integration as MAIN_NAV item
- Verify: click domain node → source scrolls to entity → click unmapped method → mapping dialog

---

## Future Infrastructure (Post Phase 2a)

| # | Item | Trigger | Notes |
|---|------|---------|-------|
| INFRA-1 | Docker Sandbox | Sandbox phase start | Docker Engine API for container lifecycle |
| INFRA-2 | Redis file tree cache | 100K+ file repos | Current filesystem scan sufficient for now |
| INFRA-3 | Mapping audit trail | Change history requirement | YAML lacks version tracking |
| INFRA-4 | WebSocket sync | Multi-user simultaneous mapping | Single-user sufficient for now |

---

## Testing Strategy

### Backend Tests
- `test_source_api.py`: file tree generation, file content serving, entity position joining, path traversal rejection, binary file filtering

### Frontend Verification
- File tree renders correct structure after demo load
- Monaco displays Java with syntax highlighting
- React Flow graph shows SCOR hierarchy with correct node colors
- Drag-and-drop creates mapping via API
- Cross-panel highlighting works bidirectionally
- Resizable divider functions correctly

### Integration
- Full flow: demo load → workbench → click domain node → view source → verify mapping → drag new mapping
