"use client";

import { ChevronDown, Plus, Trash2 } from "lucide-react";
import { useSimulationStore } from "@/lib/simulation/useSimulationStore";
import { SCENARIO_META } from "@/lib/simulation/types";
import { deleteCustomAgent as apiDeleteCustomAgent } from "@/lib/simulation/api";
import { cn } from "@/lib/utils";
import type { ScenarioType } from "@/lib/simulation/types";

const BUILT_IN_SCENARIOS: { id: ScenarioType; label: string }[] = [
  { id: "A", label: "시나리오 A" },
  { id: "B", label: "시나리오 B" },
  { id: "C", label: "시나리오 C" },
  { id: "SLAB_DESIGN", label: "Slab 설계" },
];

export function SimulationSidebar() {
  const {
    activeView,
    setActiveView,
    customAgents,
    deleteCustomAgent,
    isRunning,
    builderRunning,
  } = useSimulationStore();

  const handleDeleteAgent = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiDeleteCustomAgent(id);
      deleteCustomAgent(id);
      // 삭제된 에이전트가 현재 활성화된 경우 hub로 이동
      if (activeView.kind === "custom_agent" && activeView.agentId === id) {
        setActiveView({ kind: "custom_hub" });
      }
    } catch (err) {
      console.error("Agent 삭제 실패:", err);
    }
  };

  return (
    <div className="flex flex-col h-full w-52 shrink-0 border-r bg-muted/20 overflow-y-auto select-none">
      {/* ── 주요 시나리오 섹션 ───────────────────────────────────── */}
      <div className="p-2 pt-3">
        <div className="flex items-center gap-1.5 px-2 py-1 mb-1">
          <ChevronDown className="w-3 h-3 text-muted-foreground" />
          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            주요 시나리오
          </span>
        </div>

        {BUILT_IN_SCENARIOS.map(({ id, label }) => {
          const meta = SCENARIO_META[id];
          const isActive = activeView.kind === "scenario" && activeView.id === id;
          const disabled = isRunning && id !== "SLAB_DESIGN" && !isActive;

          return (
            <button
              key={id}
              disabled={disabled}
              onClick={() => setActiveView({ kind: "scenario", id })}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-all mb-0.5",
                isActive
                  ? "text-white shadow-sm"
                  : "hover:bg-muted text-foreground/80",
                disabled && "opacity-40 cursor-not-allowed"
              )}
              style={isActive ? { backgroundColor: meta.color } : undefined}
              title={meta.description}
            >
              <span className="text-sm">{meta.icon}</span>
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </div>

      {/* ── 구분선 ───────────────────────────────────────────────── */}
      <div className="border-t mx-3 my-1" />

      {/* ── Custom Agent 섹션 ────────────────────────────────────── */}
      <div className="p-2 flex-1">
        <button
          onClick={() => setActiveView({ kind: "custom_hub" })}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 mb-1 w-full rounded-md transition-colors",
            activeView.kind === "custom_hub"
              ? "bg-muted text-foreground"
              : "hover:bg-muted/60 text-muted-foreground"
          )}
        >
          <ChevronDown className="w-3 h-3" />
          <span className="text-[10px] font-semibold uppercase tracking-wider">
            Custom Agent
          </span>
        </button>

        {/* 채팅으로 만들기 */}
        <button
          onClick={() => setActiveView({ kind: "custom_chat_builder" })}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-all mb-0.5",
            activeView.kind === "custom_chat_builder"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "hover:bg-muted text-muted-foreground"
          )}
        >
          <Plus className="w-3 h-3 shrink-0" />
          <span>채팅으로 만들기</span>
          {builderRunning && (
            <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
          )}
        </button>

        {/* 양식으로 만들기 */}
        <button
          onClick={() => setActiveView({ kind: "custom_form_builder" })}
          className={cn(
            "w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-all mb-0.5",
            activeView.kind === "custom_form_builder"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "hover:bg-muted text-muted-foreground"
          )}
        >
          <Plus className="w-3 h-3 shrink-0" />
          <span>양식으로 만들기</span>
        </button>

        {/* 등록된 Custom Agent 목록 */}
        {customAgents.length > 0 && (
          <div className="mt-3">
            <div className="text-[10px] text-muted-foreground px-2 mb-1 font-medium">
              등록된 Agent ({customAgents.length})
            </div>
            {customAgents.map((agent) => {
              const isActive =
                activeView.kind === "custom_agent" &&
                activeView.agentId === agent.id;
              return (
                <div key={agent.id} className="group flex items-center gap-1 mb-0.5">
                  <button
                    onClick={() =>
                      setActiveView({ kind: "custom_agent", agentId: agent.id })
                    }
                    className={cn(
                      "flex-1 flex items-center gap-2 px-3 py-2 rounded-md text-xs transition-all",
                      isActive
                        ? "text-white shadow-sm"
                        : "hover:bg-muted text-foreground/80"
                    )}
                    style={isActive ? { backgroundColor: agent.color } : undefined}
                    title={agent.description}
                  >
                    <span className="text-sm shrink-0">{agent.icon}</span>
                    <span className="truncate">{agent.name}</span>
                  </button>
                  <button
                    onClick={(e) => handleDeleteAgent(agent.id, e)}
                    className="p-1 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive transition-all rounded"
                    title="에이전트 삭제"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── 하단: Custom Agent 수 표시 ──────────────────────────── */}
      {customAgents.length === 0 && (
        <div className="p-3 text-[10px] text-muted-foreground text-center">
          아직 등록된 Agent가 없습니다.
          <br />
          위에서 만들어보세요!
        </div>
      )}
    </div>
  );
}
