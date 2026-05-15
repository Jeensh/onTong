/**
 * Ontology Query API client — backend/modeling/api/ontology_router.py 와 1:1 매칭.
 *
 * Agent boundary contract (backend/shared/contracts/ontology_query.py) 의
 * REST 노출. Phase 1 에서는 fetch wrapper.
 */

// 기본은 빈 문자열 — relative URL 로 next.config.ts 의 rewrite (/api/* → BACKEND_URL) 활용.
// 절대 origin 으로 직접 호출하고 싶으면 NEXT_PUBLIC_API_BASE_URL=http://host:port 으로 명시.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

// ---------------------------------------------------------------------------
// Types — backend Pydantic model 과 1:1
// ---------------------------------------------------------------------------
export type TermKind = "atomic" | "composite";
export type CodeTypeKind = "class" | "abstract_class" | "interface" | "enum" | "record";
export type CodeTypeRole = "domain" | "framework" | "infra" | "unknown";
export type MethodRole = "business" | "helper" | "adapter" | "unknown";
export type ActionKind = "pure_function" | "effectful" | "workflow";
export type VerificationLevel =
  | "unmapped" | "draft" | "signature_locked"
  | "body_anchored" | "sim_verified" | "pr_proven";

export type Cardinality = "1:1" | "0:1" | "1:N" | "0:N";

export interface TermDTO {
  fqn: string;
  label: string;
  aliases: string[];
  domain: string;
  description: string;
  kind: TermKind;
  is_abstract: boolean;
  is_interface: boolean;
  is_root_entity: boolean;
  struct_like_hint: boolean;
  value_type?: string | null;
  unit?: string | null;
  range?: number[] | null;
  enum_values?: string[] | null;
  confirmed: boolean;
  repo_id: string;
}

export interface CompositionDTO {
  parent_fqn: string;
  child_fqn: string;
  role_name: string;
  cardinality: Cardinality;
  required: boolean;
  description: string;
  repo_id: string;
}

export interface InheritanceDTO {
  child_fqn: string;
  parent_fqn: string;
  kind: "extends" | "implements";
  repo_id: string;
}

export interface CodeFieldDTO {
  name: string;
  type: string;
  modifiers: string[];
  annotations: string[];
  is_collection: boolean;
  element_type?: string | null;
  line?: number | null;
}

export interface CodeMethodDTO {
  fqn: string;
  name: string;
  parent_type_fqn: string;
  return_type: string;
  params: { name: string; type: string }[];
  modifiers: string[];
  annotations: string[];
  role: MethodRole;
  is_abstract: boolean;
  is_override: boolean;
  is_constructor: boolean;
  body_text?: string | null;
  line_start?: number | null;
  line_end?: number | null;
  anchors: Array<{
    method_fqn: string;
    kind: string;
    locator: string;
    line?: number | null;
    snippet: string;
    extra: Record<string, unknown>;
  }>;
  extra: Record<string, unknown>;
}

export interface CodeTypeDTO {
  fqn: string;
  simple_name: string;
  package: string;
  kind: CodeTypeKind;
  role: CodeTypeRole;
  is_abstract: boolean;
  extends?: string | null;
  implements: string[];
  extends_interfaces: string[];
  fields: CodeFieldDTO[];
  methods: CodeMethodDTO[];
  modifiers: string[];
  annotations: string[];
  source_file: string;
  line_start?: number | null;
  line_end?: number | null;
  repo_id: string;
}

export interface ActionParamDTO {
  name: string;
  type: string;
  object_ref_term?: string | null;
  unit?: string | null;
  range?: number[] | null;
  nullable: boolean;
  description: string;
  anchor_locator?: string | null;
  confirmed: boolean;
}

export interface ActionEffectDTO {
  op: "create" | "mutate" | "read" | "delete";
  target_term: string;
  target_attr?: string | null;
  description: string;
}

export interface RealizationDTO {
  code_method_fqn: string;
  applies_to_code_type_fqn?: string | null;
  is_override: boolean;
  dispatch_source: string;
  confidence: number;
  scope: "primary" | "partial";
  confirmed: boolean;
  rationale: string;
}

