// ── Router ────────────────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  session_id: string;
}

export type AgentType = "WIKI_QA" | "SIMULATION" | "DEBUG_TRACE" | "UNKNOWN";

export interface RouterDecision {
  agent: AgentType;
  confidence: number;
  reasoning: string;
}

// ── Agent Response & SSE Events ───────────────────────────────────────

export interface SourceRef {
  doc: string;
  relevance: number;
  updated?: string;
  updated_by?: string;
  status?: string;  // draft | review | approved | deprecated
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
}

export interface ContentDelta {
  event: "content_delta";
  delta: string;
}

export interface SourcesEvent {
  event: "sources";
  sources: SourceRef[];
}

export interface ApprovalRequestEvent {
  event: "approval_request";
  action_id: string;
  action_type: string;
  path: string;
  diff_preview: string;
}

export interface ConflictWarningEvent {
  event: "conflict_warning";
  details: string;
  conflicting_docs: string[];
}

export interface ErrorEvent {
  event: "error";
  error_code: string;
  message: string;
  retry_hint: string | null;
}

export interface DoneEvent {
  event: "done";
  usage: TokenUsage | null;
}

export type SSEEvent =
  | ContentDelta
  | SourcesEvent
  | ConflictWarningEvent
  | ApprovalRequestEvent
  | ErrorEvent
  | DoneEvent;

// ── Human-in-the-loop ─────────────────────────────────────────────────

export interface ApprovalRequest {
  session_id: string;
  action_id: string;
  approved: boolean;
}

// ── Error ─────────────────────────────────────────────────────────────

export interface ErrorResponse {
  error_code: string;
  message: string;
  retry_hint: string | null;
}
