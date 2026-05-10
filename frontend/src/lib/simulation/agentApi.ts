// Section 3 v3 — Agent 4종 API 클라이언트.
//
// 모든 Agent 응답에 ontology_trace 필드가 포함되어 그래프 시각화에 직접 사용.

const API_BASE = "";

// ─── 공통: OntologyTrace ────────────────────────────────────────────

export interface OntologyTrace {
  nodes: { id: string; label: string; group: string }[];
  edges: { from: string; to: string; label?: string }[];
  seed_ids?: string[];
  path_edge_keys?: string[];
  cypher: string;
}

// ─── Agent 1 (영향도) ───────────────────────────────────────────────

export type ChangeKind = "program" | "data";
export type TargetType =
  | "method"
  | "class"
  | "table"
  | "column"
  | "standard_value"
  | "order";
export type ModificationType = "logic" | "signature" | "deletion" | "value_change";

export interface Agent1Request {
  change_kind: ChangeKind;
  target_type: TargetType;
  target_id: string;
  modification_type: ModificationType;
  new_value?: string | null;
  sample_size?: number;
  run_sandbox?: boolean;
}

export interface Agent1MetricStats {
  n: number;
  mean: number;
  median: number;
  min: number;
  max: number;
}

export interface Agent1MetricDiff {
  before: Agent1MetricStats;
  after: Agent1MetricStats;
  delta_mean: number;
  delta_pct: number;
  changed_orders: number;
  before_values: number[];
  after_values: number[];
}

export interface StageTransitions {
  ok_to_ok: number;
  ok_to_fail: number;
  fail_to_ok: number;
  fail_to_fail: number;
}

export interface Agent1DiffSummary {
  sample_size: number;
  metrics: Record<string, Agent1MetricDiff>;
  affected_count: number;
  failure_count_before: number;
  failure_count_after: number;
  stage_transitions?: StageTransitions;
  case_pairs: Array<Record<string, number>>;
}

export interface Agent1VizData {
  histograms: Record<string, {
    before_values: number[];
    after_values: number[];
    delta_mean: number;
    delta_pct: number;
  }>;
  case_pairs: Array<Record<string, number>>;
  affected_count: number;
  sample_size: number;
}

export interface Agent1Result {
  request_id: string;
  status: "success" | "partial" | "need_more_info" | "unsupported" | "error";
  summary: string;
  direct_impact: Record<string, unknown>;
  indirect_impact: Record<string, unknown>;
  risk_level?: "HIGH" | "MEDIUM" | "LOW" | null;
  risk_factors: string[];
  ontology_trace?: OntologyTrace | null;
  raw_message?: string | null;
  diff_summary?: Agent1DiffSummary | null;
  viz_data?: Agent1VizData | null;
}

export async function runAgent1(req: Agent1Request): Promise<Agent1Result> {
  const res = await fetch(`${API_BASE}/api/simulation/agents/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Agent 1 failed: ${res.status}`);
  return res.json();
}

// ─── Agent 2 (테스트 데이터) ────────────────────────────────────────

export type CaseType = "normal" | "boundary" | "error" | "performance";

export interface Agent2Request {
  target_type: "step" | "method" | "standard";
  target_id: string;
  case_types: CaseType[];
  test_count: number;
}

export interface TestCase {
  case_id: string;
  case_type: string;
  description: string;
  input_data: Record<string, unknown>;
  expected_output: Record<string, unknown>;
}

export interface Agent2Result {
  request_id: string;
  status: string;
  summary: string;
  test_cases: TestCase[];
  code_skeleton: string;
  data_dependencies: string[];
  ontology_trace?: OntologyTrace | null;
  raw_message?: string | null;
}

