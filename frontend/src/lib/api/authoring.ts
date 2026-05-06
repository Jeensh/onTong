/**
 * Authoring AI API client.
 *
 * Mirrors backend/api/authoring.py — all paths are under /api/authoring.
 * Types mirror the Pydantic schemas in backend/application/authoring/.
 *
 * Kept intentionally untyped on the JSON surface in places where the schema
 * is rich and would create churn if backend evolves; the types here pin
 * the parts the frontend actually destructures.
 */

// ── Session ─────────────────────────────────────────────────────────

export type SessionStatus = "active" | "paused" | "merged" | "abandoned";

export interface AuthoringSession {
  id: string;
  branch_name: string;
  operator_id: string;
  entity_focus: string | null;
  repo_id: string | null;
  status: SessionStatus;
  meta: Record<string, unknown>;
  created_at: string;
  last_activity_at: string;
}

export interface CreateSessionRequest {
  operator_id?: string;
  branch_name?: string;
  repo_id?: string;
  entity_focus?: string;
  meta?: Record<string, unknown>;
}

// ── Decision log ────────────────────────────────────────────────────

export type DecisionKind =
  | "hypothesis_seeded"
  | "interview_designed"
  | "answer_absorbed"
  | "option_selected"
  | "naming_confirmed"
  | "gap_resolved"
  | "archive_saved"
  | "next_entity_started"
  | "other";

export interface AuthoringDecision {
  id: number;
  session_id: string;
  turn_no: number;
  step_label: string | null;
  entity_id: string | null;
  decision_kind: DecisionKind;
  payload: Record<string, unknown>;
  archive_markdown: string | null;
  created_at: string;
}

// ── Capability schemas ──────────────────────────────────────────────

export interface CodeColumn {
  name: string;
  db_column: string;
  java_type: string;
  db_length?: number | null;
  db_precision?: number | null;
  db_scale?: number | null;
  is_pk: boolean;
  comment?: string | null;
}

export interface ExtractedJpo {
  package: string;
  class_name: string;
  table_name: string;
  pk_class?: string | null;
  pk_columns: CodeColumn[];
  regular_columns: CodeColumn[];
  class_docstring?: string | null;
}

export type DomainRole =
  | "equipment"
  | "standard"
  | "rule_table"
  | "lookup_table"
  | "transactional"
  | "audit_log"
  | "unknown";

export interface ColumnNote {
  db_column: string;
  note: string;
}

export interface EntityHypothesis {
  candidate_term_korean: string;
  candidate_term_english: string;
  domain_role: DomainRole;
  pk_role_summary: string;
  column_notes: ColumnNote[];
  relations_hint: string[];
  domain_questions: string[];
  confidence: number;
  assumptions: string[];
  concerns: string[];
}

export type Importance = "critical" | "standard" | "optional";

export interface InterviewQuestion {
  id: string;
  prompt: string;
  my_guess: string | null;
  placeholder: string;
  options: string[] | null;
  importance: Importance;
  skip_ok: boolean;
}

export interface InterviewBatch {
  intro: string;
  questions: InterviewQuestion[];
}

export interface AbsorbedAnswer {
  question_id: string;
  raw_text: string;
  normalized: string;
  is_unknown: boolean;
  picked_option: string | null;
  contradicts_my_guess: boolean;
  contradicts_note: string | null;
}

export interface AbsorbedAnswers {
  per_question: Record<string, AbsorbedAnswer>;
  unanswered: string[];
  emergent_facts: string[];
  contradictions: string[];
}

export type DomainAlignment = "high" | "medium" | "low";

export interface OntologyOption {
  id: string;
  name: string;
  description: string;
  structure_sketch: string;
  pros: string[];
  cons: string[];
  entities_count_hint: string;
  domain_alignment: DomainAlignment;
  trade_offs_one_line: string;
}

export interface OptionTable {
  title: string;
  context_summary: string;
  options: OntologyOption[];
  recommended_id: string;
  recommendation_reasoning: string;
  caveats: string[];
}

