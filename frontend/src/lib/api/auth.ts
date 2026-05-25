import type { User } from "@/types/auth";

/**
 * Fetch the current user. Returns `null` when the backend is unreachable or
 * the user is unauthenticated (401/404) — these are normal states, not errors.
 * Throws only on unexpected server failures (5xx, parse errors).
 */
export async function fetchCurrentUser(): Promise<User | null> {
  let res: Response;
  try {
    res = await fetch("/api/auth/me");
  } catch {
    // Network error / backend down. Treat as unauthenticated.
    return null;
  }
  if (res.status === 401 || res.status === 403 || res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch user (${res.status})`);
  }
  return res.json() as Promise<User>;
}
