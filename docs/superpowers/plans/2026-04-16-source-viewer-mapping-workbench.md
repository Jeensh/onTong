# Source Viewer + Mapping Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a split-panel mapping workbench with a React Flow domain graph (left) and Monaco-based source code viewer (right) for code-to-domain mapping verification.

**Architecture:** New `source_api.py` backend serves file tree and source content from cloned repos, joining Neo4j entity positions and YAML mapping data. Frontend adds three new components: `SourceViewer.tsx` (file tree + Monaco read-only), `MappingCanvas.tsx` (React Flow graph + entity panel), and `MappingWorkbench.tsx` (split-panel container with bidirectional linking). Integrated into existing `ModelingSection.tsx` sidebar as a new MAIN_NAV tab.

**Tech Stack:** React Flow v12 (`@xyflow/react`), dagre layout (`@dagrejs/dagre`), Monaco Editor (`@monaco-editor/react`), existing FastAPI + Neo4j + YAML mapping store.

**Spec:** `docs/superpowers/specs/2026-04-16-source-viewer-mapping-workbench-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `backend/modeling/api/source_api.py` | File tree + file content + entity positions API |
| `tests/test_source_api.py` | Backend tests for source API |
| `frontend/src/components/sections/modeling/SourceViewer.tsx` | File tree + Monaco read-only code display |
| `frontend/src/components/sections/modeling/MappingCanvas.tsx` | React Flow domain graph + code entity panel |
| `frontend/src/components/sections/modeling/MappingWorkbench.tsx` | Split-panel container + bidirectional linking |

### Modified Files

| File | Change |
|------|--------|
| `backend/modeling/api/modeling.py` | Wire source_api router + inject dependencies |
| `frontend/src/lib/api/modeling.ts` | Add `getSourceTree()`, `getSourceFile()` functions + types |
| `frontend/src/components/sections/ModelingSection.tsx` | Add "workbench" to ModelingView, add MAIN_NAV entry, wire component |

---

## Task 1: Backend — Source File Tree API

**Files:**
- Create: `backend/modeling/api/source_api.py`
- Create: `tests/test_source_api.py`
- Modify: `backend/modeling/api/modeling.py`

- [ ] **Step 1: Write failing tests for file tree endpoint**

```python
# tests/test_source_api.py
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import os

from backend.modeling.api import source_api


@pytest.fixture
def sample_repo(tmp_path):
    """Create a minimal Java project structure."""
    java_dir = tmp_path / "scm-demo" / "src" / "main" / "java" / "com" / "ontong" / "scm"
    inv_dir = java_dir / "inventory"
    inv_dir.mkdir(parents=True)
    order_dir = java_dir / "order"
    order_dir.mkdir(parents=True)

    (inv_dir / "SafetyStockCalculator.java").write_text(
        "package com.ontong.scm.inventory;\n\npublic class SafetyStockCalculator {\n    public int calculate() { return 0; }\n}\n"
    )
    (inv_dir / "InventoryManager.java").write_text(
        "package com.ontong.scm.inventory;\n\npublic class InventoryManager {}\n"
    )
    (order_dir / "OrderService.java").write_text(
        "package com.ontong.scm.order;\n\npublic class OrderService {}\n"
    )
    # Non-java file
    (java_dir / "README.md").write_text("# readme")

    return tmp_path


@pytest.fixture
def app(sample_repo):
    test_app = FastAPI()
    test_app.include_router(source_api.router)

    mock_neo4j = MagicMock()
    mock_neo4j.query.return_value = []

    source_api.init(repos_dir=sample_repo, neo4j_client=mock_neo4j)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_file_tree_returns_directory_structure(client):
    res = client.get("/api/modeling/source/tree/scm-demo")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "scm-demo"
    assert data["type"] == "directory"
    assert len(data["children"]) > 0


def test_file_tree_contains_java_files(client):
    res = client.get("/api/modeling/source/tree/scm-demo")
    data = res.json()

    # Walk the tree to find .java files
    java_files = []
    def walk(node):
        if node["type"] == "file" and node["name"].endswith(".java"):
            java_files.append(node["name"])
        for child in node.get("children", []):
            walk(child)
    walk(data)

    assert "SafetyStockCalculator.java" in java_files
    assert "InventoryManager.java" in java_files
    assert "OrderService.java" in java_files


def test_file_tree_excludes_hidden_dirs(client, sample_repo):
    # Create a .git dir
    (sample_repo / "scm-demo" / ".git").mkdir()
    (sample_repo / "scm-demo" / ".git" / "config").write_text("x")

    res = client.get("/api/modeling/source/tree/scm-demo")
    data = res.json()

    names = []
    def walk(node):
        names.append(node["name"])
        for child in node.get("children", []):
            walk(child)
    walk(data)

    assert ".git" not in names


def test_file_tree_nonexistent_repo(client):
    res = client.get("/api/modeling/source/tree/does-not-exist")
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.modeling.api.source_api'`

- [ ] **Step 3: Implement source_api.py with file tree endpoint**

