/**
 * Central lock manager — batches all editor lock refreshes into
 * a single POST /api/lock/batch-refresh every 2 minutes.
 *
 * Instead of N editors each calling refreshLock individually,
 * editors register/unregister their paths, and this manager
 * sends one batch request covering all active locks.
 */

import { batchRefreshLock } from "@/lib/api/wiki";

const SESSION_USER =
  typeof window !== "undefined"
    ? localStorage.getItem("wiki_user") || `user-${Math.random().toString(36).slice(2, 8)}`
    : "anonymous";

const REFRESH_INTERVAL = 120_000; // 2 minutes

class LockManager {
  private activePaths = new Set<string>();
  private intervalId: ReturnType<typeof setInterval> | null = null;

  /** Register a path that has an active lock. Starts the refresh loop if needed. */
  register(path: string): void {
    this.activePaths.add(path);
    if (!this.intervalId) {
      this.intervalId = setInterval(() => this.refresh(), REFRESH_INTERVAL);
    }
  }

  /** Unregister a path (lock released). Stops the loop when no paths remain. */
  unregister(path: string): void {
    this.activePaths.delete(path);
    if (this.activePaths.size === 0 && this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /** Send a single batch-refresh for all registered paths. */
  private async refresh(): Promise<void> {
    if (this.activePaths.size === 0) return;
    try {
      await batchRefreshLock([...this.activePaths], SESSION_USER);
    } catch {
      // Silently ignore — locks will expire naturally and re-acquire on next edit
    }
  }
}

export const lockManager = new LockManager();
