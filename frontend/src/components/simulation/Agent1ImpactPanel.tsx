"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import {
  runAgent1,
  type Agent1Result,
  type ChangeKind,
  type ModificationType,
  type TargetType,
} from "@/lib/simulation/agentApi";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

const TARGET_PRESETS: { id: string; label: string; target_type: TargetType; modification: ModificationType }[] = [
  { id: "HR_PRODUCTIVITY", label: "HR 실수율 (default 0.95)", target_type: "column", modification: "value_change" },
  { id: "HRF_PRODUCTIVITY", label: "HRF 실수율 (default 0.93)", target_type: "column", modification: "value_change" },
  { id: "ANL1_PRODUCTIVITY", label: "ANL1 실수율 (default 0.92)", target_type: "column", modification: "value_change" },
];

const METRIC_LABELS: Record<string, string> = {
  slab_count: "Slab 매수",
  productivity: "누적 실수율",
  slab_weight: "Slab 단중",
  split_wgt_high: "분할단중 상한",
};

/**
 * Agent 1 패널 — 영향도 분석 + 변경 전후 sandbox 실행 비교.
 *
 * 시연 시나리오 5: HR/HRF/ANL1 실수율 변경 → 표본 N건 sandbox 비교 → Slab 매수 분포 차이 시각화.
 */
export function Agent1ImpactPanel() {
  const [presetId, setPresetId] = useState(TARGET_PRESETS[1].id);
  const [newValue, setNewValue] = useState("0.85");
  const [sampleSize, setSampleSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Agent1Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  const preset = TARGET_PRESETS.find((p) => p.id === presetId)!;

  const submit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await runAgent1({
        change_kind: "data" as ChangeKind,
        target_type: preset.target_type,
        target_id: preset.id,
        modification_type: preset.modification,
        new_value: newValue,
        sample_size: sampleSize,
        run_sandbox: true,
      });
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const histograms = useMemo(() => {
    const hist = result?.viz_data?.histograms;
    if (!hist) return [];
    return Object.entries(hist).map(([metric, data]) => ({
      metric,
      label: METRIC_LABELS[metric] ?? metric,
      ...data,
    }));
  }, [result]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[420px_1fr]">
      {/* 입력 패널 */}
      <section className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h2 className="text-base font-semibold text-gray-800">영향도 분석</h2>
        <p className="text-xs text-gray-500">
          룰/값 변경 → 영향받는 step·method를 추출하고, 변경 전/후 동일 표본을 sandbox에서
          실행해 Slab 매수·단중·실수율의 변동을 비교합니다.
        </p>

        {/* Preset 선택 */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">변경 대상</label>
          <select
            value={presetId}
            onChange={(e) => setPresetId(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          >
            {TARGET_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
          <p className="text-[10px] text-gray-400 mt-1">
            target_type: <code>{preset.target_type}</code> · modification: <code>{preset.modification}</code>
          </p>
        </div>

        {/* New value */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">새 값</label>
          <input
            type="text"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="0.85"
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
          />
        </div>

        {/* Sample size */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            표본 크기: <span className="text-blue-600">{sampleSize}</span>
          </label>
          <input
            type="range"
            min={5}
            max={100}
            value={sampleSize}
            onChange={(e) => setSampleSize(Number(e.target.value))}
            className="w-full"
          />
          <div className="text-[10px] text-gray-400">
            Hypothesis가 정상 분포 주문 {sampleSize}건 생성 → sandbox 2회 실행 (전/후)
          </div>
        </div>

        <button
          disabled={loading}
          onClick={submit}
          className="w-full rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          {loading ? "분석 중..." : "▶ 영향도 분석 실행"}
        </button>

        {error && (
          <div className="rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">
            {error}
          </div>
        )}
      </section>

      {/* 결과 패널 */}
      <section className="space-y-4">
        {!result && !loading && (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center text-sm text-gray-400">
            "영향도 분석 실행"을 누르면 변경 전/후 Slab 결과 분포가 표시됩니다.
          </div>
        )}

        {result && (
          <>
            {/* 요약 카드 */}
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-gray-800 mb-2">분석 요약</h3>
              <p className="text-sm text-gray-600">{result.summary}</p>
              {result.diff_summary && (
                <div className="mt-3 grid grid-cols-3 gap-2">
                  <Stat label="표본" value={String(result.diff_summary.sample_size)} />
                  <Stat
                    label="결과 변동 주문"
                    value={String(result.diff_summary.affected_count)}
                    accent="text-blue-600"
                  />
                  <Stat
                    label="변경 후 실패"
                    value={String(result.diff_summary.failure_count_after)}
                    accent="text-red-600"
                  />
                </div>
              )}
            </div>

            {/* metric별 histogram */}
            {histograms.length > 0 && (
              <div className="space-y-3">
                {histograms.map((h) => (
                  <div key={h.metric} className="rounded-lg border border-gray-200 bg-white p-4">
                    <div className="flex items-baseline justify-between mb-2">
                      <h4 className="text-sm font-semibold text-gray-700">{h.label}</h4>
                      <span className={`text-xs font-medium ${h.delta_mean === 0 ? "text-gray-400" : Math.abs(h.delta_pct) > 5 ? "text-red-600" : "text-amber-600"}`}>
                        Δ평균 {h.delta_mean >= 0 ? "+" : ""}{h.delta_mean.toFixed(3)} ({h.delta_pct >= 0 ? "+" : ""}{h.delta_pct.toFixed(1)}%)
                      </span>
                    </div>
                    {(h.before_values.length > 0 || h.after_values.length > 0) && (
                      <Plot
                        data={[
                          {
                            x: h.before_values,
                            type: "histogram",
                            name: "변경 전",
                            marker: { color: "#94a3b8" },
                            opacity: 0.7,
                          },
                          {
                            x: h.after_values,
                            type: "histogram",
                            name: "변경 후",
                            marker: { color: "#3b82f6" },
                            opacity: 0.7,
                          },
                        ] as any}
                        layout={{
                          autosize: true,
                          height: 200,
                          margin: { l: 40, r: 16, t: 8, b: 32 },
                          barmode: "overlay",
                          showlegend: true,
                          legend: { orientation: "h", y: -0.2 },
                        }}
                        useResizeHandler
                        style={{ width: "100%", height: "100%" }}
                        config={{ displayModeBar: false }}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 위험도 / 영향도 카드 */}
            {(result.risk_level || (result.risk_factors && result.risk_factors.length > 0)) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                {result.risk_level && (
                  <div className="text-sm font-semibold text-amber-800">
                    위험도: {result.risk_level}
                  </div>
                )}
                {result.risk_factors?.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-amber-700">
                    {result.risk_factors.map((f, i) => (
                      <li key={i}>• {f}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded border border-gray-200 bg-gray-50 p-2">
      <div className="text-[10px] text-gray-500">{label}</div>
      <div className={`text-base font-semibold ${accent ?? "text-gray-800"}`}>{value}</div>
    </div>
  );
}
