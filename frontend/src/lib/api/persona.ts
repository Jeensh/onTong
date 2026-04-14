/**
 * API client for per-user AI persona.
 *
 * The persona is a regular wiki document edited in Tiptap.
 * This API only ensures the file exists (creates template if needed).
 */

export async function ensurePersonaFile(): Promise<{ path: string; created: boolean }> {
  const res = await fetch("/api/persona/ensure", { method: "POST" });
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}
