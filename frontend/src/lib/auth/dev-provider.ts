/**
 * Dev/demo auth provider — always authenticated, no credentials required.
 */

import type { AuthProvider, User } from "./types";

const DEV_USER: User = {
  id: "dev-user",
  name: "개발자",
  email: "dev@ontong.local",
  roles: ["admin"],
};

export class DevAuthProvider implements AuthProvider {
  async init(): Promise<User> {
    return DEV_USER;
  }

  async login(): Promise<User> {
    return DEV_USER;
  }

  async logout(): Promise<void> {
    // No-op in dev mode
  }

  async getAuthHeaders(): Promise<Record<string, string>> {
    // No auth headers needed in dev mode
    return {};
  }
}
