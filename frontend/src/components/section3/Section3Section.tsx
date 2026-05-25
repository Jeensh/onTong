"use client";

/**
 * Section 3 entry — 멀티턴 chat 중심으로 단순화 (2026-05-18).
 *
 * 변경:
 * - Dashboard + Multiturn 만 primary nav 노출 (사용자 워크플로우 최단경로)
 * - v1 chat / Sandbox / CodeImpact / DataImpact 는 multiturn 의 Gate I~III 가
 *   동등하거나 그 이상 기능 제공 → 진입점 hide. URL `?view=...` 로 강제 진입은 가능.
 */

import { useEffect, useState } from "react";
import { MessageSquare, Beaker, Flame, Database, Zap, Activity, Sparkles, Workflow } from "lucide-react";
import { BridgeChatPanel } from "./BridgeChatPanel";
import { SandboxPanel } from "./SandboxPanel";
import { CodeImpactPanel } from "./CodeImpactPanel";
import { DataImpactPanel } from "./DataImpactPanel";
import { DashboardPanel } from "./DashboardPanel";
import { MultiturnChat } from "./multiturn/MultiturnChat";
import { SimulationChat } from "./simulation/SimulationChat";

type View = "dashboard" | "multiturn" | "simulation" | "bridge" | "sandbox" | "code-impact" | "data-impact";

/** Primary 화면 — 사용자 진입 경로. */
const NAV: Array<{ id: View; label: string; icon: React.ReactNode; description: string }> = [
  { id: "simulation", label: "시뮬레이션 에이전트", icon: <Workflow size={16} />, description: "IT 운영자용 — 5 시나리오 · 6 intent · 변경 전·후 비교" },
  { id: "multiturn", label: "멀티턴 agent", icon: <Sparkles size={16} />, description: "자연어 → 후보 → 코드 검토 → 시뮬레이션 / 영향도" },
  { id: "dashboard", label: "대시보드", icon: <Activity size={16} />, description: "ontology 통계 + 빠른 진입" },
];

/** Hidden — URL `?view=...` 로만 접근 가능 (deprecated / debug). */
const HIDDEN_VIEWS = new Set<View>(["bridge", "sandbox", "code-impact", "data-impact"]);

const VALID: View[] = ["dashboard", "multiturn", "simulation", "bridge", "sandbox", "code-impact", "data-impact"];

function readInitial(): View {
  if (typeof window === "undefined") return "simulation";
  const params = new URLSearchParams(window.location.search);
  const v = params.get("view");
  if (v && (VALID as string[]).includes(v)) return v as View;
  return "simulation";
}

function readInitialSid(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("sid");
}

function readInitialRepo(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("repo");
}

/** URL searchParams `view` / `sid` / `repo` 갱신 + popstate 호환. */
function pushUrlState(
  view: View, sid: string | null, repo: string | null,
): void {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("view", view);
  if (sid)  url.searchParams.set("sid", sid);  else url.searchParams.delete("sid");
  if (repo) url.searchParams.set("repo", repo); else url.searchParams.delete("repo");
  window.history.pushState({}, "", url.toString());
}

export function Section3Section() {
  const [active, setActive] = useState<View>(readInitial);
  const [initialSid, setInitialSid] = useState<string | null>(readInitialSid);
  /** dashboard ↔ multiturn 공유 — 사용자가 dashboard 에서 repo 칩 클릭하면 chat 의 기본값으로 들어감. */
  const [selectedRepo, setSelectedRepo] = useState<string | null>(readInitialRepo);

  useEffect(() => {
    const onPop = () => {
      setActive(readInitial());
      setInitialSid(readInitialSid());
      setSelectedRepo(readInitialRepo());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  /** DashboardPanel → MultiturnChat 로 sid 전달 (히스토리 진입). */
  const openSession = (sid: string) => {
    setActive("multiturn");
    setInitialSid(sid);
    pushUrlState("multiturn", sid, selectedRepo);
  };

  /** MultiturnChat "새 대화" 클릭 시 sid 정리 (repo 는 유지). */
  const clearSid = () => {
    setInitialSid(null);
    pushUrlState("multiturn", null, selectedRepo);
  };

  /** DashboardPanel 의 repo 칩 클릭. */
  const onRepoChange = (repo: string) => {
    setSelectedRepo(repo);
    pushUrlState(active, initialSid, repo);
  };

  return (
    <div className="flex h-full">
      {/* Left nav */}
      <div className="w-60 border-r border-border bg-muted/30 p-3 flex flex-col gap-1">
        <div className="px-2 py-3 mb-2">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Zap size={14} className="text-primary" />
            Section 3 — Simulation
          </h2>
          <p className="text-[10px] text-muted-foreground mt-1">
            modeling API 기반 4 agent
          </p>
        </div>

        {NAV.map((item) => {
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={`flex items-start gap-2 px-3 py-2 rounded text-sm text-left transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              <span className="mt-0.5">{item.icon}</span>
              <span className="flex-1 min-w-0">
                <span className="block">{item.label}</span>
                <span className="block text-[10px] text-muted-foreground/70 font-normal mt-0.5">{item.description}</span>
              </span>
            </button>
          );
        })}

        <div className="mt-auto mx-2 px-2 py-2 rounded bg-primary/5 border border-primary/20 text-[10px]">
          <p className="text-primary/80 font-medium">백엔드</p>
          <p className="text-muted-foreground mt-0.5">/api/section3/* (4 agent)</p>
          <p className="text-muted-foreground">→ /api/modeling/ontology/query</p>
        </div>
      </div>

      {/* Main panel */}
      <div className="flex-1 overflow-hidden">
        {active === "dashboard" && (
          <DashboardPanel
            selectedRepo={selectedRepo}
            onRepoChange={onRepoChange}
            onOpenSession={openSession}
          />
        )}
        {active === "multiturn" && (
          <MultiturnChat
            initialSid={initialSid}
            onNewSession={clearSid}
            defaultRepoId={selectedRepo}
            onOpenSession={openSession}
          />
        )}
        {active === "simulation" && (
          <SimulationChat
            initialSid={initialSid}
            onNewSession={clearSid}
            defaultRepoId={selectedRepo}
          />
        )}
        {active === "bridge" && <BridgeChatPanel />}
        {active === "sandbox" && <SandboxPanel />}
        {active === "code-impact" && <CodeImpactPanel />}
        {active === "data-impact" && <DataImpactPanel />}
      </div>
    </div>
  );
}
