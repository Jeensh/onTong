/**
 * 기준 가상 주문 editable + 실시간 sweep 재계산 + 21-step 산식 trace.
 *
 * 사용자가 ORDER_WIDTH/WGT_LOW/WGT_HIGH/DESIGN_PEND_QTY 를 직접 수정 → debounce 후
 * /weight_optimize/sweep 재호출 → best 결과 + 산식 trace 갱신.
 *
 * 산식 trace 는 walkthrough.md 형식 — step_no + title + formula + computation + result.
 */
import React, { useState, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";

type SweepBest = {
  vars: Record<string, number>;
  projected_slab_wgt: number;
  projected_split_count: number;
};

type TraceStep = {
  step_no: number;
  title: string;
  formula: string;
  computation?: string;
  result: string;
  phase?: string;
  notes?: string;
};

type SweepResponse = {
  base_order: Record<string, unknown>;
  sweep_variables: string[];
  best: SweepBest | null;
  summary: string;
  calculation_trace: TraceStep[];
  var_ranges: Record<string, number[]>;
};

interface Props {
  initial: SweepResponse;
}

const EDITABLE_KEYS = ["ORDER_WIDTH", "ORDER_LENGTH", "ORDER_WGT_LOW", "ORDER_WGT_HIGH", "DESIGN_PEND_QTY"] as const;
type EditKey = (typeof EDITABLE_KEYS)[number];

const KEY_LABEL: Record<EditKey, string> = {
  ORDER_WIDTH: "주문 폭",
  ORDER_LENGTH: "주문 길이",
  ORDER_WGT_LOW: "주문 단중 하한",
  ORDER_WGT_HIGH: "주문 단중 상한",
  DESIGN_PEND_QTY: "설계 대기량",
};
const KEY_UNIT: Record<EditKey, string> = {
  ORDER_WIDTH: "mm",
  ORDER_LENGTH: "mm",
  ORDER_WGT_LOW: "kg",
  ORDER_WGT_HIGH: "kg",
  DESIGN_PEND_QTY: "kg",
};

const PHASE_COLOR: Record<string, string> = {
  phase_1: "bg-sky-100 text-sky-800 border-sky-200",
  phase_2a: "bg-emerald-100 text-emerald-800 border-emerald-200",
  phase_2b: "bg-amber-100 text-amber-800 border-amber-200",
  phase_2c: "bg-violet-100 text-violet-800 border-violet-200",
  save: "bg-rose-100 text-rose-800 border-rose-200",
};

export function EditableBaseOrderPanel({ initial }: Props) {
  // 편집 가능한 base order 값
  const [draft, setDraft] = useState<Record<EditKey, number | string>>(() => {
    const d: Record<EditKey, number | string> = {} as never;
    for (const k of EDITABLE_KEYS) {
      const v = initial.base_order[k];
      d[k] = typeof v === "number" ? v : (v === undefined || v === null ? "" : String(v));
    }
    return d;
  });
  const [resp, setResp] = useState<SweepResponse>(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [autoMode, setAutoMode] = useState(true);   // input 변경 시 자동 재계산
  const [traceOpen, setTraceOpen] = useState(false);
  const [dirty, setDirty] = useState(false);

  const _recompute = useCallback(async () => {
    setBusy(true); setErr(null);
    try {
      const newBase: Record<string, unknown> = { ...initial.base_order };
      for (const k of EDITABLE_KEYS) {
        const v = draft[k];
        if (v === "" || v === null) continue;
        const n = Number(v);
        if (!isNaN(n)) newBase[k] = n;
      }
      const r = await fetch("/api/section3/simulation/weight_optimize/sweep", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          base_order: newBase,
          sweep_variables: initial.sweep_variables.length > 0
            ? initial.sweep_variables
            : ["ORDER_WGT_HIGH", "DESIGN_PEND_QTY"],
          grid_size: 5,
          repo_id: "slab-design-real-v2",
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setResp(data);
      setDirty(false);
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  }, [draft, initial.base_order, initial.sweep_variables]);

  // 자동 재계산 — debounce 600ms
  useEffect(() => {
    if (!autoMode || !dirty) return;
    const t = setTimeout(_recompute, 600);
    return () => clearTimeout(t);
  }, [autoMode, dirty, _recompute]);

  const _onChange = (k: EditKey, raw: string) => {
    setDraft((d) => ({ ...d, [k]: raw === "" ? "" : raw }));
    setDirty(true);
  };

  const best = resp.best;
  const trace = resp.calculation_trace ?? [];

  return (
    <div className="border-2 border-teal-400 bg-gradient-to-br from-teal-50 to-emerald-50 rounded-lg p-3 sim-anim-fadein">
      <div className="flex items-center gap-2 flex-wrap mb-2">
        <span className="text-[10.5px] px-2 py-0.5 rounded bg-teal-700 text-white font-bold">🏆 인터랙티브 최적화</span>
        <strong className="text-[13px] text-teal-900">기준 주문 수정 → 실시간 최적 조합 단중 재계산</strong>
        {busy && <Loader2 size={13} className="animate-spin text-teal-700" />}
        <label className="ml-auto text-[10.5px] text-teal-800 flex items-center gap-1 cursor-pointer">
          <input type="checkbox" checked={autoMode} onChange={(e) => setAutoMode(e.target.checked)} className="accent-teal-600" />
          자동 재계산
        </label>
        {!autoMode && (
          <button onClick={_recompute} disabled={busy || !dirty}
            className="text-[10.5px] px-2 py-1 rounded bg-teal-600 text-white disabled:bg-gray-300 hover:bg-teal-700">
            재계산
          </button>
        )}
      </div>

      {/* 편집 가능한 base order 필드 grid */}
      <div className="bg-white/85 rounded-lg p-3 border-2 border-teal-100 mb-3">
        <div className="text-[10.5px] text-teal-700 font-bold uppercase mb-2">기준 가상 주문 (수정 가능)</div>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-2">
          {EDITABLE_KEYS.map((k) => (
            <label key={k} className="flex flex-col">
              <span className="text-[10px] text-gray-600 font-medium mb-0.5">{KEY_LABEL[k]} <code className="text-[9px] text-gray-400">{k}</code></span>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  value={draft[k] === "" ? "" : Number(draft[k])}
                  onChange={(e) => _onChange(k, e.target.value)}
                  className="flex-1 text-[12px] px-2 py-1 rounded border border-teal-200 bg-white focus:outline-none focus:border-teal-500 font-mono"
                  placeholder="—"
                />
                <span className="text-[10px] text-gray-500">{KEY_UNIT[k]}</span>
              </div>
            </label>
          ))}
        </div>
        {err && <div className="mt-2 text-[10.5px] text-red-700 bg-red-50 rounded p-1.5 border border-red-200">⚠ {err}</div>}
      </div>

      {/* 최적 결과 */}
      {best ? (
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div className="bg-white rounded-lg p-3 border-2 border-teal-200">
            <div className="text-[10.5px] text-teal-700 uppercase font-bold mb-1">예상 Slab 단중 (최대)</div>
            <div className="text-3xl font-extrabold leading-none text-teal-800">
              {Number(best.projected_slab_wgt ?? 0).toLocaleString()}
              <span className="text-base font-semibold ml-1">kg</span>
            </div>
            <div className="text-[11px] text-gray-700 mt-1">
              split <strong>{best.projected_split_count}</strong>개 · 총 <strong>{(best.projected_slab_wgt * best.projected_split_count).toLocaleString()}</strong> kg
            </div>
          </div>
          <div className="bg-white rounded-lg p-3 border-2 border-emerald-200">
            <div className="text-[10.5px] text-emerald-700 uppercase font-bold mb-1">권장 변수값</div>
            <ul className="space-y-0.5 text-[11.5px]">
              {Object.entries(best.vars ?? {}).map(([k, v]) => (
                <li key={k} className="flex items-baseline gap-1.5">
                  <code className="text-[10px] text-emerald-800">{k}</code>
                  <span className="text-gray-400">=</span>
                  <strong className="font-mono text-emerald-900">{Number(v).toLocaleString()}</strong>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded p-2 text-[11.5px] text-amber-900 mb-3">
          ⚠ feasible 조합 없음 — 단중 하한·상한 또는 설계대기량을 조정해 보세요
        </div>
      )}

      {/* 21-step 산식 trace */}
      {trace.length > 0 && (
        <details className="bg-white/85 rounded-lg border border-teal-200" open={traceOpen}
                 onToggle={(e) => setTraceOpen((e.target as HTMLDetailsElement).open)}>
          <summary className="cursor-pointer px-3 py-2 text-[12px] text-teal-900 font-bold flex items-center gap-2">
            🧮 계산 과정 보기 — 21-step 산식 전개 ({trace.length} step)
            <span className="text-[10px] text-teal-600 font-normal ml-auto">walkthrough.md 형식</span>
          </summary>
          <div className="px-3 pb-3 space-y-2">
            {trace.map((s, i) => (
              <div key={i} className="border border-gray-200 rounded p-2 bg-gray-50/40">
                <div className="flex items-baseline gap-2 mb-1 flex-wrap">
                  {s.phase && (
                    <span className={"text-[9.5px] px-1.5 py-0.5 rounded border font-semibold " + (PHASE_COLOR[s.phase] ?? "bg-gray-100 text-gray-700 border-gray-200")}>
                      {s.phase}
                    </span>
                  )}
                  <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-teal-100 text-teal-900 font-bold">step {s.step_no}</span>
                  <span className="text-[12.5px] font-bold text-gray-900">{s.title}</span>
                  <span className="text-[10.5px] text-teal-700 ml-auto font-mono font-bold">→ {s.result}</span>
                </div>
                <div className="text-[10.5px] text-gray-600 mb-1.5">
                  <span className="font-semibold">공식:</span> <code className="bg-white px-1 py-0.5 rounded border border-gray-200 text-gray-800">{s.formula}</code>
                </div>
                {s.computation && (
                  <pre className="text-[10.5px] bg-violet-50/60 border border-violet-100 rounded p-1.5 whitespace-pre-wrap font-mono text-violet-900">
{s.computation}
                  </pre>
                )}
                {s.notes && (
                  <div className="text-[10px] text-gray-500 italic mt-1">💡 {s.notes}</div>
                )}
              </div>
            ))}
          </div>
        </details>
      )}

      <div className="mt-2 text-[10.5px] text-teal-700 italic">
        💡 위 input 값을 바꾸면 자동으로 sweep 재계산 + 21-step 산식이 변경 값으로 다시 전개됩니다
      </div>
    </div>
  );
}
