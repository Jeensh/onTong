"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Flame,
  Loader2,
  Play,
  ShieldCheck,
  Sliders,
  TrendingDown,
  TrendingUp,
  Minus,
  Activity,
  ArrowRight,
} from "lucide-react";
import {
  runAgent1,
  type Agent1Result,
  type ChangeKind,
  type ModificationType,
  type TargetType,
} from "@/lib/simulation/agentApi";
import {
  PLOT_COLORS,
  PLOT_LAYOUT_BASE,
  barOutline,
} from "@/lib/simulation/plotTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const TARGET_PRESETS: { id: string; label: string; tone: string; default: string; target_type: TargetType; modification: ModificationType }[] = [
  { id: "HR_PRODUCTIVITY", label: "HR 실수율", tone: "default 0.95", default: "0.95", target_type: "column", modification: "value_change" },
  { id: "HRF_PRODUCTIVITY", label: "HRF 실수율", tone: "default 0.93", default: "0.93", target_type: "column", modification: "value_change" },
  { id: "ANL1_PRODUCTIVITY", label: "ANL1 실수율", tone: "default 0.92", default: "0.92", target_type: "column", modification: "value_change" },
];

const METRIC_LABELS: Record<string, string> = {
  slab_count: "Slab 매수",
  productivity: "누적 실수율",
  slab_weight: "Slab 단중",
  split_wgt_high: "분할단중 상한",
};

