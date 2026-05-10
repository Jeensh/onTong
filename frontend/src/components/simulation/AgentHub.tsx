"use client";

import { useState } from "react";
import { Agent1ImpactPanel } from "./Agent1ImpactPanel";
import { Agent2RunPanel } from "./Agent2RunPanel";
import { Agent3LocatorPanel } from "./Agent3LocatorPanel";
import { Agent4ExplorerForm } from "./Agent4ExplorerForm";
import { AgentSidebar, type AgentKey } from "./AgentSidebar";

export function AgentHub() {
  const [active, setActive] = useState<AgentKey>("test");
  const [handoffStepId, setHandoffStepId] = useState<string | null>(null);

  // Agent 3 → Agent 2 핸드오프
  const handoffToTest = (stepId: string) => {
    setHandoffStepId(stepId);
    setActive("test");
  };

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      <AgentSidebar active={active} onChange={setActive} />
      <main className="flex-1 overflow-auto p-6">
        {active === "impact" && <Agent1ImpactPanel />}
        {active === "test" && (
          <Agent2RunPanel
            initialStepId={handoffStepId ?? undefined}
            onConsumeInitial={() => setHandoffStepId(null)}
          />
        )}
        {active === "locator" && <Agent3LocatorPanel onHandoffToTest={handoffToTest} />}
        {active === "explorer" && <Agent4ExplorerForm />}
      </main>
    </div>
  );
}
