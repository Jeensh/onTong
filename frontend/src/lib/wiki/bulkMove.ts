"use client";

export interface BulkMoveProgress {
  total: number;
  done: number;
  failed: number;
  current: string | null;
  errors: { path: string; message: string }[];
}

export interface BulkMoveResult {
  total: number;
  done: number;
  failed: number;
  errors: { path: string; message: string }[];
}

const userIdHeader = (): Record<string, string> => {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem("ontong_user_id") || "demo";
  return { "X-User-Id": id };
};

export async function bulkMove(opts: {
  pairs: { oldPath: string; newPath: string }[];
  onProgress?: (p: BulkMoveProgress) => void;
}): Promise<BulkMoveResult> {
  const total = opts.pairs.length;
  const errors: { path: string; message: string }[] = [];
  let done = 0;
  let failed = 0;

  for (const { oldPath, newPath } of opts.pairs) {
    opts.onProgress?.({ total, done, failed, current: oldPath, errors: [...errors] });
    try {
      const r = await fetch(`/api/wiki/file/${encodeURIComponent(oldPath)}`, {
        method: "PATCH",
        headers: { ...userIdHeader(), "Content-Type": "application/json" },
        body: JSON.stringify({ new_path: newPath }),
      });
      if (!r.ok) {
        const body = await r.text();
        let msg = `HTTP ${r.status}`;
        try {
          const j = JSON.parse(body);
          msg = j?.detail?.error ?? j?.detail?.message ?? body;
        } catch { /* keep raw */ }
        errors.push({ path: oldPath, message: msg });
        failed++;
      } else {
        done++;
      }
    } catch (e: unknown) {
      const err = e as { message?: string } | null;
      errors.push({ path: oldPath, message: String(err?.message ?? e) });
      failed++;
    }
  }

  opts.onProgress?.({ total, done, failed, current: null, errors: [...errors] });
  return { total, done, failed, errors };
}