```python
# backend/modeling/api/source_api.py
"""Source code viewer API — file tree and content serving."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/modeling/source", tags=["modeling-source"])
logger = logging.getLogger(__name__)

_repos_dir: Path | None = None
_neo4j_client = None

HIDDEN_DIRS = {".git", ".svn", ".hg", "__pycache__", ".idea", ".vscode", "node_modules"}
BINARY_EXTENSIONS = {".class", ".jar", ".war", ".ear", ".pyc", ".so", ".dll", ".exe", ".png", ".jpg", ".gif", ".zip", ".tar", ".gz"}


def init(repos_dir: Path, neo4j_client=None) -> None:
    global _repos_dir, _neo4j_client
    _repos_dir = repos_dir
    _neo4j_client = neo4j_client


def _resolve_repo_path(repo_id: str) -> Path:
    """Resolve repo directory, checking sample-repos as fallback."""
    if _repos_dir is None:
        raise HTTPException(status_code=503, detail="Source API not initialized")

    repo_path = _repos_dir / repo_id
    if repo_path.is_dir():
        return repo_path

    # Fallback: check sample-repos relative to project root
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "sample-repos" / repo_id
        if candidate.is_dir():
            return candidate

    raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")


def _build_tree(path: Path, base_path: Path) -> dict:
    """Recursively build file tree structure."""
    rel_path = str(path.relative_to(base_path))
    if rel_path == ".":
        rel_path = ""

    node = {
        "name": path.name,
        "type": "directory" if path.is_dir() else "file",
        "path": rel_path,
    }

    if path.is_dir():
        children = []
        for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name.startswith(".") or child.name in HIDDEN_DIRS:
                continue
            if child.is_file() and child.suffix.lower() in BINARY_EXTENSIONS:
                continue
            children.append(_build_tree(child, base_path))
        node["children"] = children

    return node


@router.get("/tree/{repo_id}")
async def get_file_tree(repo_id: str):
    """Get the file/directory tree for a repository."""
    repo_path = _resolve_repo_path(repo_id)
    tree = _build_tree(repo_path, repo_path)
    tree["name"] = repo_id
    return tree
```

- [ ] **Step 4: Wire source_api into modeling.py**

Add to `backend/modeling/api/modeling.py`:

```python
# Add import at top
from backend.modeling.api import code_api, ontology_api, mapping_api, query_api, seed_api, engine_api, source_api

# Add router inclusion after engine_api
router.include_router(source_api.router)

# In init() function, add at the end before the final log:
source_api.init(repos_dir=git.repos_dir, neo4j_client=neo4j_client)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/modeling/api/source_api.py tests/test_source_api.py backend/modeling/api/modeling.py
git commit -m "feat(modeling): add source file tree API endpoint"
```

---

## Task 2: Backend — Source File Content API

**Files:**
- Modify: `backend/modeling/api/source_api.py`
- Modify: `tests/test_source_api.py`

- [ ] **Step 1: Write failing tests for file content endpoint**

Add to `tests/test_source_api.py`:

```python
def test_file_content_returns_source(client):
    res = client.get(
        "/api/modeling/source/file/scm-demo",
        params={"path": "src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "content" in data
    assert "package com.ontong.scm.inventory" in data["content"]
    assert data["language"] == "java"
    assert isinstance(data["entities"], list)


def test_file_content_with_entity_positions(client, sample_repo):
    # Mock Neo4j to return entity positions
    from backend.modeling.api import source_api
    source_api._neo4j_client.query.return_value = [
        {
            "qualified_name": "com.ontong.scm.inventory.SafetyStockCalculator",
            "kind": "class",
            "line_start": 3,
            "line_end": 5,
            "domain": "SCOR/Plan/InventoryPlanning",
            "mapping_status": "confirmed",
            "granularity": "class",
        }
    ]

    res = client.get(
        "/api/modeling/source/file/scm-demo",
        params={"path": "src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java"}
    )
    data = res.json()
    assert len(data["entities"]) == 1
    ent = data["entities"][0]
    assert ent["fqn"] == "com.ontong.scm.inventory.SafetyStockCalculator"
    assert ent["kind"] == "class"
    assert ent["start_line"] == 3
    assert ent["end_line"] == 5
    assert ent["mapping"]["domain_path"] == "SCOR/Plan/InventoryPlanning"
    assert ent["mapping"]["status"] == "confirmed"


def test_file_content_path_traversal_blocked(client):
    res = client.get(
        "/api/modeling/source/file/scm-demo",
        params={"path": "../../etc/passwd"}
    )
    assert res.status_code == 403


def test_file_content_nonexistent_file(client):
    res = client.get(
        "/api/modeling/source/file/scm-demo",
        params={"path": "src/main/java/NoSuchFile.java"}
    )
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py::test_file_content_returns_source -v`
Expected: FAIL — 404 or AttributeError

- [ ] **Step 3: Implement file content endpoint**

Add to `backend/modeling/api/source_api.py`:

```python
LANGUAGE_MAP = {
    ".java": "java",
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".xml": "xml",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".properties": "properties",
    ".md": "markdown",
    ".sql": "sql",
    ".sh": "shell",
    ".gradle": "groovy",
}


@router.get("/file/{repo_id}")
async def get_file_content(repo_id: str, path: str):
    """Get the content of a source file with entity position annotations."""
    repo_path = _resolve_repo_path(repo_id)
    file_path = (repo_path / path).resolve()

    # Security: path traversal guard
    if not str(file_path).startswith(str(repo_path.resolve())):
        raise HTTPException(status_code=403, detail="Path traversal not allowed")

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    if file_path.suffix.lower() in BINARY_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Binary files not supported")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not text-readable")

    language = LANGUAGE_MAP.get(file_path.suffix.lower(), "text")

    # Query entity positions + mappings from Neo4j
    entities = _get_entities_for_file(repo_id, path)

    return {
        "path": path,
        "language": language,
        "content": content,
        "entities": entities,
    }


def _get_entities_for_file(repo_id: str, file_path: str) -> list[dict]:
    """Get code entities and their mappings for a specific file."""
    if _neo4j_client is None:
        return []

    results = _neo4j_client.query(
        """
        MATCH (e:CodeEntity {repo_id: $repo_id, file_path: $file_path})
        OPTIONAL MATCH (e)-[r:MAPPED_TO]->(d:DomainNode)
        RETURN e.qualified_name as qualified_name,
               e.kind as kind,
               e.line_start as line_start,
               e.line_end as line_end,
               d.id as domain,
               r.status as mapping_status,
               r.granularity as granularity
        ORDER BY e.line_start
        """,
        {"repo_id": repo_id, "file_path": file_path},
    )

    entities = []
    for row in results:
        entity = {
            "fqn": row["qualified_name"],
            "kind": row["kind"],
            "start_line": row["line_start"],
            "end_line": row["line_end"],
            "mapping": None,
        }
        if row.get("domain"):
            entity["mapping"] = {
                "domain_path": row["domain"],
                "status": row["mapping_status"],
                "granularity": row["granularity"],
            }
        entities.append(entity)

    return entities
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/modeling/api/source_api.py tests/test_source_api.py
git commit -m "feat(modeling): add source file content API with entity positions"
```

