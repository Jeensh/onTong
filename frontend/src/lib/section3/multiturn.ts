/**
 * Section 3 multiturn agent — API client.
 *
 * endpoints:
 *   POST   /api/section3/multiturn/start                 — session 생성 + Gate I stub
 *   POST   /api/section3/multiturn/respond/{sid}         — gate progression
 *   POST   /api/section3/multiturn/confirm/{sid}/{turn}  — user_response 저장
 *   GET    /api/section3/multiturn/session/{sid}         — replay (decision_log hydrate)
 *   GET    /api/section3/multiturn/session/{sid}/stream  — SSE snapshot
 */

const BASE = "/api/section3/multiturn";

// ─── Schema types (백엔드 backend/section3/agents/multiturn/schemas.py 와 1:1) ───

export type ProvenanceSource = "ontology" | "sim_v2" | "llm_inference" | "user_input";

export interface Provenance {
  source: ProvenanceSource;
  detail: string;
  confidence: number | null;
}

export interface CodeLocation {
  file_path: string;
  line_start: number;
  line_end: number;
}

export interface ActionCandidate {
  action_id: string;
  label: string;
  score: number;
  code_method_fqn: string;
  aliases: string[];
  location?: CodeLocation | null;
  body_preview?: string | null;
  return_type?: string | null;
  // Phase 12 + 16K — ontology 풍부 메타 (모두 optional, backward-compat).
  // boost rationale 시각화: declared_on_term 매칭이 ranking 의 강한 신호.
  role?: string | null;              // code_methods.role: business/adapter/helper/unknown
  parent_role?: string | null;       // code_types.role: domain/infra/framework/unknown
  annotations?: string[];            // @Service, @Transactional, ...
  declared_on_term?: string | null;  // actions.declared_on_term — domain term linkage
}

export interface ActionRef {
  action_id: string;
  code_method_fqn: string;
  repo_id: string;
  location: CodeLocation;
}

export interface FixtureRow {
  fixture_id: string;
  args: Record<string, unknown>;
}

export interface SchemaField {
  name: string;
  type_name: string;
  nullable: boolean;
}

export interface SchemaSummary {
  entity_name: string;
  fields: SchemaField[];
}

export interface IdiomDiff {
  idiom_name: string;
  java_snippet: string;
  python_snippet: string;
}

export interface CaseResult {
  fixture_id: string;
  status: "PASS" | "FAIL" | "ERROR" | "SKIPPED";
  output: unknown;
  error_class: string | null;
  error_message: string | null;
}

export type InvariantStatus =
  | "clean"
  | "fail_nondeterministic"
  | "fail_unexpected_throw"
  | "fail_return_type"
  | "error";

export interface BaselineDiff {
  fixture_id: string;
  java_expected: unknown;
  python_actual: unknown;
  matches: boolean;
}

export interface AffectedMethod {
  fqn: string;
  distance: number;
  via: string;
  match_kind?: "receiver_exact" | "receiver_short" | "runtime_type" | "package_proximity" | "name_only" | null;
  strength?: number | null;
}

export interface Finding {
  kind: string;
  severity: "info" | "warn" | "error";
  message: string;
}

// ─── Gate payload union ───

// Phase 21b — Gate I-a: intent 분류만 (candidates 미수행).
// 사용자 vision: 의도 분류 후 "맞아?" 묻고 → confirm 후 candidates 진행.
export interface GateIntentClassified {
  kind: "intent_classified";
  intent: "simulate" | "impact" | "ambiguous" | "locate" | "explain" | "hypothesis";
  user_query: string;
  search_terms: string[];
  conditions: Array<{ var: string; op: string; value: string; unit: string }>;
  sources: Provenance[];
}

export interface GateTarget {
  kind: "target_selected";
  intent: "simulate" | "impact" | "ambiguous" | "locate" | "explain" | "hypothesis";
  user_query: string;
  candidates: ActionCandidate[];
  recommended_index: number | null;
  selected: ActionRef | null;
  sources: Provenance[];
  // Phase 13b — 0-cand fallback: business_terms.aliases_json 인접어 추천.
  suggestions?: string[];
  // Phase 13c — hypothesis intent 에서만 채워짐.
  conditions?: Array<{ var: string; op: string; value: string; unit: string }>;
}

export interface GateBundle {
  kind: "bundle_prepared";
  target: ActionRef;
  java_source: string;
  python_source: string;
  idiom_diffs: IdiomDiff[];
  fixtures: FixtureRow[];
  schema_summary: SchemaSummary;
  sources: Provenance[];
  confidence: number;
}

export interface GateExecutedSimulation {
  kind: "executed_simulation";
  mode: "simulate";
  results: CaseResult[];
  invariant_status: InvariantStatus;
  baseline_diff: BaselineDiff[] | null;
  sources: Provenance[];
}

export interface GateExecutedImpact {
  kind: "executed_impact";
  mode: "impact";
  affected_methods: AffectedMethod[];
  sim_v2_findings: Finding[];
  confidence: number;
  sources: Provenance[];
}

// Phase 13a — locate / explain intent 응답 (executed_lookup)
export interface BusinessRuleEvidence {
  fqn: string;
  statement: string;
  severity: string;
}

export interface GateExecutedLookup {
  kind: "executed_lookup";
  mode: "locate" | "explain";
  target: ActionRef;
  body_text: string;
  file_path: string;
  line_start: number;
  line_end: number;
  return_type: string;
  linked_action_label: string | null;
  linked_term: string | null;
  callers: AffectedMethod[];
  business_rules: BusinessRuleEvidence[];
  sources: Provenance[];
}

// Phase 13c — hypothesis intent 응답
export type HypothesisVerdict =
  | "yes" | "likely_yes" | "likely_no" | "no" | "unknown";

