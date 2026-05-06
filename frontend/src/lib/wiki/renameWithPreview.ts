"use client";

export interface ImpactItem {
  source_path: string;
  ref_count: number;
}

export interface RenamePlanResponse {
  audit_id: string;
  old_path: string;
  new_path: string;
  inbound_count: number;
  unique_inbound_sources: number;
  confirm_required: boolean;
  estimated_seconds: number;
  impact_items: ImpactItem[];
}

export interface RenameExecResponse {
  old_path: string;
  new_path: string;
  audit_id: string;
  status: "success" | "partial" | "queued" | "failed";
  inbound_done: number;
  inbound_failed: number;
  inbound_total: number;
  warning?: string;
}

const userIdHeader = (): Record<string, string> => {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem("ontong_user_id") || "demo";
  return { "X-User-Id": id };
};

export async function fetchRenamePlan(oldPath: string, newPath: string): Promise<RenamePlanResponse> {
  const url = `/api/wiki/rename-preview/${encodeURIComponent(oldPath)}?to=${encodeURIComponent(newPath)}`;
  const r = await fetch(url, { headers: userIdHeader() });
  if (!r.ok) throw new Error(`rename-preview HTTP ${r.status}: ${await r.text()}`);
  return r.json();
}

export async function executeRename(oldPath: string, newPath: string): Promise<RenameExecResponse> {
  const url = `/api/wiki/file/${encodeURIComponent(oldPath)}`;
  const r = await fetch(url, {
    method: "PATCH",
    headers: { ...userIdHeader(), "Content-Type": "application/json" },
    body: JSON.stringify({ new_path: newPath }),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`rename HTTP ${r.status}: ${text}`);
  }
  return r.json();
}