export interface ActionDTO {
  fqn: string;
  label: string;
  aliases: string[];
  domain: string;
  description: string;
  kind: ActionKind;
  is_abstract: boolean;
  declared_on_term?: string | null;
  params: ActionParamDTO[];
  output?: { type: string; object_ref_term?: string | null; description: string } | null;
  preconditions: string[];
  postconditions: string[];
  effects: ActionEffectDTO[];
  realizations: RealizationDTO[];
  sub_actions: string[];
  verification_level: VerificationLevel;
  signature_locked_at?: string | null;
  confirmed_by?: string | null;
  repo_id: string;
}

export interface AnchorBindingDTO {
  id: string;
  anchor_locator: string;
  code_method_fqn: string;
  target_action_fqn: string;
  target_slot: string;
  confidence: number;
  source: string;
  confirmed: boolean;
  rationale: string;
  repo_id: string;
  line: number | null;          // 2026-05-10 추가 — source code line (1-indexed)
}

export interface IncidentRefDTO {
  incident_id: string;
  summary: string;
  occurred_at: string | null;
  triggered_by: string | null;
  fixed_at_commit: string | null;
}

export interface BusinessRuleDTO {
  fqn: string;
  statement: string;
  severity: string;             // "hard" / "soft"
  terms_ref: string[];
  source: string;
  confirmed: boolean;
  repo_id: string;
  // 2026-05-10 추가 — 코드 ↔ BR mapping
  enforced_by: string[];                            // method_fqn list
  violated_at_call: Record<string, unknown>[];      // call site dict list
  operational_history: IncidentRefDTO[];
}

export interface CallSiteDTO {
  id: string;
  caller_method_fqn: string;
  callee_simple_name: string;
  callee_receiver_static_type: string;
  line?: number | null;
  possible_runtime_types: { code_type_fqn: string; score: number; reason: string }[];
  confidence: number;
  analysis_source: string;
  needs_user_confirm: boolean;
  user_confirmed_type?: string | null;
  user_confirmed_at?: string | null;
  repo_id: string;
}

export interface SearchHitDTO {
  fqn: string;
  label: string;
  kind: "term" | "action" | "code_type" | "code_method" | "rule";
  domain: string;
  score: number;
}

export interface VerificationProgressDTO {
  repo_id: string;
  total_actions: number;
  by_level: Record<string, number>;
}

export interface UnmappedMethodDTO {
  code_method: CodeMethodDTO;
  parent_type_role: string;
  reason: string;
}

export interface AmbiguousCallSiteDTO {
  call_site: CallSiteDTO;
  caller_term_fqn?: string | null;
  caller_business_process?: string | null;
  suggested_choice_fqn?: string | null;
  suggested_rationale: string;
}

// ---------------------------------------------------------------------------
// Fetch wrapper
// ---------------------------------------------------------------------------
async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    // dev 중에 Next.js / browser fetch cache 가 stale 응답을 재사용하는 경우 방지.
    cache: init?.cache ?? "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    // FastAPI 는 `{"detail": "..."}` 또는 `{"detail": [{"msg": "..."}]}` 형식으로 에러를 반환.
    // raw JSON 덤프 대신 detail 만 추출해서 사용자에게 깔끔히 노출.
    let message = txt || res.statusText;
    try {
      const parsed = JSON.parse(txt);
      if (typeof parsed?.detail === "string") {
        message = parsed.detail;
      } else if (Array.isArray(parsed?.detail) && parsed.detail[0]?.msg) {
        message = parsed.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
      }
    } catch {
      // not JSON — keep raw text
    }
    throw new Error(`API ${res.status}: ${message}`);
  }
  return res.json();
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Public API — 16 메서드 (backend OntologyQueryClient Protocol 정합)
// ---------------------------------------------------------------------------

