/**
 * Auth abstraction types.
 *
 * To add a new auth provider (SSO, LDAP, OIDC, etc.):
 *   1. Implement AuthProvider interface
 *   2. Pass it to <AuthContextProvider provider={yourProvider}>
 */

export interface User {
  id: string;
  name: string;
  email: string;
  roles: string[];
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthProvider {
  /** Initialize the provider (e.g., check stored tokens, SSO redirect) */
  init(): Promise<User | null>;

  /** Login — provider decides the mechanism (redirect, popup, form, etc.) */
  login(): Promise<User>;

  /** Logout — clear tokens, session, redirect, etc. */
  logout(): Promise<void>;

  /**
   * Return headers to attach to every API request.
   * e.g., { Authorization: "Bearer <token>" }
   */
  getAuthHeaders(): Promise<Record<string, string>>;
}
