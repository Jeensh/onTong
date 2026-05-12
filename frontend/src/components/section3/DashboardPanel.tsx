"use client";

/**
 * Section 3 — 진입 대시보드. modeling 의 /graph/stats 시각화 + 빠른 진입.
 *
 * 첫 사용자가 "현재 ontology DB 에 뭐가 있는지" 한눈에 보고 어느 메뉴로 갈지 결정.
 */

import { useEffect, useState } from "react";
import { Activity, ArrowRight, BookOpen, Database, Layers, Server } from "lucide-react";
import { getStats } from "@/lib/section3/api";

interface Stats {
  nodes: Record<string, number>;
  relations: Record<string, number>;
  totals?: Record<string, number>;
}

const NODE_GROUPS: Array<{ keys: string[]; label: string; icon: React.ReactNode; tone: string }> = [
  { keys: ["Term", "TermCategory"], label: "도메인 (Term)", icon: <BookOpen size={16} />, tone: "border-pink-300 bg-pink-50 text-pink-700" },
  { keys: ["Step"], label: "프로세스 (Step)", icon: <Activity size={16} />, tone: "border-blue-300 bg-blue-50 text-blue-700" },
  { keys: ["Standard", "Variable", "ErrorCode"], label: "기준 / 변수 / 에러", icon: <Layers size={16} />, tone: "border-amber-300 bg-amber-50 text-amber-700" },
  { keys: ["Class", "Method"], label: "코드 (Class / Method)", icon: <Server size={16} />, tone: "border-emerald-300 bg-emerald-50 text-emerald-700" },
  { keys: ["Table"], label: "데이터 (Table)", icon: <Database size={16} />, tone: "border-orange-300 bg-orange-50 text-orange-700" },
];

interface Props {
  onJump?: (view: "bridge" | "sandbox" | "code-impact" | "data-impact") => void;
}

export function DashboardPanel({ onJump }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    getStats().then(setStats).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="overflow-y-auto h-full">
      <div className="p-6 space-y-5">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Activity size={20} className="text-primary" />
            Section 3 — Simulation Dashboard
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            modeling API 가 제공하는 ontology 데이터 한눈에 + 4 agent 빠른 진입.
          </p>
        </div>

        {err && <div className="text-sm text-red-600">modeling stats 로딩 실패: {err}</div>}

        {/* node groups */}
        <div>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            🗂 Ontology 노드 ({stats ? Object.values(stats.nodes).reduce((a, b) => a + b, 0) : "—"})
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
            {NODE_GROUPS.map((g) => {
              const total = stats ? g.keys.reduce((sum, k) => sum + (stats.nodes[k] ?? 0), 0) : 0;
              return (
                <div key={g.label} className={`rounded-lg border-2 p-3 ${g.tone}`}>
                  <div className="flex items-center gap-2 mb-1">
                    {g.icon}
                    <span className="text-[11px] font-semibold">{g.label}</span>
                  </div>
                  <div className="text-2xl font-bold">{stats ? total : "—"}</div>
                  <div className="text-[10px] opacity-70 mt-1">
                    {stats && g.keys.map((k) => `${k}: ${stats.nodes[k] ?? 0}`).join(" · ")}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* relations */}
        {stats && (
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
              🔗 Relations ({Object.values(stats.relations).reduce((a, b) => a + b, 0)})
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(stats.relations)
                .sort((a, b) => b[1] - a[1])
                .map(([rel, count]) => (
                  <span
                    key={rel}
                    className="inline-flex items-center gap-1 rounded-full bg-muted border border-border px-2 py-0.5 text-[10px] font-mono"
                  >
                    <span className="text-foreground">{rel}</span>
                    <span className="text-muted-foreground">×{count}</span>
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* quick entries */}
        <div>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
            🚀 빠른 진입
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <QuickCard
              title="자연어 질문 (브릿지 chat)"
              desc="실수율은 어디서 계산되나? / Method 바꾸면? — chat 으로 의도 분석"
              onClick={() => onJump?.("bridge")}
            />
            <QuickCard
              title="샌드박스 — Step 시뮬"
              desc="modeling 이 만든 test_case + LLM 합성 Python 격리 실행"
              onClick={() => onJump?.("sandbox")}
            />
            <QuickCard
              title="영향도 분석 — 코드 변경"
              desc="Method / Class 변경 시 어느 Step 깨지나"
              onClick={() => onJump?.("code-impact")}
            />
            <QuickCard
              title="데이터 변경 분석"
              desc="SC 기준값 / Table / 주문 변경 영향"
              onClick={() => onJump?.("data-impact")}
            />
          </div>
        </div>

        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-[11px] text-amber-800">
          💡 모든 agent 는 oncology API (<code className="text-[10px]">/api/modeling/ontology/query</code>) 응답만 활용 — Neo4j 직접 접근 0건. modeling 측에 추가 요청 사항은
          <code className="text-[10px]">toClaude/simulation/SECTION2_REQUESTS.md</code> 에 누적됩니다.
        </div>
      </div>
    </div>
  );
}

function QuickCard({ title, desc, onClick }: { title: string; desc: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="text-left rounded-lg border border-border bg-card p-3 hover:border-primary/40 hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-sm text-foreground">{title}</div>
          <div className="text-[11px] text-muted-foreground mt-1">{desc}</div>
        </div>
        <ArrowRight size={14} className="text-muted-foreground flex-shrink-0 mt-0.5" />
      </div>
    </button>
  );
}
