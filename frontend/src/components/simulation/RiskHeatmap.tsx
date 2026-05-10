"use client";

import { useMemo } from "react";
import { Flame } from "lucide-react";
import type { HeatmapData } from "@/lib/simulation/useAgent2Stream";

interface Props {
  heatmap: HeatmapData | null | undefined;
}

/**
 * Risk Heatmap — Java 코드에 sandbox 실행 빈도를 시각화.
 *
 * 정적 분석 도구는 "코드 커버리지" (테스트가 도달했는가)만 보여준다.
 * 우리는 "비즈니스 데이터로 도달한 빈도"를 보여줌:
 * - 🟢 자주 (count >= 0.3 × total): 안전한 분기
 * - 🟡 드물게: 잠재 위험
 * - 🔴 0건: Hypothesis로도 도달 못한 분기 — 진짜 위험
 */
export function RiskHeatmap({ heatmap }: Props) {
  const lineMap = useMemo(() => {
    if (!heatmap) return new Map<number, { count: number; label: string }>();
    const m = new Map<number, { count: number; label: string }>();
    for (const mark of heatmap.marks) {
      m.set(mark.line, { count: mark.count, label: mark.label });
    }
    return m;
  }, [heatmap]);

  const colorFor = (count: number, total: number): string => {
    if (count === 0)
      return "bg-red-500/25 border-l-red-500 ring-1 ring-inset ring-red-500/30";
    if (count < total * 0.1)
      return "bg-amber-500/20 border-l-amber-500 ring-1 ring-inset ring-amber-500/25";
    if (count < total * 0.3)
      return "bg-yellow-500/15 border-l-yellow-500 ring-1 ring-inset ring-yellow-500/20";
    return "bg-emerald-500/15 border-l-emerald-500 ring-1 ring-inset ring-emerald-500/20";
  };

  if (!heatmap) {
    return null;
  }

  const lines = heatmap.file_content.split("\n");
  const total = heatmap.total_cases || 1;

  // 마크 통계
  const coveredBranches = heatmap.marks.filter((m) => m.count > 0).length;
  const uncoveredBranches = heatmap.marks.filter((m) => m.count === 0).length;

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="border-b border-border bg-muted/40 px-4 py-2.5">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Flame size={12} className="text-orange-500" />
            Risk Heatmap (Java 코드 분기 도달 빈도)
          </h4>
          <div className="text-[11px] text-muted-foreground tabular-nums">
            {coveredBranches}/{heatmap.marks.length} 분기 도달 ·{" "}
            {uncoveredBranches > 0 && (
              <span className="text-red-500">{uncoveredBranches}개 미도달 ★</span>
            )}
          </div>
        </div>
        <div className="text-[10px] text-muted-foreground mt-1 font-mono truncate">
          {heatmap.file_path}
        </div>
      </div>

      {/* Branch summary chips */}
      <div className="border-b border-border bg-muted/20 px-3 py-2 flex flex-wrap gap-1.5">
        {heatmap.marks.map((m, i) => {
          const tone = m.count === 0
            ? "bg-red-500/15 text-red-700 dark:text-red-300 border-red-500/40 shadow-sm shadow-red-500/10"
            : m.count < total * 0.1
            ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40"
            : "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40";
          return (
            <span
              key={i}
              className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-mono ${tone}`}
              title={`line ${m.line}`}
            >
              {m.label}
              <span className="font-bold tabular-nums">×{m.count}</span>
            </span>
          );
        })}
      </div>

      {/* Source lines */}
      <div className="max-h-[400px] overflow-auto">
        <pre className="text-[11px] font-mono leading-[1.45] text-foreground">
          <code>
            {lines.map((line, idx) => {
              const lineNo = idx + 1;
              const mark = lineMap.get(lineNo);
              const tone = mark
                ? colorFor(mark.count, total)
                : "border-l-transparent";
              return (
                <div
                  key={lineNo}
                  className={`flex border-l-4 px-3 py-px ${tone} ${mark ? "" : "hover:bg-muted/40"}`}
                  title={mark ? `${mark.label} (×${mark.count})` : undefined}
                >
                  <span className="text-muted-foreground/50 text-right pr-3 select-none w-10 shrink-0">
                    {lineNo}
                  </span>
                  <span className="flex-1 whitespace-pre">{line || " "}</span>
                  {mark && (
                    <span
                      className={`shrink-0 ml-2 text-[9px] font-bold tabular-nums ${
                        mark.count === 0
                          ? "text-red-500"
                          : mark.count < total * 0.1
                          ? "text-amber-500"
                          : "text-emerald-500"
                      }`}
                    >
                      ×{mark.count}
                    </span>
                  )}
                </div>
              );
            })}
          </code>
        </pre>
      </div>

      <div className="border-t border-border bg-muted/40 px-3 py-2">
        <div className="text-[10px] text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-3 rounded bg-emerald-500/30 border border-emerald-500/40 border-l-4 border-l-emerald-500" />
            자주 도달
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-3 rounded bg-yellow-500/25 border border-yellow-500/40 border-l-4 border-l-yellow-500" />
            가끔 (≤30%)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-3 rounded bg-amber-500/30 border border-amber-500/40 border-l-4 border-l-amber-500" />
            드물게 (≤10%)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-3 rounded bg-red-500/35 border border-red-500/50 border-l-4 border-l-red-500" />
            <strong className="text-red-600 dark:text-red-400">0건 — 진짜 위험</strong>
          </span>
        </div>
      </div>
    </div>
  );
}
