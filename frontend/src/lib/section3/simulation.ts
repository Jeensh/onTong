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

export const simulationApi = {
  start: (req: StartRequest) => _post<StartResponse>("/start", req),
  respond: (sid: string, req: RespondRequest) =>
    _post<RespondResponse>(`/respond/${sid}`, req),
  replay: (sid: string) => _get<ReplayResponse>(`/replay/${sid}`),
};