---

## Task 3: Frontend — Install Dependencies + API Client

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Modify: `frontend/src/lib/api/modeling.ts`

- [ ] **Step 1: Install React Flow, dagre, and Monaco**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend
npm install @xyflow/react @dagrejs/dagre @monaco-editor/react
```

- [ ] **Step 2: Verify install succeeded**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend
npx tsc --noEmit 2>&1 | head -5
# Expected: no new type errors
```

- [ ] **Step 3: Add API types and functions to modeling.ts**

Add to the end of `frontend/src/lib/api/modeling.ts`:

```typescript
// ── Source Viewer ──

export interface SourceTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: SourceTreeNode[];
}

export interface SourceEntityMapping {
  domain_path: string;
  status: "draft" | "review" | "confirmed";
  granularity: string;
}

export interface SourceEntity {
  fqn: string;
  kind: string;
  start_line: number;
  end_line: number;
  mapping: SourceEntityMapping | null;
}

export interface SourceFileResponse {
  path: string;
  language: string;
  content: string;
  entities: SourceEntity[];
}

export async function getSourceTree(repoId: string): Promise<SourceTreeNode> {
  const res = await fetch(`${API_BASE}/api/modeling/source/tree/${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getSourceFile(repoId: string, path: string): Promise<SourceFileResponse> {
  const res = await fetch(`${API_BASE}/api/modeling/source/file/${repoId}?path=${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean (no errors)

- [ ] **Step 5: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/package.json frontend/package-lock.json frontend/src/lib/api/modeling.ts
git commit -m "feat(modeling): add React Flow, Monaco deps + source viewer API client"
```

---

## Task 4: Frontend — Source Code Viewer Component

**Files:**
- Create: `frontend/src/components/sections/modeling/SourceViewer.tsx`

- [ ] **Step 1: Create SourceViewer component**

```tsx
// frontend/src/components/sections/modeling/SourceViewer.tsx
"use client";

import React, { useCallback, useEffect, useState, useRef } from "react";
import {
  ChevronRight,
  ChevronDown,
  FileCode,
  Folder,
  FolderOpen,
  Search,
  Filter,
} from "lucide-react";
import Editor, { type Monaco } from "@monaco-editor/react";
import type { editor as MonacoEditor } from "monaco-editor";
import {
  getSourceTree,
  getSourceFile,
  type SourceTreeNode,
  type SourceFileResponse,
  type SourceEntity,
} from "@/lib/api/modeling";

interface SourceViewerProps {
  repoId: string;
  highlightEntity?: string | null;
  onEntityClick?: (fqn: string, filePath: string) => void;
}

// ── File Tree ──

interface FileTreeItemProps {
  node: SourceTreeNode;
  depth: number;
  selectedPath: string | null;
  expandedDirs: Set<string>;
  onFileClick: (path: string) => void;
  onToggleDir: (path: string) => void;
  filter: string;
}

function FileTreeItem({
  node,
  depth,
  selectedPath,
  expandedDirs,
  onFileClick,
  onToggleDir,
  filter,
}: FileTreeItemProps) {
  if (filter && node.type === "file" && !node.name.toLowerCase().includes(filter.toLowerCase())) {
    return null;
  }

  const isDir = node.type === "directory";
  const isExpanded = expandedDirs.has(node.path);
  const isSelected = node.path === selectedPath;

  // For directories with filter, check if any child matches
  if (filter && isDir) {
    const hasMatch = hasMatchingChild(node, filter);
    if (!hasMatch) return null;
  }

  return (
    <>
      <button
        onClick={() => isDir ? onToggleDir(node.path) : onFileClick(node.path)}
        className={`flex items-center gap-1 w-full px-2 py-0.5 text-xs hover:bg-muted/50 rounded transition-colors ${
          isSelected ? "bg-primary/10 text-primary font-medium" : "text-foreground/80"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDir ? (
          <>
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            {isExpanded ? <FolderOpen size={14} className="text-amber-500" /> : <Folder size={14} className="text-amber-500" />}
          </>
        ) : (
          <>
            <span style={{ width: 12 }} />
            <FileCode size={14} className="text-blue-400" />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && isExpanded && node.children?.map((child) => (
        <FileTreeItem
          key={child.path}
          node={child}
          depth={depth + 1}
          selectedPath={selectedPath}
          expandedDirs={expandedDirs}
          onFileClick={onFileClick}
          onToggleDir={onToggleDir}
          filter={filter}
        />
      ))}
    </>
  );
}

function hasMatchingChild(node: SourceTreeNode, filter: string): boolean {
  if (node.type === "file") return node.name.toLowerCase().includes(filter.toLowerCase());
  return node.children?.some((child) => hasMatchingChild(child, filter)) ?? false;
}

// ── Main Component ──

export function SourceViewer({ repoId, highlightEntity, onEntityClick }: SourceViewerProps) {
  const [tree, setTree] = useState<SourceTreeNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileData, setFileData] = useState<SourceFileResponse | null>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const monacoRef = useRef<Monaco | null>(null);
  const decorationsRef = useRef<string[]>([]);

  // Load file tree
  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    setError(null);
    getSourceTree(repoId)
      .then((data) => {
        setTree(data);
        // Auto-expand first two levels
        const dirs = new Set<string>();
        function expandLevels(node: SourceTreeNode, depth: number) {
          if (node.type === "directory" && depth < 3) {
            dirs.add(node.path);
            node.children?.forEach((c) => expandLevels(c, depth + 1));
          }
        }
        expandLevels(data, 0);
        setExpandedDirs(dirs);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [repoId]);

  // Load file content
  const handleFileClick = useCallback(
    async (path: string) => {
      setSelectedFile(path);
      try {
        const data = await getSourceFile(repoId, path);
        setFileData(data);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [repoId]
  );

  const handleToggleDir = useCallback((path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  // Highlight entity in editor
  useEffect(() => {
    if (!highlightEntity || !fileData || !editorRef.current || !monacoRef.current) return;

    const entity = fileData.entities.find((e) => e.fqn === highlightEntity);
    if (!entity) return;

    const monaco = monacoRef.current;
    const editor = editorRef.current;

    // Scroll to entity
    editor.revealLineInCenter(entity.start_line);

    // Apply decoration
    const newDecorations = editor.deltaDecorations(decorationsRef.current, [
      {
        range: new monaco.Range(entity.start_line, 1, entity.end_line, 1),
        options: {
          isWholeLine: true,
          className: "bg-primary/15",
          glyphMarginClassName: "bg-primary",
        },
      },
    ]);
    decorationsRef.current = newDecorations;
  }, [highlightEntity, fileData]);

  // Apply entity gutter markers
  useEffect(() => {
    if (!fileData || !editorRef.current || !monacoRef.current) return;
    if (highlightEntity) return; // skip if highlight is active

    const monaco = monacoRef.current;
    const editor = editorRef.current;

    const decorations = fileData.entities
      .filter((e) => e.mapping)
      .map((e) => ({
        range: new monaco.Range(e.start_line, 1, e.end_line, 1),
        options: {
          isWholeLine: true,
          linesDecorationsClassName: e.mapping?.status === "confirmed"
            ? "border-l-2 border-green-500"
            : "border-l-2 border-yellow-500",
          minimap: { color: e.mapping?.status === "confirmed" ? "#22c55e" : "#eab308", position: 1 },
        },
      }));

    const newDecorations = editor.deltaDecorations(decorationsRef.current, decorations);
    decorationsRef.current = newDecorations;
  }, [fileData, highlightEntity]);

  const handleEditorMount = useCallback(
    (editor: MonacoEditor.IStandaloneCodeEditor, monaco: Monaco) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Click handler: detect clicks on entity lines
      editor.onMouseDown((e) => {
        if (!fileData || !onEntityClick) return;
        const lineNumber = e.target.position?.lineNumber;
        if (!lineNumber) return;

        const entity = fileData.entities.find(
          (ent) => lineNumber >= ent.start_line && lineNumber <= ent.end_line
        );
        if (entity && fileData.path) {
          onEntityClick(entity.fqn, fileData.path);
        }
      });
    },
    [fileData, onEntityClick]
  );

  return (
    <div className="flex flex-col h-full">
      {/* File tree header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/30">
        <span className="text-xs font-medium text-foreground">소스 코드</span>
        <div className="flex-1" />
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="파일 검색..."
            className="pl-6 pr-2 py-0.5 text-[11px] w-32 bg-background border border-border rounded"
          />
        </div>
      </div>

      {/* File tree */}
      <div className="h-48 min-h-[120px] overflow-auto border-b border-border">
        {loading && <p className="text-xs text-muted-foreground p-3">로딩 중...</p>}
        {error && <p className="text-xs text-red-500 p-3">{error}</p>}
        {tree && (
          <div className="py-1">
            {tree.children?.map((child) => (
              <FileTreeItem
                key={child.path}
                node={child}
                depth={0}
                selectedPath={selectedFile}
                expandedDirs={expandedDirs}
                onFileClick={handleFileClick}
                onToggleDir={handleToggleDir}
                filter={filter}
              />
            ))}
          </div>
        )}
      </div>

      {/* Code display */}
      <div className="flex-1 min-h-0">
        {!fileData ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p className="text-xs">파일을 선택하세요</p>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* File path bar */}
            <div className="flex items-center gap-1 px-3 py-1 bg-muted/20 border-b border-border">
              <FileCode size={12} className="text-blue-400" />
              <span className="text-[11px] text-muted-foreground font-mono truncate">{fileData.path}</span>
              {fileData.entities.length > 0 && (
                <span className="ml-auto text-[10px] text-muted-foreground">
                  {fileData.entities.length}개 엔티티
                </span>
              )}
            </div>
            <div className="flex-1 min-h-0">
              <Editor
                language={fileData.language}
                value={fileData.content}
                theme="vs-dark"
                onMount={handleEditorMount}
                options={{
                  readOnly: true,
                  minimap: { enabled: true },
                  fontSize: 13,
                  lineNumbers: "on",
                  scrollBeyondLastLine: false,
                  glyphMargin: true,
                  folding: true,
                  wordWrap: "off",
                  renderLineHighlight: "line",
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/SourceViewer.tsx
git commit -m "feat(modeling): add SourceViewer component with file tree + Monaco"
```

---

## Task 5: Frontend — Mapping Canvas Component

**Files:**
- Create: `frontend/src/components/sections/modeling/MappingCanvas.tsx`

- [ ] **Step 1: Create MappingCanvas component**

```tsx
// frontend/src/components/sections/modeling/MappingCanvas.tsx
"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Panel,
  Handle,
  Position,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "@dagrejs/dagre";
import { Search, GripVertical, Circle } from "lucide-react";
import {
  getOntologyTree,
  getMappings,
  getCodeGraph,
  addMapping,
  removeMapping,
  type DomainNode,
  type MappingEntry,
  type CodeEntity,
} from "@/lib/api/modeling";

interface MappingCanvasProps {
  repoId: string;
  onDomainNodeClick?: (nodeId: string, mappedEntities: string[]) => void;
  onEntityClick?: (fqn: string) => void;
  highlightDomainNode?: string | null;
}

// ── Domain Node Component ──

interface DomainNodeData {
  label: string;
  description: string;
  kind: string;
  mappingCount: number;
  mappingStatus: "confirmed" | "draft" | "none";
  isHighlighted: boolean;
  [key: string]: unknown;
}

function DomainNodeComponent({ data }: NodeProps<Node<DomainNodeData>>) {
  const bgColor =
    data.mappingStatus === "confirmed"
      ? "bg-green-500/10 border-green-500/50"
      : data.mappingStatus === "draft"
      ? "bg-yellow-500/10 border-yellow-500/50"
      : "bg-muted/50 border-border";

  const highlight = data.isHighlighted ? "ring-2 ring-primary ring-offset-1" : "";

  return (
    <div className={`px-3 py-2 rounded-lg border-2 ${bgColor} ${highlight} min-w-[140px]`}>
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground !w-2 !h-2" />
      <div className="text-xs font-medium text-foreground">{data.label}</div>
      {data.mappingCount > 0 && (
        <div className="text-[10px] text-muted-foreground mt-0.5">
          {data.mappingCount}개 코드 연결
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground !w-2 !h-2" />
    </div>
  );
}

const nodeTypes = { domain: DomainNodeComponent };

// ── Layout ──

function layoutGraph(
  nodes: Node<DomainNodeData>[],
  edges: Edge[]
): { nodes: Node<DomainNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80 });

  nodes.forEach((node) => {
    g.setNode(node.id, { width: 160, height: 50 });
  });
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  dagre.layout(g);

  const layoutNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return { ...node, position: { x: pos.x - 80, y: pos.y - 25 } };
  });

  return { nodes: layoutNodes, edges };
}

// ── Entity Panel ──

interface EntityPanelProps {
  entities: CodeEntity[];
  mappings: MappingEntry[];
  filter: string;
  onFilterChange: (f: string) => void;
  onEntityClick: (fqn: string) => void;
  onDragStart: (e: React.DragEvent, fqn: string) => void;
}

function EntityPanel({
  entities,
  mappings,
  filter,
  onFilterChange,
  onEntityClick,
  onDragStart,
}: EntityPanelProps) {
  const mappingMap = useMemo(() => {
    const map = new Map<string, MappingEntry>();
    mappings.forEach((m) => map.set(m.code, m));
    return map;
  }, [mappings]);

  const filtered = useMemo(() => {
    const f = filter.toLowerCase();
    return entities.filter(
      (e) =>
        (e.kind === "class" || e.kind === "interface") &&
        (e.name.toLowerCase().includes(f) || e.id.toLowerCase().includes(f))
    );
  }, [entities, filter]);

  return (
    <div className="border-t border-border bg-background/80">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border">
        <span className="text-[11px] font-medium text-foreground">코드 엔티티</span>
        <div className="flex-1" />
        <div className="relative">
          <Search size={11} className="absolute left-1.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={filter}
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder="검색..."
            className="pl-5 pr-2 py-0.5 text-[10px] w-28 bg-background border border-border rounded"
          />
        </div>
      </div>
      <div className="max-h-[200px] overflow-auto p-1">
        {filtered.map((entity) => {
          const mapping = mappingMap.get(entity.id);
          return (
            <div
              key={entity.id}
              draggable
              onDragStart={(e) => onDragStart(e, entity.id)}
              onClick={() => onEntityClick(entity.id)}
              className="flex items-center gap-2 px-2 py-1 rounded text-[11px] cursor-grab hover:bg-muted/50 group"
            >
              <GripVertical size={10} className="text-muted-foreground/40 group-hover:text-muted-foreground" />
              <Circle
                size={8}
                className={mapping ? "text-green-500 fill-green-500" : "text-red-400 fill-red-400"}
              />
              <span className="truncate flex-1 font-mono">{entity.name}</span>
              {mapping && (
                <span className="text-[9px] text-muted-foreground truncate max-w-[100px]">
                  {mapping.domain.split("/").pop()}
                </span>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <p className="text-[10px] text-muted-foreground p-2">엔티티 없음</p>
        )}
      </div>
    </div>
  );
}

// ── Main Component ──

export function MappingCanvas({
  repoId,
  onDomainNodeClick,
  onEntityClick,
  highlightDomainNode,
}: MappingCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<DomainNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [domainNodes, setDomainNodes] = useState<DomainNode[]>([]);
  const [mappings, setMappings] = useState<MappingEntry[]>([]);
  const [codeEntities, setCodeEntities] = useState<CodeEntity[]>([]);
  const [entityFilter, setEntityFilter] = useState("");
  const [loading, setLoading] = useState(false);

  // Load data
  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    Promise.all([
      getOntologyTree(),
      getMappings(repoId),
      getCodeGraph(repoId),
    ])
      .then(([ontoRes, mapRes, codeRes]) => {
        setDomainNodes(ontoRes.nodes);
        setMappings(mapRes.mappings);
        setCodeEntities(codeRes.entities);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [repoId]);

  // Build graph from domain nodes + mappings
  useEffect(() => {
    if (domainNodes.length === 0) return;

    const mappingsByDomain = new Map<string, MappingEntry[]>();
    mappings.forEach((m) => {
      const list = mappingsByDomain.get(m.domain) || [];
      list.push(m);
      mappingsByDomain.set(m.domain, list);
    });

    const graphNodes: Node<DomainNodeData>[] = domainNodes.map((dn) => {
      const domainMappings = mappingsByDomain.get(dn.id) || [];
      const hasConfirmed = domainMappings.some((m) => m.status === "confirmed");
      return {
        id: dn.id,
        type: "domain",
        position: { x: 0, y: 0 },
        data: {
          label: dn.name,
          description: dn.description || "",
          kind: dn.kind,
          mappingCount: domainMappings.length,
          mappingStatus: domainMappings.length === 0 ? "none" : hasConfirmed ? "confirmed" : "draft",
          isHighlighted: dn.id === highlightDomainNode,
        },
      };
    });

    const graphEdges: Edge[] = domainNodes
      .filter((dn) => dn.parent_id)
      .map((dn) => ({
        id: `${dn.parent_id}-${dn.id}`,
        source: dn.parent_id!,
        target: dn.id,
        type: "smoothstep",
        style: { stroke: "hsl(var(--muted-foreground))", strokeWidth: 1 },
      }));

    const laid = layoutGraph(graphNodes, graphEdges);
    setNodes(laid.nodes);
    setEdges(laid.edges);
  }, [domainNodes, mappings, highlightDomainNode, setNodes, setEdges]);

  // Handle node click
  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (!onDomainNodeClick) return;
      const mapped = mappings
        .filter((m) => m.domain === node.id)
        .map((m) => m.code);
      onDomainNodeClick(node.id, mapped);
    },
    [mappings, onDomainNodeClick]
  );

  // Handle drop (create mapping)
  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const entityFqn = e.dataTransfer.getData("application/entity-fqn");
      if (!entityFqn) return;

      // Find the domain node under the cursor via React Flow's internals
      const target = (e.target as HTMLElement).closest("[data-id]");
      const domainId = target?.getAttribute("data-id");
      if (!domainId) return;

      try {
        await addMapping(repoId, entityFqn, domainId, "user");
        // Refresh mappings
        const mapRes = await getMappings(repoId);
        setMappings(mapRes.mappings);
      } catch (err) {
        console.error("Failed to create mapping:", err);
      }
    },
    [repoId]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "link";
  }, []);

  const handleEntityDragStart = useCallback((e: React.DragEvent, fqn: string) => {
    e.dataTransfer.setData("application/entity-fqn", fqn);
    e.dataTransfer.effectAllowed = "link";
  }, []);

  const handleEntityClick = useCallback(
    (fqn: string) => {
      onEntityClick?.(fqn);
    },
    [onEntityClick]
  );

  if (loading) {
    return <div className="flex items-center justify-center h-full text-xs text-muted-foreground">로딩 중...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Graph area */}
      <div className="flex-1 min-h-0" onDrop={handleDrop} onDragOver={handleDragOver}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls position="top-right" />
          <MiniMap
            position="bottom-right"
            nodeStrokeWidth={3}
            pannable
            zoomable
          />
          <Panel position="top-left">
            <div className="bg-background/80 backdrop-blur-sm rounded px-2 py-1 text-[10px] text-muted-foreground border border-border">
              도메인 노드에 코드 엔티티를 드래그하여 매핑
            </div>
          </Panel>
        </ReactFlow>
      </div>

      {/* Entity panel */}
      <EntityPanel
        entities={codeEntities}
        mappings={mappings}
        filter={entityFilter}
        onFilterChange={setEntityFilter}
        onEntityClick={handleEntityClick}
        onDragStart={handleEntityDragStart}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/MappingCanvas.tsx
git commit -m "feat(modeling): add MappingCanvas with React Flow domain graph + entity panel"
```

---

## Task 6: Frontend — Mapping Workbench (Split Panel Integration)

**Files:**
- Create: `frontend/src/components/sections/modeling/MappingWorkbench.tsx`

- [ ] **Step 1: Create MappingWorkbench container**

```tsx
// frontend/src/components/sections/modeling/MappingWorkbench.tsx
"use client";

import React, { useCallback, useRef, useState } from "react";
import { MappingCanvas } from "./MappingCanvas";
import { SourceViewer } from "./SourceViewer";

interface MappingWorkbenchProps {
  repoId: string;
}

export function MappingWorkbench({ repoId }: MappingWorkbenchProps) {
  const [splitPercent, setSplitPercent] = useState(55);
  const [highlightEntity, setHighlightEntity] = useState<string | null>(null);
  const [highlightDomain, setHighlightDomain] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  // Canvas → Viewer: domain node clicked → show connected entities' source
  const handleDomainNodeClick = useCallback((nodeId: string, mappedEntities: string[]) => {
    setHighlightDomain(null);
    if (mappedEntities.length > 0) {
      setHighlightEntity(mappedEntities[0]);
    }
  }, []);

  // Viewer → Canvas: entity clicked in source → highlight domain node
  const handleEntityClickInViewer = useCallback((fqn: string, _filePath: string) => {
    setHighlightEntity(null);
    // The canvas will highlight the domain node connected to this entity
    setHighlightDomain(fqn);
  }, []);

  // Canvas entity panel → Viewer: entity clicked → open its file
  const handleEntityClickInCanvas = useCallback((fqn: string) => {
    setHighlightEntity(fqn);
  }, []);

  // Resizer
  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.min(Math.max(percent, 25), 75));
    };

    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
  }, []);

  return (
    <div ref={containerRef} className="flex h-full">
      {/* Left: Mapping Canvas */}
      <div style={{ width: `${splitPercent}%` }} className="h-full overflow-hidden">
        <MappingCanvas
          repoId={repoId}
          onDomainNodeClick={handleDomainNodeClick}
          onEntityClick={handleEntityClickInCanvas}
          highlightDomainNode={highlightDomain}
        />
      </div>

      {/* Resizer */}
      <div
        onMouseDown={handleMouseDown}
        className="w-1 bg-border hover:bg-primary/50 cursor-col-resize shrink-0 transition-colors"
      />

      {/* Right: Source Viewer */}
      <div style={{ width: `${100 - splitPercent}%` }} className="h-full overflow-hidden">
        <SourceViewer
          repoId={repoId}
          highlightEntity={highlightEntity}
          onEntityClick={handleEntityClickInViewer}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/MappingWorkbench.tsx
git commit -m "feat(modeling): add MappingWorkbench split-panel with bidirectional linking"
```

---

## Task 7: Frontend — ModelingSection Integration

**Files:**
- Modify: `frontend/src/components/sections/ModelingSection.tsx`

- [ ] **Step 1: Add workbench to ModelingSection**

Changes to `ModelingSection.tsx`:

1. Add import at top:
```tsx
import { MappingWorkbench } from "./modeling/MappingWorkbench";
```

2. Add `"workbench"` to the `ModelingView` type:
```tsx
type ModelingView = "analysis" | "simulation" | "workbench" | "code" | "ontology" | "mapping" | "impact" | "approval";
```

3. Add workbench to `MAIN_NAV` array (after simulation):
```tsx
import { GitBranch } from "lucide-react";
// ...
const MAIN_NAV: NavItem[] = [
  { id: "analysis", label: "분석 콘솔", icon: <Search size={18} />, description: "자연어 영향 분석" },
  { id: "simulation", label: "시뮬레이션", icon: <Zap size={18} />, description: "파라미터 what-if 분석" },
  { id: "workbench", label: "매핑 워크벤치", icon: <GitBranch size={18} />, description: "코드-도메인 시각 매핑" },
];
```

4. Add case in `ViewRouter`:
```tsx
case "workbench":
  return <MappingWorkbench repoId={repoId} />;
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 3: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/ModelingSection.tsx
git commit -m "feat(modeling): integrate MappingWorkbench into sidebar navigation"
```

---

## Task 8: Backend — Entity File Path Resolution for Viewer Linking

The source API needs to resolve which file a code entity belongs to, so the viewer can auto-open the right file when an entity is clicked in the canvas. The `file_path` is stored in Neo4j as a relative path (e.g., `src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java`).

**Files:**
- Modify: `backend/modeling/api/source_api.py`
- Modify: `tests/test_source_api.py`

- [ ] **Step 1: Write failing test for entity lookup endpoint**

Add to `tests/test_source_api.py`:

```python
def test_entity_lookup_returns_file_path(client, sample_repo):
    from backend.modeling.api import source_api
    source_api._neo4j_client.query.return_value = [
        {
            "qualified_name": "com.ontong.scm.inventory.SafetyStockCalculator",
            "file_path": "src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java",
            "line_start": 5,
            "line_end": 37,
        }
    ]

    res = client.get(
        "/api/modeling/source/entity/scm-demo/com.ontong.scm.inventory.SafetyStockCalculator"
    )
    assert res.status_code == 200
    data = res.json()
    assert data["file_path"] == "src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java"
    assert data["line_start"] == 5
    assert data["line_end"] == 37


def test_entity_lookup_not_found(client, sample_repo):
    from backend.modeling.api import source_api
    source_api._neo4j_client.query.return_value = []

    res = client.get("/api/modeling/source/entity/scm-demo/com.does.not.Exist")
    assert res.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py::test_entity_lookup_returns_file_path -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement entity lookup endpoint**

Add to `backend/modeling/api/source_api.py`:

```python
@router.get("/entity/{repo_id}/{qualified_name:path}")
async def get_entity_location(repo_id: str, qualified_name: str):
    """Look up the file path and line range for a code entity."""
    if _neo4j_client is None:
        raise HTTPException(status_code=503, detail="Source API not initialized")

    results = _neo4j_client.query(
        """
        MATCH (e:CodeEntity {repo_id: $repo_id, qualified_name: $qn})
        RETURN e.qualified_name as qualified_name,
               e.file_path as file_path,
               e.line_start as line_start,
               e.line_end as line_end
        """,
        {"repo_id": repo_id, "qn": qualified_name},
    )

    if not results:
        raise HTTPException(status_code=404, detail=f"Entity '{qualified_name}' not found")

    row = results[0]
    return {
        "qualified_name": row["qualified_name"],
        "file_path": row["file_path"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
    }
```

- [ ] **Step 4: Add frontend API function**

Add to `frontend/src/lib/api/modeling.ts`:

```typescript
export interface EntityLocation {
  qualified_name: string;
  file_path: string;
  line_start: number;
  line_end: number;
}

export async function getEntityLocation(repoId: string, fqn: string): Promise<EntityLocation> {
  const res = await fetch(`${API_BASE}/api/modeling/source/entity/${repoId}/${fqn}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 5: Run all tests**

Run: `cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py -v`
Expected: 10 PASS

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 7: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/api/source_api.py tests/test_source_api.py frontend/src/lib/api/modeling.ts
git commit -m "feat(modeling): add entity location lookup API for viewer linking"
```

---

## Task 9: Integration — Wire Entity-to-File Navigation

When an entity is clicked in the MappingCanvas entity panel, the SourceViewer should auto-open the correct file and scroll to the entity's line. This uses the entity lookup API from Task 8.

**Files:**
- Modify: `frontend/src/components/sections/modeling/MappingWorkbench.tsx`
- Modify: `frontend/src/components/sections/modeling/SourceViewer.tsx`

- [ ] **Step 1: Add openFile callback to SourceViewer**

Add a new prop to `SourceViewer`:

```tsx
interface SourceViewerProps {
  repoId: string;
  highlightEntity?: string | null;
  openFilePath?: string | null;       // NEW: auto-open this file
  onEntityClick?: (fqn: string, filePath: string) => void;
}
```

Add useEffect in SourceViewer to auto-open file when `openFilePath` changes:

```tsx
// Auto-open file when openFilePath changes
useEffect(() => {
  if (openFilePath && openFilePath !== selectedFile) {
    handleFileClick(openFilePath);
    // Expand parent directories
    const parts = openFilePath.split("/");
    const dirs = new Set(expandedDirs);
    let current = "";
    for (let i = 0; i < parts.length - 1; i++) {
      current = current ? `${current}/${parts[i]}` : parts[i];
      dirs.add(current);
    }
    setExpandedDirs(dirs);
  }
}, [openFilePath]);
```

- [ ] **Step 2: Update MappingWorkbench to resolve entity locations**

Update `handleEntityClickInCanvas` in `MappingWorkbench.tsx`:

```tsx
import { getEntityLocation } from "@/lib/api/modeling";

// Add state
const [openFilePath, setOpenFilePath] = useState<string | null>(null);

// Update handler
const handleEntityClickInCanvas = useCallback(async (fqn: string) => {
  try {
    const loc = await getEntityLocation(repoId, fqn);
    setOpenFilePath(loc.file_path);
    setHighlightEntity(fqn);
  } catch {
    // Entity not found in Neo4j, just set highlight
    setHighlightEntity(fqn);
  }
}, [repoId]);

// Pass to SourceViewer
<SourceViewer
  repoId={repoId}
  highlightEntity={highlightEntity}
  openFilePath={openFilePath}
  onEntityClick={handleEntityClickInViewer}
/>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 4: Commit**

```bash
cd /Users/donghae/workspace/ai/onTong
git add frontend/src/components/sections/modeling/MappingWorkbench.tsx frontend/src/components/sections/modeling/SourceViewer.tsx
git commit -m "feat(modeling): wire entity-to-file navigation in workbench"
```

---

## Task 10: End-to-End Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

```bash
cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/test_source_api.py -v
```
Expected: 10 PASS

- [ ] **Step 2: Run all existing tests (regression check)**

```bash
cd /Users/donghae/workspace/ai/onTong && .venv/bin/python -m pytest tests/ -v --timeout=30
```
Expected: all existing tests still pass

- [ ] **Step 3: TypeScript build check**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npx tsc --noEmit
```
Expected: clean

- [ ] **Step 4: Start backend and verify source API**

```bash
# Terminal 1: Start backend
cd /Users/donghae/workspace/ai/onTong
source .venv/bin/activate && set -a && source .env && set +a
uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Terminal 2: Test source API
# 1. Seed demo
curl -s -X POST http://localhost:8001/api/modeling/seed/scm-demo | python3 -m json.tool

# 2. File tree
curl -s http://localhost:8001/api/modeling/source/tree/scm-demo | python3 -m json.tool

# 3. File content with entity positions
curl -s "http://localhost:8001/api/modeling/source/file/scm-demo?path=src/main/java/com/ontong/scm/inventory/SafetyStockCalculator.java" | python3 -m json.tool

# 4. Entity lookup
curl -s http://localhost:8001/api/modeling/source/entity/scm-demo/com.ontong.scm.inventory.SafetyStockCalculator | python3 -m json.tool
```

Expected:
- File tree returns directory structure with Java files
- File content returns source with `entities` array containing line positions
- Entity lookup returns `file_path` and `line_start`/`line_end`

- [ ] **Step 5: Start frontend and verify UI**

```bash
cd /Users/donghae/workspace/ai/onTong/frontend && npm run dev
```

Browser verification:
1. Navigate to http://localhost:3000 → Modeling tab
2. Click "SCM 데모 프로젝트 로드"
3. Click "매핑 워크벤치" in sidebar
4. Verify: left panel shows SCOR domain graph with colored nodes (green = mapped)
5. Verify: right panel shows file tree with Java files
6. Click a Java file → Monaco editor shows syntax-highlighted source
7. Click a domain node in graph → entity panel shows connected entities
8. Click an entity → source viewer opens the file and scrolls to the entity
9. Drag an unmapped entity to a domain node → mapping created, node turns green

- [ ] **Step 6: Update health endpoint**

Add `"source_viewer"` to capabilities in `backend/modeling/api/modeling.py`:

```python
"capabilities": [
    "code_analysis",
    "ontology_management",
    "mapping_management",
    "impact_analysis",
    "approval_workflow",
    "simulation",
    "engine_query",
    "source_viewer",
],
```

- [ ] **Step 7: Commit verification results**

```bash
cd /Users/donghae/workspace/ai/onTong
git add backend/modeling/api/modeling.py
git commit -m "feat(modeling): add source_viewer to health capabilities"
```
