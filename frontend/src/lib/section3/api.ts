/**
 * Section 3 — backend API client.
 *
 * 모든 agent endpoint 는 SSE (text/event-stream) 스트리밍. fetch + ReadableStream 으로
 * event 단위 파싱.
 */

export type StreamEvent =
  | { type: "thinking"; payload: { message: string }; timestamp: string }
  | { type: "intent_classification"; payload: IntentClassificationPayload; timestamp: string }
  | { type: "modeling_call"; payload: { intent: string; parameters: Record<string, unknown> }; timestamp: string }
  | { type: "modeling_result"; payload: { response: ModelingResponse }; timestamp: string }
  | { type: "layer_scan"; payload: { layer: string; items: Array<Record<string, unknown>> }; timestamp: string }
  | { type: "code_gen"; payload: { source: string }; timestamp: string }
  | { type: "sandbox_run"; payload: { message: string }; timestamp: string }
  | { type: "sandbox_result"; payload: { result: SandboxCaseResult[] }; timestamp: string }
  | { type: "final"; payload: AgentFinalPayload; timestamp: string }
  | { type: "error"; payload: { message: string; [k: string]: unknown }; timestamp: string }
  | { type: "need_more_info"; payload: { missing_info: MissingInfo }; timestamp: string };

export interface IntentClassificationPayload {
  modeling_intent: "impact_analysis" | "simulate" | "explain";
  parameters: Record<string, unknown>;
  confidence: number;
  reasoning: string;
  suggested_followups: string[];
}

export interface ModelingResponse {
  request_id: string;
  status: string;
  confidence?: number;
  result?: Record<string, unknown> | null;
  missing_info?: MissingInfo | null;
  timestamp?: string;
}

export interface MissingInfo {
  reason: string;
  questions: Array<{
    field: string;
    question: string;
    input_type: "text" | "select" | "number" | "boolean";
    options?: Array<{ id: string; label: string }>;
    default_value?: unknown;
  }>;
}

export interface SandboxCaseResult {
  case_id: string;
  case_type: "normal" | "boundary" | "error";
  input: Record<string, unknown>;
  expected_output: Record<string, unknown> | null;
  execution: {
    ok: boolean;
    result: Record<string, unknown> | null;
    stdout: string;
    stderr: string;
    elapsed_sec: number;
    error: string | null;
    returncode: number;
  };
  matched_expected: boolean | null;
}

export interface AgentFinalPayload {
  ok: boolean;
  summary: string;
  modeling_response?: ModelingResponse | null;
  generated_python?: string | null;
  sandbox_result?: {
    cases: SandboxCaseResult[];
    ok_count: number;
    matched_count: number;
  } | null;
  visualization?: {
    nodes?: Array<{ id: string; label: string; group: string }>;
    edges?: Array<{ from: string; to: string; label?: string }>;
    cypher?: string;
  } | null;
  /** legacy /api/ontology/* 에서 가져온 보강 정보 (modeling graph 가 빈약할 때 채움) */
  legacy_enrich?: LegacyEnrich | null;
  error?: string | null;
}

export interface LegacyEnrich {
  /** 메서드의 실 Java body_text + line 범위 */
  source_code?: Array<{
    method_fqn: string;
    body_text: string;
    line_start?: number;
    line_end?: number;
    source_file?: string;
    role?: string;
    annotations?: string[];
  }>;
  /** 영향 받는 비즈니스 룰 + 과거 incident */
  business_rules?: Array<{
    fqn: string;
    statement: string;
    severity?: string;
    enforced_by?: string[];
    operational_history?: Array<{ incident_id?: string; summary?: string; occurred_at?: string }>;
  }>;
  /** anchor — 코드 라인 ↔ action slot 매핑 */
  anchors?: Array<{
    id: string;
    anchor_locator?: string;
    target_slot?: string;
    target_action_fqn?: string;
    code_method_fqn?: string;
    line?: number;
    confidence?: number;
  }>;
  /** action.realizations[] */
  action_realizations?: Array<{ code_method_fqn: string; confidence?: number; scope?: string; rationale?: string }>;
  /** delegates-to-tree */
  delegates_tree?: { action_fqn: string; children: unknown[]; cycle_detected: boolean };
  /** call-sites (confidence>0.5 또는 needs_user_confirm) */
  call_sites?: Array<{ callee_simple_name: string; line?: number; needs_user_confirm?: boolean; analysis_source?: string }>;
  /** legacy /api/ontology/search hits */
  search_hits?: Array<Record<string, unknown>>;
  queries?: string[];
}

