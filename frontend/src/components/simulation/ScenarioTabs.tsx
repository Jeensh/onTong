"use client";

import { SCENARIO_META } from "@/lib/simulation/types";
import type { ScenarioType } from "@/lib/simulation/types";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { cn } from "@/lib/utils";

// 탭 순서: A/B/C 에이전트 시나리오 + Slab 설계 시뮬레이터
const TAB_IDS: ScenarioType[] = ["A", "B", "C", "SLAB_DESIGN"];

const TAB_LABELS: Record<ScenarioType, string> = {
  A: "시나리오 A",
  B: "시나리오 B",
  C: "시나리오 C",
  SLAB_DESIGN: "Slab 설계",
};

export function ScenarioTabs() {
  const { activeScenario, setActiveScenario, isRunning } = useSimulationStore();

  return (
    <div className="flex items-center gap-1 px-4 py-2 border-b bg-muted/30">
      <span className="text-xs font-medium text-muted-foreground mr-2">시나리오:</span>
      {TAB_IDS.map((id) => {
        const meta = SCENARIO_META[id];
        const isActive = activeScenario === id;
        // Slab 설계 탭은 에이전트 실행 중이어도 전환 가능
        const disabled = isRunning && id !== "SLAB_DESIGN" && !isActive;
        return (
          <button
            key={id}
            disabled={disabled}
            onClick={() => setActiveScenario(id)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
              isActive
                ? "text-white shadow-sm"
                : "bg-background border hover:bg-muted text-muted-foreground",
              disabled && "opacity-50 cursor-not-allowed",
              // 구분선: Slab 탭 앞에 약간의 간격
              id === "SLAB_DESIGN" && "ml-2 border-l border-border"
            )}
            style={isActive ? { backgroundColor: meta.color } : undefined}
            title={meta.description}
          >
            <span>{meta.icon}</span>
            <span>{TAB_LABELS[id]}</span>
          </button>
        );
      })}

      {/* Active scenario description */}
      <div className="ml-4 text-xs text-muted-foreground truncate max-w-xs">
        {SCENARIO_META[activeScenario].description}
      </div>
    </div>
  );
}
