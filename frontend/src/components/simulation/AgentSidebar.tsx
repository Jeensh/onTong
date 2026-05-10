"use client";

import { useEffect, useState } from "react";
import { fetchGraphStats, type GraphStats } from "@/lib/simulation/agentApi";

export type AgentKey = "impact" | "test" | "locator" | "explorer";

interface AgentSidebarProps {
  active: AgentKey;
  onChange: (key: AgentKey) => void;
}

const AGENTS: {
  key: AgentKey;
  icon: string;
  title: string;
  desc: string;
  accent: string;
}[] = [
  {
    key: "impact",
    icon: "📊",
    title: "Agent 1 — 영향도 파악",
    desc: "변경 → traversal 그래프",
    accent: "border-blue-300",
  },
  {
    key: "test",
    icon: "🧪",
    title: "Agent 2 — 테스트 데이터",
    desc: "변수 의존성 + SC 시드",
    accent: "border-emerald-300",
  },
  {
    key: "locator",
    icon: "🗺",
    title: "Agent 3 — 위치 파악",
    desc: "용어 → 경로 highlight",
    accent: "border-amber-300",
  },
  {
    key: "explorer",
    icon: "🌐",
    title: "Agent 4 — 온톨로지 익스플로러",
    desc: "노드 검색 + 1-2 hop expand",
    accent: "border-fuchsia-300",
  },
];

export function AgentSidebar({ active, onChange }: AgentSidebarProps) {
  const [stats, setStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    fetchGraphStats().then(setStats).catch(() => setStats(null));
  }, []);

  return (
    <aside className="flex h-full w-72 flex-col border-r border-gray-200 bg-white">
      <div className="border-b border-gray-200 bg-gradient-to-br from-fuchsia-50 to-blue-50 p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Section 3 · Slab Design
        </div>
        <div className="mt-1 text-base font-bold text-gray-900">
          📋 기능 표준화 Agent 허브
        </div>
        {stats && (
          <div className="mt-3 rounded border border-gray-200 bg-white px-2.5 py-1.5 text-xs">
            <div className="font-semibold text-gray-700">🌐 온톨로지</div>
            <div className="text-gray-600">
              노드 <b>{stats.totals.nodes}</b> · 관계 <b>{stats.totals.relations}</b>
            </div>
            <div className="mt-0.5 text-[10px] text-gray-500">
              T{stats.nodes.Term} · S{stats.nodes.Step} · Std{stats.nodes.Standard}
              {" · "}M{stats.nodes.Method} · C{stats.nodes.Class}
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        <ul className="space-y-1.5">
          {AGENTS.map((a) => {
            const isActive = active === a.key;
            return (
              <li key={a.key}>
                <button
                  onClick={() => onChange(a.key)}
                  className={`w-full rounded-lg border-2 px-3 py-2.5 text-left transition ${
                    isActive
                      ? `${a.accent} bg-gray-50 shadow-sm`
                      : "border-transparent hover:border-gray-200 hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-2xl">{a.icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-gray-900">
                        {a.title}
                      </div>
                      <div className="truncate text-[11px] text-gray-500">
                        {a.desc}
                      </div>
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <footer className="border-t border-gray-200 px-3 py-2 text-[10px] text-gray-400">
        🌐 Neo4j 기반 3-Layer 온톨로지 — 실시간 호출
      </footer>
    </aside>
  );
}