export async function runAgent2(req: Agent2Request): Promise<Agent2Result> {
  const res = await fetch(`${API_BASE}/api/simulation/agents/test-data`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Agent 2 failed: ${res.status}`);
  return res.json();
}

// ─── Agent 3 (위치 파악) ────────────────────────────────────────────

export type LocatorScope = "source" | "table" | "process";

export interface Agent3Request {
  natural_language_query: string;
  search_scope?: LocatorScope[];
  include_preview?: boolean;
  preview_lines?: number;
}

export interface Agent3SourceLocation {
  file_path: string;
  class_name?: string | null;
  method_name?: string | null;
  line?: number | null;
  preview?: string | null;  // 코드 snippet (Phase 3 신규)
  step_id?: string | null;  // sandbox handoff 힌트
}

export interface Agent3Result {
  request_id: string;
  status: string;
  summary: string;
  matched_terms: {
    id?: string;
    korean?: string;
    english?: string;
    category?: string;
    description?: string;
  }[];
  process_locations: {
    step_number?: number;
    korean_name?: string;
    roles?: string[];
  }[];
  source_locations: Agent3SourceLocation[];
  data_locations: {
    table_name?: string;
    standard_code?: string;
    schema_name?: string;
  }[];
  related_terms: {
    id?: string;
    korean?: string;
    english?: string;
    relation?: string;
  }[];
  extraction_method: "explicit" | "llm" | "split" | "none";
  extracted_keywords: string[];
  ontology_trace?: OntologyTrace | null;
  raw_message?: string | null;
  handoff_step_id?: string | null;  // Phase 3 신규
}

export async function runAgent3(req: Agent3Request): Promise<Agent3Result> {
  const res = await fetch(`${API_BASE}/api/simulation/agents/locator`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`Agent 3 failed: ${res.status}`);
  return res.json();
}

// ─── Section 2 직접 호출 ────────────────────────────────────────────

export interface TermSearchResult {
  id: string;
  name: string;
  english: string;
  category: string;
  description: string;
}

export async function searchTerms(q: string, limit = 10): Promise<TermSearchResult[]> {
  if (!q.trim()) return [];
  const res = await fetch(
    `${API_BASE}/api/modeling/ontology/term/search?q=${encodeURIComponent(q)}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`term search failed: ${res.status}`);
  return res.json();
}

export interface GraphStats {
  nodes: Record<string, number>;
  relations: Record<string, number>;
  totals: { nodes: number; relations: number };
}

export async function fetchGraphStats(): Promise<GraphStats> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/graph/stats`);
  if (!res.ok) throw new Error(`graph stats failed: ${res.status}`);
  return res.json();
}

// ─── Agent 4 — 온톨로지 익스플로러 ──────────────────────────────────

export interface OntologyExpandRequest {
  node_id: string;
  hops?: 1 | 2;
}

export interface OntologyExpandResult {
  node_id: string;
  trace: OntologyTrace;
}

export async function expandOntologyNode(
  req: OntologyExpandRequest
): Promise<OntologyExpandResult> {
  const res = await fetch(`${API_BASE}/api/simulation/agents/explorer/expand`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`expand failed: ${res.status}`);
  return res.json();
}

export interface OntologyPathRequest {
  from_id: string;
  to_id: string;
  max_hops?: number;
}

export interface OntologyPathResult {
  from_id: string;
  to_id: string;
  found: boolean;
  trace: OntologyTrace;
}

export async function findOntologyPath(
  req: OntologyPathRequest
): Promise<OntologyPathResult> {
  const res = await fetch(`${API_BASE}/api/simulation/agents/explorer/path`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`path failed: ${res.status}`);
  return res.json();
}

export interface OntologySearchResult {
  nodes: {
    id: string;
    label: string;
    group: string;
    snippet?: string;
  }[];
}

export async function searchOntologyNodes(
  query: string,
  groups?: string[]
): Promise<OntologySearchResult> {
  const params = new URLSearchParams({ q: query });
  if (groups && groups.length > 0) params.append("groups", groups.join(","));
  const res = await fetch(
    `${API_BASE}/api/simulation/agents/explorer/search?${params}`
  );
  if (!res.ok) throw new Error(`node search failed: ${res.status}`);
  return res.json();
}
