/**
 * 동적 UI block 렌더러 — backend `_dynamic_blocks` 를 type 별 컴포넌트로 분기.
 *
 * 2026-05-25 신설 — 사용자 자연어 질문 → LLM 이 응답 plan 결정 → frontend 가 가변 렌더.
 * 정적 카드가 아니라 질문 의도에 따라 매번 다른 UI 조합이 등장.
 *
 * Block types: metric_grid · table · sweep_chart · comparison · step_callout · formula · text
 */
import React from "react";

type Block =
  | { type: "metric_grid"; title?: string; data: MetricGridData; _estimated?: boolean }
  | { type: "table"; title?: string; data: TableData; _estimated?: boolean }
  | { type: "sweep_chart"; title?: string; data: SweepChartData; _estimated?: boolean }
  | { type: "comparison"; title?: string; data: ComparisonData; _estimated?: boolean }
  | { type: "step_callout"; title?: string; data: StepCalloutData; _estimated?: boolean }
  | { type: "formula"; title?: string; data: FormulaData; _estimated?: boolean }
  | { type: "text"; title?: string; data: TextData; _estimated?: boolean }
  | { type: "new_standard_form"; title?: string; data: NewStandardFormData; _estimated?: boolean }
  | { type: "clarify_form"; title?: string; data: ClarifyFormData; _estimated?: boolean };

interface NewStandardFormData {
  kind: string;
  fields: Array<{ key: string; label: string; default: string | number; type: "string" | "number"; unit?: string }>;
  submit_label?: string;
}

interface ClarifyFormData {
  intent: string;
  target_key: string | null;
  fields: Array<{
    key: string; label: string; default: string | number;
    type: "string" | "number" | "select";
    unit?: string; hint?: string;
    options?: Array<{ value: string; label: string }>;
  }>;
  submit_label?: string;
}

interface MetricGridData {
  items: Array<{ label: string; value: string | number; unit?: string; delta?: string | number; tone?: "default" | "positive" | "negative" | "neutral" }>;
}
interface TableData {
  columns: Array<{ key: string; label: string; align?: "left" | "right" | "center" }>;
  rows: Array<Record<string, unknown>>;
}
interface SweepChartData {
  x_label: string;
  y_label: string;
  points: Array<{ x: string | number; y: number; label?: string }>;
  best_index?: number;
}
interface ComparisonData {
  before_label: string;
  after_label: string;
  rows: Array<{ label: string; before: string | number; after: string | number; change_pct?: number }>;
}
interface StepCalloutData {
  steps: Array<{ phase: string; step_no: number; title: string; why?: string }>;
}
interface FormulaData {
  expr: string;
  vars?: Array<{ name: string; meaning: string }>;
  note?: string;
}
interface TextData {
  body: string;
}

export function DynamicBlocksCard({ blocks }: { blocks: Block[] | null | undefined }) {
  if (!blocks || blocks.length === 0) return null;
  return (
    <div className="border-2 border-violet-200 bg-gradient-to-br from-violet-50/70 to-fuchsia-50/40 rounded-lg p-4 sim-anim-fadein space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] px-2 py-0.5 rounded bg-violet-600 text-white font-bold">✨ 맞춤 응답</span>
        <span className="text-[12.5px] text-violet-900 font-bold">질문 분석 후 맞춤형 응답 결과 도출</span>
        <span className="text-[10px] text-violet-600 ml-auto">{blocks.length}개 결과 카드</span>
      </div>
      <div className="space-y-3">
        {blocks.map((b, i) => <_BlockRender key={i} block={b} />)}
      </div>
    </div>
  );
}

