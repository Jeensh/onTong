"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import type { AuthProvider, AuthState, User } from "./types";

interface AuthContextValue extends AuthState {
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAuthHeaders: () => Promise<Record<string, string>>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthContextProvider({
  provider,
  children,
}: {
  provider: AuthProvider;
  children: ReactNode;
}) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Initialize on mount
  useEffect(() => {
    provider
      .init()
      .then((user) =>
        setState({
          user,
          isAuthenticated: user !== null,
          isLoading: false,
        })
      )
      .catch(() =>
        setState({ user: null, isAuthenticated: false, isLoading: false })
      );
  }, [provider]);

  const login = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true }));
    try {
      const user = await provider.login();
      setState({ user, isAuthenticated: true, isLoading: false });
    } catch {
      setState((s) => ({ ...s, isLoading: false }));
      throw new Error("Login failed");
    }
  }, [provider]);

  const logout = useCallback(async () => {
    await provider.logout();
    setState({ user: null, isAuthenticated: false, isLoading: false });
  }, [provider]);

  const getAuthHeaders = useCallback(
    () => provider.getAuthHeaders(),
    [provider]
  );

  return (
    <AuthContext.Provider
      value={{ ...state, login, logout, getAuthHeaders }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within <AuthContextProvider>");
  }
  return ctx;
}
