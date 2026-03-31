/**
 * Auth-aware fetch wrapper.
 *
 * Usage:
 *   const { authFetch } = useAuthFetch();
 *   const res = await authFetch("/api/wiki/tree");
 *
 * Automatically attaches auth headers from the current provider.
 * When provider changes (e.g., noop → SSO), all API calls get updated headers.
 */

import { useCallback } from "react";
import { useAuth } from "./AuthContext";

export function useAuthFetch() {
  const { getAuthHeaders } = useAuth();

  const authFetch = useCallback(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const headers = await getAuthHeaders();
      const merged = new Headers(init?.headers);
      for (const [key, value] of Object.entries(headers)) {
        merged.set(key, value);
      }
      return fetch(input, { ...init, headers: merged });
    },
    [getAuthHeaders]
  );

  return { authFetch };
}