export interface GateExecutedHypothesis {
  kind: "executed_hypothesis";
  mode: "hypothesis";
  target: ActionRef;
  conditions: Array<{ var: string; op: string; value: string; unit: string }>;
  body_text: string;
  file_path: string;
  line_start: number;
  line_end: number;
  verdict: HypothesisVerdict;
  reasoning: string;
  evidence: BusinessRuleEvidence[];
  confidence: number;
  sources: Provenance[];
}

export type GatePayload =
  | GateIntentClassified
  | GateTarget
  | GateBundle
  | GateExecutedSimulation
  | GateExecutedImpact
  | GateExecutedLookup
  | GateExecutedHypothesis;

// ─── Endpoint envelopes ───

export interface SessionInfo {
  id: string;
  repo_id: string;
  status: "active" | "done" | "blocked";
  user_query: string | null;
  created_at: string;
  last_activity_at: string;
}

export interface DecisionView {
  id: number;
  turn_no: number;
  gate_kind: string;
  payload: GatePayload;
  user_response: Record<string, unknown> | null;
  created_at: string;
}

export interface SessionResponse {
  session: SessionInfo;
  decisions: DecisionView[];
}

export interface SessionSummary {
  id: string;
  repo_id: string;
  status: "active" | "done" | "blocked";
  user_query: string | null;
  created_at: string;
  last_activity_at: string;
  turn_count: number;
  last_gate_kind: string | null;
}

export interface SessionsListResponse {
  sessions: SessionSummary[];
}

// Phase 16L — integrity_warning 발화율 metric (운영 dashboard)
export interface WarningRatesResponse {
  total_sessions: number;
  by_kind: Record<string, number>;
  by_kind_pct: Record<string, number>;
}

// Phase 16O — 0-candidate 매핑 갭 추적
export interface ZeroCandQueryView {
  session_id: string;
  user_query: string;
  repo_id: string;
  created_at: string;
  suggestions: string[];
}

export interface ZeroCandQueriesResponse {
  queries: ZeroCandQueryView[];
}

// Phase 18 — Stage 2 scope aggregator
export interface ScopeEntityView {
  kind: "action" | "caller" | "term" | "rule" | string;
  fqn: string;
  label: string;
  detail: string;
  in_scope_default: boolean;
  meta: Record<string, unknown>;
}

export interface ScopeResponse {
  primary_action_fqn: string;
  primary_method_fqn: string;
  entities: ScopeEntityView[];
  counts: Record<string, number>;
}

export interface StartResponse {
  session_id: string;
  turn_no: number;
  payload: GatePayload;
}

export interface RespondResponse {
  session_id: string;
  turn_no: number;
  payload: GatePayload;
}

export interface ConfirmResponse {
  ok: boolean;
  next_gate_kind: string | null;
}

// ─── API calls ───

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<T>;
}

export class MultiturnError extends Error {
  constructor(public status: number, public detail: string) {
    super(`${status}: ${detail}`);
    this.name = "MultiturnError";
  }
}

export function startSession(
  user_query: string,
  repo_id: string,
): Promise<StartResponse> {
  return postJSON(`${BASE}/start`, { user_query, repo_id });
}

export function respond(
  session_id: string,
  message: string,
): Promise<RespondResponse> {
  return postJSON(`${BASE}/respond/${encodeURIComponent(session_id)}`, { message });
}

export function confirmTurn(
  session_id: string,
  turn_no: number,
  action: "confirm" | "modify" | "retry",
  user_response: Record<string, unknown>,
): Promise<ConfirmResponse> {
  return postJSON(
    `${BASE}/confirm/${encodeURIComponent(session_id)}/${turn_no}`,
    { action, user_response },
  );
}

export async function getSession(session_id: string): Promise<SessionResponse> {
  const r = await fetch(
    `${BASE}/session/${encodeURIComponent(session_id)}`,
  );
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<SessionResponse>;
}

export async function listSessions(
  opts: { limit?: number; repo_id?: string; search?: string } = {},
): Promise<SessionsListResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.repo_id) params.set("repo_id", opts.repo_id);
  if (opts.search) params.set("search", opts.search);
  const qs = params.toString();
  const url = `${BASE}/sessions${qs ? `?${qs}` : ""}`;
  const r = await fetch(url);
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<SessionsListResponse>;
}

// Phase 16L — fetch integrity_warning 발화율
export async function getWarningRates(
  opts: { limit?: number; repo_id?: string } = {},
): Promise<WarningRatesResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.repo_id) params.set("repo_id", opts.repo_id);
  const qs = params.toString();
  const url = `${BASE}/metrics/warnings${qs ? `?${qs}` : ""}`;
  const r = await fetch(url);
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<WarningRatesResponse>;
}

// Phase 18 — Stage 2 scope fetch
export async function getScope(
  req: {
    action_fqn: string;
    code_method_fqn: string;
    declared_on_term: string | null;
    repo_id: string;
  },
): Promise<ScopeResponse> {
  const r = await fetch(`${BASE}/scope`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<ScopeResponse>;
}

// Phase 16O — fetch 0-candidate 매핑 갭 query 리스트
export async function getZeroCandQueries(
  opts: { limit?: number; repo_id?: string } = {},
): Promise<ZeroCandQueriesResponse> {
  const params = new URLSearchParams();
  if (opts.limit) params.set("limit", String(opts.limit));
  if (opts.repo_id) params.set("repo_id", opts.repo_id);
  const qs = params.toString();
  const url = `${BASE}/metrics/zero-cand-queries${qs ? `?${qs}` : ""}`;
  const r = await fetch(url);
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new MultiturnError(r.status, detail || r.statusText);
  }
  return r.json() as Promise<ZeroCandQueriesResponse>;
}
