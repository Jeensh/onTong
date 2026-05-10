// Phase 7-D — Java→Python transpile API client.
// /api/simulation/transpile/* 프록시 (next.config.ts → :8001)

const BASE = "/api/simulation/transpile";

export interface MethodInfo {
  class_name: string;
  method_name: string;
  return_type: string;
  parameters: [string, string][];
  modifiers: string[];
  signature_line: number;
  end_line: number;
  javadoc: string;
}

export interface LineOrigin {
  /** 1-based line number in python_source */
  line: number;
  kind: "det" | "llm" | "stub" | "human";
  /** 0~1 — det=1.0, stub=0.0, llm=LLM 추론 점수 */
  confidence: number;
  note?: string | null;
}

export interface PythonStepDraft {
  step_id: string;
  function_name: string;
  python_source: string;
  imports: string[];
  rationale: string;
  confidence: number;
  method: "llm" | "fallback";
  /** Phase J — 라인별 신뢰도 영역. 빈 배열이면 라인 단위 시각화 불가 (confidence 단일값만 사용). */
  line_origins: LineOrigin[];
}

export interface FieldDiff {
  path: string;
  before: unknown;
  after: unknown;
}

export interface EquivalenceReport {
  mode: "shadow" | "structural";
  passed: boolean;
  sample_count: number;
  matched: number;
  mismatched: number;
  field_diffs: FieldDiff[];
  structural_errors: string[];
  summary: string;
}

export interface PreviewResponse {
  draft: PythonStepDraft;
  equivalence: EquivalenceReport;
  java_summary: {
    class_name: string;
    method_name: string;
    signature: string;
    lines: string;
    javadoc: string;
  };
}

export async function listMethods(javaPath: string): Promise<MethodInfo[]> {
  const url = `${BASE}/methods?java_path=${encodeURIComponent(javaPath)}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`listMethods ${r.status}: ${await r.text()}`);
  return r.json();
}

export interface PreviewRequest {
  java_path: string;
  method_name: string;
  class_name?: string;
  target_step_id?: string;
  reference_step_id?: string;
  sample_inputs?: Record<string, unknown>[];
  prefer_llm?: boolean;
}

export async function previewTranspile(req: PreviewRequest): Promise<PreviewResponse> {
  const r = await fetch(`${BASE}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`previewTranspile ${r.status}: ${await r.text()}`);
  return r.json();
}

export interface SaveRequest {
  step_id: string;
  function_name: string;
  python_source: string;
  overwrite?: boolean;
}

export interface SaveResponse {
  saved_path: string;
  step_id: string;
  function_name: string;
}

export async function saveTranspiled(req: SaveRequest): Promise<SaveResponse> {
  const r = await fetch(`${BASE}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`saveTranspiled ${r.status}: ${await r.text()}`);
  return r.json();
}
