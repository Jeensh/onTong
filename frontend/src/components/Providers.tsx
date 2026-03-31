"use client";

import { useMemo, type ReactNode } from "react";
import { AuthContextProvider, DevAuthProvider } from "@/lib/auth";

/**
 * Client-side providers wrapper.
 *
 * To switch auth providers, replace DevAuthProvider here
 * (or select based on env var / config).
 */
export function Providers({ children }: { children: ReactNode }) {
  const authProvider = useMemo(() => new DevAuthProvider(), []);

  return (
    <AuthContextProvider provider={authProvider}>
      {children}
    </AuthContextProvider>
  );
}