export type GapKind = "structure" | "consistency" | "intent" | "historical";
export type GapSeverity = "high" | "medium" | "low";
export type GapResolution =
  | "simplification_note"
  | "code_fix_scenario"
  | "business_intent"
  | "investigate";

export interface Gap {
  id: string;
  kind: GapKind;
  severity: GapSeverity;
  title: string;
  description: string;
  evidence_code: string;
  evidence_domain: string;
  recommended_resolution: GapResolution;
  resolution_rationale: string;
  demo_potential: boolean;
}

export interface GapAnalysis {
  gaps: Gap[];
  severity_summary: string;
  blocks_modeling: boolean;
  recommendation: string;
}

export type EntityRole = "root" | "child" | "standalone";

export interface EntityName {
  korean_label: string;
  english_id: string;
  role: EntityRole;
  parent_english_id: string | null;
  description_short: string;
}

export interface NamingDecision {
  entities: EntityName[];
  naming_conflicts: string[];
  naming_rationale: string;
  alternatives_considered: string[];
}

export interface ArchiveDecisionRow {
  topic_korean: string;
  decision_korean: string;
  rationale_korean: string;
}

export interface ArchiveBody {
  summary_korean: string;
  decisions: ArchiveDecisionRow[];
  structure_diagram: string;
}

export interface ArchiveDocument {
  title: string;
  status: "completed" | "partial";
  body: ArchiveBody;
  markdown: string;
}

// R6 cap 10 — next_step advisor
export type RecommendedAction =
  | "run_interview"
  | "submit_answers"
  | "run_options"
  | "accept_option"
  | "run_pattern_check"
  | "run_gaps"
  | "revise_hypothesis"
  | "revise_options"
  | "run_naming"
  | "run_archive"
  | "run_confirm"
  | "done"
  | "escalate_to_user";

export type StepPriority = "critical" | "recommended" | "optional";

export interface NextStep {
  recommended_action: RecommendedAction;
  reason_korean: string;
  priority: StepPriority;
  alternatives: RecommendedAction[];
}

export interface SessionStateSnapshot {
  has_hypothesis: boolean;
  hypothesis_confidence: number | null;
  has_interview_batch: boolean;
  has_answers: boolean;
  has_option_table: boolean;
  has_accepted_option: boolean;
  has_gaps: boolean;
  gaps_block_modeling: boolean;
  gap_high_count: number;
  has_pattern_check: boolean;
  pattern_recommendation: string | null;
  has_names: boolean;
  has_archive: boolean;
  persisted_fqn_count: number;
}

// P1a-B — session resume (page reload restore)
export interface CompletedEntitySnapshot {
  jpo: ExtractedJpo | null;
  hypothesis: EntityHypothesis | null;
  accepted_option: OntologyOption | null;
  names: NamingDecision | null;
  archive: ArchiveDocument | null;
  pattern: PatternCheck | null;
  gaps: GapAnalysis | null;
  persisted_fqns: string[];
  completed_at: string | null;
}

export interface CurrentEntityState {
  jpo: ExtractedJpo | null;
  hypothesis: EntityHypothesis | null;
  batch: InterviewBatch | null;
  answers: AbsorbedAnswers | null;
  option_table: OptionTable | null;
  accepted_option: OntologyOption | null;
  gaps: GapAnalysis | null;
  pattern: PatternCheck | null;
  names: NamingDecision | null;
  archive: ArchiveDocument | null;
  persisted_fqns: string[];
}

export interface SessionResumeState {
  session: AuthoringSession;
  completed_entities: CompletedEntitySnapshot[];
  current: CurrentEntityState;
  cost_total_usd: number;
  decision_count: number;
}

// P1a-E cap 12 — comprehensive archive (multi-entity domain report)
export interface EntitySnapshot {
  class_name: string;
  package?: string;
  candidate_term_korean: string;
  candidate_term_english: string;
  domain_role: string;
  accepted_option_name?: string | null;
  accepted_option_alignment?: string | null;
  accepted_option_structure?: string | null;
  persisted_fqns?: string[];
  gap_titles?: string[];
  pattern_findings_summary?: string | null;
  archive_excerpt?: string | null;
  in_progress?: boolean;
}