export function ImpactPanel() {
  const [presetId, setPresetId] = useState(TARGET_PRESETS[1].id);
  const [newValue, setNewValue] = useState("0.85");
  const [sampleSize, setSampleSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent1Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  // What-if 미세조정 — 결과가 한 번 나온 뒤 슬라이더로 값 즉시 변경 + 작은 표본 자동 재실행
  const [whatIfValue, setWhatIfValue] = useState<number>(0.85);
  const [whatIfRunning, setWhatIfRunning] = useState(false);
  const whatIfTimer = useRef<number | null>(null);

  const preset = TARGET_PRESETS.find((p) => p.id === presetId)!;

  // result 가 처음 도착하면 슬라이더 값을 그 값으로 동기화
  useEffect(() => {
    if (result) {
      const parsed = parseFloat(newValue);
      if (!Number.isNaN(parsed)) setWhatIfValue(parsed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const runImpactWith = async (value: string, size: number, isWhatIf: boolean) => {
    if (isWhatIf) setWhatIfRunning(true);
    else setLoading(true);
    setError(null);
    if (!isWhatIf) setResult(null);
    try {
      const r = await runAgent1({
        change_kind: "data" as ChangeKind,
        target_type: preset.target_type,
        target_id: preset.id,
        modification_type: preset.modification,
        new_value: value,
        sample_size: size,
        run_sandbox: true,
      });
      setResult(r);
      if (isWhatIf) setNewValue(value); // 슬라이더로 변경한 값을 입력란에도 동기화
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (isWhatIf) setWhatIfRunning(false);
      else setLoading(false);
    }
  };

  const submit = () => runImpactWith(newValue, sampleSize, false);

  // 슬라이더 변경 → 600ms 디바운스 후 작은 표본 (5건) 빠른 재시뮬
  const onWhatIfChange = (v: number) => {
    setWhatIfValue(v);
    if (whatIfTimer.current !== null) {
      window.clearTimeout(whatIfTimer.current);
    }
    whatIfTimer.current = window.setTimeout(() => {
      runImpactWith(v.toFixed(3), 5, true);
    }, 600);
  };

  // 마운트 해제 시 타이머 정리
  useEffect(() => {
    return () => {
      if (whatIfTimer.current !== null) {
        window.clearTimeout(whatIfTimer.current);
      }
    };
  }, []);

  const histograms = useMemo(() => {
    const hist = result?.viz_data?.histograms;
    if (!hist) return [];
    return Object.entries(hist).map(([metric, data]) => ({
      metric,
      label: METRIC_LABELS[metric] ?? metric,
      ...data,
    }));
  }, [result]);

  // 변화 매트릭스 — 변경 전·후 OK/Fail 4셀 cross-tab
  const transitions = useMemo(() => {
    const t = result?.diff_summary?.stage_transitions;
    if (!t) return null;
    return t;
  }, [result]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground flex items-center gap-2">
          <Flame size={20} className="text-primary" />
          변경 영향 분석
        </h1>
        <p className="text-xs text-muted-foreground mt-1">
          룰/값을 바꾼 뒤, 같은 표본 N건을 변경 전·후로 동시 실행해 결과 분포가 어떻게 달라졌는지 보여줍니다 — Slab 매수, 단중, 실수율 변동량 + 「OK→Fail」 흐름도(Cascade Sankey).
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[400px_1fr]">
        <section className="rounded-lg border border-border bg-card p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">변경 대상</label>
            <select
              value={presetId}
              onChange={(e) => setPresetId(e.target.value)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            >
              {TARGET_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>{p.label} ({p.tone})</option>
              ))}
            </select>
            <p className="text-[10px] text-muted-foreground mt-1 font-mono">
              target_type=column · modification=value_change
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">
              새 값 <span className="text-muted-foreground">(현재 {preset.default})</span>
            </label>
            <input
              type="text"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              placeholder="0.85"
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-foreground mb-1.5">
              표본 크기: <span className="text-primary tabular-nums">{sampleSize}</span>
            </label>
            <input
              type="range"
              min={5}
              max={100}
              value={sampleSize}
              onChange={(e) => setSampleSize(Number(e.target.value))}
              className="w-full accent-primary"
            />
            <p className="text-[10px] text-muted-foreground">
              {sampleSize}건 주문 → sandbox 2회 실행 (변경 전/후 동일 입력)
            </p>
          </div>

          <button
            disabled={loading}
            onClick={submit}
            className="w-full inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                분석 중
              </>
            ) : (
              <>
                <Play size={14} />
                영향도 분석 실행
              </>
            )}
          </button>

          {error && (
            <div className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
        </section>

        <section className="space-y-4">
          {!result && !loading && (
            <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              <Activity size={28} className="mx-auto mb-2 opacity-30" />
              "영향도 분석 실행"을 누르면 변경 전/후 Slab 결과 분포가 표시됩니다.
            </div>
          )}

          {loading && (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
              <Loader2 size={28} className="mx-auto mb-2 animate-spin text-primary" />
              {sampleSize}건 표본을 sandbox에서 변경 전/후 실행 중...
            </div>
          )}

          {result && (
            <>
              <div className="rounded-lg border border-border bg-card p-4">
                <h3 className="text-sm font-semibold text-foreground mb-2">분석 요약</h3>
                <p className="text-sm text-muted-foreground">{result.summary}</p>
                {result.diff_summary && (
                  <div className="mt-3 grid grid-cols-3 gap-2">
                    <Stat label="표본" value={String(result.diff_summary.sample_size)} />
                    <Stat
                      label="결과 변동"
                      value={`${result.diff_summary.affected_count}건`}
                      tone="text-primary"
                    />
                    <Stat
                      label="변경 후 fail"
                      value={`${result.diff_summary.failure_count_after}건`}
                      tone="text-destructive"
                    />
                  </div>
                )}
              </div>

              {/* What-if 미니 슬라이더 — 결과 화면에서 즉시 값 바꿔 재시뮬 */}
              <WhatIfSlider
                presetLabel={preset.label}
                presetDefault={preset.default}
                value={whatIfValue}
                onChange={onWhatIfChange}
                running={whatIfRunning}
              />

              {/* 변화 매트릭스 — Sankey 대체 */}
              {transitions && result?.diff_summary && (
                <TransitionMatrix
                  t={transitions}
                  total={result.diff_summary.sample_size}
                  affected={result.diff_summary.affected_count}
                />
              )}

              {histograms.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {histograms.map((h) => (
                    <div key={h.metric} className="rounded-lg border border-border bg-card p-3">
                      <div className="flex items-baseline justify-between mb-1.5">
                        <h4 className="text-xs font-semibold text-foreground">{h.label}</h4>
                        <DeltaBadge delta_mean={h.delta_mean} delta_pct={h.delta_pct} />
                      </div>
                      {(h.before_values.length > 0 || h.after_values.length > 0) ? (
                        <Plot
                          data={[
                            {
                              x: h.before_values,
                              type: "histogram",
                              name: "변경 전",
                              marker: {
                                color: "rgba(148,163,184,0.55)",
                                line: barOutline("#475569"),
                              },
                            },
                            {
                              x: h.after_values,
                              type: "histogram",
                              name: "변경 후",
                              marker: {
                                color: "rgba(59,130,246,0.55)",
                                line: barOutline(PLOT_COLORS.primaryDeep),
                              },
                            },
                          ] as any}
                          layout={{
                            ...PLOT_LAYOUT_BASE,
                            height: 200,
                            margin: { l: 40, r: 12, t: 8, b: 28 },
                            barmode: "overlay",
                            bargap: 0.06,
                            showlegend: true,
                            legend: { orientation: "h", y: -0.28, font: { size: 9 } },
                          } as any}
                          useResizeHandler
                          style={{ width: "100%", height: "100%" }}
                          config={{ displayModeBar: false }}
                        />
                      ) : (
                        <div className="text-[10px] text-muted-foreground/60 text-center py-6">데이터 없음</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
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

function WhatIfSlider({
  presetLabel,
  presetDefault,
  value,
  onChange,
  running,
}: {
  presetLabel: string;
  presetDefault: string;
  value: number;
  onChange: (v: number) => void;
  running: boolean;
}) {
  const defaultNum = parseFloat(presetDefault);
  const delta = value - defaultNum;
  const deltaPct = defaultNum !== 0 ? (delta / defaultNum) * 100 : 0;
  const tone =
    Math.abs(deltaPct) < 1
      ? "text-muted-foreground"
      : Math.abs(deltaPct) < 5
      ? "text-amber-700 dark:text-amber-300"
      : "text-red-700 dark:text-red-300";

  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Sliders size={14} className="text-primary" />
          What-if 미세조정
          <span className="text-[10px] text-muted-foreground font-normal ml-1">
            슬라이더 변경 후 0.6초 → 표본 5건 자동 재시뮬
          </span>
        </h4>
        {running && (
          <span className="inline-flex items-center gap-1 text-[10px] text-primary">
            <Loader2 size={11} className="animate-spin" />
            재시뮬 중
          </span>
        )}
      </div>

      <div className="space-y-1.5">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-muted-foreground">{presetLabel}</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tabular-nums text-foreground">{value.toFixed(3)}</span>
            <span className={`text-[11px] font-medium tabular-nums ${tone}`}>
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(3)} ({deltaPct >= 0 ? "+" : ""}
              {deltaPct.toFixed(1)}%)
            </span>
            <span className="text-[10px] text-muted-foreground">vs default {presetDefault}</span>
          </div>
        </div>
        <input
          type="range"
          min={0.5}
          max={1.0}
          step={0.005}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full accent-primary"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground/70 font-mono">
          <span>0.500</span>
          <span>0.750</span>
          <span>1.000</span>
        </div>
      </div>
      <p className="text-[10px] text-muted-foreground italic leading-relaxed">
        ↑ 슬라이더를 움직이면 작은 표본(5건) 으로 빠르게 재시뮬되어 아래 매트릭스가 즉시 갱신됩니다.
        충분히 인상적인 값을 찾았으면 좌측 입력란에 그대로 반영되어 본 분석(N={"{표본 크기}"})에 활용됩니다.
      </p>
    </div>
  );
}

function TransitionMatrix({
  t,
  total,
  affected,
}: {
  t: { ok_to_ok: number; ok_to_fail: number; fail_to_ok: number; fail_to_fail: number };
  total: number;
  affected: number;
}) {
  const okBefore = t.ok_to_ok + t.ok_to_fail;
  const failBefore = t.fail_to_ok + t.fail_to_fail;
  const okAfter = t.ok_to_ok + t.fail_to_ok;
  const failAfter = t.ok_to_fail + t.fail_to_fail;

  const cells = [
    {
      key: "ok_to_ok",
      title: "유지 (안전)",
      sub: "변경 전 OK → 변경 후 OK",
      value: t.ok_to_ok,
      tone: "border-emerald-500/40 bg-emerald-500/10",
      icon: <ShieldCheck size={14} className="text-emerald-600" />,
      titleTone: "text-emerald-700 dark:text-emerald-300",
    },
    {
      key: "ok_to_fail",
      title: "새로 깨짐 (위험 ★)",
      sub: "변경 전 OK → 변경 후 Fail",
      value: t.ok_to_fail,
      tone: "border-red-500/50 bg-red-500/10 ring-1 ring-inset ring-red-500/20",
      icon: <AlertTriangle size={14} className="text-red-600" />,
      titleTone: "text-red-700 dark:text-red-300",
    },
    {
      key: "fail_to_ok",
      title: "개선됨 (회복)",
      sub: "변경 전 Fail → 변경 후 OK",
      value: t.fail_to_ok,
      tone: "border-blue-500/40 bg-blue-500/10",
      icon: <CheckCircle2 size={14} className="text-blue-600" />,
      titleTone: "text-blue-700 dark:text-blue-300",
    },
    {
      key: "fail_to_fail",
      title: "유지 (이미 알려진 문제)",
      sub: "변경 전 Fail → 변경 후 Fail",
      value: t.fail_to_fail,
      tone: "border-slate-500/30 bg-slate-500/10",
      icon: <Minus size={14} className="text-slate-600" />,
      titleTone: "text-slate-700 dark:text-slate-300",
    },
  ];

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-1.5">
          <Activity size={14} className="text-primary" />
          변화 매트릭스 (Stage Transition)
        </h4>
        <p className="text-[10px] text-muted-foreground">
          같은 표본 {total}건을 변경 전·후 두 번 실행 → 어떻게 갈렸는지
        </p>
      </div>

      {/* 어떻게 읽나 */}
      <div className="rounded border border-border bg-muted/30 p-2 text-[11px] text-muted-foreground leading-relaxed">
        <span className="font-medium text-foreground">어떻게 읽나</span>: 4 칸은 같은 케이스가
        변경 전·후로 어떤 결과를 냈는지 분류. <span className="text-red-700 dark:text-red-300 font-medium">「새로 깨짐」</span>
        이 핵심 — 변경으로 인해 새로 fail 된 케이스 (위험). <span className="text-blue-700 dark:text-blue-300 font-medium">「개선됨」</span>
        은 회복. <span className="text-emerald-700 dark:text-emerald-300 font-medium">「유지 (안전)」</span> 가 많을수록 변경이 안정적.
      </div>

      {/* 매트릭스 헤더 (변경 후 OK / Fail) */}
      <div className="grid grid-cols-[110px_1fr_1fr] gap-2 items-stretch">
        <div /> {/* 좌상단 빈칸 */}
        <ColHeader label="변경 후 OK" count={okAfter} tone="text-emerald-700 dark:text-emerald-300" />
        <ColHeader label="변경 후 Fail" count={failAfter} tone="text-red-700 dark:text-red-300" />

        <RowHeader label="변경 전 OK" count={okBefore} tone="text-emerald-700 dark:text-emerald-300" />
        <Cell {...cells[0]} total={total} />
        <Cell {...cells[1]} total={total} />

        <RowHeader label="변경 전 Fail" count={failBefore} tone="text-red-700 dark:text-red-300" />
        <Cell {...cells[2]} total={total} />
        <Cell {...cells[3]} total={total} />
      </div>

      {/* 보조 — 결과 메트릭 변동 (stage 무관) */}
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground border-t border-border pt-2">
        <Activity size={12} className="text-primary flex-shrink-0" />
        <span>
          이와 별도로 결과값 (Slab 매수 / 단중 등) 자체가 달라진 케이스:{" "}
          <span className="font-mono font-semibold text-foreground">{affected}건</span> / {total} —
          {affected > 0 && (
            <span className="text-amber-700 dark:text-amber-300 ml-1">
              통과는 했지만 결과가 변한 case ({((affected / total) * 100).toFixed(1)}%)
            </span>
          )}
          {affected === 0 && (
            <span className="text-emerald-700 dark:text-emerald-300 ml-1">결과값 변동 없음</span>
          )}
        </span>
      </div>
    </div>
  );
}

function ColHeader({ label, count, tone }: { label: string; count: number; tone: string }) {
  return (
    <div className={`text-[11px] font-semibold text-center pb-1 border-b-2 border-dashed border-border ${tone}`}>
      {label}
      <span className="text-muted-foreground ml-1 font-normal">({count})</span>
    </div>
  );
}

function RowHeader({ label, count, tone }: { label: string; count: number; tone: string }) {
  return (
    <div className={`text-[11px] font-semibold flex items-center justify-end gap-1 pr-2 border-r-2 border-dashed border-border ${tone}`}>
      <span>{label}</span>
      <span className="text-muted-foreground font-normal">({count})</span>
      <ArrowRight size={11} className="text-muted-foreground/50" />
    </div>
  );
}

function Cell({
  title,
  sub,
  value,
  tone,
  icon,
  titleTone,
  total,
}: {
  title: string;
  sub: string;
  value: number;
  tone: string;
  icon: React.ReactNode;
  titleTone: string;
  total: number;
}) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className={`rounded-lg border-2 ${tone} p-3 space-y-1.5`}>
      <div className="flex items-center gap-1.5">
        {icon}
        <span className={`text-xs font-semibold ${titleTone}`}>{title}</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums text-foreground">{value}</span>
        <span className="text-[10px] text-muted-foreground">건 ({pct.toFixed(1)}%)</span>
      </div>
      <p className="text-[10px] text-muted-foreground/80">{sub}</p>
    </div>
  );
}

function DeltaBadge({ delta_mean, delta_pct }: { delta_mean: number; delta_pct: number }) {
  const Icon = delta_mean > 0 ? TrendingUp : delta_mean < 0 ? TrendingDown : Minus;
  const tone = Math.abs(delta_pct) > 5 ? "text-destructive" : Math.abs(delta_pct) > 1 ? "text-amber-600" : "text-muted-foreground";
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium ${tone}`}>
      <Icon size={10} />
      {delta_mean >= 0 ? "+" : ""}
      {delta_mean.toFixed(2)} ({delta_pct >= 0 ? "+" : ""}
      {delta_pct.toFixed(1)}%)
    </span>
  );
}
