import type { WikiFile, WikiTreeNode } from "@/types";

// ---- ETag Cache ----
const etagCache = new Map<string, { etag: string; data: unknown }>();

async function fetchWithETag<T>(url: string): Promise<T> {
  const cached = etagCache.get(url);
  const headers: Record<string, string> = {};
  if (cached) {
    headers["If-None-Match"] = cached.etag;
  }
  const res = await fetch(url, { headers });
  if (res.status === 304 && cached) {
    return cached.data as T;
  }
  if (!res.ok) throw new Error(`GET ${url} failed: ${res.status}`);
  const data = await res.json();
  const etag = res.headers.get("etag");
  if (etag) {
    etagCache.set(url, { etag, data });
  }
  return data as T;
}

// ---- Lock API ----
export interface LockStatus {
  locked: boolean;
  path: string;
  user: string;
  remaining: number;
  message?: string;
}

export async function acquireLock(path: string, user: string): Promise<LockStatus> {
  const res = await fetch("/api/lock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, user }),
  });
  return res.json();
}

export async function releaseLock(path: string, user: string): Promise<void> {
  await fetch(`/api/lock?path=${encodeURIComponent(path)}&user=${encodeURIComponent(user)}`, {
    method: "DELETE",
  });
}

export async function getLockStatus(path: string): Promise<LockStatus> {
  const res = await fetch(`/api/lock/status?path=${encodeURIComponent(path)}`);
  return res.json();
}

export async function refreshLock(path: string, user: string): Promise<void> {
  await fetch(`/api/lock/refresh?path=${encodeURIComponent(path)}&user=${encodeURIComponent(user)}`, {
    method: "POST",
  });
}

export async function batchRefreshLock(paths: string[], user: string): Promise<{ refreshed: number; total: number }> {
  const res = await fetch("/api/lock/batch-refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paths, user }),
  });
  return res.json();
}

export async function fetchTree(): Promise<WikiTreeNode[]> {
  return fetchWithETag<WikiTreeNode[]>("/api/wiki/tree?depth=1");
}

export async function fetchSubtree(path: string): Promise<WikiTreeNode[]> {
  const res = await fetch(`/api/wiki/tree/${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error(`GET /api/wiki/tree/${path} failed: ${res.status}`);
  return res.json();
}

export async function fetchFile(path: string): Promise<WikiFile> {
  const res = await fetch(`/api/wiki/file/${path}`);
  if (!res.ok)
    throw new Error(`GET /api/wiki/file/${path} failed: ${res.status}`);
  return res.json();
}

export async function saveFile(
  path: string,
  content: string
): Promise<WikiFile> {
  const res = await fetch(`/api/wiki/file/${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok)
    throw new Error(`PUT /api/wiki/file/${path} failed: ${res.status}`);
  return res.json();
}
