# Section 2: Modeling — Design Spec

## Overview

Section 2 is a code-analysis and domain-mapping tool for manufacturing SCM systems. It parses customer Java codebases, builds a code dependency graph, and lets IT engineers map code entities to SCOR+ISA-95 domain concepts. The resulting ontology enables deterministic impact analysis ("if this code changes, which business processes are affected?") and sandbox-based simulation.

**Core philosophy:** Modeling is hard, but results must be accurate. Section 2 makes the hard work of modeling easier through structure and UI — it does not try to automate it away with unreliable AI guesses. Every analysis result traces back to explicit, human-confirmed data.

## Non-goals

- Section 1 (Wiki) integration — sections are independent
- Real-time operational data dashboards (this is not Palantir)
- LLM-driven ontology generation or mapping inference

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Section 2: Modeling                     │
│                                                             │
│  ┌─────────────┐   ┌────────────────┐   ┌───────────────┐  │
│  │ Code        │   │ Mapping Engine │   │ Domain        │  │
│  │ Analyzer    │──→│ (core)         │←──│ Ontology      │  │
│  │             │   │                │   │               │  │
│  │ JavaParser  │   │ YAML mgmt     │   │ SCOR+ISA-95   │  │
│  │ AST→Graph   │   │ Mapping UI     │   │ template      │  │
│  │ Neo4j store │   │ Gap detection  │   │ + custom ext  │  │
│  └─────────────┘   │ Impact queries │   │ Neo4j store   │  │
│       ↑            └────────────────┘   └───────────────┘  │
│       │                   │                    ↑            │
│  ┌─────────────┐   ┌────────────────┐   ┌───────────────┐  │
│  │ Git         │   │ Change         │   │ Query         │  │
│  │ Connector   │   │ Detector       │   │ Engine        │  │
│  │             │   │                │   │               │  │
│  │ clone/pull  │   │ diff analysis  │   │ NL→lookup     │  │
│  │ branch mgmt │   │ impact classify│   │ graph BFS     │  │
│  │ webhook     │   │ notify         │   │ result report │  │
│  └─────────────┘   └────────────────┘   └───────────────┘  │
│                                                             │
│  ┌─────────────┐   ┌────────────────┐   ┌───────────────┐  │
│  │ Approval    │   │ Sandbox        │   │ View Layer    │  │
│  │ Workflow    │   │ Engine         │   │               │  │
│  │             │   │                │   │ IT view       │  │
│  │ draft →     │   │ Docker/JVM     │   │ (code-centric)│  │
│  │ review →    │   │ isolation exec │   │ Biz view      │  │
│  │ confirmed   │   │ before/after   │   │ (domain-cntrc)│  │
│  └─────────────┘   └────────────────┘   └───────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Parser Plugin Interface                              │   │
│  │ JavaParser (MVP) │ tree-sitter (future) │ ...        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         ↕ Python Protocol (modular monolith)
┌─────────────────────────────────────────────────────────────┐
│                    Section 3: Simulation                    │
│  Scenario UI → calls Section 2 APIs → result visualization │
│  Uses existing shared/contracts/simulation.py               │
└─────────────────────────────────────────────────────────────┘
```

### Data stores

| Store | Purpose | Data |
|-------|---------|------|
| Neo4j Community | Graph queries | Code graph + domain ontology + mappings (cache) |
| Customer repo `.ontology/` | Source of truth for mappings | YAML mapping files (co-versioned with code) |
| PostgreSQL (future) | Approval workflow state | Review requests, comments, statuses |

### Section interaction

- Section 1 (Wiki): **Independent.** No integration.
- Section 3 (Simulation): Connected via Python Protocol. Section 3 sends scenario requests, Section 2 provides ontology data and code execution. Uses existing `backend/shared/contracts/simulation.py`.

---

## 2. Three-Layer Data Model

The ontology consists of three layers with different change frequencies and ownership:

### Layer 1: Code Graph (automated, every commit)

Extracted automatically via static analysis. No human intervention needed.

```
Nodes:
  - Package (e.g., com.client.inventory)
  - Class (e.g., SafetyStockCalculator)
  - Method (e.g., calculate)
  - Field

