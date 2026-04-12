# Section 2 Modeling MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Section 2 Modeling MVP — Java code analysis → SCOR domain ontology → mapping UI → deterministic impact analysis query engine.

**Architecture:** Bridge-First approach. Three layers (code graph, domain ontology, mapping) built simultaneously around the mapping engine as the core. Neo4j stores all three layers. Mapping YAML files are the source of truth, Neo4j is the query cache. All analysis is deterministic — LLM only at presentation edges.

**Tech Stack:** Python 3.11+, FastAPI, Neo4j Community, tree-sitter + tree-sitter-java, React + TypeScript, Zustand, D3 Force (graph viz)

**Spec:** `docs/superpowers/specs/2026-04-12-section2-modeling-design.md`

---

## File Structure

### Backend — New Files

```
backend/modeling/
├── infrastructure/
│   ├── neo4j_client.py          # Neo4j connection + health check
│   └── git_connector.py         # Clone/pull customer repos
├── code_analysis/
│   ├── parser_protocol.py       # CodeParser Protocol + types
│   ├── java_parser.py           # tree-sitter Java implementation
│   └── graph_writer.py          # Code entities → Neo4j
├── ontology/
│   ├── domain_models.py         # SCOR+ISA-95 Pydantic models
│   ├── scor_template.py         # Pre-built SCOR Level 1-3 template
│   └── ontology_store.py        # Domain ontology CRUD in Neo4j
├── mapping/
│   ├── mapping_models.py        # Mapping Pydantic models
│   ├── yaml_store.py            # YAML read/write in .ontology/
│   ├── mapping_service.py       # Mapping CRUD + gap detection
│   └── neo4j_cache.py           # Mapping → Neo4j sync
├── query/
│   ├── query_engine.py          # Term lookup + BFS + reverse mapping
│   └── query_models.py          # Query/result Pydantic models
├── change/
│   └── change_detector.py       # Git diff → mapping impact classification
├── approval/
│   ├── approval_models.py       # ReviewRequest, status enums
│   └── approval_service.py      # draft→review→confirmed workflow
├── api/
│   ├── modeling.py              # (modify existing) Wire up new endpoints
│   ├── code_api.py              # POST /parse, GET /graph
│   ├── ontology_api.py          # CRUD domain nodes
│   ├── mapping_api.py           # CRUD mappings + gap detection
│   ├── query_api.py             # POST /impact/analyze
│   └── approval_api.py          # Review request lifecycle
```

### Backend — Modified Files

```
backend/main.py                   # Add Neo4j init + new API routers
docker-compose.yml                # Add Neo4j service
pyproject.toml                    # Add neo4j, tree-sitter-java deps
```

### Frontend — New Files

```
frontend/src/
├── lib/api/
│   └── modeling.ts               # Section 2 API client
├── components/sections/modeling/
│   ├── CodeGraphViewer.tsx        # Code tree + graph viz
│   ├── DomainOntologyEditor.tsx   # SCOR tree editor
│   ├── MappingSplitView.tsx       # Code↔domain mapping UI
│   ├── ImpactQueryPanel.tsx       # Impact analysis query + results
│   └── ApprovalList.tsx           # Review requests list
```

### Frontend — Modified Files

```
frontend/src/components/sections/ModelingSection.tsx  # Replace scaffold
```

### Test Files

```
tests/
├── test_neo4j_client.py
├── test_java_parser.py
├── test_code_graph.py
├── test_scor_template.py
├── test_ontology_store.py
├── test_mapping_service.py
├── test_query_engine.py
├── test_change_detector.py
├── test_approval_service.py
└── test_modeling_api.py
```

---

## Task 1: Infrastructure — Neo4j + Dependencies

**Files:**
- Modify: `docker-compose.yml`
- Modify: `pyproject.toml`
- Create: `backend/modeling/infrastructure/neo4j_client.py`
- Test: `tests/test_neo4j_client.py`

- [ ] **Step 1: Add Neo4j to docker-compose.yml**

Add after the `redis` service:

```yaml
  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"   # Browser
      - "7687:7687"   # Bolt
    environment:
      NEO4J_AUTH: neo4j/ontong_dev
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5
```

Add to `volumes:` section:

```yaml
  neo4j_data:
```

- [ ] **Step 2: Add Python dependencies**

Add to `pyproject.toml` `[project.dependencies]`:

```toml
neo4j = "^5.0"
tree-sitter = "^0.23"
tree-sitter-java = "^0.23"
```

Run:

```bash
source venv/bin/activate && pip install neo4j tree-sitter tree-sitter-java
```

- [ ] **Step 3: Add Neo4j config to settings**

Add to `backend/core/config.py` (Settings class):

```python
# Neo4j (Section 2 - Modeling)
neo4j_uri: str = "bolt://localhost:7687"
neo4j_user: str = "neo4j"
neo4j_password: str = "ontong_dev"
```

- [ ] **Step 4: Write failing test for Neo4j client**

```python
# tests/test_neo4j_client.py
import pytest
from unittest.mock import MagicMock, patch

from backend.modeling.infrastructure.neo4j_client import Neo4jClient


class TestNeo4jClient:
    def test_connect_and_verify(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        # Should not raise on valid connection params
        assert client.uri == "bolt://localhost:7687"

    def test_health_check_returns_dict(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            mock_driver.verify_connectivity.return_value = None
            result = client.health()
            assert result["status"] == "healthy"

    def test_run_query(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            mock_session = MagicMock()
            mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value.data.return_value = [{"n": 1}]

            result = client.query("RETURN 1 as n")
            assert result == [{"n": 1}]

    def test_close(self):
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        with patch.object(client, '_driver') as mock_driver:
            client.close()
            mock_driver.close.assert_called_once()
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_neo4j_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.modeling.infrastructure.neo4j_client'`

- [ ] **Step 6: Implement Neo4j client**

```python
# backend/modeling/infrastructure/neo4j_client.py
"""Neo4j connection client for Section 2 graph storage."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Thin wrapper around Neo4j driver with health check and query helpers."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        self.uri = uri
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j client created for {uri}")

    def health(self) -> dict[str, str]:
        try:
            self._driver.verify_connectivity()
            return {"status": "healthy", "uri": self.uri}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict]:
        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return result.data()

    def write(self, cypher: str, params: dict[str, Any] | None = None) -> None:
        with self._driver.session() as session:
            session.run(cypher, params or {})

    def write_tx(self, cypher_list: list[tuple[str, dict]]) -> None:
        """Execute multiple writes in a single transaction."""
        with self._driver.session() as session:
            with session.begin_transaction() as tx:
                for cypher, params in cypher_list:
                    tx.run(cypher, params)
                tx.commit()

    def close(self) -> None:
        self._driver.close()
        logger.info("Neo4j client closed")
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_neo4j_client.py -v
```

Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml pyproject.toml backend/core/config.py \
  backend/modeling/infrastructure/neo4j_client.py tests/test_neo4j_client.py
git commit -m "feat(modeling): add Neo4j infrastructure + client"
```

---

## Task 2: Code Parser Protocol + Types

**Files:**
- Create: `backend/modeling/code_analysis/parser_protocol.py`

- [ ] **Step 1: Define parser protocol and entity types**

```python
# backend/modeling/code_analysis/parser_protocol.py
"""Language-agnostic code parser protocol and shared entity types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable
from pathlib import Path


class EntityKind(str, Enum):
    PACKAGE = "package"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    METHOD = "method"
    FIELD = "field"
    CONSTRUCTOR = "constructor"


class RelationKind(str, Enum):
    CONTAINS = "contains"          # package→class, class→method
    CALLS = "calls"                # method→method
    EXTENDS = "extends"            # class→class
    IMPLEMENTS = "implements"      # class→interface
    DEPENDS_ON = "depends_on"     # class→class (import)
    READS = "reads"                # method→field
    WRITES = "writes"              # method→field


@dataclass(frozen=True)
class CodeEntity:
    """A single code element extracted by a parser."""
    kind: EntityKind
    qualified_name: str            # e.g., "com.client.inventory.SafetyStockCalculator"
    name: str                      # e.g., "SafetyStockCalculator"
    file_path: str                 # relative path in repo
    line_start: int
    line_end: int
    modifiers: list[str] = field(default_factory=list)   # public, static, abstract, etc.
    parent: str | None = None      # qualified name of containing entity


@dataclass(frozen=True)
class CodeRelation:
    """A directed relationship between two code entities."""
    kind: RelationKind
    source: str                    # qualified name
    target: str                    # qualified name
    file_path: str | None = None   # where the relation was found
    line: int | None = None


@dataclass
class ParseResult:
    """Output of parsing a single file."""
    entities: list[CodeEntity]
    relations: list[CodeRelation]
    file_path: str
    language: str
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class CodeParser(Protocol):
    """Language-specific parser plugin interface."""

    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.java'])."""
        ...

    def language_name(self) -> str:
        """Human-readable language name (e.g., 'Java')."""
        ...

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        """Parse a single source file into entities and relations."""
        ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/modeling/code_analysis/parser_protocol.py
git commit -m "feat(modeling): define CodeParser protocol + entity types"
```

---

## Task 3: Java Parser (tree-sitter)

**Files:**
- Create: `backend/modeling/code_analysis/java_parser.py`
- Test: `tests/test_java_parser.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_java_parser.py
import pytest
from pathlib import Path

from backend.modeling.code_analysis.java_parser import JavaParser
from backend.modeling.code_analysis.parser_protocol import EntityKind, RelationKind


SAMPLE_JAVA = """\
package com.example.inventory;

import com.example.data.StockRepository;

public class SafetyStockCalculator {
    private final StockRepository repo;

    public SafetyStockCalculator(StockRepository repo) {
        this.repo = repo;
    }

    public double calculate(double avgDemand, double leadTime, double serviceLevel) {
        double zScore = getZScore(serviceLevel);
        double stdDev = repo.getDemandStdDev();
        return zScore * stdDev * Math.sqrt(leadTime);
    }

    private double getZScore(double level) {
        if (level >= 0.99) return 2.33;
        if (level >= 0.95) return 1.65;
        return 1.28;
    }
}
"""


