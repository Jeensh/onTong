/**
 * Global current-user singleton — bridging React auth context with
 * plain-module code (lockManager, sseClient, etc.).
 *
 * Initialized once from AuthContext on mount. Non-React modules
 * call getCurrentUserName() to get the authenticated user name.
 */

let _userName = "anonymous";

export function setCurrentUser(name: string): void {
  _userName = name;
}

export function getCurrentUserName(): string {
  return _userName;
}
