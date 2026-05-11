/**
 * Audit log API client — matches backend/modeling/api/audit_api.py 1:1.
 *
 * Endpoints:
 *   GET /api/ontology/audit/{entity_kind}/{entity_id}?repo_id=X&limit=50
 *   GET /api/ontology/audit/recent?repo_id=X&limit=50
 *
 * Uses cache: "no-store" (project pattern from ontology.ts).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export type AuditEntityKind = "term" | "action" | "rule" | "anchor" | "code_type";
export type AuditAction =
  | "patched"
  | "confirmed"
  | "unconfirmed"
  | "created"
  | "deleted";

export interface AuditLogDTO {
  id: number;
  repo_id: string;
  entity_kind: string;
  entity_id: string;
  /** NULL when whole-entity action (confirm / unconfirm / created / deleted). */
  field: string | null;
  /** JSON string. Partial dict — only the changed field(s). Caller does JSON.parse. */
  before_json: string;
  after_json: string;
  action: string;            // AuditAction (string for forward compat)
  user_id: string | null;
  /** ISO 8601 timestamp. */
  ts: string;
}

function qs(params: Record<string, string | number | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Audit API ${res.status}: ${txt || res.statusText}`);
  }
  return res.json();
}

export const auditApi = {
  /**
   * 단일 entity 의 최근 audit row (ts DESC).
   * `entity_id` 는 fqn (term/action/rule/code_type) 또는 anchor id.
   */
  getEntityHistory: (
    entity_kind: AuditEntityKind,
    entity_id: string,
    repo_id?: string,
    limit?: number,
  ): Promise<AuditLogDTO[]> =>
    fetchJson<AuditLogDTO[]>(
      `/api/ontology/audit/${entity_kind}/${encodeURIComponent(entity_id)}${qs({
        repo_id,
        limit,
      })}`,
    ),

  /** repo 전체 (또는 글로벌) 최근 audit row (ts DESC). 짧은 dashboard 용. */
  getRecent: (repo_id?: string, limit?: number): Promise<AuditLogDTO[]> =>
    fetchJson<AuditLogDTO[]>(`/api/ontology/audit/recent${qs({ repo_id, limit })}`),
};