Edges:
  - CALLS (method → method)
  - EXTENDS / IMPLEMENTS (class → class)
  - DEPENDS_ON (class → class, via imports)
  - CONTAINS (package → class → method)
  - READS / WRITES (method → field)
```

### Layer 2: Domain Ontology (manual, rarely changes)

SCOR + ISA-95 hybrid. Provided as a template, customized per customer.

```
Nodes:
  - DomainProcess (e.g., SCOR/Plan/DemandPlanning)
  - DomainEntity (e.g., SafetyStock, BOM, PurchaseOrder)
  - DomainRole (e.g., InventoryManager, Planner)

Edges:
  - PART_OF (process hierarchy)
  - USES / PRODUCES (process → entity)
  - RESPONSIBLE_FOR (role → process)
```

### Layer 3: Mapping (human-confirmed, changes when code structure changes)

Bridges code and domain. Stored as YAML in customer repo, cached in Neo4j.

```yaml
# .ontology/mapping.yaml
mappings:
  - code: "com.client.inventory.SafetyStockCalculator"
    domain: "SCOR/Plan/InventoryPlanning/SafetyStock"
    owner: "kim-inventory"
    status: confirmed  # draft | review | confirmed
    confirmed_by: "lee-scm"
    confirmed_at: "2026-04-10"

  - code: "com.client.order.OrderService"
    domain: "SCOR/Deliver/OrderFulfillment"
    owner: "park-logistics"
    status: draft
```

**Mapping inheritance:** Mappings at package level are inherited by contained classes/methods. Override at any level for exceptions.

```yaml
# Package-level mapping (applies to all classes within)
- code: "com.client.inventory"
  domain: "SCOR/Plan/InventoryPlanning"
  granularity: package

# Override for specific class
- code: "com.client.inventory.DemandForecaster"
  domain: "SCOR/Plan/DemandPlanning"
  granularity: class
```

---

## 3. Core Components

### 3.1 Code Analyzer

Parses customer Java source code and builds the code graph in Neo4j.

**Parser plugin interface:**

```python
class CodeParser(Protocol):
    """Language-specific parser plugin."""
    def supported_extensions(self) -> list[str]: ...
    def parse_file(self, path: Path, content: str) -> list[CodeEntity]: ...
    def extract_relations(self, entities: list[CodeEntity]) -> list[CodeRelation]: ...
```

**MVP implementation:** JavaParser library (full Java syntax support, type resolution).

**Future extensions:** tree-sitter for Python, Go, Kotlin, etc. Each language adds a new parser plugin without changing the core.

**Process:**
1. Git Connector clones/pulls the customer repo
2. Parser plugin extracts code entities and relations
3. Code graph is written to Neo4j
4. On subsequent pulls, only changed files are re-parsed (incremental update)

### 3.2 Domain Ontology Manager

Manages the SCOR+ISA-95 domain model.

**SCOR template:** Pre-built template covering Plan/Source/Make/Deliver/Return at Level 1-3. Customer customizes by adding/removing/renaming nodes.

**ISA-95 integration:** Detailed breakdown of the Make process into production levels (Level 0-4).

**Operations:**
- Load template → customize for customer
- Add/remove/rename domain nodes
- Define relationships between domain entities
- Visual editor: tree view + graph view
- All changes saved to Neo4j + exportable as YAML

### 3.3 Mapping Engine (core value)

The central piece — connecting code entities to domain concepts.

**Mapping UI features:**
- Split view: code tree (left) ↔ domain tree (right)
- Drag-and-drop mapping creation
- Search + autocomplete for both sides
- Package-level bulk mapping with inheritance
- Gap detection: unmapped code entities highlighted
- Conflict detection: one code entity mapped to multiple domain nodes

**Mapping file management:**
- Source of truth: YAML files in customer repo `.ontology/`
- On save: YAML written + Neo4j cache updated
- Co-versioned with code via git

### 3.4 Change Detector

Monitors customer repo for code changes and classifies impact on mappings.

**Classification:**
```
Git diff arrives
  → File-level: which files changed?
  → Entity-level: which classes/methods added/removed/renamed/modified?
  → Mapping impact:
     ├── Rename/move → auto-update mapping references
     ├── Delete → flag mapping as broken, notify owner
     ├── New code → flag as unmapped, suggest mapping
     └── Logic change → flag as "review mapping", show AST diff
