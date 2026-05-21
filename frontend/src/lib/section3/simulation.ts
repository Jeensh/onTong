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

export const simulationApi = {
  start: (req: StartRequest) => _post<StartResponse>("/start", req),
  respond: (sid: string, req: RespondRequest) =>
    _post<RespondResponse>(`/respond/${sid}`, req),
  replay: (sid: string) => _get<ReplayResponse>(`/replay/${sid}`),
  graph: (sid: string) => _get<GraphResponse>(`/graph/${sid}`),
  listTables: () => _get<DomainTableView[]>("/data/tables"),
  getTable: (name: string) => _get<DomainTableDetail>(`/data/table/${name}`),
};
