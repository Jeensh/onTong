"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { SummaryEvent } from "@/lib/simulation/useAgent2Stream";
import { PLOT_COLORS, PLOT_LAYOUT_BASE, barOutline } from "@/lib/simulation/plotTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface Props {
  summary: SummaryEvent["data"] | null;
}

export function ResultChart({ summary }: Props) {
  const slabHistogram = useMemo(() => {
    if (!summary?.slab_count_distribution || summary.slab_count_distribution.length === 0) return null;
    // 정수 분포 → 1 bin = 1 정수, 막대 사이 여백 강조
    return [{
      x: summary.slab_count_distribution,
      type: "histogram" as const,
      xbins: { size: 1 },
      marker: {
        color: PLOT_COLORS.primary,
        line: barOutline(PLOT_COLORS.primaryDeep),
      },
      name: "Slab 매수",
    }];
  }, [summary]);

  const productivityHistogram = useMemo(() => {
    if (!summary?.productivity_distribution || summary.productivity_distribution.length === 0) return null;
    return [{
      x: summary.productivity_distribution,
      type: "histogram" as const,
      marker: {
        color: PLOT_COLORS.accent,
        line: barOutline(PLOT_COLORS.accentDeep),
      },
      name: "누적 실수율",
      xbins: { size: 0.02 },
    }];
  }, [summary]);

  const matchRateData = useMemo(() => {
    if (!summary?.by_type) return null;
    const labels: string[] = [];
    const matched: number[] = [];
    const failed: number[] = [];
    for (const [k, v] of Object.entries(summary.by_type)) {
      labels.push(k);
      matched.push(v.matched);
      failed.push(v.failed);
    }
    return [
      {
        x: labels,
        y: matched,
        name: "기대 일치",
        type: "bar" as const,
        marker: {
          color: PLOT_COLORS.emerald,
          line: barOutline(PLOT_COLORS.emeraldDeep),
        },
      },
      {
        x: labels,
        y: failed,
        name: "기대 불일치",
        type: "bar" as const,
        marker: {
          color: PLOT_COLORS.red,
          line: barOutline(PLOT_COLORS.redDeep),
        },
      },
    ];
  }, [summary]);

  if (!summary) {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground/70">
        실행 결과 요약이 도착하면 분포 차트가 표시됩니다.
      </div>
    );
  }

  const layoutBase = {
    ...PLOT_LAYOUT_BASE,
    height: 220,
    margin: { l: 44, r: 16, t: 8, b: 36 },
    showlegend: false,
    bargap: 0.35, // 막대 사이 여백 — 너무 두꺼운 막대 방지
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {slabHistogram && (
          <div className="rounded-lg border border-border bg-card p-3">
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">Slab 매수 분포</h4>
            <Plot
              data={slabHistogram as any}
              layout={layoutBase as any}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
              config={{ displayModeBar: false }}
            />
          </div>
        )}

        {productivityHistogram && (
          <div className="rounded-lg border border-border bg-card p-3">
            <h4 className="mb-1.5 text-xs font-semibold text-foreground">누적 실수율 분포</h4>
            <Plot
              data={productivityHistogram as any}
              layout={layoutBase as any}
              useResizeHandler
              style={{ width: "100%", height: "100%" }}
              config={{ displayModeBar: false }}
            />
          </div>
        )}
      </div>

      {matchRateData && (
        <div className="rounded-lg border border-border bg-card p-3">
          <h4 className="mb-1.5 text-xs font-semibold text-foreground">케이스 유형별 기대 일치율</h4>
          <Plot
            data={matchRateData as any}
            layout={{
              ...layoutBase,
              height: 240,
              barmode: "stack",
              bargap: 0.55, // 케이스 유형 4개라도 막대 너비 적당히 좁게
              showlegend: true,
              legend: { orientation: "h", y: -0.25, font: { size: 10 } },
            } as any}
            useResizeHandler
            style={{ width: "100%", height: "100%" }}
            config={{ displayModeBar: false }}
          />
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        <Stat label="총 케이스" value={String(summary.total)} />
        <Stat
          label="기대 일치"
          value={String(summary.total - summary.failed_count)}
          tone="text-emerald-600 dark:text-emerald-400"
        />
        <Stat
          label="평균 시간"
          value={`${Math.round(summary.avg_elapsed_ms)}ms`}
          tone="text-purple-600 dark:text-purple-400"
        />
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded border border-border bg-muted/40 p-2">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className={`text-base font-semibold tabular-nums ${tone ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}