class TestJavaParser:
    def setup_method(self):
        self.parser = JavaParser()

    def test_supported_extensions(self):
        assert ".java" in self.parser.supported_extensions()

    def test_language_name(self):
        assert self.parser.language_name() == "Java"

    def test_parse_extracts_package(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        packages = [e for e in result.entities if e.kind == EntityKind.PACKAGE]
        assert len(packages) == 1
        assert packages[0].qualified_name == "com.example.inventory"

    def test_parse_extracts_class(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        classes = [e for e in result.entities if e.kind == EntityKind.CLASS]
        assert len(classes) == 1
        assert classes[0].qualified_name == "com.example.inventory.SafetyStockCalculator"
        assert "public" in classes[0].modifiers

    def test_parse_extracts_methods(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        methods = [e for e in result.entities if e.kind == EntityKind.METHOD]
        names = {m.name for m in methods}
        assert "calculate" in names
        assert "getZScore" in names

    def test_parse_extracts_field(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        fields = [e for e in result.entities if e.kind == EntityKind.FIELD]
        assert len(fields) == 1
        assert fields[0].name == "repo"

    def test_parse_extracts_contains_relations(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        contains = [r for r in result.relations if r.kind == RelationKind.CONTAINS]
        # package→class, class→methods, class→field, class→constructor
        assert len(contains) >= 4

    def test_parse_extracts_depends_on(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        deps = [r for r in result.relations if r.kind == RelationKind.DEPENDS_ON]
        targets = {d.target for d in deps}
        assert "com.example.data.StockRepository" in targets

    def test_parse_extracts_calls(self):
        result = self.parser.parse_file(
            Path("src/com/example/inventory/SafetyStockCalculator.java"),
            SAMPLE_JAVA,
        )
        calls = [r for r in result.relations if r.kind == RelationKind.CALLS]
        # calculate calls getZScore and repo.getDemandStdDev
        call_names = {c.target.split(".")[-1] for c in calls}
        assert "getZScore" in call_names

    def test_no_errors_on_valid_java(self):
        result = self.parser.parse_file(
            Path("Test.java"),
            SAMPLE_JAVA,
        )
        assert result.errors == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_java_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Java parser**

```python
# backend/modeling/code_analysis/java_parser.py
"""Java parser using tree-sitter for structural analysis."""

from __future__ import annotations

import logging
from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node

from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, CodeParser, ParseResult,
    EntityKind, RelationKind,
)

logger = logging.getLogger(__name__)

JAVA_LANGUAGE = Language(tsjava.language())


class JavaParser:
    """tree-sitter based Java source code parser."""

    def __init__(self) -> None:
        self._parser = Parser(JAVA_LANGUAGE)

    def supported_extensions(self) -> list[str]:
        return [".java"]

    def language_name(self) -> str:
        return "Java"

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        tree = self._parser.parse(content.encode())
        entities: list[CodeEntity] = []
        relations: list[CodeRelation] = []
        errors: list[str] = []
        file_str = str(file_path)

        # Extract package
        package_name = self._extract_package(tree.root_node)

        if package_name:
            entities.append(CodeEntity(
                kind=EntityKind.PACKAGE,
                qualified_name=package_name,
                name=package_name.split(".")[-1],
                file_path=file_str,
                line_start=1,
                line_end=1,
            ))

        # Extract imports → DEPENDS_ON relations
        imports = self._extract_imports(tree.root_node)

        # Walk class/interface/enum declarations
        for node in self._find_type_declarations(tree.root_node):
            self._process_type_declaration(
                node, package_name, file_str,
                entities, relations, imports,
            )

        # Add import-based DEPENDS_ON for each class
        classes = [e for e in entities if e.kind in (EntityKind.CLASS, EntityKind.INTERFACE, EntityKind.ENUM)]
        for cls in classes:
            for imp in imports:
                relations.append(CodeRelation(
                    kind=RelationKind.DEPENDS_ON,
                    source=cls.qualified_name,
                    target=imp,
                    file_path=file_str,
                ))

        # Check for parse errors
        if tree.root_node.has_error:
            errors.append(f"Parse errors in {file_path}")

        return ParseResult(
            entities=entities,
            relations=relations,
            file_path=file_str,
            language="Java",
            errors=errors,
        )

    def _extract_package(self, root: Node) -> str:
        for child in root.children:
            if child.type == "package_declaration":
                for c in child.children:
                    if c.type == "scoped_identifier" or c.type == "identifier":
                        return c.text.decode()
        return ""

    def _extract_imports(self, root: Node) -> list[str]:
        imports = []
        for child in root.children:
            if child.type == "import_declaration":
                for c in child.children:
                    if c.type == "scoped_identifier":
                        imports.append(c.text.decode())
        return imports

    def _find_type_declarations(self, root: Node) -> list[Node]:
        results = []
        for child in root.children:
            if child.type in ("class_declaration", "interface_declaration", "enum_declaration"):
                results.append(child)
        return results

    def _process_type_declaration(
        self,
        node: Node,
        package: str,
        file_str: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
        imports: list[str],
    ) -> None:
        kind_map = {
            "class_declaration": EntityKind.CLASS,
            "interface_declaration": EntityKind.INTERFACE,
            "enum_declaration": EntityKind.ENUM,
        }
        kind = kind_map[node.type]
        name = self._get_name(node)
        qualified = f"{package}.{name}" if package else name
        modifiers = self._get_modifiers(node)

        entities.append(CodeEntity(
            kind=kind,
            qualified_name=qualified,
            name=name,
            file_path=file_str,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            modifiers=modifiers,
            parent=package or None,
        ))

        # CONTAINS: package → class
        if package:
            relations.append(CodeRelation(
                kind=RelationKind.CONTAINS,
                source=package,
                target=qualified,
                file_path=file_str,
            ))

        # Extract superclass/interfaces
        self._extract_inheritance(node, qualified, file_str, relations, imports)

        # Walk body for methods, fields, constructors
        body = self._find_child(node, "class_body") or self._find_child(node, "interface_body")
        if body:
            self._process_body(body, qualified, file_str, entities, relations)

    def _process_body(
        self,
        body: Node,
        parent_qualified: str,
        file_str: str,
        entities: list[CodeEntity],
        relations: list[CodeRelation],
    ) -> None:
        for child in body.children:
            if child.type == "method_declaration":
                self._process_method(child, parent_qualified, file_str, entities, relations)
            elif child.type == "constructor_declaration":
                self._process_constructor(child, parent_qualified, file_str, entities, relations)
            elif child.type == "field_declaration":
                self._process_field(child, parent_qualified, file_str, entities, relations)

    def _process_method(
        self, node: Node, parent: str, file_str: str,
        entities: list[CodeEntity], relations: list[CodeRelation],
    ) -> None:
        name = self._get_name(node)
        qualified = f"{parent}.{name}"
        modifiers = self._get_modifiers(node)

        entities.append(CodeEntity(
            kind=EntityKind.METHOD,
            qualified_name=qualified,
            name=name,
            file_path=file_str,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            modifiers=modifiers,
            parent=parent,
        ))

        relations.append(CodeRelation(
            kind=RelationKind.CONTAINS,
            source=parent,
            target=qualified,
            file_path=file_str,
        ))

        # Extract method calls within the body
        method_body = self._find_child(node, "block")
        if method_body:
            self._extract_calls(method_body, qualified, file_str, relations)

    def _process_constructor(
        self, node: Node, parent: str, file_str: str,
        entities: list[CodeEntity], relations: list[CodeRelation],
    ) -> None:
        name = self._get_name(node)
        qualified = f"{parent}.{name}"

        entities.append(CodeEntity(
            kind=EntityKind.CONSTRUCTOR,
            qualified_name=qualified,
            name=name,
            file_path=file_str,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            parent=parent,
        ))

        relations.append(CodeRelation(
            kind=RelationKind.CONTAINS,
            source=parent,
            target=qualified,
            file_path=file_str,
        ))

    def _process_field(
        self, node: Node, parent: str, file_str: str,
        entities: list[CodeEntity], relations: list[CodeRelation],
    ) -> None:
        # Field declarations can have multiple declarators
        for child in self._walk(node):
            if child.type == "variable_declarator":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = name_node.text.decode()
                    qualified = f"{parent}.{name}"
                    entities.append(CodeEntity(
                        kind=EntityKind.FIELD,
                        qualified_name=qualified,
                        name=name,
                        file_path=file_str,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        modifiers=self._get_modifiers(node),
                        parent=parent,
                    ))
                    relations.append(CodeRelation(
                        kind=RelationKind.CONTAINS,
                        source=parent,
                        target=qualified,
                        file_path=file_str,
                    ))

    def _extract_calls(
        self, node: Node, caller: str, file_str: str,
        relations: list[CodeRelation],
    ) -> None:
        for child in self._walk(node):
            if child.type == "method_invocation":
                call_name = self._get_method_invocation_name(child)
                if call_name:
                    relations.append(CodeRelation(
                        kind=RelationKind.CALLS,
                        source=caller,
                        target=call_name,
                        file_path=file_str,
                        line=child.start_point[0] + 1,
                    ))

    def _extract_inheritance(
        self, node: Node, qualified: str, file_str: str,
        relations: list[CodeRelation], imports: list[str],
    ) -> None:
        for child in node.children:
            if child.type == "superclass":
                type_node = self._find_child(child, "type_identifier")
                if type_node:
                    target = self._resolve_type(type_node.text.decode(), imports)
                    relations.append(CodeRelation(
                        kind=RelationKind.EXTENDS,
                        source=qualified,
                        target=target,
                        file_path=file_str,
                    ))
            elif child.type == "super_interfaces":
                for t in self._walk(child):
                    if t.type == "type_identifier":
                        target = self._resolve_type(t.text.decode(), imports)
                        relations.append(CodeRelation(
                            kind=RelationKind.IMPLEMENTS,
                            source=qualified,
                            target=target,
                            file_path=file_str,
                        ))

    def _resolve_type(self, simple_name: str, imports: list[str]) -> str:
        """Resolve a simple type name to fully qualified using imports."""
        for imp in imports:
            if imp.endswith(f".{simple_name}"):
                return imp
        return simple_name

    def _get_name(self, node: Node) -> str:
        name_node = self._find_child(node, "identifier")
        return name_node.text.decode() if name_node else "<unknown>"

    def _get_modifiers(self, node: Node) -> list[str]:
        mods = []
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type in ("public", "private", "protected", "static",
                                    "final", "abstract", "synchronized"):
                        mods.append(mod.type)
                    elif mod.type == "modifier":
                        mods.append(mod.text.decode())
        return mods

    def _get_method_invocation_name(self, node: Node) -> str:
        """Extract the method name from a method_invocation node."""
        parts = []
        for child in node.children:
            if child.type == "identifier":
                parts.append(child.text.decode())
            elif child.type == "field_access":
                parts.append(child.text.decode())
            elif child.type == "method_invocation":
                # Chained call — only care about outermost
                break
        return ".".join(parts) if parts else ""

    def _find_child(self, node: Node, child_type: str) -> Node | None:
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _walk(self, node: Node):
        """Iterate all descendants depth-first."""
        cursor = node.walk()
        visited = False
        while True:
            if not visited:
                yield cursor.node
                if cursor.goto_first_child():
                    continue
            if cursor.goto_next_sibling():
                visited = False
                continue
            if not cursor.goto_parent():
                break
            visited = True
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_java_parser.py -v
```

Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/code_analysis/java_parser.py tests/test_java_parser.py
git commit -m "feat(modeling): implement Java parser with tree-sitter"
```

---

## Task 4: Code Graph → Neo4j Storage

**Files:**
- Create: `backend/modeling/code_analysis/graph_writer.py`
- Test: `tests/test_code_graph.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_code_graph.py
import pytest
from unittest.mock import MagicMock, call

from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, EntityKind, RelationKind, ParseResult,
)


class TestCodeGraphWriter:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.writer = CodeGraphWriter(self.neo4j)

    def test_write_entities_generates_merge_cypher(self):
        entities = [
            CodeEntity(
                kind=EntityKind.CLASS,
                qualified_name="com.example.Foo",
                name="Foo",
                file_path="Foo.java",
                line_start=1,
                line_end=10,
                modifiers=["public"],
            ),
        ]
        self.writer.write_entities(entities, repo_id="test-repo")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "MERGE" in cypher
        assert "CodeEntity" in cypher

    def test_write_relations_generates_merge_cypher(self):
        relations = [
            CodeRelation(
                kind=RelationKind.CALLS,
                source="com.example.Foo.bar",
                target="com.example.Baz.qux",
            ),
        ]
        self.writer.write_relations(relations, repo_id="test-repo")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "CALLS" in cypher

    def test_clear_repo_deletes_all_nodes(self):
        self.writer.clear_repo("test-repo")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "DELETE" in cypher
        assert "test-repo" in str(self.neo4j.write.call_args)

    def test_write_parse_result(self):
        result = ParseResult(
            entities=[
                CodeEntity(
                    kind=EntityKind.CLASS,
                    qualified_name="com.example.Foo",
                    name="Foo",
                    file_path="Foo.java",
                    line_start=1, line_end=10,
                ),
            ],
            relations=[
                CodeRelation(
                    kind=RelationKind.CONTAINS,
                    source="com.example",
                    target="com.example.Foo",
                ),
            ],
            file_path="Foo.java",
            language="Java",
        )
        self.writer.write_parse_result(result, repo_id="test-repo")
        assert self.neo4j.write.call_count >= 2  # entities + relations
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_code_graph.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement graph writer**

```python
# backend/modeling/code_analysis/graph_writer.py
"""Writes parsed code entities and relations to Neo4j."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.code_analysis.parser_protocol import (
    CodeEntity, CodeRelation, ParseResult, RelationKind,
)

logger = logging.getLogger(__name__)


class CodeGraphWriter:
    """Writes code analysis results to Neo4j graph database."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def write_parse_result(self, result: ParseResult, repo_id: str) -> None:
        self.write_entities(result.entities, repo_id)
        self.write_relations(result.relations, repo_id)

    def write_entities(self, entities: list[CodeEntity], repo_id: str) -> None:
        for entity in entities:
            cypher = """
            MERGE (n:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
            SET n.kind = $kind,
                n.name = $name,
                n.file_path = $file_path,
                n.line_start = $line_start,
                n.line_end = $line_end,
                n.modifiers = $modifiers,
                n.parent = $parent
            """
            self._neo4j.write(cypher, {
                "qn": entity.qualified_name,
                "repo_id": repo_id,
                "kind": entity.kind.value,
                "name": entity.name,
                "file_path": entity.file_path,
                "line_start": entity.line_start,
                "line_end": entity.line_end,
                "modifiers": entity.modifiers,
                "parent": entity.parent,
            })

    def write_relations(self, relations: list[CodeRelation], repo_id: str) -> None:
        for rel in relations:
            rel_type = rel.kind.value.upper()
            cypher = f"""
            MATCH (a:CodeEntity {{qualified_name: $source, repo_id: $repo_id}})
            MATCH (b:CodeEntity {{qualified_name: $target, repo_id: $repo_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            SET r.file_path = $file_path,
                r.line = $line
            """
            self._neo4j.write(cypher, {
                "source": rel.source,
                "target": rel.target,
                "repo_id": repo_id,
                "file_path": rel.file_path,
                "line": rel.line,
            })

    def clear_repo(self, repo_id: str) -> None:
        cypher = """
        MATCH (n:CodeEntity {repo_id: $repo_id})
        DETACH DELETE n
        """
        self._neo4j.write(cypher, {"repo_id": repo_id})
        logger.info(f"Cleared code graph for repo {repo_id}")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_code_graph.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/code_analysis/graph_writer.py tests/test_code_graph.py
git commit -m "feat(modeling): implement code graph writer for Neo4j"
```

---

## Task 5: Git Connector

**Files:**
- Create: `backend/modeling/infrastructure/git_connector.py`
- Test: `tests/test_git_connector.py` (unit tests with mocked subprocess)

- [ ] **Step 1: Write failing test**

```python
# tests/test_git_connector.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.modeling.infrastructure.git_connector import GitConnector


class TestGitConnector:
    def setup_method(self):
        self.connector = GitConnector(repos_dir=Path("/tmp/ontong-repos"))

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    def test_clone_repo(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        path = self.connector.clone("https://github.com/test/repo.git", "test-repo")
        assert path == Path("/tmp/ontong-repos/test-repo")
        mock_run.assert_called_once()
        assert "clone" in mock_run.call_args[0][0]

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_pull_existing_repo(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Already up to date.")
        result = self.connector.pull("test-repo")
        assert "Already up to date" in result

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_list_java_files(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="src/Main.java\nsrc/Util.java\n",
        )
        files = self.connector.list_files("test-repo", extension=".java")
        assert len(files) == 2
        assert "src/Main.java" in files

    @patch("backend.modeling.infrastructure.git_connector.subprocess.run")
    @patch("pathlib.Path.exists", return_value=True)
    def test_diff_returns_changed_files(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M\tsrc/Main.java\nA\tsrc/New.java\nD\tsrc/Old.java\n",
        )
        diff = self.connector.diff("test-repo", "abc123", "def456")
        assert diff.modified == ["src/Main.java"]
        assert diff.added == ["src/New.java"]
        assert diff.deleted == ["src/Old.java"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_git_connector.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement git connector**

```python
# backend/modeling/infrastructure/git_connector.py
"""Git connector for cloning and monitoring customer repositories."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitDiff:
    """Result of comparing two commits."""
    modified: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


class GitConnector:
    """Manages customer code repositories (clone, pull, diff)."""

    def __init__(self, repos_dir: Path) -> None:
        self.repos_dir = repos_dir
        self.repos_dir.mkdir(parents=True, exist_ok=True)

    def clone(self, url: str, repo_id: str) -> Path:
        dest = self.repos_dir / repo_id
        if dest.exists():
            logger.info(f"Repo {repo_id} already exists, pulling instead")
            self.pull(repo_id)
            return dest

        subprocess.run(
            ["git", "clone", "--depth=1", url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Cloned {url} → {dest}")
        return dest

    def pull(self, repo_id: str) -> str:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found at {repo_path}")

        result = subprocess.run(
            ["git", "pull"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Pulled {repo_id}: {result.stdout.strip()}")
        return result.stdout

    def list_files(self, repo_id: str, extension: str = "") -> list[str]:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found")

        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        if extension:
            files = [f for f in files if f.endswith(extension)]
        return files

    def diff(self, repo_id: str, from_commit: str, to_commit: str) -> GitDiff:
        repo_path = self.repos_dir / repo_id
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo {repo_id} not found")

        result = subprocess.run(
            ["git", "diff", "--name-status", from_commit, to_commit],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )

        diff = GitDiff()
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            status, path = parts[0], parts[1]
            if status == "M":
                diff.modified.append(path)
            elif status == "A":
                diff.added.append(path)
            elif status == "D":
                diff.deleted.append(path)

        return diff

    def get_head_commit(self, repo_id: str) -> str:
        repo_path = self.repos_dir / repo_id
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def read_file(self, repo_id: str, file_path: str) -> str:
        full_path = self.repos_dir / repo_id / file_path
        return full_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_git_connector.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/infrastructure/git_connector.py tests/test_git_connector.py
git commit -m "feat(modeling): implement Git connector for customer repos"
```

---

## Task 6: SCOR+ISA-95 Domain Ontology

**Files:**
- Create: `backend/modeling/ontology/domain_models.py`
- Create: `backend/modeling/ontology/scor_template.py`
- Create: `backend/modeling/ontology/ontology_store.py`
- Test: `tests/test_scor_template.py`
- Test: `tests/test_ontology_store.py`

- [ ] **Step 1: Define domain Pydantic models**

```python
# backend/modeling/ontology/domain_models.py
"""Pydantic models for SCOR+ISA-95 domain ontology."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class DomainNodeKind(str, Enum):
    PROCESS = "process"
    ENTITY = "entity"
    ROLE = "role"


class DomainRelationKind(str, Enum):
    PART_OF = "part_of"
    USES = "uses"
    PRODUCES = "produces"
    RESPONSIBLE_FOR = "responsible_for"


class DomainNode(BaseModel):
    """A single node in the domain ontology."""
    kind: DomainNodeKind
    id: str                      # e.g., "SCOR/Plan/DemandPlanning"
    name: str                    # e.g., "Demand Planning"
    description: str = ""
    parent_id: str | None = None  # for PART_OF hierarchy
    metadata: dict = {}


class DomainRelation(BaseModel):
    """A relationship between domain nodes."""
    kind: DomainRelationKind
    source_id: str
    target_id: str


class DomainOntology(BaseModel):
    """Complete domain ontology with nodes and relations."""
    nodes: list[DomainNode]
    relations: list[DomainRelation]
```

- [ ] **Step 2: Write failing test for SCOR template**

```python
# tests/test_scor_template.py
import pytest

from backend.modeling.ontology.scor_template import load_scor_template
from backend.modeling.ontology.domain_models import DomainNodeKind


class TestSCORTemplate:
    def test_template_loads(self):
        ontology = load_scor_template()
        assert len(ontology.nodes) > 0

    def test_has_level_1_processes(self):
        ontology = load_scor_template()
        level1 = [n for n in ontology.nodes if n.id.count("/") == 1 and n.kind == DomainNodeKind.PROCESS]
        names = {n.name for n in level1}
        assert "Plan" in names
        assert "Source" in names
        assert "Make" in names
        assert "Deliver" in names
        assert "Return" in names

    def test_has_level_2_processes(self):
        ontology = load_scor_template()
        plan_children = [n for n in ontology.nodes if n.parent_id == "SCOR/Plan"]
        assert len(plan_children) >= 3  # DemandPlanning, SupplyPlanning, InventoryPlanning, ...

    def test_has_isa95_make_breakdown(self):
        ontology = load_scor_template()
        make_descendants = [n for n in ontology.nodes if n.id.startswith("SCOR/Make/ISA95")]
        assert len(make_descendants) >= 3  # Production levels

    def test_has_part_of_relations(self):
        ontology = load_scor_template()
        part_of = [r for r in ontology.relations if r.kind.value == "part_of"]
        assert len(part_of) > 0

    def test_all_nodes_have_unique_ids(self):
        ontology = load_scor_template()
        ids = [n.id for n in ontology.nodes]
        assert len(ids) == len(set(ids))
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_scor_template.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement SCOR template**

```python
# backend/modeling/ontology/scor_template.py
"""Pre-built SCOR Level 1-3 + ISA-95 Make breakdown template."""

from backend.modeling.ontology.domain_models import (
    DomainNode, DomainRelation, DomainOntology,
    DomainNodeKind, DomainRelationKind,
)


def _p(id: str, name: str, desc: str = "", parent: str | None = None) -> DomainNode:
    return DomainNode(kind=DomainNodeKind.PROCESS, id=id, name=name, description=desc, parent_id=parent)


def _e(id: str, name: str, desc: str = "") -> DomainNode:
    return DomainNode(kind=DomainNodeKind.ENTITY, id=id, name=name, description=desc)


def _r(id: str, name: str, desc: str = "") -> DomainNode:
    return DomainNode(kind=DomainNodeKind.ROLE, id=id, name=name, description=desc)


def load_scor_template() -> DomainOntology:
    """Load the standard SCOR+ISA-95 template."""

    nodes: list[DomainNode] = []
    relations: list[DomainRelation] = []

    # ── SCOR Level 1 ──
    nodes.extend([
        _p("SCOR/Plan", "Plan", "Demand/supply planning and balancing"),
        _p("SCOR/Source", "Source", "Procurement and supplier management"),
        _p("SCOR/Make", "Make", "Production and manufacturing"),
        _p("SCOR/Deliver", "Deliver", "Order fulfillment and logistics"),
        _p("SCOR/Return", "Return", "Returns and reverse logistics"),
    ])

    # ── SCOR Level 2: Plan ──
    plan_l2 = [
        _p("SCOR/Plan/DemandPlanning", "Demand Planning", "Forecast and demand analysis", "SCOR/Plan"),
        _p("SCOR/Plan/SupplyPlanning", "Supply Planning", "Supply capacity and allocation", "SCOR/Plan"),
        _p("SCOR/Plan/InventoryPlanning", "Inventory Planning", "Safety stock, reorder points", "SCOR/Plan"),
        _p("SCOR/Plan/S&OP", "S&OP", "Sales and operations planning", "SCOR/Plan"),
    ]
    nodes.extend(plan_l2)

    # ── SCOR Level 2: Source ──
    source_l2 = [
        _p("SCOR/Source/SupplierSelection", "Supplier Selection", "Supplier evaluation and choice", "SCOR/Source"),
        _p("SCOR/Source/Procurement", "Procurement", "Purchase orders and contracts", "SCOR/Source"),
        _p("SCOR/Source/Receiving", "Receiving", "Goods receipt and inspection", "SCOR/Source"),
    ]
    nodes.extend(source_l2)

    # ── SCOR Level 2: Make ──
    make_l2 = [
        _p("SCOR/Make/ProductionScheduling", "Production Scheduling", "Sequence and timing", "SCOR/Make"),
        _p("SCOR/Make/Manufacturing", "Manufacturing", "Actual production execution", "SCOR/Make"),
        _p("SCOR/Make/QualityControl", "Quality Control", "Inspection and testing", "SCOR/Make"),
    ]
    nodes.extend(make_l2)

    # ── ISA-95 under Make ──
    isa95 = [
        _p("SCOR/Make/ISA95/Level4", "Business Planning", "ERP-level planning (ISA-95 L4)", "SCOR/Make"),
        _p("SCOR/Make/ISA95/Level3", "Manufacturing Operations", "MES-level execution (ISA-95 L3)", "SCOR/Make"),
        _p("SCOR/Make/ISA95/Level2", "Supervisory Control", "SCADA and batch control (ISA-95 L2)", "SCOR/Make"),
        _p("SCOR/Make/ISA95/Level1", "Direct Control", "PLC and sensor level (ISA-95 L1)", "SCOR/Make"),
    ]
    nodes.extend(isa95)

    # ── SCOR Level 2: Deliver ──
    deliver_l2 = [
        _p("SCOR/Deliver/OrderManagement", "Order Management", "Order entry and tracking", "SCOR/Deliver"),
        _p("SCOR/Deliver/Warehousing", "Warehousing", "Storage and picking", "SCOR/Deliver"),
        _p("SCOR/Deliver/Transportation", "Transportation", "Shipping and routing", "SCOR/Deliver"),
    ]
    nodes.extend(deliver_l2)

    # ── SCOR Level 2: Return ──
    return_l2 = [
        _p("SCOR/Return/ReturnProcessing", "Return Processing", "RMA and disposition", "SCOR/Return"),
        _p("SCOR/Return/Repair", "Repair", "Refurbishment and rework", "SCOR/Return"),
    ]
    nodes.extend(return_l2)

    # ── Common Domain Entities ──
    entities = [
        _e("Entity/SafetyStock", "Safety Stock"),
        _e("Entity/BOM", "Bill of Materials"),
        _e("Entity/PurchaseOrder", "Purchase Order"),
        _e("Entity/ProductionOrder", "Production Order"),
        _e("Entity/SalesOrder", "Sales Order"),
        _e("Entity/Inventory", "Inventory"),
        _e("Entity/LeadTime", "Lead Time"),
    ]
    nodes.extend(entities)

    # ── Common Roles ──
    roles = [
        _r("Role/Planner", "Planner"),
        _r("Role/Buyer", "Buyer"),
        _r("Role/ProductionManager", "Production Manager"),
        _r("Role/WarehouseManager", "Warehouse Manager"),
        _r("Role/QualityEngineer", "Quality Engineer"),
    ]
    nodes.extend(roles)

    # ── PART_OF relations (hierarchy) ──
    for node in nodes:
        if node.parent_id:
            relations.append(DomainRelation(
                kind=DomainRelationKind.PART_OF,
                source_id=node.id,
                target_id=node.parent_id,
            ))

    # ── USES/PRODUCES sample relations ──
    relations.extend([
        DomainRelation(kind=DomainRelationKind.USES, source_id="SCOR/Plan/InventoryPlanning", target_id="Entity/SafetyStock"),
        DomainRelation(kind=DomainRelationKind.USES, source_id="SCOR/Plan/DemandPlanning", target_id="Entity/LeadTime"),
        DomainRelation(kind=DomainRelationKind.USES, source_id="SCOR/Make/Manufacturing", target_id="Entity/BOM"),
        DomainRelation(kind=DomainRelationKind.PRODUCES, source_id="SCOR/Source/Procurement", target_id="Entity/PurchaseOrder"),
        DomainRelation(kind=DomainRelationKind.PRODUCES, source_id="SCOR/Deliver/OrderManagement", target_id="Entity/SalesOrder"),
        DomainRelation(kind=DomainRelationKind.RESPONSIBLE_FOR, source_id="Role/Planner", target_id="SCOR/Plan"),
        DomainRelation(kind=DomainRelationKind.RESPONSIBLE_FOR, source_id="Role/Buyer", target_id="SCOR/Source"),
        DomainRelation(kind=DomainRelationKind.RESPONSIBLE_FOR, source_id="Role/ProductionManager", target_id="SCOR/Make"),
    ])

    return DomainOntology(nodes=nodes, relations=relations)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_scor_template.py -v
```

Expected: 6 passed

- [ ] **Step 6: Write failing test for ontology store**

```python
# tests/test_ontology_store.py
import pytest
from unittest.mock import MagicMock

from backend.modeling.ontology.ontology_store import OntologyStore
from backend.modeling.ontology.domain_models import DomainNode, DomainNodeKind


class TestOntologyStore:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.store = OntologyStore(self.neo4j)

    def test_load_template_writes_nodes(self):
        self.store.load_template()
        assert self.neo4j.write.call_count > 0

    def test_add_node(self):
        node = DomainNode(
            kind=DomainNodeKind.PROCESS,
            id="SCOR/Plan/Custom",
            name="Custom Process",
            parent_id="SCOR/Plan",
        )
        self.store.add_node(node)
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "MERGE" in cypher
        assert "DomainNode" in cypher

    def test_remove_node(self):
        self.store.remove_node("SCOR/Plan/Custom")
        self.neo4j.write.assert_called()
        cypher = self.neo4j.write.call_args[0][0]
        assert "DELETE" in cypher

    def test_get_tree_returns_list(self):
        self.neo4j.query.return_value = [
            {"id": "SCOR/Plan", "name": "Plan", "kind": "process", "parent_id": None},
        ]
        result = self.store.get_tree()
        assert len(result) == 1
        assert result[0]["id"] == "SCOR/Plan"

    def test_get_children(self):
        self.neo4j.query.return_value = [
            {"id": "SCOR/Plan/DemandPlanning", "name": "Demand Planning"},
        ]
        result = self.store.get_children("SCOR/Plan")
        assert len(result) == 1
```

- [ ] **Step 7: Implement ontology store**

```python
# backend/modeling/ontology/ontology_store.py
"""CRUD operations for domain ontology in Neo4j."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.ontology.domain_models import (
    DomainNode, DomainRelation, DomainOntology, DomainRelationKind,
)
from backend.modeling.ontology.scor_template import load_scor_template

logger = logging.getLogger(__name__)


class OntologyStore:
    """Manages domain ontology nodes and relations in Neo4j."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def load_template(self) -> int:
        """Load SCOR+ISA-95 template into Neo4j. Returns node count."""
        ontology = load_scor_template()
        for node in ontology.nodes:
            self.add_node(node)
        for rel in ontology.relations:
            self._write_relation(rel)
        logger.info(f"Loaded SCOR template: {len(ontology.nodes)} nodes, {len(ontology.relations)} relations")
        return len(ontology.nodes)

    def add_node(self, node: DomainNode) -> None:
        cypher = """
        MERGE (n:DomainNode {id: $id})
        SET n.kind = $kind,
            n.name = $name,
            n.description = $description,
            n.parent_id = $parent_id,
            n.metadata = $metadata
        """
        self._neo4j.write(cypher, {
            "id": node.id,
            "kind": node.kind.value,
            "name": node.name,
            "description": node.description,
            "parent_id": node.parent_id,
            "metadata": str(node.metadata),
        })

    def update_node(self, node_id: str, name: str | None = None, description: str | None = None) -> None:
        sets = []
        params: dict = {"id": node_id}
        if name is not None:
            sets.append("n.name = $name")
            params["name"] = name
        if description is not None:
            sets.append("n.description = $description")
            params["description"] = description
        if not sets:
            return
        cypher = f"MATCH (n:DomainNode {{id: $id}}) SET {', '.join(sets)}"
        self._neo4j.write(cypher, params)

    def remove_node(self, node_id: str) -> None:
        cypher = "MATCH (n:DomainNode {id: $id}) DETACH DELETE n"
        self._neo4j.write(cypher, {"id": node_id})

    def get_tree(self) -> list[dict]:
        cypher = """
        MATCH (n:DomainNode)
        RETURN n.id as id, n.name as name, n.kind as kind, n.parent_id as parent_id,
               n.description as description
        ORDER BY n.id
        """
        return self._neo4j.query(cypher)

    def get_children(self, parent_id: str) -> list[dict]:
        cypher = """
        MATCH (n:DomainNode {parent_id: $parent_id})
        RETURN n.id as id, n.name as name, n.kind as kind,
               n.description as description
        ORDER BY n.id
        """
        return self._neo4j.query(cypher, {"parent_id": parent_id})

    def get_node(self, node_id: str) -> dict | None:
        result = self._neo4j.query(
            "MATCH (n:DomainNode {id: $id}) RETURN n.id as id, n.name as name, n.kind as kind, n.parent_id as parent_id, n.description as description",
            {"id": node_id},
        )
        return result[0] if result else None

    def _write_relation(self, rel: DomainRelation) -> None:
        rel_type = rel.kind.value.upper()
        cypher = f"""
        MATCH (a:DomainNode {{id: $source}})
        MATCH (b:DomainNode {{id: $target}})
        MERGE (a)-[r:{rel_type}]->(b)
        """
        self._neo4j.write(cypher, {"source": rel.source_id, "target": rel.target_id})
```

- [ ] **Step 8: Run tests**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_scor_template.py tests/test_ontology_store.py -v
```

Expected: 11 passed

- [ ] **Step 9: Commit**

```bash
git add backend/modeling/ontology/ tests/test_scor_template.py tests/test_ontology_store.py
git commit -m "feat(modeling): implement SCOR+ISA-95 ontology template + store"
```

---

## Task 7: Mapping Engine

**Files:**
- Create: `backend/modeling/mapping/mapping_models.py`
- Create: `backend/modeling/mapping/yaml_store.py`
- Create: `backend/modeling/mapping/mapping_service.py`
- Create: `backend/modeling/mapping/neo4j_cache.py`
- Test: `tests/test_mapping_service.py`

- [ ] **Step 1: Define mapping models**

```python
# backend/modeling/mapping/mapping_models.py
"""Pydantic models for code↔domain mappings."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MappingStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    CONFIRMED = "confirmed"


class MappingGranularity(str, Enum):
    PACKAGE = "package"
    CLASS = "class"
    METHOD = "method"


class Mapping(BaseModel):
    """A single code↔domain mapping entry."""
    code: str                           # qualified name of code entity
    domain: str                         # domain node id
    granularity: MappingGranularity = MappingGranularity.CLASS
    owner: str = ""                     # who created this mapping
    status: MappingStatus = MappingStatus.DRAFT
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    notes: str = ""


class MappingFile(BaseModel):
    """Complete mapping file (maps to .ontology/mapping.yaml)."""
    version: str = "1"
    repo_id: str
    mappings: list[Mapping]


class MappingGap(BaseModel):
    """A code entity that has no domain mapping."""
    qualified_name: str
    kind: str
    file_path: str
    suggested_domain: str | None = None  # LLM can suggest (user confirms)
```

- [ ] **Step 2: Write failing test for mapping service**

```python
# tests/test_mapping_service.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from backend.modeling.mapping.mapping_models import Mapping, MappingStatus, MappingFile
from backend.modeling.mapping.mapping_service import MappingService


class TestMappingService:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.service = MappingService(self.neo4j)

    def test_load_from_yaml(self, tmp_path):
        yaml_file = tmp_path / ".ontology" / "mapping.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(
            'version: "1"\n'
            'repo_id: test-repo\n'
            'mappings:\n'
            '  - code: "com.example.Foo"\n'
            '    domain: "SCOR/Plan"\n'
            '    status: confirmed\n'
            '    owner: kim\n'
        )
        mapping_file = self.service.load_yaml(yaml_file)
        assert len(mapping_file.mappings) == 1
        assert mapping_file.mappings[0].code == "com.example.Foo"
        assert mapping_file.mappings[0].status == MappingStatus.CONFIRMED

    def test_save_to_yaml(self, tmp_path):
        yaml_file = tmp_path / ".ontology" / "mapping.yaml"
        yaml_file.parent.mkdir(parents=True)
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Bar", domain="SCOR/Source", owner="lee"),
        ])
        self.service.save_yaml(yaml_file, mf)
        assert yaml_file.exists()
        content = yaml_file.read_text()
        assert "com.example.Bar" in content
        assert "SCOR/Source" in content

    def test_add_mapping(self):
        mf = MappingFile(repo_id="test-repo", mappings=[])
        m = Mapping(code="com.example.Foo", domain="SCOR/Plan")
        result = self.service.add_mapping(mf, m)
        assert len(result.mappings) == 1

    def test_add_duplicate_mapping_raises(self):
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan"),
        ])
        m = Mapping(code="com.example.Foo", domain="SCOR/Source")
        with pytest.raises(ValueError, match="already mapped"):
            self.service.add_mapping(mf, m)

    def test_remove_mapping(self):
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan"),
        ])
        result = self.service.remove_mapping(mf, "com.example.Foo")
        assert len(result.mappings) == 0

    def test_find_gaps(self):
        # Mock: neo4j returns code entities
        self.neo4j.query.return_value = [
            {"qualified_name": "com.example.Foo", "kind": "class", "file_path": "Foo.java"},
            {"qualified_name": "com.example.Bar", "kind": "class", "file_path": "Bar.java"},
        ]
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan"),
        ])
        gaps = self.service.find_gaps(mf, "test-repo")
        assert len(gaps) == 1
        assert gaps[0].qualified_name == "com.example.Bar"

    def test_update_status(self):
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan", status=MappingStatus.DRAFT),
        ])
        result = self.service.update_status(mf, "com.example.Foo", MappingStatus.REVIEW)
        assert result.mappings[0].status == MappingStatus.REVIEW

    def test_resolve_mapping_with_inheritance(self):
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.inventory", domain="SCOR/Plan/InventoryPlanning",
                    granularity="package"),
        ])
        # Should resolve a class under that package
        domain = self.service.resolve(mf, "com.example.inventory.SafetyStockCalc")
        assert domain == "SCOR/Plan/InventoryPlanning"

    def test_resolve_with_override(self):
        mf = MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.inventory", domain="SCOR/Plan/InventoryPlanning",
                    granularity="package"),
            Mapping(code="com.example.inventory.DemandForecaster",
                    domain="SCOR/Plan/DemandPlanning", granularity="class"),
        ])
        domain = self.service.resolve(mf, "com.example.inventory.DemandForecaster")
        assert domain == "SCOR/Plan/DemandPlanning"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_mapping_service.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement mapping service**

```python
# backend/modeling/mapping/yaml_store.py
"""YAML read/write for mapping files."""

from __future__ import annotations

from pathlib import Path

import yaml

from backend.modeling.mapping.mapping_models import MappingFile


def load_mapping_yaml(path: Path) -> MappingFile:
    with open(path) as f:
        data = yaml.safe_load(f)
    return MappingFile(**data)


def save_mapping_yaml(path: Path, mf: MappingFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": mf.version,
        "repo_id": mf.repo_id,
        "mappings": [m.model_dump(exclude_none=True, mode="json") for m in mf.mappings],
    }
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
```

```python
# backend/modeling/mapping/mapping_service.py
"""Core mapping operations: CRUD, gap detection, inheritance resolution."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import (
    Mapping, MappingFile, MappingGap, MappingStatus,
)
from backend.modeling.mapping.yaml_store import load_mapping_yaml, save_mapping_yaml

logger = logging.getLogger(__name__)


class MappingService:
    """Manages code↔domain mappings with YAML persistence and Neo4j cache."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def load_yaml(self, path: Path) -> MappingFile:
        return load_mapping_yaml(path)

    def save_yaml(self, path: Path, mf: MappingFile) -> None:
        save_mapping_yaml(path, mf)

    def add_mapping(self, mf: MappingFile, mapping: Mapping) -> MappingFile:
        existing = {m.code for m in mf.mappings}
        if mapping.code in existing:
            raise ValueError(f"{mapping.code} is already mapped")
        mf.mappings.append(mapping)
        return mf

    def remove_mapping(self, mf: MappingFile, code: str) -> MappingFile:
        mf.mappings = [m for m in mf.mappings if m.code != code]
        return mf

    def update_status(self, mf: MappingFile, code: str, status: MappingStatus,
                      confirmed_by: str | None = None) -> MappingFile:
        for m in mf.mappings:
            if m.code == code:
                m.status = status
                if status == MappingStatus.CONFIRMED and confirmed_by:
                    m.confirmed_by = confirmed_by
                    from datetime import datetime
                    m.confirmed_at = datetime.now()
                return mf
        raise ValueError(f"Mapping not found: {code}")

    def find_gaps(self, mf: MappingFile, repo_id: str) -> list[MappingGap]:
        """Find code entities that have no mapping (direct or inherited)."""
        code_entities = self._neo4j.query(
            "MATCH (n:CodeEntity {repo_id: $repo_id}) WHERE n.kind IN ['class', 'interface'] "
            "RETURN n.qualified_name as qualified_name, n.kind as kind, n.file_path as file_path",
            {"repo_id": repo_id},
        )

        gaps = []
        for entity in code_entities:
            qn = entity["qualified_name"]
            if self.resolve(mf, qn) is None:
                gaps.append(MappingGap(
                    qualified_name=qn,
                    kind=entity["kind"],
                    file_path=entity["file_path"],
                ))

        return gaps

    def resolve(self, mf: MappingFile, qualified_name: str) -> str | None:
        """Resolve the domain mapping for a code entity, using inheritance."""
        # Direct match first
        for m in mf.mappings:
            if m.code == qualified_name:
                return m.domain

        # Walk up the package hierarchy for inherited mappings
        parts = qualified_name.rsplit(".", 1)
        while len(parts) == 2:
            parent = parts[0]
            for m in mf.mappings:
                if m.code == parent:
                    return m.domain
            parts = parent.rsplit(".", 1)

        return None

    def sync_to_neo4j(self, mf: MappingFile) -> None:
        """Write all mappings to Neo4j as MAPPED_TO relations."""
        # Clear existing mappings for this repo
        self._neo4j.write(
            "MATCH (:CodeEntity {repo_id: $repo_id})-[r:MAPPED_TO]->(:DomainNode) DELETE r",
            {"repo_id": mf.repo_id},
        )

        for m in mf.mappings:
            self._neo4j.write(
                """
                MATCH (c:CodeEntity {qualified_name: $code, repo_id: $repo_id})
                MATCH (d:DomainNode {id: $domain})
                MERGE (c)-[r:MAPPED_TO]->(d)
                SET r.status = $status, r.owner = $owner, r.granularity = $granularity
                """,
                {
                    "code": m.code,
                    "repo_id": mf.repo_id,
                    "domain": m.domain,
                    "status": m.status.value,
                    "owner": m.owner,
                    "granularity": m.granularity.value,
                },
            )
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_mapping_service.py -v
```

Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/mapping/ tests/test_mapping_service.py
git commit -m "feat(modeling): implement mapping engine with YAML persistence + inheritance"
```

---

## Task 8: Query Engine (Impact Analysis)

**Files:**
- Create: `backend/modeling/query/query_models.py`
- Create: `backend/modeling/query/query_engine.py`
- Test: `tests/test_query_engine.py`

- [ ] **Step 1: Define query models**

```python
# backend/modeling/query/query_models.py
"""Pydantic models for impact analysis queries and results."""

from __future__ import annotations

from pydantic import BaseModel


class ImpactQuery(BaseModel):
    """User's impact analysis request."""
    term: str                      # natural language term or code entity name
    repo_id: str
    depth: int = 3                 # BFS traversal depth
    confirmed_only: bool = True    # only use confirmed mappings


class AffectedProcess(BaseModel):
    """A domain process affected by the queried change."""
    domain_id: str
    domain_name: str
    path: list[str]                # code entities in the impact path
    distance: int                  # BFS hops from source


class ImpactResult(BaseModel):
    """Deterministic result of an impact analysis query."""
    source_term: str
    source_code_entity: str | None  # resolved code entity
    source_domain: str | None       # resolved domain mapping
    affected_processes: list[AffectedProcess]
    unmapped_entities: list[str]    # code entities found but not mapped
    resolved: bool                  # whether the term was found in mappings
    message: str                    # human-readable summary
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_query_engine.py
import pytest
from unittest.mock import MagicMock

from backend.modeling.query.query_engine import QueryEngine
from backend.modeling.query.query_models import ImpactQuery
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


class TestQueryEngine:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.engine = QueryEngine(self.neo4j)

    def _make_mapping_file(self) -> MappingFile:
        return MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.inventory.SafetyStockCalc",
                    domain="SCOR/Plan/InventoryPlanning",
                    status=MappingStatus.CONFIRMED, owner="kim"),
            Mapping(code="com.example.order.OrderService",
                    domain="SCOR/Deliver/OrderManagement",
                    status=MappingStatus.CONFIRMED, owner="lee"),
            Mapping(code="com.example.replenish.ReplenishJob",
                    domain="SCOR/Source/Procurement",
                    status=MappingStatus.CONFIRMED, owner="park"),
        ])

    def test_resolve_term_by_exact_match(self):
        mf = self._make_mapping_file()
        result = self.engine._resolve_term("SafetyStockCalc", mf)
        assert result == "com.example.inventory.SafetyStockCalc"

    def test_resolve_term_not_found(self):
        mf = self._make_mapping_file()
        result = self.engine._resolve_term("NonExistent", mf)
        assert result is None

    def test_resolve_term_by_domain_name(self):
        mf = self._make_mapping_file()
        # Should find via domain lookup when code doesn't match
        self.neo4j.query.return_value = []  # no code entity match
        result = self.engine._resolve_term("InventoryPlanning", mf)
        # Should resolve via domain id partial match
        assert result == "com.example.inventory.SafetyStockCalc"

    def test_analyze_returns_affected_processes(self):
        mf = self._make_mapping_file()
        # Mock BFS: SafetyStockCalc is called by OrderService and ReplenishJob
        self.neo4j.query.return_value = [
            {"qn": "com.example.order.OrderService", "depth": 1},
            {"qn": "com.example.replenish.ReplenishJob", "depth": 1},
        ]
        query = ImpactQuery(term="SafetyStockCalc", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert result.resolved is True
        assert len(result.affected_processes) == 2
        domains = {p.domain_id for p in result.affected_processes}
        assert "SCOR/Deliver/OrderManagement" in domains
        assert "SCOR/Source/Procurement" in domains

    def test_analyze_unresolved_term(self):
        mf = self._make_mapping_file()
        query = ImpactQuery(term="DoesNotExist", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert result.resolved is False
        assert "매핑되지 않은" in result.message or "not found" in result.message.lower()

    def test_analyze_reports_unmapped_entities(self):
        mf = self._make_mapping_file()
        # BFS finds an entity that's not mapped
        self.neo4j.query.return_value = [
            {"qn": "com.example.order.OrderService", "depth": 1},
            {"qn": "com.example.util.Logger", "depth": 2},
        ]
        query = ImpactQuery(term="SafetyStockCalc", repo_id="test-repo")
        result = self.engine.analyze(query, mf)
        assert "com.example.util.Logger" in result.unmapped_entities
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_query_engine.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement query engine**

```python
# backend/modeling/query/query_engine.py
"""Deterministic impact analysis: term lookup → BFS → reverse mapping."""

from __future__ import annotations

import logging

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.mapping.mapping_models import MappingFile, MappingStatus
from backend.modeling.mapping.mapping_service import MappingService
from backend.modeling.query.query_models import (
    ImpactQuery, ImpactResult, AffectedProcess,
)

logger = logging.getLogger(__name__)


class QueryEngine:
    """100% deterministic impact analysis — no LLM in the data path."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j
        self._mapping_svc = MappingService(neo4j)

    def analyze(self, query: ImpactQuery, mf: MappingFile) -> ImpactResult:
        # Step 1: Resolve term to a code entity
        code_entity = self._resolve_term(query.term, mf)

        if code_entity is None:
            return ImpactResult(
                source_term=query.term,
                source_code_entity=None,
                source_domain=None,
                affected_processes=[],
                unmapped_entities=[],
                resolved=False,
                message=f"'{query.term}'은(는) 매핑되지 않은 용어입니다. 매핑을 추가하시겠습니까?",
            )

        # Step 2: Get source domain mapping
        source_domain = self._mapping_svc.resolve(mf, code_entity)

        # Step 3: BFS traversal — find all code entities that depend on this one
        dependents = self._bfs_dependents(code_entity, query.repo_id, query.depth)

        # Step 4: Reverse mapping — map dependent code entities to domain processes
        affected: list[AffectedProcess] = []
        unmapped: list[str] = []

        for dep in dependents:
            qn = dep["qn"]
            domain = self._mapping_svc.resolve(mf, qn)

            if domain is None:
                unmapped.append(qn)
                continue

            # Filter by confirmed_only
            if query.confirmed_only:
                mapping = next((m for m in mf.mappings if m.code == qn), None)
                if mapping and mapping.status != MappingStatus.CONFIRMED:
                    # Check inherited mapping status
                    parent_mapping = self._find_inherited_mapping(mf, qn)
                    if parent_mapping and parent_mapping.status != MappingStatus.CONFIRMED:
                        continue

            # Get domain name from Neo4j
            domain_info = self._neo4j.query(
                "MATCH (n:DomainNode {id: $id}) RETURN n.name as name",
                {"id": domain},
            )
            domain_name = domain_info[0]["name"] if domain_info else domain

            affected.append(AffectedProcess(
                domain_id=domain,
                domain_name=domain_name,
                path=[code_entity, qn],
                distance=dep["depth"],
            ))

        # Deduplicate by domain_id (keep shortest path)
        seen: dict[str, AffectedProcess] = {}
        for ap in affected:
            if ap.domain_id not in seen or ap.distance < seen[ap.domain_id].distance:
                seen[ap.domain_id] = ap
        affected = list(seen.values())

        message = f"'{query.term}' 변경 시 {len(affected)}개 프로세스에 영향."
        if unmapped:
            message += f" 미매핑 코드 {len(unmapped)}건."

        return ImpactResult(
            source_term=query.term,
            source_code_entity=code_entity,
            source_domain=source_domain,
            affected_processes=affected,
            unmapped_entities=unmapped,
            resolved=True,
            message=message,
        )

    def _resolve_term(self, term: str, mf: MappingFile) -> str | None:
        """Resolve a natural language term to a code entity qualified name."""
        # 1. Direct code entity match (exact or suffix)
        for m in mf.mappings:
            if m.code == term or m.code.endswith(f".{term}"):
                return m.code

        # 2. Domain id match → find code entity mapped to that domain
        for m in mf.mappings:
            domain_suffix = m.domain.split("/")[-1]
            if term.lower() == domain_suffix.lower() or term.lower() in m.domain.lower():
                return m.code

        return None

    def _bfs_dependents(self, entity: str, repo_id: str, max_depth: int) -> list[dict]:
        """Find all code entities that depend on the given entity (callers, inheritors)."""
        cypher = """
        MATCH (source:CodeEntity {qualified_name: $qn, repo_id: $repo_id})
        MATCH path = (other:CodeEntity)-[:CALLS|EXTENDS|IMPLEMENTS|DEPENDS_ON*1..%d]->(source)
        WHERE other.repo_id = $repo_id
        RETURN DISTINCT other.qualified_name as qn,
               length(path) as depth
        ORDER BY depth
        """ % max_depth
        return self._neo4j.query(cypher, {"qn": entity, "repo_id": repo_id})

    def _find_inherited_mapping(self, mf: MappingFile, qn: str):
        """Find the mapping entry that would apply via inheritance."""
        parts = qn.rsplit(".", 1)
        while len(parts) == 2:
            parent = parts[0]
            for m in mf.mappings:
                if m.code == parent:
                    return m
            parts = parent.rsplit(".", 1)
        return None
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_query_engine.py -v
```

Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/query/ tests/test_query_engine.py
git commit -m "feat(modeling): implement deterministic impact analysis query engine"
```

---

## Task 9: Change Detector

**Files:**
- Create: `backend/modeling/change/change_detector.py`
- Test: `tests/test_change_detector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_change_detector.py
import pytest
from unittest.mock import MagicMock

from backend.modeling.change.change_detector import ChangeDetector, ChangeImpact, ChangeKind
from backend.modeling.infrastructure.git_connector import GitDiff
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


class TestChangeDetector:
    def setup_method(self):
        self.neo4j = MagicMock()
        self.detector = ChangeDetector(self.neo4j)

    def _make_mapping_file(self) -> MappingFile:
        return MappingFile(repo_id="test-repo", mappings=[
            Mapping(code="com.example.Foo", domain="SCOR/Plan", owner="kim",
                    status=MappingStatus.CONFIRMED),
        ])

    def test_deleted_file_flags_broken_mapping(self):
        mf = self._make_mapping_file()
        # Foo.java is the file containing com.example.Foo
        self.neo4j.query.return_value = [
            {"qualified_name": "com.example.Foo"},
        ]
        diff = GitDiff(deleted=["src/Foo.java"])

        impacts = self.detector.classify(diff, mf, "test-repo")
        broken = [i for i in impacts if i.kind == ChangeKind.BROKEN]
        assert len(broken) == 1
        assert broken[0].code_entity == "com.example.Foo"

    def test_new_file_flags_unmapped(self):
        mf = self._make_mapping_file()
        self.neo4j.query.return_value = [
            {"qualified_name": "com.example.NewClass"},
        ]
        diff = GitDiff(added=["src/NewClass.java"])

        impacts = self.detector.classify(diff, mf, "test-repo")
        unmapped = [i for i in impacts if i.kind == ChangeKind.UNMAPPED]
        assert len(unmapped) == 1

    def test_modified_file_flags_review(self):
        mf = self._make_mapping_file()
        self.neo4j.query.return_value = [
            {"qualified_name": "com.example.Foo"},
        ]
        diff = GitDiff(modified=["src/Foo.java"])

        impacts = self.detector.classify(diff, mf, "test-repo")
        review = [i for i in impacts if i.kind == ChangeKind.REVIEW]
        assert len(review) == 1
        assert review[0].owner == "kim"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_change_detector.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement change detector**

```python
# backend/modeling/change/change_detector.py
"""Git diff → mapping impact classification."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from backend.modeling.infrastructure.neo4j_client import Neo4jClient
from backend.modeling.infrastructure.git_connector import GitDiff
from backend.modeling.mapping.mapping_models import MappingFile

logger = logging.getLogger(__name__)


class ChangeKind(str, Enum):
    BROKEN = "broken"        # mapped entity was deleted
    REVIEW = "review"        # mapped entity was modified — review mapping
    UNMAPPED = "unmapped"    # new entity has no mapping
    AUTO_UPDATE = "auto_update"  # rename/move — can auto-fix mapping ref


@dataclass
class ChangeImpact:
    kind: ChangeKind
    code_entity: str
    file_path: str
    owner: str              # mapping owner to notify
    message: str


class ChangeDetector:
    """Classifies git diff impact on existing mappings."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    def classify(self, diff: GitDiff, mf: MappingFile, repo_id: str) -> list[ChangeImpact]:
        impacts: list[ChangeImpact] = []

        # Map of code entity → mapping for quick lookup
        mapping_by_code = {m.code: m for m in mf.mappings}

        # Deleted files → broken mappings
        for path in diff.deleted:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn in mapping_by_code:
                    m = mapping_by_code[qn]
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.BROKEN,
                        code_entity=qn,
                        file_path=path,
                        owner=m.owner,
                        message=f"매핑된 코드 '{qn}'가 삭제되었습니다.",
                    ))

        # Modified files → review needed
        for path in diff.modified:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn in mapping_by_code:
                    m = mapping_by_code[qn]
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.REVIEW,
                        code_entity=qn,
                        file_path=path,
                        owner=m.owner,
                        message=f"매핑된 코드 '{qn}'가 변경되었습니다. 매핑 검토가 필요합니다.",
                    ))

        # Added files → unmapped
        for path in diff.added:
            entities = self._entities_in_file(path, repo_id)
            for e in entities:
                qn = e["qualified_name"]
                if qn not in mapping_by_code:
                    impacts.append(ChangeImpact(
                        kind=ChangeKind.UNMAPPED,
                        code_entity=qn,
                        file_path=path,
                        owner="",
                        message=f"새 코드 '{qn}'에 도메인 매핑이 필요합니다.",
                    ))

        return impacts

    def _entities_in_file(self, file_path: str, repo_id: str) -> list[dict]:
        return self._neo4j.query(
            "MATCH (n:CodeEntity {file_path: $fp, repo_id: $repo_id}) "
            "RETURN n.qualified_name as qualified_name",
            {"fp": file_path, "repo_id": repo_id},
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_change_detector.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/change/ tests/test_change_detector.py
git commit -m "feat(modeling): implement change detector for mapping impact classification"
```

---

## Task 10: Approval Workflow

**Files:**
- Create: `backend/modeling/approval/approval_models.py`
- Create: `backend/modeling/approval/approval_service.py`
- Test: `tests/test_approval_service.py`

- [ ] **Step 1: Define approval models**

```python
# backend/modeling/approval/approval_models.py
"""Pydantic models for mapping approval workflow."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewRequest(BaseModel):
    """A request for a business user to review a mapping."""
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex[:12])
    mapping_code: str           # code entity being mapped
    mapping_domain: str         # proposed domain mapping
    repo_id: str
    requested_by: str           # IT user who created the mapping
    requested_at: datetime = Field(default_factory=datetime.now)
    status: ReviewStatus = ReviewStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    comment: str = ""
    impact_summary: str = ""    # attached impact analysis summary
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_approval_service.py
import pytest

from backend.modeling.approval.approval_service import ApprovalService
from backend.modeling.approval.approval_models import ReviewRequest, ReviewStatus
from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus


class TestApprovalService:
    def setup_method(self):
        self.service = ApprovalService()

    def test_create_review_request(self):
        req = self.service.create_review(
            mapping_code="com.example.Foo",
            mapping_domain="SCOR/Plan",
            repo_id="test-repo",
            requested_by="kim",
        )
        assert req.status == ReviewStatus.PENDING
        assert req.mapping_code == "com.example.Foo"

    def test_approve_review(self):
        req = self.service.create_review("com.Foo", "SCOR/Plan", "repo", "kim")
        mf = MappingFile(repo_id="repo", mappings=[
            Mapping(code="com.Foo", domain="SCOR/Plan", status=MappingStatus.REVIEW),
        ])
        result_req, result_mf = self.service.approve(req.id, "lee-biz", mf)
        assert result_req.status == ReviewStatus.APPROVED
        assert result_mf.mappings[0].status == MappingStatus.CONFIRMED
        assert result_mf.mappings[0].confirmed_by == "lee-biz"

    def test_reject_review(self):
        req = self.service.create_review("com.Foo", "SCOR/Plan", "repo", "kim")
        mf = MappingFile(repo_id="repo", mappings=[
            Mapping(code="com.Foo", domain="SCOR/Plan", status=MappingStatus.REVIEW),
        ])
        result_req, result_mf = self.service.reject(req.id, "lee-biz", "도메인이 잘못됨", mf)
        assert result_req.status == ReviewStatus.REJECTED
        assert result_req.comment == "도메인이 잘못됨"
        assert result_mf.mappings[0].status == MappingStatus.DRAFT

    def test_list_pending_reviews(self):
        self.service.create_review("com.A", "SCOR/Plan", "repo", "kim")
        self.service.create_review("com.B", "SCOR/Source", "repo", "kim")
        pending = self.service.list_pending("repo")
        assert len(pending) == 2

    def test_approve_nonexistent_raises(self):
        mf = MappingFile(repo_id="repo", mappings=[])
        with pytest.raises(ValueError):
            self.service.approve("nonexistent", "lee", mf)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_approval_service.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement approval service**

```python
# backend/modeling/approval/approval_service.py
"""Mapping approval workflow: draft → review → confirmed."""

from __future__ import annotations

import logging
from datetime import datetime

from backend.modeling.approval.approval_models import ReviewRequest, ReviewStatus
from backend.modeling.mapping.mapping_models import MappingFile, MappingStatus

logger = logging.getLogger(__name__)


class ApprovalService:
    """In-memory approval workflow. Future: persist to PostgreSQL."""

    def __init__(self) -> None:
        self._reviews: dict[str, ReviewRequest] = {}

    def create_review(
        self, mapping_code: str, mapping_domain: str,
        repo_id: str, requested_by: str, impact_summary: str = "",
    ) -> ReviewRequest:
        req = ReviewRequest(
            mapping_code=mapping_code,
            mapping_domain=mapping_domain,
            repo_id=repo_id,
            requested_by=requested_by,
            impact_summary=impact_summary,
        )
        self._reviews[req.id] = req
        logger.info(f"Review request created: {req.id} for {mapping_code}")
        return req

    def approve(
        self, review_id: str, reviewer: str, mf: MappingFile,
    ) -> tuple[ReviewRequest, MappingFile]:
        req = self._get_review(review_id)
        req.status = ReviewStatus.APPROVED
        req.reviewer = reviewer
        req.reviewed_at = datetime.now()

        # Update mapping status to confirmed
        for m in mf.mappings:
            if m.code == req.mapping_code:
                m.status = MappingStatus.CONFIRMED
                m.confirmed_by = reviewer
                m.confirmed_at = datetime.now()
                break

        logger.info(f"Review {review_id} approved by {reviewer}")
        return req, mf

    def reject(
        self, review_id: str, reviewer: str, comment: str, mf: MappingFile,
    ) -> tuple[ReviewRequest, MappingFile]:
        req = self._get_review(review_id)
        req.status = ReviewStatus.REJECTED
        req.reviewer = reviewer
        req.reviewed_at = datetime.now()
        req.comment = comment

        # Revert mapping to draft
        for m in mf.mappings:
            if m.code == req.mapping_code:
                m.status = MappingStatus.DRAFT
                break

        logger.info(f"Review {review_id} rejected by {reviewer}: {comment}")
        return req, mf

    def list_pending(self, repo_id: str) -> list[ReviewRequest]:
        return [
            r for r in self._reviews.values()
            if r.repo_id == repo_id and r.status == ReviewStatus.PENDING
        ]

    def list_all(self, repo_id: str) -> list[ReviewRequest]:
        return [r for r in self._reviews.values() if r.repo_id == repo_id]

    def _get_review(self, review_id: str) -> ReviewRequest:
        if review_id not in self._reviews:
            raise ValueError(f"Review request not found: {review_id}")
        return self._reviews[review_id]
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /Users/donghae/workspace/ai/onTong && venv/bin/python -m pytest tests/test_approval_service.py -v
```

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/approval/ tests/test_approval_service.py
git commit -m "feat(modeling): implement approval workflow for mapping review"
```

---

## Task 11: API Layer (FastAPI Endpoints)

**Files:**
- Create: `backend/modeling/api/code_api.py`
- Create: `backend/modeling/api/ontology_api.py`
- Create: `backend/modeling/api/mapping_api.py`
- Create: `backend/modeling/api/query_api.py`
- Create: `backend/modeling/api/approval_api.py`
- Modify: `backend/modeling/api/modeling.py`
- Test: `tests/test_modeling_api.py`

- [ ] **Step 1: Implement code analysis API**

```python
# backend/modeling/api/code_api.py
"""API endpoints for code analysis operations."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/modeling/code", tags=["modeling-code"])

# Injected at init
_git_connector = None
_java_parser = None
_graph_writer = None


def init(git_connector, java_parser, graph_writer):
    global _git_connector, _java_parser, _graph_writer
    _git_connector = git_connector
    _java_parser = java_parser
    _graph_writer = graph_writer


class ParseRequest(BaseModel):
    repo_url: str
    repo_id: str


class ParseResponse(BaseModel):
    repo_id: str
    files_parsed: int
    entities_count: int
    relations_count: int


@router.post("/parse", response_model=ParseResponse)
async def parse_repo(req: ParseRequest):
    """Clone/pull a Java repo and parse into code graph."""
    repo_path = _git_connector.clone(req.repo_url, req.repo_id)
    java_files = _git_connector.list_files(req.repo_id, extension=".java")

    total_entities = 0
    total_relations = 0
    _graph_writer.clear_repo(req.repo_id)

    for file_path in java_files:
        content = _git_connector.read_file(req.repo_id, file_path)
        result = _java_parser.parse_file(repo_path / file_path, content)
        _graph_writer.write_parse_result(result, repo_id=req.repo_id)
        total_entities += len(result.entities)
        total_relations += len(result.relations)

    return ParseResponse(
        repo_id=req.repo_id,
        files_parsed=len(java_files),
        entities_count=total_entities,
        relations_count=total_relations,
    )


@router.get("/graph/{repo_id}")
async def get_code_graph(repo_id: str, kind: str | None = None):
    """Get code entities and relations for a repo."""
    from backend.modeling.infrastructure.neo4j_client import Neo4jClient
    neo4j: Neo4jClient = _graph_writer._neo4j

    filter_clause = ""
    params = {"repo_id": repo_id}
    if kind:
        filter_clause = " AND n.kind = $kind"
        params["kind"] = kind

    entities = neo4j.query(
        f"MATCH (n:CodeEntity {{repo_id: $repo_id}}){filter_clause} "
        "RETURN n.qualified_name as id, n.name as name, n.kind as kind, "
        "n.file_path as file_path, n.parent as parent "
        "ORDER BY n.qualified_name",
        params,
    )
    return {"repo_id": repo_id, "entities": entities, "count": len(entities)}
```

- [ ] **Step 2: Implement ontology API**

```python
# backend/modeling/api/ontology_api.py
"""API endpoints for domain ontology management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.modeling.ontology.domain_models import DomainNode, DomainNodeKind

router = APIRouter(prefix="/api/modeling/ontology", tags=["modeling-ontology"])

_ontology_store = None


def init(ontology_store):
    global _ontology_store
    _ontology_store = ontology_store


@router.post("/load-template")
async def load_template():
    """Load the SCOR+ISA-95 template into Neo4j."""
    count = _ontology_store.load_template()
    return {"loaded": count}


@router.get("/tree")
async def get_tree():
    """Get the full domain ontology tree."""
    nodes = _ontology_store.get_tree()
    return {"nodes": nodes, "count": len(nodes)}


@router.get("/children/{node_id:path}")
async def get_children(node_id: str):
    """Get child nodes of a domain node."""
    children = _ontology_store.get_children(node_id)
    return {"parent": node_id, "children": children}


class AddNodeRequest(BaseModel):
    id: str
    name: str
    kind: DomainNodeKind = DomainNodeKind.PROCESS
    parent_id: str | None = None
    description: str = ""


@router.post("/node")
async def add_node(req: AddNodeRequest):
    """Add a custom domain node."""
    node = DomainNode(**req.model_dump())
    _ontology_store.add_node(node)
    return {"added": node.id}


class UpdateNodeRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.put("/node/{node_id:path}")
async def update_node(node_id: str, req: UpdateNodeRequest):
    """Update a domain node."""
    _ontology_store.update_node(node_id, name=req.name, description=req.description)
    return {"updated": node_id}


@router.delete("/node/{node_id:path}")
async def delete_node(node_id: str):
    """Delete a domain node."""
    _ontology_store.remove_node(node_id)
    return {"deleted": node_id}
```

- [ ] **Step 3: Implement mapping API**

```python
# backend/modeling/api/mapping_api.py
"""API endpoints for code↔domain mapping management."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.modeling.mapping.mapping_models import Mapping, MappingStatus, MappingGranularity

router = APIRouter(prefix="/api/modeling/mapping", tags=["modeling-mapping"])

_mapping_service = None
_git_connector = None


def init(mapping_service, git_connector):
    global _mapping_service, _git_connector
    _mapping_service = mapping_service
    _git_connector = git_connector


def _yaml_path(repo_id: str) -> Path:
    return _git_connector.repos_dir / repo_id / ".ontology" / "mapping.yaml"


def _load_mf(repo_id: str):
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


@router.get("/{repo_id}")
async def get_mappings(repo_id: str):
    """Get all mappings for a repo."""
    mf = _load_mf(repo_id)
    return {"repo_id": repo_id, "mappings": [m.model_dump(mode="json") for m in mf.mappings]}


class AddMappingRequest(BaseModel):
    code: str
    domain: str
    granularity: MappingGranularity = MappingGranularity.CLASS
    owner: str = ""


@router.post("/{repo_id}")
async def add_mapping(repo_id: str, req: AddMappingRequest):
    """Add a new code↔domain mapping."""
    mf = _load_mf(repo_id)
    mapping = Mapping(**req.model_dump())
    try:
        mf = _mapping_service.add_mapping(mf, mapping)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)
    _mapping_service.sync_to_neo4j(mf)
    return {"added": req.code}


@router.delete("/{repo_id}/{code:path}")
async def remove_mapping(repo_id: str, code: str):
    """Remove a mapping."""
    mf = _load_mf(repo_id)
    mf = _mapping_service.remove_mapping(mf, code)
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)
    _mapping_service.sync_to_neo4j(mf)
    return {"removed": code}


@router.get("/{repo_id}/gaps")
async def get_gaps(repo_id: str):
    """Find unmapped code entities."""
    mf = _load_mf(repo_id)
    gaps = _mapping_service.find_gaps(mf, repo_id)
    return {"repo_id": repo_id, "gaps": [g.model_dump() for g in gaps], "count": len(gaps)}


@router.get("/{repo_id}/resolve/{qualified_name:path}")
async def resolve_mapping(repo_id: str, qualified_name: str):
    """Resolve the domain mapping for a code entity (with inheritance)."""
    mf = _load_mf(repo_id)
    domain = _mapping_service.resolve(mf, qualified_name)
    return {"code": qualified_name, "domain": domain, "resolved": domain is not None}
```

- [ ] **Step 4: Implement query API**

```python
# backend/modeling/api/query_api.py
"""API endpoint for impact analysis queries."""

from __future__ import annotations

from fastapi import APIRouter

from backend.modeling.query.query_models import ImpactQuery

router = APIRouter(prefix="/api/modeling/impact", tags=["modeling-impact"])

_query_engine = None
_mapping_service = None
_git_connector = None


def init(query_engine, mapping_service, git_connector):
    global _query_engine, _mapping_service, _git_connector
    _query_engine = query_engine
    _mapping_service = mapping_service
    _git_connector = git_connector


def _load_mf(repo_id: str):
    from backend.modeling.api.mapping_api import _yaml_path
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


@router.post("/analyze")
async def analyze_impact(query: ImpactQuery):
    """Run deterministic impact analysis."""
    mf = _load_mf(query.repo_id)
    result = _query_engine.analyze(query, mf)
    return result.model_dump(mode="json")
```

- [ ] **Step 5: Implement approval API**

```python
# backend/modeling/api/approval_api.py
"""API endpoints for mapping approval workflow."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/modeling/approval", tags=["modeling-approval"])

_approval_service = None
_mapping_service = None
_git_connector = None


def init(approval_service, mapping_service, git_connector):
    global _approval_service, _mapping_service, _git_connector
    _approval_service = approval_service
    _mapping_service = mapping_service
    _git_connector = git_connector


def _load_mf(repo_id: str):
    from backend.modeling.api.mapping_api import _yaml_path
    path = _yaml_path(repo_id)
    if not path.exists():
        from backend.modeling.mapping.mapping_models import MappingFile
        return MappingFile(repo_id=repo_id, mappings=[])
    return _mapping_service.load_yaml(path)


def _save_mf(repo_id: str, mf):
    from backend.modeling.api.mapping_api import _yaml_path
    _mapping_service.save_yaml(_yaml_path(repo_id), mf)


class SubmitReviewRequest(BaseModel):
    mapping_code: str
    mapping_domain: str
    repo_id: str
    requested_by: str


@router.post("/submit")
async def submit_review(req: SubmitReviewRequest):
    """Submit a mapping for business review."""
    # Update mapping status to review
    mf = _load_mf(req.repo_id)
    _mapping_service.update_status(mf, req.mapping_code, "review")
    _save_mf(req.repo_id, mf)

    review = _approval_service.create_review(
        req.mapping_code, req.mapping_domain, req.repo_id, req.requested_by,
    )
    return review.model_dump(mode="json")


class ApproveRequest(BaseModel):
    reviewer: str


@router.post("/{review_id}/approve")
async def approve(review_id: str, req: ApproveRequest):
    """Business user approves a mapping."""
    review = _approval_service._get_review(review_id)
    mf = _load_mf(review.repo_id)
    review, mf = _approval_service.approve(review_id, req.reviewer, mf)
    _save_mf(review.repo_id, mf)
    return review.model_dump(mode="json")


class RejectRequest(BaseModel):
    reviewer: str
    comment: str


@router.post("/{review_id}/reject")
async def reject(review_id: str, req: RejectRequest):
    """Business user rejects a mapping."""
    review = _approval_service._get_review(review_id)
    mf = _load_mf(review.repo_id)
    review, mf = _approval_service.reject(review_id, req.reviewer, req.comment, mf)
    _save_mf(review.repo_id, mf)
    return review.model_dump(mode="json")


@router.get("/pending/{repo_id}")
async def list_pending(repo_id: str):
    """List pending review requests."""
    reviews = _approval_service.list_pending(repo_id)
    return {"reviews": [r.model_dump(mode="json") for r in reviews]}
```

- [ ] **Step 6: Update modeling.py to register all sub-routers**

Update `backend/modeling/api/modeling.py` to include all new routers and initialize dependencies:

```python
# backend/modeling/api/modeling.py
"""Section 2 Modeling API — main router aggregator."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter

from backend.modeling.api import code_api, ontology_api, mapping_api, query_api
from backend.modeling.api import approval_api as modeling_approval_api

logger = logging.getLogger(__name__)

router = APIRouter(tags=["modeling"])

# Include sub-routers
router.include_router(code_api.router)
router.include_router(ontology_api.router)
router.include_router(mapping_api.router)
router.include_router(query_api.router)
router.include_router(modeling_approval_api.router)


def init(neo4j_client=None, repos_dir: Path | None = None) -> None:
    """Initialize Section 2 API with dependencies."""
    if neo4j_client is None:
        logger.info("Modeling API initialized (no Neo4j — limited mode)")
        return

    from backend.modeling.infrastructure.git_connector import GitConnector
    from backend.modeling.code_analysis.java_parser import JavaParser
    from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
    from backend.modeling.ontology.ontology_store import OntologyStore
    from backend.modeling.mapping.mapping_service import MappingService
    from backend.modeling.query.query_engine import QueryEngine
    from backend.modeling.approval.approval_service import ApprovalService

    git = GitConnector(repos_dir or Path("/tmp/ontong-repos"))
    parser = JavaParser()
    writer = CodeGraphWriter(neo4j_client)
    onto_store = OntologyStore(neo4j_client)
    mapping_svc = MappingService(neo4j_client)
    query_eng = QueryEngine(neo4j_client)
    approval_svc = ApprovalService()

    code_api.init(git, parser, writer)
    ontology_api.init(onto_store)
    mapping_api.init(mapping_svc, git)
    query_api.init(query_eng, mapping_svc, git)
    modeling_approval_api.init(approval_svc, mapping_svc, git)

    logger.info("Modeling API fully initialized with Neo4j")


@router.get("/api/modeling/health")
async def health():
    """Section 2 health check."""
    return {
        "section": "modeling",
        "status": "healthy",
        "phase": "1-mvp",
        "capabilities": [
            "code_analysis",
            "ontology_management",
            "mapping_management",
            "impact_analysis",
            "approval_workflow",
        ],
    }
```

- [ ] **Step 7: Update main.py to wire Neo4j and modeling init**

In `backend/main.py`, update the modeling API initialization in the `lifespan` function:

Replace:
```python
modeling_api.init()
```

With:
```python
# Initialize Section 2 (Modeling) with Neo4j
from backend.modeling.infrastructure.neo4j_client import Neo4jClient
try:
    neo4j_client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    neo4j_health = neo4j_client.health()
    logger.info(f"Neo4j: {neo4j_health['status']}")
    modeling_api.init(neo4j_client=neo4j_client)
except Exception as e:
    logger.warning(f"Neo4j unavailable, modeling in limited mode: {e}")
    modeling_api.init()
```

- [ ] **Step 8: Write integration test for API**

```python
# tests/test_modeling_api.py
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestModelingHealthAPI:
    def test_health_endpoint(self):
        from backend.main import app
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/modeling/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["section"] == "modeling"
        assert "code_analysis" in data["capabilities"]
```

- [ ] **Step 9: Commit**

```bash
git add backend/modeling/api/ backend/main.py tests/test_modeling_api.py
git commit -m "feat(modeling): implement full API layer + main.py wiring"
```

---

## Task 12: Frontend — API Client + ModelingSection Update

**Files:**
- Create: `frontend/src/lib/api/modeling.ts`
- Modify: `frontend/src/components/sections/ModelingSection.tsx`

- [ ] **Step 1: Create modeling API client**

```typescript
// frontend/src/lib/api/modeling.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ── Code Analysis ──

export interface ParseRequest {
  repo_url: string;
  repo_id: string;
}

export interface ParseResponse {
  repo_id: string;
  files_parsed: number;
  entities_count: number;
  relations_count: number;
}

export async function parseRepo(req: ParseRequest): Promise<ParseResponse> {
  const res = await fetch(`${API_BASE}/api/modeling/code/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface CodeEntity {
  id: string;
  name: string;
  kind: string;
  file_path: string;
  parent: string | null;
}

export async function getCodeGraph(repoId: string, kind?: string): Promise<{ entities: CodeEntity[] }> {
  const params = kind ? `?kind=${kind}` : "";
  const res = await fetch(`${API_BASE}/api/modeling/code/graph/${repoId}${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Domain Ontology ──

export interface DomainNode {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  description?: string;
}

export async function loadTemplate(): Promise<{ loaded: number }> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/load-template`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getOntologyTree(): Promise<{ nodes: DomainNode[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/tree`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Mappings ──

export interface MappingEntry {
  code: string;
  domain: string;
  granularity: string;
  owner: string;
  status: "draft" | "review" | "confirmed";
  confirmed_by?: string;
}

export async function getMappings(repoId: string): Promise<{ mappings: MappingEntry[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addMapping(repoId: string, code: string, domain: string, owner: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, domain, owner }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function removeMapping(repoId: string, code: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}/${code}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

export async function getMappingGaps(repoId: string): Promise<{ gaps: { qualified_name: string; kind: string; file_path: string }[]; count: number }> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}/gaps`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Impact Analysis ──

export interface ImpactResult {
  source_term: string;
  source_code_entity: string | null;
  source_domain: string | null;
  affected_processes: {
    domain_id: string;
    domain_name: string;
    path: string[];
    distance: number;
  }[];
  unmapped_entities: string[];
  resolved: boolean;
  message: string;
}

export async function analyzeImpact(term: string, repoId: string): Promise<ImpactResult> {
  const res = await fetch(`${API_BASE}/api/modeling/impact/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term, repo_id: repoId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Approvals ──

export interface ReviewRequest {
  id: string;
  mapping_code: string;
  mapping_domain: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  reviewer?: string;
  comment?: string;
}

export async function submitReview(repoId: string, code: string, domain: string, requestedBy: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping_code: code, mapping_domain: domain, repo_id: repoId, requested_by: requestedBy }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveReview(reviewId: string, reviewer: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/${reviewId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPendingReviews(repoId: string): Promise<{ reviews: ReviewRequest[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/pending/${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 2: Update ModelingSection.tsx**

Replace the scaffold in `frontend/src/components/sections/ModelingSection.tsx` with the real section shell that routes between sub-views. The sub-view components (CodeGraphViewer, DomainOntologyEditor, MappingSplitView, ImpactQueryPanel, ApprovalList) will be implemented in Tasks 13-17. For now, use inline placeholders within this file.

```typescript
// frontend/src/components/sections/ModelingSection.tsx
"use client";

import React, { useState } from "react";
import { Code, Network, GitCompare, Search, CheckSquare } from "lucide-react";

type ModelingView = "code" | "ontology" | "mapping" | "impact" | "approval";

interface NavItem {
  id: ModelingView;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "code", label: "코드 분석", icon: <Code size={18} />, description: "Java 코드 파싱 및 의존성 그래프" },
  { id: "ontology", label: "도메인 온톨로지", icon: <Network size={18} />, description: "SCOR+ISA-95 프로세스 트리" },
  { id: "mapping", label: "매핑 관리", icon: <GitCompare size={18} />, description: "코드 ↔ 도메인 연결" },
  { id: "impact", label: "영향분석", icon: <Search size={18} />, description: "변경 시 영향 범위 조회" },
  { id: "approval", label: "검토 요청", icon: <CheckSquare size={18} />, description: "매핑 승인/반려 관리" },
];

export default function ModelingSection() {
  const [activeView, setActiveView] = useState<ModelingView>("mapping");
  const [repoId, setRepoId] = useState<string>("");

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-56 border-r border-border bg-muted/30 p-3 flex flex-col gap-1">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold text-foreground">Modeling</h2>
          <p className="text-xs text-muted-foreground mt-1">Section 2</p>
        </div>

        {/* Repo selector */}
        <div className="px-2 mb-3">
          <label className="text-xs text-muted-foreground">Repository</label>
          <input
            type="text"
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            placeholder="repo-id"
            className="w-full mt-1 px-2 py-1 text-xs bg-background border border-border rounded"
          />
        </div>

        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
              activeView === item.id
                ? "bg-primary/10 text-primary font-medium"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </div>

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {!repoId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Repository ID를 입력하세요</p>
          </div>
        ) : (
          <ViewRouter view={activeView} repoId={repoId} />
        )}
      </div>
    </div>
  );
}

function ViewRouter({ view, repoId }: { view: ModelingView; repoId: string }) {
  const info = NAV_ITEMS.find((n) => n.id === view);

  // Placeholder — individual view components will be added in Tasks 13-17
  return (
    <div>
      <h2 className="text-lg font-semibold mb-1">{info?.label}</h2>
      <p className="text-sm text-muted-foreground mb-6">{info?.description}</p>
      <div className="border border-dashed border-border rounded-lg p-8 text-center text-muted-foreground">
        {view} view — repo: {repoId}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api/modeling.ts \
  frontend/src/components/sections/ModelingSection.tsx
git commit -m "feat(modeling): add frontend API client + update ModelingSection shell"
```

---

## Tasks 13-17: Frontend View Components

> Tasks 13-17 implement the individual view components (CodeGraphViewer, DomainOntologyEditor, MappingSplitView, ImpactQueryPanel, ApprovalList). Each follows the same pattern:
>
> 1. Create the component file in `frontend/src/components/sections/modeling/`
> 2. Import and wire into `ViewRouter` in `ModelingSection.tsx`
> 3. Test in browser
>
> These tasks are detailed but follow established React patterns from the existing codebase. They can be implemented by the executing agent with the API client from Task 12 as reference. Each component:
>
> - **CodeGraphViewer**: Fetch `getCodeGraph()` → tree view of packages/classes/methods + D3 force graph
> - **DomainOntologyEditor**: Fetch `getOntologyTree()` → SCOR tree with add/edit/delete node buttons
> - **MappingSplitView**: Side-by-side code tree (left) + domain tree (right) + drag-to-connect
> - **ImpactQueryPanel**: Text input → `analyzeImpact()` → result cards showing affected processes
> - **ApprovalList**: Fetch `getPendingReviews()` → list with approve/reject buttons
>
> The implementing agent should create each component following the existing patterns in `frontend/src/components/editors/` (e.g., ConflictDashboard.tsx, MetadataTemplateEditor.tsx) for styling and layout conventions.

---

## Task 18: End-to-End Integration Test

**Files:**
- Test: `tests/test_modeling_e2e.py`

- [ ] **Step 1: Write integration test**

This test requires a running Neo4j instance (`docker compose up -d neo4j`).

```python
# tests/test_modeling_e2e.py
"""End-to-end integration test for Section 2 Modeling MVP.

Requires: docker compose up -d neo4j
Run: ONTONG_E2E=1 pytest tests/test_modeling_e2e.py -v
"""

import os
import pytest
from pathlib import Path

pytestmark = pytest.mark.skipif(
    os.getenv("ONTONG_E2E") != "1",
    reason="E2E tests require ONTONG_E2E=1 and running Neo4j",
)


class TestModelingE2E:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        from backend.modeling.infrastructure.neo4j_client import Neo4jClient
        from backend.modeling.code_analysis.java_parser import JavaParser
        from backend.modeling.code_analysis.graph_writer import CodeGraphWriter
        from backend.modeling.ontology.ontology_store import OntologyStore
        from backend.modeling.mapping.mapping_service import MappingService
        from backend.modeling.mapping.mapping_models import Mapping, MappingFile
        from backend.modeling.query.query_engine import QueryEngine

        self.neo4j = Neo4jClient("bolt://localhost:7687", "neo4j", "ontong_dev")
        self.parser = JavaParser()
        self.writer = CodeGraphWriter(self.neo4j)
        self.onto_store = OntologyStore(self.neo4j)
        self.mapping_svc = MappingService(self.neo4j)
        self.query_engine = QueryEngine(self.neo4j)
        self.tmp_path = tmp_path

        # Clean up from previous runs
        self.neo4j.write("MATCH (n) DETACH DELETE n", {})

        yield

        self.neo4j.close()

    def test_full_flow(self):
        """Parse Java → load ontology → create mapping → run impact analysis."""
        from backend.modeling.code_analysis.parser_protocol import ParseResult
        from backend.modeling.mapping.mapping_models import Mapping, MappingFile, MappingStatus
        from backend.modeling.query.query_models import ImpactQuery

        # 1. Parse sample Java code
        sample = '''
        package com.example.inventory;
        import com.example.order.OrderService;
        public class SafetyStockCalc {
            public double calculate(double demand, double leadTime) {
                return 1.65 * demand * Math.sqrt(leadTime);
            }
        }
        '''
        result = self.parser.parse_file(Path("SafetyStockCalc.java"), sample)
        self.writer.write_parse_result(result, repo_id="e2e-repo")

        order_svc = '''
        package com.example.order;
        import com.example.inventory.SafetyStockCalc;
        public class OrderService {
            private SafetyStockCalc calc;
            public void processOrder() {
                double ss = calc.calculate(100, 7);
            }
        }
        '''
        result2 = self.parser.parse_file(Path("OrderService.java"), order_svc)
        self.writer.write_parse_result(result2, repo_id="e2e-repo")

        # 2. Load SCOR ontology template
        count = self.onto_store.load_template()
        assert count > 20

        # 3. Create mappings
        mf = MappingFile(repo_id="e2e-repo", mappings=[
            Mapping(code="com.example.inventory.SafetyStockCalc",
                    domain="SCOR/Plan/InventoryPlanning",
                    status=MappingStatus.CONFIRMED, owner="kim"),
            Mapping(code="com.example.order.OrderService",
                    domain="SCOR/Deliver/OrderManagement",
                    status=MappingStatus.CONFIRMED, owner="lee"),
        ])
        self.mapping_svc.sync_to_neo4j(mf)

        # 4. Run impact analysis
        query = ImpactQuery(term="SafetyStockCalc", repo_id="e2e-repo")
        impact = self.query_engine.analyze(query, mf)

        assert impact.resolved is True
        assert impact.source_code_entity == "com.example.inventory.SafetyStockCalc"
        assert len(impact.affected_processes) >= 1

        affected_domains = {p.domain_id for p in impact.affected_processes}
        assert "SCOR/Deliver/OrderManagement" in affected_domains
```

- [ ] **Step 2: Run test (requires Neo4j)**

```bash
docker compose up -d neo4j
sleep 10  # wait for Neo4j to start
cd /Users/donghae/workspace/ai/onTong && ONTONG_E2E=1 venv/bin/python -m pytest tests/test_modeling_e2e.py -v
```

Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_modeling_e2e.py
git commit -m "test(modeling): add end-to-end integration test for full MVP flow"
```

---

## Self-Review Checklist

| Spec Requirement | Task | Covered |
|------------------|------|---------|
| Git Connector: clone customer repo | Task 5 | Yes |
| Code Analyzer: JavaParser → Neo4j | Tasks 2-4 | Yes |
| Domain Ontology: SCOR template + editor | Task 6 | Yes |
| Mapping UI: split-view, YAML persistence | Tasks 7, 12-13 | Yes |
| Query Engine: term lookup → BFS → result | Task 8 | Yes |
| Change Detector: diff classification | Task 9 | Yes |
| Approval Workflow: draft/review/confirmed | Task 10 | Yes |
| IT view + Business view | Task 12 (shell) | Partial — view switching exists, per-role filtering deferred to frontend tasks |
| Parser Plugin Interface | Task 2 | Yes |
| Mapping inheritance | Task 7 | Yes |
| Neo4j infrastructure | Task 1 | Yes |
| API layer | Task 11 | Yes |
| Frontend API client | Task 12 | Yes |
| E2E integration test | Task 18 | Yes |