export interface EntitySectionSummary {
  class_name: string;
  candidate_term_korean: string;
  candidate_term_english: string;
  domain_role: string;
  accepted_option_name: string | null;
  persisted_fqns: string[];
  summary_korean: string;
  notable_gaps_or_concerns: string[];
}

export interface CrossCuttingObservation {
  title: string;
  description_korean: string;
  affected_entities: string[];
}

export interface ComprehensiveArchiveBody {
  title: string;
  executive_summary: string;
  entity_sections: EntitySectionSummary[];
  cross_cutting_observations: CrossCuttingObservation[];
  decisions_made: string[];
  next_steps_korean: string[];
}

export interface ComprehensiveArchive {
  body: ComprehensiveArchiveBody;
  markdown: string;
  rendered_at: string;
}

// P1a-C cap 11 — next_entity picker
export type NextEntitySignal =
  | "pk_overlap"
  | "same_package"
  | "uncovered_domain"
  | "frequent_caller"
  | "inheritance_chain";

export interface NextEntityCandidate {
  fqn: string;
  simple_name: string;
  reason_korean: string;
  signal: NextEntitySignal;
  confidence: number;
}

export interface NextEntityRecommendation {
  candidates: NextEntityCandidate[];
  summary_korean: string;
}

// R6 cap 7 — pattern_checker
export type PatternDimension =
  | "composition_pattern"
  | "naming_convention"
  | "domain_grouping"
  | "facet_consistency"
  | "inheritance_pattern";

export type PatternAlignment = "matches" | "deviates" | "neutral";
export type PatternSeverity = "info" | "warn" | "block";
export type PatternRecommendation = "그대로 진행" | "옵션 재고려" | "사용자 의견 필요";

export interface PatternFinding {
  id: string;
  dimension: PatternDimension;
  alignment: PatternAlignment;
  title: string;
  evidence_existing: string;
  evidence_proposed: string;
  severity: PatternSeverity;
  suggestion: string;
}

export interface PatternCheck {
  findings: PatternFinding[];
  consistency_score: number;
  summary: string;
  recommendation: PatternRecommendation;
}

/** P1a-D: snapshot of an in-session prior entity, sent to cap 7 so it can
 * detect cross-entity patterns (e.g. user just adopted Composition for
 * HrPlant — the new entity should consider it too). */
export interface PriorEntitySnapshot {
  class_name: string;
  candidate_term_korean: string;
  candidate_term_english: string;
  domain_role: string;
  accepted_option_name: string | null;
  accepted_option_structure: string | null;
  accepted_option_alignment: string | null;
  persisted_fqns: string[];
  archive_summary: string | null;
}

export interface ConfirmResponse {
  session_id: string;
  repo_id: string;
  persisted_fqns: string[];
  persisted_count: number;
  decision_id: number;
}

export interface CostSummary {
  session_id: string;
  total_usd: number;
  call_count: number;
}

export interface SessionPreview {
  session: AuthoringSession;
  decision_count: number;
  latest_decisions: AuthoringDecision[];
  latest_archive_markdown: string | null;
  cost: CostSummary;
}

// ── Tool call trace (R6) ────────────────────────────────────────────

/** One row from the persisted authoring_tool_call_log. */
export interface ToolCallRow {
  turn_no: number;
  capability: string;
  tool_name: string;
  args: Record<string, unknown>;
  result_summary: string;
  duration_ms: number;
  cached: boolean;
  error: string | null;
  created_at: string;
}

/** SSE events emitted during agentic capabilities (gaps / options). */
export type ToolStreamEvent =
  | { type: "stream_open" }
  | {
      type: "tool_call_start";
      seq: number;
      tool_name: string;
      args_summary: string;
    }
  | {
      type: "tool_call_end";
      tool_name: string;
      result_summary: string;
      duration_ms: number;
      cached: boolean;
      error: string | null;
    }
  | { type: "heartbeat"; stale_for_s: number }
  | { type: "done"; output: unknown; tool_call_count: number }
  | { type: "error"; message: string };