```

**Notification targets:** Each mapping has an `owner` field — notifications go to the owner.

### 3.5 Query Engine

Translates user questions into deterministic graph queries.

**Query flow (no LLM in data path):**
1. **Term lookup:** Search mapping YAML/Neo4j for the mentioned concept. If not found → "unmapped term" response.
2. **Graph traversal:** BFS/DFS on Neo4j code graph from the identified node.
3. **Reverse mapping:** Map discovered code entities back to domain concepts.
4. **Result assembly:** Structured result (affected processes, owners, paths).
5. **Presentation (LLM allowed here):** Format structured result as natural language explanation.

**LLM role boundaries:**
- Allowed: interpreting user's natural language input → mapping table lookup terms. Formatting structured results into readable explanation. Suggesting follow-up queries.
- Forbidden: generating graph query results. Inferring unmapped relationships. Guessing domain meanings.

**If the user's term is ambiguous:** Present candidates and ask user to pick, rather than guessing.

### 3.6 Approval Workflow

IT creates mappings → business users review and confirm.

**States:** `draft` → `review` → `confirmed`

**Flow:**
1. IT creates/modifies mapping (status: `draft`)
2. IT submits review request with impact analysis attached
3. Business user sees domain-centric view (no code details)
4. Business user approves → `confirmed`, rejects → back to `draft` with comment
5. Only `confirmed` mappings are used in impact analysis results

**Views:**
- IT view: code-centric. Shows AST, dependencies, technical details, mapping status.
- Business view: domain-centric. Shows SCOR process tree, impact in business terms, no code.

### 3.7 Sandbox Engine

Executes customer code in isolation for simulation and verification.

**Execution modes:**

| Mode | Input | Method | Use case |
|------|-------|--------|----------|
| Scenario simulation | User-defined parameters | Function isolation + Docker JVM | "What if demand = 500/month?" |
| Before/after comparison | Same input, different code | Branch A vs Branch B execution | "What changes with this code fix?" |
| Record & Replay | Captured production I/O | Replay against modified code | "Same real inputs, different logic" |
| State Snapshot | DB snapshot in sandbox | Full system execution | "Run entire engine with this state" |

**Phase 2 scope:** Scenario simulation (user-defined inputs). Other modes in later phases. Sandbox is not part of MVP — MVP focuses on mapping + impact analysis.

**Isolation:** Docker containers with JVM. Network-isolated. Time-limited. Resource-capped.

---

## 4. Edit → Preview → Verify Loop

Section 2 supports three types of edits, all following the same pattern:

```
Edit → Impact preview → Execute/verify → Commit or discard
```

### 4.1 Code editing

- Edits happen on a git branch (never directly on main)
- After edit: re-parse changed files, generate code graph diff
- Impact preview: "this change affects N domain processes"
- Sandbox: run before/after with same inputs, compare outputs
- Commit: push branch, create PR in customer repo
- MVP: read-only + diff preview. Direct editing in Phase 2.

### 4.2 Ontology editing

- Add/remove/rename domain nodes in SCOR tree
- Impact preview: "this node has N mappings — they will be affected"
- If deleting a node with mappings: require remapping or confirmation
- Changes saved to Neo4j immediately, exportable as YAML

### 4.3 Mapping editing

- Create/modify/delete code↔domain connections
- Impact preview: "adding this mapping changes impact analysis for N queries"
- Status tracking: all new/modified mappings start as `draft`
- YAML + Neo4j sync on save

---

## 5. Simulation Capability

### What's possible (everything, given code exists)

| Code complexity | Simulation method | Accuracy |
|----------------|-------------------|----------|
| Simple formulas (safety stock, EOQ) | Computation graph extraction → parameter tuning | 100% (fast) |
| Complex logic (MRP, provisioning, schedulers) | Actual code execution with user-defined inputs | 100% (real code) |
| Large systems (ERP engine) | State snapshot + sandboxed execution | 100% (full env replica) |

### What varies

- **Speed:** Formula extraction is instant. Full system execution takes time.
- **Setup cost:** Simple functions need minimal setup. Large systems need data preparation.
- **Data requirements:** Simulation uses user-defined scenarios (no production data needed). Diagnostics ("why is this happening?") needs real data (Phase 3+).

### LLM role in simulation

- **Before:** Interpret user's natural language scenario → structured simulation parameters
- **During:** None. Execution is deterministic.
- **After:** Explain results in natural language. Suggest follow-up scenarios.

---

## 6. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Java parsing (MVP) | JavaParser | Full Java syntax, type resolution, mature |
| Future language parsing | tree-sitter | Multi-language, fast, good enough for structure |
| Graph database | Neo4j Community | Native graph queries (Cypher), free |
| Mapping format | YAML in `.ontology/` | Git co-versioning, human-readable |
| Sandbox runtime | Docker + JVM | Isolation, resource limits, reproducible |
| Backend | Python (FastAPI) | Consistent with existing onTong backend |
| Frontend | React + TypeScript | Consistent with existing onTong frontend |
| Parser plugin interface | Python Protocol | Same pattern as existing agent plugins |

---

## 7. Phased Delivery

### MVP (Phase 1): End-to-end mapping + impact analysis

- Git Connector: clone customer Java repo
- Code Analyzer: JavaParser → Neo4j code graph
- Domain Ontology: SCOR template + custom node editor
- Mapping UI: split-view, drag-and-drop, YAML persistence
- Query Engine: term lookup → BFS → reverse mapping → result
- Change Detector: basic diff classification + notifications
- Approval Workflow: draft/review/confirmed states
- IT view + Business view

### Phase 2: Code editing + sandbox execution

- Monaco-based code editor (branch-only)
- Docker sandbox: function isolation + scenario simulation
- Before/after comparison
- Computation graph extraction for simple formulas
- Impact preview on edit

### Phase 3: Data integration + advanced simulation

- Record & Replay (production I/O capture)
- State Snapshot (DB replication to sandbox)
- ERP/MES data connectors (read-only)
- Diagnostics mode ("why is this happening?")

### Phase 4: Multi-language + ecosystem

- tree-sitter parsers for Python, Go, Kotlin
- Parser plugin marketplace
- CI/CD integration (git hook → mapping revalidation)
- Section 3 full integration (scenario UI → Section 2 execution)

---

## 8. Key Design Principles

1. **100% reliability over convenience.** Never guess. If it's not mapped, say "not mapped." Wrong answers destroy trust faster than slow answers.

2. **Humans model, tools assist.** The system makes modeling easier (visualization, drag-and-drop, gap detection, auto-suggestions). It does not try to model automatically.

3. **Code is the source of truth.** The code graph is always derived from actual code. Mappings are always explicit. Simulation runs actual code. Nothing is inferred.

4. **LLM at the edges only.** LLM helps translate natural language ↔ structured queries and format results. LLM never touches the data path (lookup → traverse → map → result).

5. **Co-version everything with code.** Mapping YAML lives in the customer repo. Code changes trigger mapping review. The two evolve together.

6. **Sections are independent.** Section 1 (Wiki) is a separate tool. Section 2 connects only to Section 3 (Simulation) via typed Protocol interfaces.