function _BlockRender({ block }: { block: Block }) {
  try {
    switch (block.type) {
      case "metric_grid":  return <_MetricGrid title={block.title} data={block.data} estimated={block._estimated} />;
      case "table":        return <_Table title={block.title} data={block.data} estimated={block._estimated} />;
      case "sweep_chart":  return <_SweepChart title={block.title} data={block.data} estimated={block._estimated} />;
      case "comparison":   return <_Comparison title={block.title} data={block.data} estimated={block._estimated} />;
      case "step_callout": return <_StepCallout title={block.title} data={block.data} estimated={block._estimated} />;
      case "formula":      return <_Formula title={block.title} data={block.data} estimated={block._estimated} />;
      case "text":         return <_Text title={block.title} data={block.data} estimated={block._estimated} />;
      case "new_standard_form": return <_NewStandardForm title={block.title} data={block.data} />;
      case "clarify_form": return <_ClarifyForm title={block.title} data={block.data} />;
      default:
        return <div className="text-[11px] text-gray-500">알 수 없는 block type: {(block as { type: string }).type}</div>;
    }
  } catch (e) {
    return (
      <div className="text-[11px] text-amber-700 border border-amber-200 bg-amber-50 rounded p-2">
        ⚠ block 렌더 실패 ({block.type}) — {String((e as Error).message)}
      </div>
    );
  }
}

function _Header({ title, estimated }: { title?: string; estimated?: boolean }) {
  if (!title && !estimated) return null;
  return (
    <div className="flex items-center gap-2 mb-2">
      {title && <h4 className="text-[12.5px] font-bold text-violet-900">{title}</h4>}
      {estimated && <span className="text-[9.5px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">추정값</span>}
    </div>
  );
}

const TONE_BG: Record<string, string> = {
  positive: "bg-emerald-50 border-emerald-200 text-emerald-900",
  negative: "bg-rose-50 border-rose-200 text-rose-900",
  neutral:  "bg-gray-50 border-gray-200 text-gray-700",
  default:  "bg-white border-violet-100 text-violet-900",
};

