"""Shared Pydantic schemas for the entire application."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, computed_field


# ── Wiki ──────────────────────────────────────────────────────────────

class DocumentMetadata(BaseModel):
    domain: str = ""
    process: str = ""
    error_codes: list[str] = []
    tags: list[str] = []
    status: str = ""          # document lifecycle: draft | review | approved | deprecated
    supersedes: str = ""      # file path this doc replaces (newer version of)
    superseded_by: str = ""   # file path that replaces this doc (older version)
    related: list[str] = []   # file paths of related documents
    created: str = ""         # ISO date — set once on first save
    updated: str = ""         # ISO date — refreshed on every save
    created_by: str = ""      # original author (user name)
    updated_by: str = ""      # last modifier (user name)

    @computed_field
    @property
    def author(self) -> str:
        """Backward-compatible alias for created_by."""
        return self.created_by


class WikiFile(BaseModel):
    path: str
    title: str
    content: str  # body without frontmatter
    raw_content: str = ""  # original content including frontmatter
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    links: list[str] = []  # forward [[wiki-link]] targets

    @computed_field
    @property
    def tags(self) -> list[str]:
        """Backward-compatible tags accessor from metadata."""
        return self.metadata.tags


class MetadataSuggestion(BaseModel):
    domain: str = ""
    process: str = ""
    error_codes: list[str] = []
    tags: list[str] = []
    confidence: float = 0.0
    reasoning: str = ""


class WikiTreeNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: list[WikiTreeNode] = []
    has_children: bool | None = None  # True if dir has children (for lazy loading)


# ── Search ────────────────────────────────────────────────────────────

class SearchIndexEntry(BaseModel):
    id: str
    path: str
    title: str
    content: str
    tags: list[str] = []


class BacklinkMap(BaseModel):
    forward: dict[str, list[str]] = {}   # file -> links_to
    backward: dict[str, list[str]] = {}  # file -> linked_from


class TagIndex(BaseModel):
    tags: dict[str, list[str]] = {}  # tag -> file_paths


class HybridSearchResult(BaseModel):
    path: str
    title: str
    snippet: str
    score: float
    tags: list[str] = []
    status: str = ""


# ── Graph ────────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str          # file path
    title: str
    status: str = ""
    tags: list[str] = []
    domain: str = ""
    depth: int = 0   # BFS distance from center node
    node_type: str = "document"  # "document" | "skill"

class GraphEdge(BaseModel):
    source: str      # source file path
    target: str      # target file path
    type: str        # "wiki-link" | "supersedes" | "related" | "similar"

class GraphData(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


# ── Router ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    attached_files: list[str] = Field(default_factory=list)  # file paths to force-reference
    skill_path: str | None = None  # explicit user-skill invocation


class RouterDecision(BaseModel):
    agent: Literal["WIKI_QA", "SIMULATION", "DEBUG_TRACE", "UNKNOWN"]
    confidence: float
    reasoning: str


# ── Agent Response & SSE Events ───────────────────────────────────────

class SourceRef(BaseModel):
    doc: str
    relevance: float = 0.0
    updated: str = ""         # last modified date
    updated_by: str = ""      # last modifier
    status: str = ""          # document lifecycle status


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class ThinkingStepEvent(BaseModel):
    """Pipeline progress step shown to user during RAG processing."""
    event: Literal["thinking_step"] = "thinking_step"
    step: str          # step identifier: "query_augment", "vector_search", "clarity_check", "answer_gen"
    status: str        # "start", "done"
    label: str         # human-readable Korean label
    detail: str = ""   # optional detail (e.g., augmented query, doc count)


class ContentDelta(BaseModel):
    event: Literal["content_delta"] = "content_delta"
    delta: str


class SourcesEvent(BaseModel):
    event: Literal["sources"] = "sources"
    sources: list[SourceRef]


class ApprovalRequestEvent(BaseModel):
    event: Literal["approval_request"] = "approval_request"
    action_id: str
    action_type: str
    path: str
    diff_preview: str


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    error_code: str
    message: str
    retry_hint: str | None = None


class ConflictWarningEvent(BaseModel):
    """Emitted when RAG pipeline detects contradictory information across documents."""
    event: Literal["conflict_warning"] = "conflict_warning"
    details: str          # human-readable conflict description
    conflicting_docs: list[str] = []  # file paths of conflicting documents


class DoneEvent(BaseModel):
    event: Literal["done"] = "done"
    usage: TokenUsage | None = None


# ── Human-in-the-loop ─────────────────────────────────────────────────

class WikiWriteAction(BaseModel):
    type: Literal["wiki_write"] = "wiki_write"
    path: str
    content: str
    diff_preview: str = ""


class WikiEditAction(BaseModel):
    type: Literal["wiki_edit"] = "wiki_edit"
    path: str
    content: str
    diff_preview: str = ""


class WikiDeleteAction(BaseModel):
    type: Literal["wiki_delete"] = "wiki_delete"
    path: str


ApprovalAction = WikiWriteAction | WikiEditAction | WikiDeleteAction


class ApprovalRequest(BaseModel):
    session_id: str
    action_id: str
    approved: bool


# ── Error ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    retry_hint: str | None = None


class UnknownIntentResponse(BaseModel):
    message: str = "질문을 더 구체적으로 해주세요."
    available_agents: list[str] = ["WIKI_QA", "SIMULATION", "DEBUG_TRACE"]
    examples: list[str] = [
        "Wiki에서 KV 캐시 장애 대응 절차 찾아줘",
        "DG320 주문이 왜 사라졌는지 추적해줘",
        "직원정보 문서에 신규 입사자 추가해줘",
    ]


# ── User-Facing Skills ──────────────────────────────────────────────

class SkillMeta(BaseModel):
    """Metadata for a user-facing skill document stored in _skills/."""
    path: str
    title: str
    description: str = ""
    trigger: list[str] = []
    icon: str = "⚡"
    scope: Literal["personal", "shared"] = "personal"
    enabled: bool = True
    created_by: str = ""
    updated: str = ""
    referenced_docs: list[str] = []  # [[wikilink]] targets extracted from body
    category: str = ""        # folder-derived or frontmatter-specified category
    priority: int = 5         # 1~10, higher = matched first (default 5)
    pinned: bool = False      # always show at top in UI


class SkillListResponse(BaseModel):
    system: list[SkillMeta] = []    # _skills/ shared skills
    personal: list[SkillMeta] = []  # _skills/@{username}/ personal skills
    categories: list[str] = []     # all unique categories (sorted)


class SkillContext(BaseModel):
    """Structured context extracted from a 6-layer skill document."""
    instructions: str = ""           # ## 지시사항
    role: str = ""                   # ## 역할
    workflow: str = ""               # ## 워크플로우
    checklist: str = ""              # ## 체크리스트
    output_format: str = ""          # ## 출력 형식
    self_regulation: str = ""        # ## 제한사항
    referenced_doc_contents: list[tuple[str, str]] = []  # (title, content) pairs
    # Preamble (runtime-computed, not from markdown)
    preamble_docs_found: int = 0
    preamble_docs_missing: list[str] = []
    preamble_date: str = ""
    preamble_user: str = ""


class SkillCreateRequest(BaseModel):
    title: str
    description: str = ""
    trigger: list[str] = []
    icon: str = "⚡"
    scope: Literal["personal", "shared"] = "personal"
    instructions: str = ""          # body text for ## 지시사항
    referenced_docs: list[str] = []  # [[wikilink]] target paths
    category: str = ""
    priority: int = 5
    pinned: bool = False
    role: str = ""                  # ## 역할 — persona/tone
    workflow: str = ""              # ## 워크플로우 — phased steps
    checklist: str = ""             # ## 체크리스트 — include/exclude
    output_format: str = ""         # ## 출력 형식 — response structure
    self_regulation: str = ""       # ## 제한사항 — limits/boundaries
