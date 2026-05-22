/**
 * Section 3 시뮬레이션 에이전트 HTTP client.
 * multiturn.ts 패턴 차용. /api/section3/simulation/* 호출.
 */

const API_BASE = "/api/section3/simulation";

export type SimulationGate =
  | "intent_classified"
  | "target_selected"
  | "bundle_prepared"
  | "executed"
  | "done"
  | "aborted";

export interface StartRequest {
  user_query: string;
  repo_id: string;
}

export interface StartResponse {
  session_id: string;
  next_gate: SimulationGate;
  payload: Record<string, unknown> | null;
  message: string;
}

export interface RespondRequest {
  turn_no: number;
  user_response: Record<string, unknown>;
}

export interface RespondResponse {
  session_id: string;
  next_gate: SimulationGate;
  payload: Record<string, unknown> | null;
  message: string;
}

export interface ReplayDecision {
  turn_no: number;
  gate_kind: string;
  payload: Record<string, unknown>;
  user_response: Record<string, unknown> | null;
  created_at: string;
}

export interface ReplayResponse {
  session_id: string;
  repo_id: string;
  intent: string | null;
  status: string;
  user_query: string | null;
  created_at: string;
  last_activity_at: string;
  decisions: ReplayDecision[];
}

async function _post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`API ${r.status}: ${txt}`);
  }
  return (await r.json()) as T;
}

async function _get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`API ${r.status}: ${txt}`);
  }
  return (await r.json()) as T;
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "term" | "action" | "code_method" | "code_type" | "rule";
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface GraphResponse {
  target_fqn: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  note: string;
}

export interface DomainTableView {
  table_name: string;
  jpa_class: string;
  jpa_file: string;
  category: string;
  pk_columns: string[];
  column_count: number;
  row_count: number;
}

export interface DomainColumnView {
  name: string;
  java_field: string;
  is_pk: boolean;
  length: number | null;
  precision: number | null;
  scale: number | null;
  type_hint: string;
}

export interface DomainTableDetail {
  table_name: string;
  jpa_class: string;
  jpa_file: string;
  category: string;
  columns: DomainColumnView[];
  pk_columns: string[];
  rows: Record<string, unknown>[];
  row_count_total: number;
}

export interface MethodBodyView {
  method_fqn: string;
  body: string;
  file_path: string;
  line_start: number | null;
  line_end: number | null;
  annotations: string[];
  callers: string[];
  callees: string[];
}

export const simulationApi = {
  start: (req: StartRequest) => _post<StartResponse>("/start", req),
  respond: (sid: string, req: RespondRequest) =>
    _post<RespondResponse>(`/respond/${sid}`, req),
  replay: (sid: string) => _get<ReplayResponse>(`/replay/${sid}`),
  graph: (sid: string) => _get<GraphResponse>(`/graph/${sid}`),
  listTables: () => _get<DomainTableView[]>("/data/tables"),
  getTable: (name: string) => _get<DomainTableDetail>(`/data/table/${name}`),
  methodBody: (fqn: string, repoId = "slab-design-real-v2") =>
    _get<MethodBodyView>(`/method/body?fqn=${encodeURIComponent(fqn)}&repo_id=${encodeURIComponent(repoId)}`),
  hypothesis: (req: HypothesisRequest) => _post<HypothesisResponse>("/hypothesis/run", req),
  suggestedQuestions: (seed = 0) => _get<SuggestedQuestionView[]>(`/suggested_questions?seed=${seed}`),
  termLookup: (text: string) => _post<DetectedTermView[]>("/term_lookup", { text }),
  impactCompare: (req: ImpactCompareRequest) => _post<ImpactCompareResponse>("/impact/compare_slab", req),
};

export interface ImpactCompareRequest {
  table: string;
  column: string;
  before?: string | null;
  after?: string | null;
  order_no: string;
  cmp_cd?: string;
  org_cd?: string;
  affected_method_fqns?: string[];
}

export interface TranspiledMethod {
  fqn: string;
  class_name?: string;
  method_name?: string;
  java: string;
  java_truncated?: boolean;
  python: string;
  python_truncated?: boolean;
  idiom_diffs?: { idiom_name?: string; summary?: string }[];
  line_start?: number;
  line_end?: number;
  error?: string;
}

export interface ImpactCompareResponse {
  ok: boolean;
  order_no: string;
  target: { table: string; column: string; before: string | null; after: string | null };
  baseline_slab: Record<string, unknown> | null;
  projected_slab: Record<string, unknown> | null;
  diff: { field: string; before: unknown; after: unknown; delta: number | null; delta_pct: number | null }[];
  notes: string[];
  transpiled_methods: TranspiledMethod[];
  error?: string;
  error_code?: string;
}

export interface HypothesisRequest {
  base_grade?: string;
  new_grade?: string;
  productivity_multiplier?: number;
  base_order_no?: string;
}

export interface SuggestedQuestionView {
  intent: string;
  label: string;
  query: string;
  rationale: string;
  grounded_terms: { token: string; term_fqn: string; label: string; definition: string }[];
}

export interface DetectedTermView {
  token: string;
  term_fqn: string;
  label: string;
  definition: string;
  aliases: string[];
}

export interface HypothesisResponse {
  base_grade: string;
  new_grade: string;
  productivity_multiplier: number;
  base_order_no: string;
  existing_productivity_rows: Record<string, unknown>[];
  existing_order_rows: Record<string, Record<string, unknown>>;
  virtual_productivity_rows: Record<string, unknown>[];
  virtual_order_rows: Record<string, Record<string, unknown>>;
  baseline_slab: Record<string, unknown> | null;
  baseline_trace: Record<string, unknown>[];
  projected_slab: Record<string, unknown> | null;
  diff_summary: { field: string; before: number; after: number; delta: number; delta_pct: number }[];
  notes: string[];
}