// ─── SSE consumer ───────────────────────────────────────────

/** POST + SSE 응답 파싱. event 단위로 콜백. */
export async function streamSSE(
  url: string,
  body: unknown,
  onEvent: (ev: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`SSE fetch failed: ${resp.status} ${await resp.text()}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    // SSE 는 `\n\n` 으로 event 구분
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const ev = parseSSEChunk(chunk);
      if (ev) onEvent(ev);
    }
  }
}

function parseSSEChunk(chunk: string): StreamEvent | null {
  const lines = chunk.split("\n");
  let dataLine = "";
  for (const ln of lines) {
    if (ln.startsWith("data:")) {
      dataLine = ln.slice(5).trim();
    }
  }
  if (!dataLine) return null;
  try {
    return JSON.parse(dataLine) as StreamEvent;
  } catch {
    return null;
  }
}

// ─── Endpoint wrappers ──────────────────────────────────────

/**
 * SSE 는 Next.js dev rewrites() proxy 가 buffering 하기 때문에 backend 직접 호출.
 * 일반 GET 은 proxy 그대로 (CORS 안 타도 됨).
 * 환경변수 NEXT_PUBLIC_BACKEND_URL 로 override (default: localhost:8001).
 */
const BACKEND_DIRECT =
  (typeof window !== "undefined" && (window as any).__BACKEND_URL__) ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8001";
const SSE_BASE = `${BACKEND_DIRECT}/api/section3`;
const BASE = "/api/section3";

export interface ChatBody {
  message: string;
  history?: Array<{ role: "user" | "assistant" | "system"; content: string; timestamp?: string }>;
  session_id?: string;
}

export interface SandboxBody {
  target_kind: "step" | "method" | "class";
  target_id: string;
  case_types?: Array<"normal" | "boundary" | "error">;
  run_after_generate?: boolean;
}

export interface CodeImpactBody {
  target_kind: "method" | "class" | "column";
  target_id: string;
}

export interface DataImpactBody {
  target_kind: "table" | "standard_value" | "order";
  target_id: string;
}

export function chat(body: ChatBody, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal) {
  return streamSSE(`${SSE_BASE}/chat`, body, onEvent, signal);
}
export function runSandbox(body: SandboxBody, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal) {
  return streamSSE(`${SSE_BASE}/sandbox/run`, body, onEvent, signal);
}
export function runCodeImpact(body: CodeImpactBody, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal) {
  return streamSSE(`${SSE_BASE}/code-impact`, body, onEvent, signal);
}
export function runDataImpact(body: DataImpactBody, onEvent: (ev: StreamEvent) => void, signal?: AbortSignal) {
  return streamSSE(`${SSE_BASE}/data-impact`, body, onEvent, signal);
}

export async function getStats(): Promise<{ nodes: Record<string, number>; relations: Record<string, number>; totals?: Record<string, number> }> {
  const r = await fetch(`${BASE}/stats`);
  if (!r.ok) throw new Error(`stats: ${r.status}`);
  return r.json();
}

export async function termSearch(q: string): Promise<Array<{ id: string; name: string; english?: string; category?: string; description?: string }>> {
  const r = await fetch(`${BASE}/term-search?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error(`term-search: ${r.status}`);
  const body = await r.json();
  return body.items ?? [];
}