// ── HTTP helper ─────────────────────────────────────────────────────

const BASE = "/api/authoring";

async function http<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${method} ${path} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

/** Stream SSE events from a POST endpoint, yielding parsed event objects. */
async function* postSSE<E>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<E> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text();
    throw new Error(`POST ${path} stream failed: ${res.status} ${text}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let frameEnd: number;
    while ((frameEnd = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, frameEnd);
      buffer = buffer.slice(frameEnd + 2);
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice("data:".length).trim();
      if (!json) continue;
      try {
        yield JSON.parse(json) as E;
      } catch {
        // ignore malformed frames — server bug not worth crashing the UI
      }
    }
  }
}

// ── Session admin ───────────────────────────────────────────────────

export const authoringApi = {
  // session admin
  createSession(req: CreateSessionRequest = {}): Promise<AuthoringSession> {
    return http("POST", "/sessions", req);
  },
  listSessions(opts: { operator_id?: string; status?: SessionStatus } = {}): Promise<AuthoringSession[]> {
    const qs = new URLSearchParams();
    if (opts.operator_id) qs.set("operator_id", opts.operator_id);
    if (opts.status) qs.set("status", opts.status);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return http("GET", `/sessions${suffix}`);
  },
  getSession(id: string): Promise<AuthoringSession> {
    return http("GET", `/sessions/${id}`);
  },
  updateSession(
    id: string,
    req: { entity_focus?: string | null; status?: SessionStatus }
  ): Promise<AuthoringSession> {
    return http("PATCH", `/sessions/${id}`, req);
  },

  // history / preview / cost
  listDecisions(id: string): Promise<AuthoringDecision[]> {
    return http("GET", `/sessions/${id}/decisions`);
  },
  getCost(id: string): Promise<CostSummary> {
    return http("GET", `/sessions/${id}/cost`);
  },
  getPreview(id: string): Promise<SessionPreview> {
    return http("GET", `/sessions/${id}/preview`);
  },

  // capabilities
  extract(
    id: string,
    req: {
      turn_no: number;
      file_path?: string;
      file_content?: string;
      fqn?: string;
      repo_id?: string;
    },
  ): Promise<ExtractedJpo> {
    // Either supply (file_path + file_content) inline, or (fqn + repo_id) and
    // the backend resolves source_file from CodeTypeRow on its own.
    return http("POST", `/sessions/${id}/extract`, req);
  },
  hypothesize(
    id: string,
    req: { turn_no: number; extracted_jpo: ExtractedJpo; user_comment?: string },
  ): Promise<EntityHypothesis> {
    return http("POST", `/sessions/${id}/hypothesize`, req);
  },
  interview(
    id: string,
    req: { turn_no: number; hypothesis: EntityHypothesis; user_comment?: string },
  ): Promise<InterviewBatch> {
    return http("POST", `/sessions/${id}/interview`, req);
  },
  absorb(id: string, req: { turn_no: number; batch: InterviewBatch; user_reply: string }): Promise<AbsorbedAnswers> {
    return http("POST", `/sessions/${id}/absorb`, req);
  },
  options(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      answers: AbsorbedAnswers;
      pattern_library?: string[] | null;
      user_comment?: string;
    },
  ): Promise<OptionTable> {
    return http("POST", `/sessions/${id}/options`, req);
  },
  gaps(
    id: string,
    req: { turn_no: number; extracted_jpo: ExtractedJpo; hypothesis: EntityHypothesis; answers: AbsorbedAnswers }
  ): Promise<GapAnalysis> {
    return http("POST", `/sessions/${id}/gaps`, req);
  },
  naming(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      accepted_option: OntologyOption;
      existing_names?: string[] | null;
      user_comment?: string;
    },
  ): Promise<NamingDecision> {
    return http("POST", `/sessions/${id}/naming`, req);
  },
  archive(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      answers: AbsorbedAnswers;
      accepted_option: OntologyOption;
      names: NamingDecision;
      gaps?: GapAnalysis | null;
      step_number?: number | null;
    }
  ): Promise<ArchiveDocument> {
    return http("POST", `/sessions/${id}/archive`, req);
  },
  confirm(
    id: string,
    req: { turn_no: number; names: NamingDecision; accepted_option: OntologyOption; repo_id: string; domain?: string }
  ): Promise<ConfirmResponse> {
    return http("POST", `/sessions/${id}/confirm`, req);
  },

  // R6 — graph-aware streaming variants
  extractStream(
    id: string,
    req: {
      turn_no: number;
      file_path?: string | null;
      file_content?: string | null;
      fqn?: string | null;
      repo_id?: string | null;
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/extract/stream`,
      req,
      signal,
    );
  },
  hypothesizeStream(
    id: string,
    req: {
      turn_no: number;
      extracted_jpo: ExtractedJpo;
      user_comment?: string;
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/hypothesize/stream`,
      req,
      signal,
    );
  },
  optionsStream(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      answers: AbsorbedAnswers;
      pattern_library?: string[] | null;
      user_comment?: string;
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/options/stream`,
      req,
      signal,
    );
  },
  gapsStream(
    id: string,
    req: {
      turn_no: number;
      extracted_jpo: ExtractedJpo;
      hypothesis: EntityHypothesis;
      answers: AbsorbedAnswers;
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/gaps/stream`,
      req,
      signal,
    );
  },
  toolCalls(id: string): Promise<{ session_id: string; tool_calls: ToolCallRow[] }> {
    return http("GET", `/sessions/${id}/tool-calls`);
  },

  // R6 cap 7 — pattern_checker (between option selection and naming)
  pattern(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      accepted_option: OntologyOption;
      prior_session_entities?: PriorEntitySnapshot[] | null;
    },
  ): Promise<PatternCheck> {
    return http("POST", `/sessions/${id}/pattern`, req);
  },
  patternStream(
    id: string,
    req: {
      turn_no: number;
      hypothesis: EntityHypothesis;
      accepted_option: OntologyOption;
      prior_session_entities?: PriorEntitySnapshot[] | null;
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/pattern/stream`,
      req,
      signal,
    );
  },

  // R6 cap 10 — next_step advisor (no graph tools, fast Sonnet call)
  nextStep(
    id: string,
    req: { turn_no: number; state: SessionStateSnapshot },
  ): Promise<NextStep> {
    return http("POST", `/sessions/${id}/next-step`, req);
  },

  // P1a-C cap 11 — next_entity picker (graph-tool driven)
  nextEntity(
    id: string,
    req: {
      turn_no: number;
      repo_id: string;
      completed_entity_fqns: string[];
      confirmed_term_fqns: string[];
    },
  ): Promise<NextEntityRecommendation> {
    return http("POST", `/sessions/${id}/next-entity`, req);
  },
  nextEntityStream(
    id: string,
    req: {
      turn_no: number;
      repo_id: string;
      completed_entity_fqns: string[];
      confirmed_term_fqns: string[];
    },
    signal?: AbortSignal,
  ) {
    return postSSE<ToolStreamEvent>(
      `/sessions/${id}/next-entity/stream`,
      req,
      signal,
    );
  },

  // P1a-E cap 12 — comprehensive archive (no graph tools, pure synthesis)
  comprehensiveArchive(
    id: string,
    req: {
      turn_no: number;
      repo_id: string;
      entities: EntitySnapshot[];
    },
  ): Promise<ComprehensiveArchive> {
    return http("POST", `/sessions/${id}/comprehensive-archive`, req);
  },

  // P1a-B — session resume
  replay(id: string): Promise<SessionResumeState> {
    return http("GET", `/sessions/${id}/replay`);
  },
  markNextEntity(id: string, req: { turn_no: number }): Promise<{ ok: boolean }> {
    return http("POST", `/sessions/${id}/next-entity-marker`, req);
  },
};
