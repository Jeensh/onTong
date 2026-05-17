"use client";

/**
 * Section 3 entry — 좌측 nav 4 항목 + 메인 panel.
 *
 * 4 항목:
 * 1. 온톨로지 브릿지 (chat) — 자연어 + 다른 3 메뉴 기능 모두 호출 가능
 * 2. 샌드박스 — 테스트 데이터 + 실행
 * 3. 영향도 분석 — 코드 변경
 * 4. 데이터 변경 분석 — 기준 / Table / 주문
 */

import { useEffect, useState } from "react";
import { MessageSquare, Beaker, Flame, Database, Zap, Activity } from "lucide-react";
import { BridgeChatPanel } from "./BridgeChatPanel";
import { SandboxPanel } from "./SandboxPanel";
import { CodeImpactPanel } from "./CodeImpactPanel";
import { DataImpactPanel } from "./DataImpactPanel";
import { DashboardPanel } from "./DashboardPanel";

type View = "dashboard" | "bridge" | "sandbox" | "code-impact" | "data-impact";

const NAV: Array<{ id: View; label: string; icon: React.ReactNode; description: string }> = [
  { id: "dashboard", label: "대시보드", icon: <Activity size={16} />, description: "ontology 통계 + 빠른 진입" },
  { id: "bridge", label: "온톨로지 브릿지", icon: <MessageSquare size={16} />, description: "자연어 chat — 의도 분석 + 4 기능 orchestration" },
  { id: "sandbox", label: "샌드박스", icon: <Beaker size={16} />, description: "테스트 데이터 생성 + 안전 가상 실행" },
  { id: "code-impact", label: "영향도 분석", icon: <Flame size={16} />, description: "코드 변경 (method/class)" },
  { id: "data-impact", label: "데이터 변경 분석", icon: <Database size={16} />, description: "기준 (Standard) / Table / 주문" },
];

const VALID: View[] = ["dashboard", "bridge", "sandbox", "code-impact", "data-impact"];

function readInitial(): View {
  if (typeof window === "undefined") return "dashboard";
  const params = new URLSearchParams(window.location.search);
  const v = params.get("view");
  if (v && (VALID as string[]).includes(v)) return v as View;
  return "dashboard";
}

export function Section3Section() {
  const [active, setActive] = useState<View>(readInitial);

  useEffect(() => {
    const onPop = () => setActive(readInitial());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

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
        {active === "dashboard" && <DashboardPanel onJump={(v) => setActive(v)} />}
        {active === "bridge" && <BridgeChatPanel />}
        {active === "sandbox" && <SandboxPanel />}
        {active === "code-impact" && <CodeImpactPanel />}
        {active === "data-impact" && <DataImpactPanel />}
      </div>
    </div>
  );
}
