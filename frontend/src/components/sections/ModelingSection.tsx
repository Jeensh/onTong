"use client";

import { WorkbenchShell } from "./modeling/WorkbenchShell";

/**
 * Section 2 — Modeling Workbench.
 * 2026-05-02 C6 Phase 1: V6 prototype 의 React 구현 시작.
 */
export function ModelingSection() {
  return (
    <div className="h-full overflow-hidden">
      <WorkbenchShell />
    </div>
  );
}
