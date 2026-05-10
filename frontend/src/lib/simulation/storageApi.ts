// Phase 6 — Scenario / Run / Regression / Bridge / Job API client.
// 모든 호출은 /api/simulation/* 프록시 (next.config.ts → :8001)

const BASE = "/api/simulation";

// ─── Types ──────────────────────────────────────────────────────────

export interface Scenario {
  id: string;
  name: string;
  description?: string;
  step_id: string;
  inputs: Record<string, unknown>;
  tags: string[];
  source: "yaml" | "user" | "auto";
  created_at?: string;
  updated_at?: string;
}

export interface RunRecord {
  id: string;
  scenario_id?: string | null;
  step_id: string;
  inputs: Record<string, unknown>;
  outputs?: Record<string, unknown> | null;
  stage?: string | null;
  error_code?: string | null;
  started_at: string;
  completed_at?: string | null;
  elapsed_ms?: number | null;
  is_baseline: boolean;
  parent_run_id?: string | null;
}

export interface RegressionDiffField {
  path: string;
  before: unknown;
  after: unknown;
}

export interface RegressionResult {
  baseline: RunRecord;
  candidate: RunRecord;
  summary: {
    stage_changed: boolean;
    error_code_changed: boolean;
    field_diffs: RegressionDiffField[];
    diff_count: number;
  };
}

export interface BridgeOverlay {
  input_term: string;
  canonical?: string | null;
  matched: boolean;
  impacted_steps: string[];
  step_count: number;
  scenario_suggestions: {
    title: string;
    step_id: string;
    inputs: Record<string, unknown>;
    rationale: string;
    tags: string[];
  }[];
  ontology: {
    available: boolean;
    reason?: string;
    status?: string;
    result?: unknown;
  };
}

export interface JobInfo {
  id: string;
  step_id: string;
  scenario_id?: string | null;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  submitted_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  elapsed_ms?: number | null;
  run_id?: string | null;
  outputs?: Record<string, unknown> | null;
  error?: string | null;
  regression?: {
    baseline_run_id: string;
    diff_count: number;
    stage_changed: boolean;
    error_code_changed: boolean;
    field_diffs: RegressionDiffField[];
  } | null;
  inputs?: Record<string, unknown>;
}

// ─── Scenarios ──────────────────────────────────────────────────────

/** {items: [...]} 또는 [...] 양쪽 응답 형식 안전 처리. */
function asArray<T>(j: unknown): T[] {
  if (Array.isArray(j)) return j as T[];
  if (j && typeof j === "object" && Array.isArray((j as { items?: unknown }).items)) {
    return (j as { items: T[] }).items;
  }
  return [];
}

export async function listScenarios(opts: { stepId?: string; tag?: string } = {}): Promise<Scenario[]> {
  const params = new URLSearchParams();
  if (opts.stepId) params.set("step_id", opts.stepId);
  if (opts.tag) params.set("tag", opts.tag);
  const r = await fetch(`${BASE}/scenarios?${params}`);
  if (!r.ok) throw new Error(`listScenarios: ${r.status}`);
  return asArray<Scenario>(await r.json());
}

export async function getScenario(id: string): Promise<Scenario> {
  const r = await fetch(`${BASE}/scenarios/${id}`);
  if (!r.ok) throw new Error(`getScenario: ${r.status}`);
  return r.json();
}

export async function createScenario(s: Omit<Scenario, "created_at" | "updated_at" | "source">): Promise<Scenario> {
  const r = await fetch(`${BASE}/scenarios`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(s),
  });
  if (!r.ok) throw new Error(`createScenario: ${r.status}`);
  return r.json();
}

export async function deleteScenario(id: string): Promise<void> {
  const r = await fetch(`${BASE}/scenarios/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`deleteScenario: ${r.status}`);
}

export async function seedScenarios(): Promise<{ loaded: number }> {
  const r = await fetch(`${BASE}/scenarios/seed`, { method: "POST" });
  if (!r.ok) throw new Error(`seedScenarios: ${r.status}`);
  return r.json();
}

export async function runScenario(id: string, parentRunId?: string): Promise<RunRecord> {
  const r = await fetch(`${BASE}/scenarios/${id}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parent_run_id: parentRunId ?? null }),
  });
  if (!r.ok) throw new Error(`runScenario: ${r.status}`);
  return r.json();
}

