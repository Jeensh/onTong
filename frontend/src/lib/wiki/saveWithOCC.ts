"use client";

/**
 * OCC-aware wiki save helper.
 *
 * Behavior:
 *   1. Caller provides path, content, baseVersion (from last GET's ETag).
 *   2. PUT with If-Match: baseVersion.
 *   3. On 200 → success, returns new ETag (extracted from response headers if present, else fetched fresh).
 *   4. On 409 → returns the conflict payload; caller shows the modal.
 *   5. On other errors → throws.
 */

export interface ConflictPayload {
  conflict: true;
  path: string;
  base_version: string;
  server_version: string;
  server_content: string;
  server_updated_by: string;
}

export interface SaveSuccess {
  conflict?: false;
  newVersion: string | null;
}

export type SaveResult = SaveSuccess | ConflictPayload;

const userIdHeader = (): Record<string, string> => {
  if (typeof window === "undefined") return {};
  const id = localStorage.getItem("ontong_user_id") || "demo";
  return { "X-User-Id": id };
};

// Encode each path segment but keep "/" so FastAPI's {path:path} still sees
// the directory structure.
function encodePath(p: string): string {
  return p
    .split("/")
    .map((seg) => encodeURIComponent(seg))
    .join("/");
}

export async function saveWithOCC(opts: {
  path: string;
  content: string;
  baseVersion: string | null;
  force?: boolean;
}): Promise<SaveResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...userIdHeader(),
  };
  if (opts.baseVersion && !opts.force) {
    headers["If-Match"] = `"${opts.baseVersion}"`;
  }
  // No If-Match when force=true (overwrites server)

  const url = `/api/wiki/file/${encodePath(opts.path)}`;
  const r = await fetch(url, {
    method: "PUT",
    headers,
    body: JSON.stringify({ content: opts.content }),
  });

  if (r.status === 409) {
    const body = await r.json();
    if (body?.detail?.conflict) {
      return body.detail as ConflictPayload;
    }
    throw new Error(`HTTP 409 (unexpected shape): ${JSON.stringify(body)}`);
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail || `HTTP ${r.status}`);
  }

  const newVersion = r.headers.get("etag")?.replace(/^"|"$/g, "") ?? null;
  return { newVersion };
}

/** Fetch current ETag for a path (GET — also warms the response cache). */
export async function fetchETag(path: string): Promise<string | null> {
  const url = `/api/wiki/file/${encodePath(path)}`;
  const r = await fetch(url, { headers: userIdHeader() });
  if (!r.ok) return null;
  return r.headers.get("etag")?.replace(/^"|"$/g, "") ?? null;
}
