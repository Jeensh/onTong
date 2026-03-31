// ── Wiki ──────────────────────────────────────────────────────────────

export type DocumentStatus = "draft" | "review" | "approved" | "deprecated" | "";

export interface DocumentMetadata {
  domain: string;
  process: string;
  error_codes: string[];
  tags: string[];
  status: DocumentStatus;
  supersedes: string;
  superseded_by: string;
  related: string[];
  created: string;
  updated: string;
  created_by: string;
  updated_by: string;
  /** Backward-compatible alias for created_by (computed on backend) */
  author?: string;
}

export interface WikiFile {
  path: string;
  title: string;
  content: string;
  raw_content: string;
  metadata: DocumentMetadata;
  tags: string[];
  links: string[];
}

export interface MetadataSuggestion {
  domain: string;
  process: string;
  error_codes: string[];
  tags: string[];
  confidence: number;
  reasoning: string;
}

export interface MetadataTagsResponse {
  domains: string[];
  processes: string[];
  error_codes: string[];
  tags: string[];
}

export interface WikiTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  children: WikiTreeNode[];
  has_children?: boolean | null;  // true if dir has unloaded children (lazy loading)
}

// ── Search ────────────────────────────────────────────────────────────

export interface SearchIndexEntry {
  id: string;
  path: string;
  title: string;
  content: string;
  tags: string[];
}

export interface BacklinkMap {
  forward: Record<string, string[]>;
  backward: Record<string, string[]>;
}

export interface TagIndex {
  tags: Record<string, string[]>;
}

// ── Graph ────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  title: string;
  status: string;
  tags: string[];
  domain: string;
  depth: number;
  node_type?: string; // "document" | "skill"
}

export interface GraphEdge {
  source: string;
  target: string;
  type: "wiki-link" | "supersedes" | "related" | "similar";
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ── User-Facing Skills ───────────────────────────────────────────────

export interface SkillMeta {
  path: string;
  title: string;
  description: string;
  trigger: string[];
  icon: string;
  scope: "personal" | "shared";
  enabled: boolean;
  created_by: string;
  updated: string;
  referenced_docs: string[];
  category: string;
  priority: number;
  pinned: boolean;
}

export interface SkillListResponse {
  system: SkillMeta[];
  personal: SkillMeta[];
  categories: string[];
}

export interface SkillCreateRequest {
  title: string;
  description?: string;
  trigger?: string[];
  icon?: string;
  scope?: "personal" | "shared";
  instructions?: string;
  referenced_docs?: string[];
  category?: string;
  priority?: number;
  pinned?: boolean;
  role?: string;              // ## 역할 — persona/tone
  workflow?: string;          // ## 워크플로우 — phased steps
  checklist?: string;         // ## 체크리스트 — include/exclude
  output_format?: string;     // ## 출력 형식 — response structure
  self_regulation?: string;   // ## 제한사항 — limits/boundaries
}

export interface SkillContext {
  instructions: string;
  role: string;
  workflow: string;
  checklist: string;
  output_format: string;
  self_regulation: string;
  referenced_doc_contents: [string, string][];
  preamble_docs_found: number;
  preamble_docs_missing: string[];
}

export interface HybridSearchResult {
  path: string;
  title: string;
  snippet: string;
  score: number;
  tags: string[];
  status: string;
}