export async function registerBaseline(scenarioId: string, runId: string): Promise<void> {
  const r = await fetch(`${BASE}/scenarios/${scenarioId}/baseline?run_id=${encodeURIComponent(runId)}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(`registerBaseline: ${r.status}`);
}

// ─── Runs ────────────────────────────────────────────────────────────

export async function listRuns(opts: {
  scenarioId?: string; stepId?: string; onlyBaseline?: boolean; limit?: number;
} = {}): Promise<RunRecord[]> {
  const params = new URLSearchParams();
  if (opts.scenarioId) params.set("scenario_id", opts.scenarioId);
  if (opts.stepId) params.set("step_id", opts.stepId);
  if (opts.onlyBaseline) params.set("only_baseline", "true");
  if (opts.limit) params.set("limit", String(opts.limit));
  const r = await fetch(`${BASE}/runs?${params}`);
  if (!r.ok) throw new Error(`listRuns: ${r.status}`);
  return asArray<RunRecord>(await r.json());
}

export async function getRun(id: string): Promise<RunRecord> {
  const r = await fetch(`${BASE}/runs/${id}`);
  if (!r.ok) throw new Error(`getRun: ${r.status}`);
  return r.json();
}

export async function getLineage(id: string): Promise<{
  upstream: { run_id: string; relation: string; at: string }[];
  downstream: { run_id: string; relation: string; at: string }[];
}> {
  const r = await fetch(`${BASE}/runs/${id}/lineage`);
  if (!r.ok) throw new Error(`getLineage: ${r.status}`);
  return r.json();
}

export async function regressionDiff(baselineRunId: string, candidateRunId: string): Promise<RegressionResult> {
  const r = await fetch(`${BASE}/runs/regression`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ baseline_run_id: baselineRunId, candidate_run_id: candidateRunId }),
  });
  if (!r.ok) throw new Error(`regressionDiff: ${r.status}`);
  return r.json();
}

// ─── Bridge ──────────────────────────────────────────────────────────

export interface ScenarioDraft {
  title: string;
  rationale: string;
  step_id: string;
  inputs: Record<string, unknown>;
  tags: string[];
  confidence: number;
  extracted_term: string | null;
  method: "llm" | "fallback";
}

export async function bridgeAssist(naturalLanguage: string, preferLlm = true): Promise<ScenarioDraft> {
  const r = await fetch(`${BASE}/bridge/assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ natural_language: naturalLanguage, prefer_llm: preferLlm }),
  });
  if (!r.ok) throw new Error(`bridgeAssist: ${r.status}`);
  return r.json();
}

export async function saveAssistAsScenario(draft: {
  name: string; step_id: string; inputs: Record<string, unknown>;
  description?: string; tags?: string[];
}): Promise<Scenario> {
  const r = await fetch(`${BASE}/scenarios/from-assist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!r.ok) throw new Error(`saveAssistAsScenario: ${r.status}`);
  return r.json();
}

export async function exportScenariosYaml(opts: { stepId?: string; tag?: string } = {}): Promise<string> {
  const params = new URLSearchParams();
  if (opts.stepId) params.set("step_id", opts.stepId);
  if (opts.tag) params.set("tag", opts.tag);
  const r = await fetch(`${BASE}/scenarios/export?${params}`);
  if (!r.ok) throw new Error(`exportScenariosYaml: ${r.status}`);
  return r.text();
}

export async function importScenariosYaml(yamlText: string, overwrite = false): Promise<{ imported: number; skipped: number }> {
  const r = await fetch(`${BASE}/scenarios/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ yaml_text: yamlText, overwrite }),
  });
  if (!r.ok) throw new Error(`importScenariosYaml: ${r.status}`);
  return r.json();
}

export async function bridgeTermOverlay(term: string): Promise<BridgeOverlay> {
  const r = await fetch(`${BASE}/bridge/term/${encodeURIComponent(term)}/overlay`);
  if (!r.ok) throw new Error(`bridgeTermOverlay: ${r.status}`);
  return r.json();
}

export async function bridgeListTerms(): Promise<{
  items: { canonical: string; aliases: string[]; step_count: number; steps: string[] }[];
}> {
  const r = await fetch(`${BASE}/bridge/terms`);
  if (!r.ok) throw new Error(`bridgeListTerms: ${r.status}`);
  return r.json();
}

// ─── Jobs ────────────────────────────────────────────────────────────

export async function listJobs(limit = 50): Promise<JobInfo[]> {
  const r = await fetch(`${BASE}/jobs?limit=${limit}`);
  if (!r.ok) throw new Error(`listJobs: ${r.status}`);
  return asArray<JobInfo>(await r.json());
}

export async function submitScenarioJob(scenarioId: string, parentRunId?: string): Promise<JobInfo> {
  const url = parentRunId
    ? `${BASE}/jobs/scenario/${scenarioId}/run?parent_run_id=${encodeURIComponent(parentRunId)}`
    : `${BASE}/jobs/scenario/${scenarioId}/run`;
  const r = await fetch(url, { method: "POST" });
  if (!r.ok) throw new Error(`submitScenarioJob: ${r.status}`);
  return r.json();
}