export const ontologyApi = {
  // Term
  listTerms: (opts?: { repo_id?: string; kind?: TermKind; domain?: string }) =>
    fetchJson<TermDTO[]>(`/api/ontology/terms${qs(opts ?? {})}`),
  getTerm: (fqn: string) =>
    fetchJson<TermDTO | null>(`/api/ontology/terms/${encodeURIComponent(fqn)}`),
  effectiveParts: (term_fqn: string, repo_id?: string) =>
    fetchJson<CompositionDTO[]>(
      `/api/ontology/terms/${encodeURIComponent(term_fqn)}/effective-parts${qs({ repo_id })}`,
    ),

  // Code
  listCodeTypes: (opts?: { repo_id?: string; kind?: string; role?: string }) =>
    fetchJson<CodeTypeDTO[]>(`/api/ontology/code-types${qs(opts ?? {})}`),
  getCodeType: (fqn: string) =>
    fetchJson<CodeTypeDTO | null>(`/api/ontology/code-types/${encodeURIComponent(fqn)}`),
  getCallSites: (caller_method_fqn: string) =>
    fetchJson<CallSiteDTO[]>(
      `/api/ontology/code-methods/${encodeURIComponent(caller_method_fqn)}/call-sites`,
    ),

  // Action
  listActions: (opts?: {
    repo_id?: string;
    kind?: ActionKind;
    declared_on_term?: string;
    verification_min?: VerificationLevel;
  }) => fetchJson<ActionDTO[]>(`/api/ontology/actions${qs(opts ?? {})}`),
  getAction: (fqn: string) =>
    fetchJson<ActionDTO | null>(`/api/ontology/actions/${encodeURIComponent(fqn)}`),
  getRealizationsForInputType: (action_fqn: string, code_type_fqn: string) =>
    fetchJson<RealizationDTO[]>(
      `/api/ontology/actions/${encodeURIComponent(action_fqn)}/realizations-for-input${qs({
        code_type_fqn,
      })}`,
    ),
  resolvePath: (action_fqn: string, slot_path: string, repo_id?: string) =>
    fetchJson<{ ok: boolean; last_term_fqn: string | null; error: string }>(
      `/api/ontology/actions/${encodeURIComponent(action_fqn)}/resolve-path${qs({
        slot_path,
        repo_id,
      })}`,
    ),

  // Anchor
  getAnchorBindingsForAction: (action_fqn: string) =>
    fetchJson<AnchorBindingDTO[]>(
      `/api/ontology/actions/${encodeURIComponent(action_fqn)}/anchor-bindings`,
    ),
  getAnchorBindingsForMethod: (code_method_fqn: string) =>
    fetchJson<AnchorBindingDTO[]>(
      `/api/ontology/code-methods/${encodeURIComponent(code_method_fqn)}/anchor-bindings`,
    ),

  // Mapping queue
  listUnmappedMethods: (repo_id?: string) =>
    fetchJson<UnmappedMethodDTO[]>(`/api/ontology/queue/unmapped-methods${qs({ repo_id })}`),
  listAmbiguousCallSites: (repo_id?: string) =>
    fetchJson<AmbiguousCallSiteDTO[]>(
      `/api/ontology/queue/ambiguous-call-sites${qs({ repo_id })}`,
    ),
  getVerificationProgress: (repo_id: string) =>
    fetchJson<VerificationProgressDTO>(
      `/api/ontology/queue/verification-progress/${encodeURIComponent(repo_id)}`,
    ),

  // Search
  search: (q: string, opts?: { repo_id?: string; limit?: number }) =>
    fetchJson<SearchHitDTO[]>(`/api/ontology/search${qs({ q, ...opts })}`),

  // ---------------------------------------------------------------------------
  // Repo Import (P3-2) + Recommendation (P3-3)
  // ---------------------------------------------------------------------------
  startRepoImport: (repo_id: string, repo_path: string) =>
    fetchJson<RepoImportJobDTO>(`/api/ontology/repos/import`, {
      method: "POST",
      body: JSON.stringify({ repo_id, repo_path }),
    }),
  getRepoImportStatus: (job_id: string) =>
    fetchJson<RepoImportStatusDTO>(`/api/ontology/repos/import/${encodeURIComponent(job_id)}`),
  /**
   * SSE stream — `event: progress` (다회) → `event: end` (1회).
   * onEvent 받으면 progress / done / error 어느 것이든 호출됨.
   * 반환: cleanup 함수 (호출 시 EventSource close).
   */
  streamRepoImportProgress: (
    job_id: string,
    onEvent: (e: RepoImportStatusDTO, eventType: "progress" | "end") => void,
    onError?: (err: Event) => void,
  ): (() => void) => {
    const url = `${API_BASE}/api/ontology/repos/import/${encodeURIComponent(job_id)}/stream`;
    const es = new EventSource(url);
    es.addEventListener("progress", (ev: MessageEvent) => {
      try {
        onEvent(JSON.parse(ev.data) as RepoImportStatusDTO, "progress");
      } catch (err) {
        // ignore parse errors — status poll fallback covers gaps
        console.warn("[repo-import] progress parse failed", err);
      }
    });
    es.addEventListener("end", (ev: MessageEvent) => {
      try {
        onEvent(JSON.parse(ev.data) as RepoImportStatusDTO, "end");
      } catch (err) {
        console.warn("[repo-import] end parse failed", err);
      }
      es.close();
    });
    es.onerror = (err) => {
      onError?.(err);
      es.close();
    };
    return () => es.close();
  },
  recommendForRepo: (
    repo_id: string,
    opts?: { persist?: boolean; min_confidence?: number },
  ) =>
    fetchJson<RecommendationResponseDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/recommend${qs({
        persist: opts?.persist ? "true" : undefined,
        min_confidence: opts?.min_confidence,
      })}`,
      { method: "POST" },
    ),

  // P3-5 Graph
  getOntologyGraph: (
    repo_id: string,
    opts?: {
      mode?: "neighborhood" | "path" | "cluster";
      focus_fqn?: string;
      target_fqn?: string;
      n_max?: number;
      hops?: number;            // deprecated, n_max 권장
      include_kinds?: string;
      connected_only?: boolean;
    },
  ) =>
    fetchJson<OntologyGraphDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/graph${qs(opts ?? {})}`,
    ),

  // V7 Modules tree (P3D-1)
  getModules: (repo_id: string, min_classes = 0) =>
    fetchJson<ModulesResponseDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/modules${qs({ min_classes })}`,
    ),

  // R4-T2.2 Perspective CRUD
  listPerspectives: (repo_id: string) =>
    fetchJson<PerspectiveDTO[]>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/perspectives`,
    ),
  getPerspective: (repo_id: string, perspective_id: number) =>
    fetchJson<PerspectiveDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/perspectives/${perspective_id}`,
    ),
  createPerspective: (repo_id: string, body: PerspectiveCreateDTO) =>
    fetchJson<PerspectiveDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/perspectives`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  updatePerspective: (repo_id: string, perspective_id: number, body: PerspectiveUpdateDTO) =>
    fetchJson<PerspectiveDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/perspectives/${perspective_id}`,
      { method: "PUT", body: JSON.stringify(body) },
    ),
  deletePerspective: async (repo_id: string, perspective_id: number) => {
    const url = `${API_BASE}/api/ontology/repos/${encodeURIComponent(repo_id)}/perspectives/${perspective_id}`;
    const res = await fetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text().catch(() => "")}`);
  },
  getModuleInventory: (repo_id: string, opts: { package: string; recursive?: boolean }) =>
    fetchJson<ModuleInventoryItemDTO[]>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/modules/inventory${qs(opts)}`,
    ),
  getModuleInventoryActions: (repo_id: string, opts: { package: string; recursive?: boolean }) =>
    fetchJson<ModuleActionInventoryItemDTO[]>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/modules/inventory/actions${qs(opts)}`,
    ),
  listBusinessRules: (opts?: { repo_id?: string }) =>
    fetchJson<BusinessRuleDTO[]>(`/api/ontology/business-rules${qs(opts ?? {})}`),
  listAnchorBindings: (opts?: { repo_id?: string }) =>
    fetchJson<AnchorBindingDTO[]>(`/api/ontology/anchor-bindings${qs(opts ?? {})}`),

  // P3-6 Mapping Queue actions
  getMappingQueue: (repo_id: string, limit = 200) =>
    fetchJson<MappingQueueDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/queue${qs({ limit })}`,
    ),
  confirmTerm: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/terms/${encodeURIComponent(fqn)}/confirm`,
      { method: "POST" },
    ),
  rejectTerm: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/terms/${encodeURIComponent(fqn)}/reject`,
      { method: "POST" },
    ),
  confirmActionCandidate: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/actions/${encodeURIComponent(fqn)}/confirm`,
      { method: "POST" },
    ),
  rejectActionCandidate: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/actions/${encodeURIComponent(fqn)}/reject`,
      { method: "POST" },
    ),
  confirmRealization: (repo_id: string, tr_id: number) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/type-realizations/${tr_id}/confirm`,
      { method: "POST" },
    ),
  rejectRealization: (repo_id: string, tr_id: number) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/type-realizations/${tr_id}/reject`,
      { method: "POST" },
    ),

  // ---------------------------------------------------------------------------
  // 5-ii Stage 1 — confirmed toggle (Term / Action / BR / Anchor)
  // unconfirm = row 보존 + confirmed=false. reject = row 삭제 (queue 패턴).
  // ---------------------------------------------------------------------------
  unconfirmTerm: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/terms/${encodeURIComponent(fqn)}/unconfirm`,
      { method: "POST" },
    ),
  unconfirmAction: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/actions/${encodeURIComponent(fqn)}/unconfirm`,
      { method: "POST" },
    ),
  confirmBusinessRule: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/business-rules/${encodeURIComponent(fqn)}/confirm`,
      { method: "POST" },
    ),
  unconfirmBusinessRule: (repo_id: string, fqn: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/business-rules/${encodeURIComponent(fqn)}/unconfirm`,
      { method: "POST" },
    ),
  confirmAnchorBinding: (repo_id: string, anchor_id: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/anchor-bindings/${encodeURIComponent(anchor_id)}/confirm`,
      { method: "POST" },
    ),
  unconfirmAnchorBinding: (repo_id: string, anchor_id: string) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/anchor-bindings/${encodeURIComponent(anchor_id)}/unconfirm`,
      { method: "POST" },
    ),

  // ---------------------------------------------------------------------------
  // 5-ii Stage 2 — inline field PATCH (Term / Action / BR / Anchor)
  // None 으로 보낸 field 는 변경 안 됨. Backend 가 partial update 처리.
  // ---------------------------------------------------------------------------
  patchTerm: (repo_id: string, fqn: string, patch: TermPatchDTO) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/terms/${encodeURIComponent(fqn)}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
  patchAction: (repo_id: string, fqn: string, patch: ActionPatchDTO) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/actions/${encodeURIComponent(fqn)}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
  patchBusinessRule: (repo_id: string, fqn: string, patch: BRPatchDTO) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/business-rules/${encodeURIComponent(fqn)}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
  patchAnchorBinding: (repo_id: string, anchor_id: string, patch: AnchorPatchDTO) =>
    fetchJson<QueueActionResultDTO>(
      `/api/ontology/repos/${encodeURIComponent(repo_id)}/anchor-bindings/${encodeURIComponent(anchor_id)}`,
      { method: "PATCH", body: JSON.stringify(patch) },
    ),
};

// ---------------------------------------------------------------------------
// 5-ii Stage 2 — Patch DTOs (1:1 with backend Pydantic models)
// ---------------------------------------------------------------------------
export interface TermPatchDTO {
  label?: string;
  aliases?: string[];
  description?: string;
  domain?: string;
  value_type?: string;
  unit?: string;
  enum_values?: string[];
}

export interface ActionPatchDTO {
  label?: string;
  aliases?: string[];
  description?: string;
}

export interface BRPatchDTO {
  statement?: string;
  severity?: "hard" | "soft";
}

export interface AnchorPatchDTO {
  anchor_locator?: string;
  target_slot?: string;
  rationale?: string;
}

// ---------------------------------------------------------------------------
// Mapping queue DTOs (P3-6)
// ---------------------------------------------------------------------------
export interface QueueTermDTO {
  fqn: string;
  label: string;
  kind: string;
  domain: string;
  is_root_entity: boolean;
  struct_like_hint: boolean;
  aliases: string[];
}

export interface QueueActionItemDTO {
  fqn: string;
  label: string;
  kind: string;
  declared_on_term: string | null;
  verification_level: string;
  realization_count: number;
}

export interface QueueRealizationDTO {
  id: number;
  code_type_fqn: string;
  term_fqn: string;
  scope: "primary" | "partial";
  confidence: number;
  rationale: string;
}

export interface MappingQueueDTO {
  repo_id: string;
  summary: { terms: number; actions: number; type_realizations: number; total: number };
  terms: QueueTermDTO[];
  actions: QueueActionItemDTO[];
  type_realizations: QueueRealizationDTO[];
}

export interface QueueActionResultDTO {
  ok: boolean;
  action: "confirmed" | "rejected";
  target: string;
}

// ---------------------------------------------------------------------------
// Graph DTOs (P3-5)
// ---------------------------------------------------------------------------
export type GraphNodeKind = "term" | "code_type" | "action" | "domain";
export type GraphEdgeKind =
  | "extends" | "implements"
  | "composition"
  | "type_realization_primary" | "type_realization_partial"
  | "realization"
  | "contains";

export interface GraphNodeDTO {
  id: string;
  label: string;
  kind: GraphNodeKind;
  role: string | null;
  domain: string | null;
  confirmed: boolean;
  extra: Record<string, unknown>;
}

export interface GraphEdgeDTO {
  id: string;
  source: string;
  target: string;
  kind: GraphEdgeKind;
  label: string | null;
}

export interface OntologyGraphDTO {
  repo_id: string;
  nodes: GraphNodeDTO[];
  edges: GraphEdgeDTO[];
  truncated: boolean;
  summary: Record<string, number>;
  focus_fqn: string | null;
  hops: number | null;
}

// V7 Modules tree (D plan)
export interface ModuleNodeDTO {
  path: string;
  name: string;
  direct_classes: number;
  total_classes: number;
  direct_actions: number;
  direct_terms: number;
  confirmed_ratio: number;
  children: ModuleNodeDTO[];
}

export interface ModulesResponseDTO {
  repo_id: string;
  root: ModuleNodeDTO;
  flat_count: number;
}

export interface ModuleInventoryItemDTO {
  fqn: string;
  simple_name: string;
  role: string;
  kind: string;
  has_term: boolean;
  term_fqn: string | null;
  method_count: number;
}

export interface ModuleActionInventoryItemDTO {
  fqn: string;
  name: string;
  kind: string;                    // pure_function / effectful / workflow
  declared_on_term: string | null;
  verification_level: string;
  realization_count: number;
  primary_method_fqn: string | null;
  confirmed: boolean;
}

// R4-T2.2 Perspective DTOs (+ R4-T3.4: compound, 5-kind defaults)
export interface PerspectiveSpecDTO {
  mode: "neighborhood" | "path" | "cluster";
  n_max: number;
  focus_fqn: string | null;
  target_fqn: string | null;
  hops: number | null;
  visible_kinds: string[];
  visible_edge_kinds: string[];
  compound: boolean;
  filter: Record<string, unknown>;
  lens: string | null;
}

export interface PerspectiveDTO {
  id: number;
  name: string;
  repo_id: string;
  description: string;
  spec: PerspectiveSpecDTO;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface PerspectiveCreateDTO {
  name: string;
  description?: string;
  spec: PerspectiveSpecDTO;
  owner_id?: string | null;
}

export interface PerspectiveUpdateDTO {
  name?: string;
  description?: string;
  spec?: PerspectiveSpecDTO;
}

// ---------------------------------------------------------------------------
// Repo Import / Recommend DTOs
// ---------------------------------------------------------------------------
export interface RepoImportJobDTO {
  job_id: string;
  repo_id: string;
  repo_path: string;
  status: string;
}

export type RepoImportStatus =
  | "pending" | "parsing" | "adapting" | "classifying" | "storing" | "done" | "error";

export interface RepoImportStatusDTO {
  id: string;
  repo_id: string;
  repo_path: string;
  status: RepoImportStatus;
  files_total: number;
  files_parsed: number;
  types_extracted: number;
  methods_extracted: number;
  call_sites_extracted: number;
  errors: string[];
  message: string;
  progress_pct: number;
  duration_ms: number;
  started_at: number;
  finished_at: number;
}

export interface RecommendationResponseDTO {
  repo_id: string;
  summary: { terms: number; actions: number; type_realizations: number };
  persisted: boolean;
  persisted_counts: { terms?: number; actions?: number; type_realizations?: number };
  term_candidates: Array<{
    suggested: TermDTO;
    derived_from_code_type_fqn: string;
    confidence: number;
    reason: string;
  }>;
  action_candidates: Array<{
    suggested: ActionDTO;
    derived_from_method_fqn: string;
    confidence: number;
    reason: string;
  }>;
  type_realization_candidates: Array<{
    suggested: {
      code_type_fqn: string;
      term_fqn: string;
      scope: "primary" | "partial";
      confidence: number;
      source: string;
      confirmed: boolean;
      rationale: string;
      repo_id: string;
    };
    confidence: number;
    reason: string;
  }>;
}
