/**
 * Phase K — Java ↔ Python differential test API client.
 * /api/simulation/differential/* (next.config.ts → :8001)
 */

const BASE = "/api/simulation/differential";

export interface FieldDiff {
  path: string;
  java: unknown;
  python: unknown;
  is_close: boolean;
}

export interface DifferentialResult {
  status: "ok";
  java_available: boolean;
  java_ok: boolean;
  python_ok: boolean;
  matched_count: number;
  mismatched_count: number;
  field_diffs: FieldDiff[];
  java_elapsed_sec: number;
  python_elapsed_sec: number;
  java_error: string | null;
  python_error: string | null;
  java_payload: Record<string, unknown> | null;
  python_payload: Record<string, unknown> | null;
}

export interface DifferentialStatus {
  java_bridge_available: boolean;
  guide: string;
}

export interface DifferentialRequest {
  order: Record<string, unknown>;
  slab?: Record<string, unknown>;
  rules?: Record<string, unknown>;
  rel_tolerance?: number;
  abs_tolerance?: number;
  java_timeout_sec?: number;
}

export async function getDifferentialStatus(): Promise<DifferentialStatus> {
  const res = await fetch(`${BASE}/status`);
  if (!res.ok) throw new Error(`status ${res.status}`);
  return res.json();
}

export async function runDifferential(req: DifferentialRequest): Promise<DifferentialResult> {
  const res = await fetch(`${BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Differential 실행 실패 (${res.status}): ${detail}`);
  }
  return res.json();
}