function _MetricGrid({ title, data, estimated }: { title?: string; data: MetricGridData; estimated?: boolean }) {
  const items = Array.isArray(data?.items) ? data.items : [];
  if (items.length === 0) return null;
  const cols = items.length <= 2 ? 2 : items.length === 3 ? 3 : 4;
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}>
        {items.map((it, i) => (
          <div key={i} className={"rounded-md border p-2 " + (TONE_BG[it.tone ?? "default"] ?? TONE_BG.default)}>
            <div className="text-[10px] font-semibold opacity-80 uppercase tracking-wide">{it.label}</div>
            <div className="text-[15px] font-bold mt-0.5 leading-tight">
              {it.value}{it.unit && <span className="text-[10px] font-normal opacity-70"> {it.unit}</span>}
            </div>
            {it.delta !== undefined && (
              <div className="text-[10px] mt-0.5 opacity-80">Δ {it.delta}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function _Table({ title, data, estimated }: { title?: string; data: TableData; estimated?: boolean }) {
  const cols = Array.isArray(data?.columns) ? data.columns : [];
  const rows = Array.isArray(data?.rows) ? data.rows : [];
  if (cols.length === 0 || rows.length === 0) return null;
  // 컬럼 많으면 글자 작게 + 가로 스크롤 + nowrap 으로 두 줄 밀림 방지
  const dense = cols.length >= 8;
  const cellPad = dense ? "px-1.5 py-1" : "px-2 py-1.5";
  const fontSize = dense ? "text-[10px]" : "text-[11.5px]";
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100 overflow-x-auto">
      <_Header title={title} estimated={estimated} />
      <table className={"w-full border-collapse " + fontSize}>
        <thead>
          <tr className="bg-violet-50 border-b border-violet-200">
            {cols.map((c) => (
              <th key={c.key}
                  className={`${cellPad} font-semibold text-violet-900 whitespace-nowrap text-${c.align ?? "left"}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 30).map((r, i) => (
            <tr key={i} className="border-b border-gray-100 hover:bg-violet-50/30">
              {cols.map((c) => (
                <td key={c.key}
                    className={`${cellPad} text-gray-800 whitespace-nowrap text-${c.align ?? "left"}`}>
                  {_fmt(r[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 30 && <div className="text-[10px] text-gray-500 mt-1">… 외 {rows.length - 30}건</div>}
    </div>
  );
}

function _SweepChart({ title, data, estimated }: { title?: string; data: SweepChartData; estimated?: boolean }) {
  const points = Array.isArray(data?.points) ? data.points : [];
  if (points.length === 0) return null;
  const ys = points.map((p) => Number(p.y) || 0);
  const yMin = Math.min(...ys, 0);
  const yMax = Math.max(...ys, 1);
  const yRange = yMax - yMin || 1;
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <div className="flex items-end gap-1 h-32 border-b border-l border-gray-200 px-1 pb-1">
        {points.map((p, i) => {
          const h = ((Number(p.y) - yMin) / yRange) * 100;
          const isBest = data.best_index === i;
          return (
            <div key={i} className="flex flex-col items-center justify-end flex-1 h-full" title={`${p.x}: ${p.y}`}>
              <div className="text-[8px] text-gray-500 mb-0.5">{(Number(p.y) || 0).toFixed(0)}</div>
              <div
                className={"w-full rounded-t " + (isBest ? "bg-emerald-500" : "bg-violet-400/70")}
                style={{ height: `${Math.max(4, h)}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-[9px] text-gray-500 mt-1 px-1">
        {points.map((p, i) => <span key={i} className="flex-1 text-center truncate">{p.x}</span>)}
      </div>
      <div className="text-[10px] text-gray-600 mt-1.5 flex justify-between">
        <span>X: {data.x_label}</span><span>Y: {data.y_label}</span>
        {data.best_index !== undefined && <span className="text-emerald-700">🏆 best @ {points[data.best_index]?.x}</span>}
      </div>
    </div>
  );
}

function _Comparison({ title, data, estimated }: { title?: string; data: ComparisonData; estimated?: boolean }) {
  const rawRows = Array.isArray(data?.rows) ? data.rows : [];
  // 2026-05-25 — LLM placeholder 행 광범위 차단.
  // "변경전/변경후/기존/현재/before/after/X값/N kg/직접 입력" 등 모든 placeholder 류 hide.
  const PLACEHOLDER_RE = /(변경\s*전|변경\s*후|변경\s*필요|기존|이전|이후|현재값?|baseline|before|after|입력\s*값|입력\s*필요|선택\s*값|TBD|N\/A|null|undefined|—|값$|값\s*$)/i;
  const _isPlaceholder = (v: unknown): boolean => {
    if (v === null || v === undefined) return true;
    if (typeof v === "number" && !isNaN(v)) return false;
    const s = String(v).trim();
    if (!s) return true;
    if (PLACEHOLDER_RE.test(s)) return true;
    // 순수 텍스트 (숫자/단위 없음) 이면 placeholder 처리
    if (!/\d/.test(s) && !/(OK|NG|PASS|FAIL|✓|✗)/i.test(s)) return true;
    return false;
  };
  const rows = rawRows.filter(r => {
    return !(_isPlaceholder(r.before) && _isPlaceholder(r.after));
  });
  if (rows.length === 0) {
    return (
      <div className="bg-white/70 rounded-lg p-3 border border-violet-100 text-[11px] text-gray-600">
        <_Header title={title} estimated={estimated} />
        <div className="bg-amber-50 border border-amber-200 rounded p-2">
          ⓘ 비교할 실측 데이터가 아직 없습니다. 위 입력 폼에서 값을 지정·승인하면 변경 전/후 수치가 채워집니다.
        </div>
      </div>
    );
  }
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <table className="w-full text-[11.5px] border-collapse">
        <thead>
          <tr className="bg-violet-50 border-b border-violet-200">
            <th className="text-left px-2 py-1.5 font-semibold text-violet-900">항목</th>
            <th className="text-right px-2 py-1.5 font-semibold text-rose-700">{data.before_label}</th>
            <th className="text-right px-2 py-1.5 font-semibold text-emerald-700">{data.after_label}</th>
            <th className="text-right px-2 py-1.5 font-semibold text-gray-600">변화율</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-100">
              <td className="px-2 py-1.5 text-gray-800">{r.label}</td>
              <td className="px-2 py-1.5 text-right font-mono text-rose-800">{_fmt(r.before)}</td>
              <td className="px-2 py-1.5 text-right font-mono text-emerald-800">{_fmt(r.after)}</td>
              <td className={"px-2 py-1.5 text-right font-mono " + (
                (r.change_pct ?? 0) > 0 ? "text-emerald-700" :
                (r.change_pct ?? 0) < 0 ? "text-rose-700" : "text-gray-500"
              )}>
                {typeof r.change_pct === "number" && !isNaN(r.change_pct)
                  ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct.toFixed(2)}%`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PHASE_COLOR: Record<string, string> = {
  "phase_1": "bg-sky-100 text-sky-800 border-sky-200",
  "phase_2a": "bg-emerald-100 text-emerald-800 border-emerald-200",
  "phase_2b": "bg-amber-100 text-amber-800 border-amber-200",
  "phase_2c": "bg-violet-100 text-violet-800 border-violet-200",
  "save": "bg-rose-100 text-rose-800 border-rose-200",
};

function _StepCallout({ title, data, estimated }: { title?: string; data: StepCalloutData; estimated?: boolean }) {
  const steps = Array.isArray(data?.steps) ? data.steps : [];
  if (steps.length === 0) return null;
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <div className="space-y-1.5">
        {steps.map((s, i) => (
          <div key={i} className="flex items-start gap-2">
            <span className={"text-[9.5px] px-1.5 py-0.5 rounded border font-semibold flex-shrink-0 " +
              (PHASE_COLOR[s.phase] ?? "bg-gray-100 text-gray-700 border-gray-200")}>
              {s.phase || "phase"}
            </span>
            <span className="text-[10.5px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-700 font-bold flex-shrink-0">
              step {s.step_no}
            </span>
            <div className="text-[11.5px] text-gray-800 flex-1">
              <span className="font-semibold">{s.title}</span>
              {s.why && <span className="text-gray-600 ml-1">— {s.why}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function _Formula({ title, data, estimated }: { title?: string; data: FormulaData; estimated?: boolean }) {
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <div className="font-mono text-[13px] text-violet-900 bg-violet-50 rounded p-2 mb-2 break-all">
        {data?.expr ?? ""}
      </div>
      {Array.isArray(data?.vars) && data.vars.length > 0 && (
        <ul className="text-[11px] text-gray-700 space-y-0.5 pl-1">
          {data.vars.map((v, i) => (
            <li key={i}><code className="bg-gray-100 px-1 rounded text-[10.5px]">{v.name}</code> — {v.meaning}</li>
          ))}
        </ul>
      )}
      {data?.note && <div className="text-[10.5px] text-gray-600 mt-1.5 italic">{data.note}</div>}
    </div>
  );
}

function _Text({ title, data, estimated }: { title?: string; data: TextData; estimated?: boolean }) {
  return (
    <div className="bg-white/70 rounded-lg p-3 border border-violet-100">
      <_Header title={title} estimated={estimated} />
      <div className="text-[12px] text-gray-800 leading-[1.75] whitespace-pre-wrap">
        {(data?.body ?? "").replace(/\*\*/g, "").replace(/`/g, "")}
      </div>
    </div>
  );
}

function _ClarifyForm({ title, data }: { title?: string; data: ClarifyFormData }) {
  const fields = Array.isArray(data?.fields) ? data.fields : [];
  const [vals, setVals] = React.useState<Record<string, string | number>>(() => {
    const init: Record<string, string | number> = {};
    for (const f of fields) init[f.key] = f.default;
    return init;
  });
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<Record<string, unknown> | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  // frontend 자체 21-step 시뮬 (사용자 입력값 반영)
  const _designOne = (order: Record<string, number>) => {
    const thickness = 230;
    const density = 7.82;
    const productivity = 0.90307;
    const hr_max = 25000, hr_min = 8000;
    const w = order.ORDER_WIDTH || 1500;
    const l = order.ORDER_LENGTH || 8000;
    const ow_high = order.ORDER_WGT_HIGH || 20000;
    const ow_low = order.ORDER_WGT_LOW || 10000;
    const dpq = order.DESIGN_PEND_QTY || 40000;
    const fw_high = thickness * w * l * density * 1e-6;
    const fw_low = fw_high * 0.85;
    const yield_adj = dpq / productivity;
    const sw_high = Math.min(fw_high, ow_high, hr_max, yield_adj);
    const sw_low = Math.max(fw_low, ow_low, hr_min);
    if (sw_low > sw_high) return { ...order, slab_wgt: 0, split: 0, count: 0, ok: false, why: "DG104 폭/길이 초과 또는 단중 범위 불일치" };
    const max_split = Math.max(1, Math.ceil(sw_high / ow_high / productivity));
    let opt_split = 0, slab_wgt = 0;
    for (let s = max_split; s >= 1; s--) {
      const swh = Math.min(ow_high * s / productivity, sw_high);
      const swl = Math.max(ow_low * s / productivity, sw_low);
      if (swl <= swh) { opt_split = s; slab_wgt = swh; break; }
    }
    if (opt_split === 0) return { ...order, slab_wgt: 0, split: 0, count: 0, ok: false, why: "DG108 모든 split 실패" };
    const slab_count = Math.max(1, Math.floor(dpq / productivity / slab_wgt));
    const total = slab_wgt * slab_count;
    const target_w = Math.ceil(slab_wgt * 1e6 / (l * thickness * density) / 10) * 10;
    const target_l = Math.floor(slab_wgt * 1e6 / (target_w * thickness * density));
    return {
      ...order,
      thickness, first_wgt: Math.round(fw_high),
      second_wgt_high: Math.round(sw_high),
      max_split, split: opt_split, slab_wgt: Math.round(slab_wgt),
      count: slab_count, total: Math.round(total),
      target_width: target_w, target_length: target_l,
      ok: true,
    };
  };

  const _onSubmit = async () => {
    setBusy(true); setErr(null);
    try {
      const n = Math.max(1, Math.min(Number(vals.n_orders ?? 5), 20));
      const afterVal = Number(vals.after_val ?? 0);
      // n_orders 만큼 random 가상 주문 생성 (정상 중앙 범위)
      const rng = () => Math.random();
      const _r = (lo: number, hi: number, unit: number) => {
        const n_ = Math.floor(rng() * ((hi - lo) / unit + 1)) + Math.round(lo / unit);
        return n_ * unit;
      };
      const orders = [];
      for (let i = 0; i < n; i++) {
        const o: Record<string, number | string> = {
          ORDER_NO: `VIRT-${data.target_key ?? "FORM"}-${String(i + 1).padStart(3, "0")}`,
          ORDER_WIDTH: _r(1100, 1700, 50),
          ORDER_LENGTH: _r(6000, 9500, 100),
          ORDER_WGT_LOW: _r(9000, 12500, 250),
          ORDER_WGT_HIGH: _r(15000, 22000, 250),
          DESIGN_PEND_QTY: _r(28000, 50000, 500),
        };
        if (data.target_key && afterVal && data.target_key !== "_HR_MAX_WGT" && data.target_key !== "_THICKNESS") {
          o[data.target_key] = afterVal;
        }
        orders.push(o);
      }
      // 각 주문 21-step 시뮬
      const designs = orders.map(o => _designOne(o as Record<string, number>));
      const okCount = designs.filter(d => d.ok).length;
      const avgWgt = designs.filter(d => d.ok).reduce((s, d) => s + (d.slab_wgt as number), 0) / Math.max(1, okCount);
      setResult({
        designs, n_orders: n, ok_count: okCount, avg_wgt: Math.round(avgWgt),
        target_key: data.target_key, after_val: afterVal,
      });
      try {
        window.dispatchEvent(new CustomEvent("sim:form-submitted", {
          detail: { kind: "clarify_form", target: data.target_key, n_orders: n, values: vals },
        }));
      } catch {}
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-amber-50/60 rounded-lg p-3 border-2 border-amber-300">
      <_Header title={title} estimated={false} />
      <div className="text-[11px] text-amber-900 mb-2 leading-relaxed">
        AI 가 정확한 답을 드리려면 아래 값을 직접 확인·수정해주세요.
        값을 바꾸지 않으셔도 default 로 시뮬됩니다.
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mb-3">
        {fields.map((f) => (
          <label key={f.key} className="flex flex-col">
            <span className="text-[10.5px] text-gray-700 font-semibold mb-0.5">
              {f.label} {f.unit && <span className="text-[9px] text-gray-400">({f.unit})</span>}
            </span>
            {f.type === "select" && Array.isArray(f.options) ? (
              <select
                value={String(vals[f.key] ?? f.default)}
                onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}
                className="text-[12px] px-2 py-1 rounded border border-amber-200 bg-white focus:outline-none focus:border-amber-500"
              >
                {f.options.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : (
              <input
                type={f.type === "number" ? "number" : "text"}
                value={vals[f.key] ?? ""}
                onChange={(e) => setVals({ ...vals, [f.key]: f.type === "number" ? (e.target.value === "" ? "" : Number(e.target.value)) : e.target.value })}
                className="text-[12px] px-2 py-1 rounded border border-amber-200 bg-white focus:outline-none focus:border-amber-500 font-mono"
              />
            )}
            {f.hint && <span className="text-[9.5px] text-gray-500 mt-0.5">{f.hint}</span>}
          </label>
        ))}
      </div>
      <button
        onClick={_onSubmit}
        disabled={busy}
        className="w-full text-[12px] px-3 py-2 rounded bg-amber-600 text-white font-bold hover:bg-amber-700 disabled:bg-gray-300"
      >
        {busy ? "⏳ 가상 주문 합성 + 21-step 시뮬 중..." : (data.submit_label ?? "✓ 승인하고 시뮬")}
      </button>
      {err && <div className="mt-2 text-[10.5px] text-red-700 bg-red-50 rounded p-1.5 border border-red-200">⚠ {err}</div>}
      {result && (() => {
        const r = result as { designs: Array<Record<string, unknown>>; n_orders: number; ok_count: number; avg_wgt: number; target_key: string | null; after_val: number };
        return (
        <div className="mt-3 bg-emerald-50/60 rounded-lg p-3 border-2 border-emerald-400">
          <div className="text-[12px] font-bold text-emerald-900 mb-2 pb-2 border-b-2 border-emerald-300 flex items-baseline gap-3 flex-wrap">
            <span>✅ 승인 완료 — 입력값으로 {r.n_orders}건 가상 주문 + 21-step 시뮬</span>
            {r.target_key && r.after_val ? (
              <code className="text-[10px] text-emerald-700 bg-white px-1.5 py-0.5 rounded">{r.target_key}={r.after_val}</code>
            ) : null}
          </div>
          <div className="grid grid-cols-3 gap-2 mb-2 text-[11px]">
            <div className="bg-white rounded p-2 border border-emerald-200">
              <div className="text-[9.5px] text-emerald-700 uppercase font-bold">생성된 가상 주문</div>
              <div className="text-xl font-extrabold text-emerald-900">{r.n_orders}<span className="text-[10px] ml-1">건</span></div>
            </div>
            <div className="bg-white rounded p-2 border border-emerald-200">
              <div className="text-[9.5px] text-emerald-700 uppercase font-bold">feasible (설계 OK)</div>
              <div className="text-xl font-extrabold text-emerald-900">{r.ok_count}<span className="text-[10px] ml-1">/ {r.n_orders}</span></div>
            </div>
            <div className="bg-white rounded p-2 border border-emerald-200">
              <div className="text-[9.5px] text-emerald-700 uppercase font-bold">평균 Slab 단중</div>
              <div className="text-xl font-extrabold text-emerald-900">{r.avg_wgt.toLocaleString()}<span className="text-[10px] ml-1">kg</span></div>
            </div>
          </div>
          {/* N 건 21-step 결과 표 */}
          <div className="bg-white rounded overflow-x-auto border border-emerald-200">
            <table className="w-full text-[10.5px] border-collapse">
              <thead>
                <tr className="bg-emerald-100 border-b border-emerald-200">
                  <th className="px-1.5 py-1 text-left whitespace-nowrap">주문번호</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">주문폭</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">DPQ</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step4 1차</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step6 2차상한</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step8 분할</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step9 매수</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step10 단중</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step18 폭</th>
                  <th className="px-1.5 py-1 text-right whitespace-nowrap">Step19 길이</th>
                  <th className="px-1.5 py-1 text-left whitespace-nowrap">결과</th>
                </tr>
              </thead>
              <tbody>
                {r.designs.slice(0, 20).map((d, i) => (
                  <tr key={i} className="border-b border-gray-100 hover:bg-emerald-50/40">
                    <td className="px-1.5 py-1 font-mono whitespace-nowrap">{String(d.ORDER_NO)}</td>
                    <td className="px-1.5 py-1 text-right">{Number(d.ORDER_WIDTH).toLocaleString()}</td>
                    <td className="px-1.5 py-1 text-right">{Number(d.DESIGN_PEND_QTY).toLocaleString()}</td>
                    <td className="px-1.5 py-1 text-right">{d.first_wgt ? Number(d.first_wgt).toLocaleString() : "—"}</td>
                    <td className="px-1.5 py-1 text-right">{d.second_wgt_high ? Number(d.second_wgt_high).toLocaleString() : "—"}</td>
                    <td className="px-1.5 py-1 text-right">{String(d.split ?? "—")}</td>
                    <td className="px-1.5 py-1 text-right">{String(d.count ?? "—")}</td>
                    <td className="px-1.5 py-1 text-right font-mono font-bold text-emerald-800">{d.slab_wgt ? Number(d.slab_wgt).toLocaleString() : "—"}</td>
                    <td className="px-1.5 py-1 text-right">{d.target_width ? Number(d.target_width).toLocaleString() : "—"}</td>
                    <td className="px-1.5 py-1 text-right">{d.target_length ? Number(d.target_length).toLocaleString() : "—"}</td>
                    <td className="px-1.5 py-1 whitespace-nowrap">{d.ok ? <span className="text-emerald-700">✓ OK</span> : <span className="text-rose-700">✗ {String(d.why)}</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        );
      })()}
    </div>
  );
}

function _NewStandardForm({ title, data }: { title?: string; data: NewStandardFormData }) {
  const fields = Array.isArray(data?.fields) ? data.fields : [];
  const [vals, setVals] = React.useState<Record<string, string | number>>(() => {
    const init: Record<string, string | number> = {};
    for (const f of fields) init[f.key] = f.default;
    return init;
  });
  const [submitted, setSubmitted] = React.useState<Record<string, string | number> | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [designResult, setDesignResult] = React.useState<Record<string, unknown> | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  const _onChange = (k: string, raw: string, type: "string" | "number") => {
    setVals((v) => ({ ...v, [k]: type === "number" ? (raw === "" ? "" : Number(raw)) : raw }));
  };

  const _onSubmit = async () => {
    setBusy(true); setErr(null); setSubmitted(vals);
    try {
      // 신규 기준 + 가상 주문 base 합성 → /weight_optimize/sweep 호출 (재활용)
      // — 신규 기준 값을 base_order 의 추가 필드로 전달
      const baseOrder: Record<string, unknown> = {
        ORDER_NO: `VIRT-NEW-${data.kind.toUpperCase().slice(0,3)}-FORM`,
        ORDER_WIDTH: 1500, ORDER_LENGTH: 8000,
        ORDER_WGT_LOW: 10000, ORDER_WGT_HIGH: 20000, DESIGN_PEND_QTY: 40000,
      };
      // 신규 기준의 값 적용 (kind 별)
      if (data.kind === "customer") {
        if (typeof vals.pkgWgtLow === "number") baseOrder.ORDER_WGT_LOW = Math.max(Number(baseOrder.ORDER_WGT_LOW), vals.pkgWgtLow);
        if (typeof vals.pkgWgtHigh === "number") baseOrder.ORDER_WGT_HIGH = Math.min(Number(baseOrder.ORDER_WGT_HIGH), vals.pkgWgtHigh);
      } else if (data.kind === "grade") {
        const sm = Number(vals.smProductivity) || 0.98;
        const hr = Number(vals.hrProductivity) || 0.97;
        const cr = Number(vals.crProductivity) || 0.95;
        baseOrder._PRODUCTIVITY = sm * hr * cr;
      } else if (data.kind === "product") {
        if (typeof vals.slabThickness === "number") baseOrder._THICKNESS = vals.slabThickness;
      }
      const r = await fetch("/api/section3/simulation/weight_optimize/sweep", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          base_order: baseOrder,
          sweep_variables: ["ORDER_WGT_HIGH", "DESIGN_PEND_QTY"],
          grid_size: 3,
          repo_id: "slab-design-real-v2",
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setDesignResult(d);
      try {
        window.dispatchEvent(new CustomEvent("sim:form-submitted", {
          detail: { kind: "new_standard_form", domain: data.kind, values: vals },
        }));
      } catch {}
    } catch (e) {
      setErr(String((e as Error).message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-white/85 rounded-lg p-3 border-2 border-emerald-200">
      <_Header title={title} estimated={false} />
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mb-3">
        {fields.map((f) => (
          <label key={f.key} className="flex flex-col">
            <span className="text-[10px] text-gray-600 font-medium mb-0.5">
              {f.label} <code className="text-[9px] text-gray-400">{f.key}</code>
            </span>
            <div className="flex items-center gap-1">
              <input
                type={f.type === "number" ? "number" : "text"}
                value={vals[f.key] ?? ""}
                onChange={(e) => _onChange(f.key, e.target.value, f.type)}
                className="flex-1 text-[12px] px-2 py-1 rounded border border-emerald-200 bg-white focus:outline-none focus:border-emerald-500 font-mono"
              />
              {f.unit && <span className="text-[10px] text-gray-500">{f.unit}</span>}
            </div>
          </label>
        ))}
      </div>
      <button
        onClick={_onSubmit}
        disabled={busy}
        className="w-full text-[12px] px-3 py-2 rounded bg-emerald-600 text-white font-bold hover:bg-emerald-700 disabled:bg-gray-300"
      >
        {busy ? "⏳ 가상 주문 + 21-step 시뮬 중..." : (data.submit_label ?? "✓ 승인하고 시뮬")}
      </button>
      {err && <div className="mt-2 text-[10.5px] text-red-700 bg-red-50 rounded p-1.5 border border-red-200">⚠ {err}</div>}
      {submitted && designResult && (
        <div className="mt-3 bg-emerald-50/60 rounded-lg p-3 border border-emerald-300">
          <div className="text-[11.5px] font-bold text-emerald-900 mb-2 pb-1 border-b border-emerald-200">
            ✅ 승인 완료 — 신규 {data.kind} 기준 적용 결과
          </div>
          {(designResult as { best?: Record<string, unknown> | null }).best ? (
            <div className="grid grid-cols-2 gap-2 text-[11.5px]">
              <div className="bg-white rounded p-2 border border-emerald-100">
                <div className="text-[9.5px] text-emerald-700 uppercase font-bold">Slab 단중</div>
                <div className="text-xl font-extrabold text-emerald-900">
                  {Number((designResult as { best: { projected_slab_wgt: number } }).best.projected_slab_wgt).toLocaleString()}
                  <span className="text-[10px] font-normal"> kg</span>
                </div>
                <div className="text-[10px] text-gray-600">
                  split {(designResult as { best: { projected_split_count: number } }).best.projected_split_count}개
                </div>
              </div>
              <div className="bg-white rounded p-2 border border-emerald-100">
                <div className="text-[9.5px] text-emerald-700 uppercase font-bold">권장 변수</div>
                <ul className="space-y-0.5">
                  {Object.entries((designResult as { best: { vars: Record<string, number> } }).best.vars || {}).map(([k, v]) => (
                    <li key={k}><code className="text-[10px] text-emerald-800">{k}</code> = <strong className="font-mono">{Number(v).toLocaleString()}</strong></li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="text-[11px] text-amber-800 bg-amber-50 rounded p-2 border border-amber-200">
              ⚠ feasible 조합 없음 — 입력 값을 조정해보세요 (예: 단중 하한 줄이기)
            </div>
          )}
          {(designResult as { calculation_trace?: Array<Record<string, unknown>> }).calculation_trace
            && (designResult as { calculation_trace: Array<Record<string, unknown>> }).calculation_trace.length > 0 && (
            <details className="mt-2 text-[10.5px]">
              <summary className="cursor-pointer text-emerald-700 font-semibold">🧮 21-step 산식 trace ({(designResult as { calculation_trace: Array<Record<string, unknown>> }).calculation_trace.length}) — 펼치기</summary>
              <ol className="mt-1 space-y-1 pl-4">
                {(designResult as { calculation_trace: Array<{step_no:number;title:string;result:string}> }).calculation_trace.slice(0, 8).map((s, i) => (
                  <li key={i} className="text-gray-700">
                    <strong>step {s.step_no}</strong> {s.title} → <span className="text-emerald-800 font-mono">{s.result}</span>
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function _fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2);
  return String(v);
}
