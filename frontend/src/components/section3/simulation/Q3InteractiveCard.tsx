"use client";

/**
 * Q3 — "포장단중 상하한·설계대기량 변경 → slab 단중 영향" interactive UI.
 *
 * 사용자 요구 (2026-05-23):
 *   "주문데이터의 포장단중 상한, 하한 값을 사용자에게 입력받고 그런식으로 시뮬레이션
 *    에이전트가 움직여야해. UI도 그런식으로 구성되어야해!"
 *
 * 4-stage progressive disclosure:
 *   stage 1 — ontology 기반 가상 주문 자동 합성 + 필드 수정 가능
 *   stage 2 — 변경 전·후 포장단중 상하한 + 설계대기량 입력
 *   stage 3 — "시뮬 실행" 클릭 → /weight_optimize/sweep 호출
 *   stage 4 — 결과 grid + best 추천 + LLM 분석은 부모 카드의 _llm_analysis 가 처리
 */
import { useState } from "react";
import { ChevronRight, Edit, RefreshCw, Loader2, Sparkles } from "lucide-react";

interface Q3Data {
  virtual_order: Record<string, unknown>;
  constraints: { HR_MAX_WGT: number; HR_MIN_WGT: number };
  ontology_basis: string[];
  default_before: { ORDER_WGT_LOW: number; ORDER_WGT_HIGH: number; DESIGN_PEND_QTY: number };
  default_after_hint: { ORDER_WGT_LOW: number; ORDER_WGT_HIGH: number; DESIGN_PEND_QTY: number };
}

interface SweepCell {
  vars: Record<string, number>;
  projected_split_count: number;
  projected_slab_wgt: number;
  feasible: boolean;
  violations: string[];
}

interface SweepResult {
  grid: SweepCell[];
  best: SweepCell | null;
  summary: string;
  total_cells?: number;
  feasible_cells?: number;
}

export function Q3InteractiveCard({ data }: { data: Q3Data }) {
  const [stage, setStage] = useState<1 | 2 | 3 | 4>(1);
  const [virtualOrder, setVirtualOrder] = useState<Record<string, unknown>>(data.virtual_order);
  const [before, setBefore] = useState(data.default_before);
  const [after, setAfter] = useState(data.default_after_hint);
  const [sweepBefore, setSweepBefore] = useState<SweepResult | null>(null);
  const [sweepAfter, setSweepAfter] = useState<SweepResult | null>(null);
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function _runSweep() {
    setRunning(true); setErr(null);
    try {
      const baseHints = {
        _HR_MAX_WGT: data.constraints.HR_MAX_WGT,
        _HR_MIN_WGT: data.constraints.HR_MIN_WGT,
      };
      // 변경 전·후 각각 sweep
      const beforeReq = {
        base_order: { ...virtualOrder, ...before, ...baseHints },
        sweep_variables: ["ORDER_WGT_HIGH", "ORDER_WGT_LOW", "DESIGN_PEND_QTY"],
        grid_size: 5,
      };
      const afterReq = {
        base_order: { ...virtualOrder, ...after, ...baseHints },
        sweep_variables: ["ORDER_WGT_HIGH", "ORDER_WGT_LOW", "DESIGN_PEND_QTY"],
        grid_size: 5,
      };
      const [r1, r2] = await Promise.all([
        fetch("/api/section3/simulation/weight_optimize/sweep", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(beforeReq),
        }).then((r) => r.json()),
        fetch("/api/section3/simulation/weight_optimize/sweep", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(afterReq),
        }).then((r) => r.json()),
      ]);
      setSweepBefore(r1);
      setSweepAfter(r2);
      setStage(4);
    } catch (e) {
      setErr(String(e));
    } finally {
      setRunning(false);
    }
  }

  // 가상 주문 표시용 필드 (사용자가 수정 가능한 영역과 read-only 분리)
  const editableKeys = ["ORDER_WIDTH", "ORDER_LENGTH", "GRADE_CD", "PRODUCT_CD"];
  const headerKeys = ["ORDER_NO", "CMP_CD", "ORG_CD", "CUSTOMER_CD"];

  function _setOrderField(k: string, v: string) {
    setVirtualOrder((o) => ({ ...o, [k]: /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v }));
  }

  return (
    <div className="border-2 border-teal-300 bg-gradient-to-br from-teal-50/60 to-cyan-50/40 rounded-lg p-3 space-y-3">
      {/* 헤더 + stepper */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-teal-700 text-white font-semibold">Q3</span>
        <span className="text-sm font-bold text-teal-900">포장단중·설계대기량 → slab 단중 영향</span>
      </div>
      <div className="flex items-center gap-1 text-[10px] flex-wrap">
        {[
          { n: 1, label: "1. 가상 주문 확인·수정" },
          { n: 2, label: "2. 변경 전·후 입력" },
          { n: 3, label: "3. 시뮬 실행" },
          { n: 4, label: "4. 결과·비교" },
        ].map((s, i) => (
          <div key={s.n} className="flex items-center gap-1">
            <span className={
              "px-2 py-0.5 rounded border " + (
                stage === s.n ? "bg-teal-200 border-teal-500 text-teal-900 font-bold" :
                stage > s.n ? "bg-emerald-50 border-emerald-300 text-emerald-700" :
                "bg-gray-50 border-gray-200 text-gray-400"
              )
            }>{stage > s.n ? "✓ " : ""}{s.label}</span>
            {i < 3 && <span className="text-gray-300">→</span>}
          </div>
        ))}
      </div>

      {/* ontology 근거 */}
      <details className="text-[10px] bg-white/70 rounded border border-teal-200 p-1.5">
        <summary className="cursor-pointer text-teal-800 font-semibold flex items-center gap-1">
          <Sparkles size={11} /> 합성 근거 (ontology)
        </summary>
        <ul className="mt-1 ml-3 list-disc text-gray-700">
          {data.ontology_basis.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
        <div className="mt-1 text-gray-600">
          제약: HR_MAX_WGT = <code>{data.constraints.HR_MAX_WGT.toLocaleString()}</code>,
          HR_MIN_WGT = <code>{data.constraints.HR_MIN_WGT.toLocaleString()}</code>
        </div>
      </details>

      {/* STAGE 1 — 가상 주문 표시 + 수정 */}
      {stage === 1 && (
        <div className="space-y-2">
          <div className="text-[11px] text-teal-800">
            <Edit size={11} className="inline mr-1" />
            ontology 기반으로 가상 주문 1건을 합성했습니다. 필요 시 필드 값을 수정하세요.
          </div>
          <div className="bg-white/80 rounded border border-teal-200 p-2">
            <div className="text-[9px] text-teal-700 uppercase font-semibold mb-1">가상 주문 (read-only)</div>
            <div className="flex flex-wrap gap-1.5 text-[10.5px]">
              {headerKeys.filter((k) => virtualOrder[k] !== undefined).map((k) => (
                <code key={k} className="bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded">
                  {k}=<strong>{String(virtualOrder[k])}</strong>
                </code>
              ))}
            </div>
            <div className="text-[9px] text-teal-700 uppercase font-semibold mt-2 mb-1">속성 (수정 가능)</div>
            <div className="grid grid-cols-2 gap-2 text-[10.5px]">
              {editableKeys.filter((k) => virtualOrder[k] !== undefined).map((k) => (
                <div key={k} className="flex items-center gap-1">
                  <code className="text-teal-800 font-mono w-28">{k}</code>
                  <input
                    type="text"
                    value={String(virtualOrder[k] ?? "")}
                    onChange={(e) => _setOrderField(k, e.target.value)}
                    className="flex-1 text-[10.5px] px-1.5 py-0.5 border border-teal-300 rounded font-mono bg-white"
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-end">
            <button onClick={() => setStage(2)}
              className="px-3 py-1.5 text-xs rounded bg-teal-600 text-white hover:bg-teal-500 flex items-center gap-1">
              <ChevronRight size={12} /> 변경 전·후 입력
            </button>
          </div>
        </div>
      )}

      {/* STAGE 2 — 변경 전·후 입력 */}
      {stage === 2 && (
        <div className="space-y-2">
          <div className="text-[11px] text-teal-800">
            변경 전·후 값을 입력하세요. 포장단중 상한·하한과 설계대기량 모두 조정 가능합니다.
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-white/80 rounded border-2 border-gray-300 p-2">
              <div className="text-[9px] text-gray-700 uppercase font-semibold mb-1">변경 전 (현재)</div>
              {(["ORDER_WGT_LOW", "ORDER_WGT_HIGH", "DESIGN_PEND_QTY"] as const).map((k) => (
                <div key={k} className="flex items-center gap-1 mt-1">
                  <code className="text-gray-700 w-32 text-[10px]">{k}</code>
                  <input type="number"
                    value={before[k]}
                    onChange={(e) => setBefore((s) => ({ ...s, [k]: Number(e.target.value) }))}
                    className="flex-1 text-[10.5px] px-1.5 py-0.5 border border-gray-300 rounded font-mono"
                  />
                </div>
              ))}
            </div>
            <div className="bg-white/80 rounded border-2 border-amber-300 p-2">
              <div className="text-[9px] text-amber-700 uppercase font-semibold mb-1">변경 후 (가설)</div>
              {(["ORDER_WGT_LOW", "ORDER_WGT_HIGH", "DESIGN_PEND_QTY"] as const).map((k) => (
                <div key={k} className="flex items-center gap-1 mt-1">
                  <code className="text-amber-700 w-32 text-[10px]">{k}</code>
                  <input type="number"
                    value={after[k]}
                    onChange={(e) => setAfter((s) => ({ ...s, [k]: Number(e.target.value) }))}
                    className="flex-1 text-[10.5px] px-1.5 py-0.5 border border-amber-400 rounded font-mono text-amber-900 font-semibold"
                  />
                </div>
              ))}
            </div>
          </div>
          <div className="flex justify-between items-center gap-2">
            <button onClick={() => setStage(1)} className="text-[10px] text-gray-500 hover:text-gray-700">← 주문 수정</button>
            <button onClick={() => { setStage(3); _runSweep(); }}
              className="px-3 py-1.5 text-xs rounded bg-teal-600 text-white hover:bg-teal-500 flex items-center gap-1">
              <RefreshCw size={12} /> 시뮬 실행
            </button>
          </div>
        </div>
      )}

      {/* STAGE 3 — 실행 중 */}
      {stage === 3 && (
        <div className="bg-white/80 rounded border border-teal-200 p-3 flex items-center gap-2">
          {running ? (
            <>
              <Loader2 size={14} className="animate-spin text-teal-700" />
              <span className="text-[11px] text-teal-800">변경 전·후 각각 sweep 실행 중…</span>
            </>
          ) : (
            <span className="text-[11px] text-teal-800">실행 완료. 결과 단계로 이동합니다.</span>
          )}
        </div>
      )}

      {/* STAGE 4 — 결과 비교 (확대된 best 카드 + best 변수값 한 번에 노출 + 계산식) */}
      {stage === 4 && (sweepBefore || sweepAfter) && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "변경 전 (기준)", data: sweepBefore, color: "gray", border: "border-gray-300", bg: "bg-gray-50" },
              { label: "변경 후 (가설)", data: sweepAfter, color: "amber", border: "border-amber-400", bg: "bg-amber-50/40" },
            ].map((side) => (
              <div key={side.label} className={"rounded-lg border-2 p-3 " + side.border + " " + side.bg}>
                <div className={"text-[10.5px] uppercase font-bold mb-1.5 " + (
                  side.color === "amber" ? "text-amber-700" : "text-gray-700"
                )}>{side.label}</div>
                {side.data?.best ? (
                  <>
                    <div className="text-[11px] text-gray-600 mb-0.5">예상 slab 단중 (최대)</div>
                    <div className={"text-3xl font-extrabold leading-none " + (
                      side.color === "amber" ? "text-amber-700" : "text-gray-900"
                    )}>
                      {side.data.best.projected_slab_wgt.toLocaleString()}
                      <span className="text-base font-semibold ml-1">kg</span>
                    </div>
                    <div className="text-[11px] text-gray-700 mt-1">
                      split <strong>{side.data.best.projected_split_count}</strong>개 ·
                      feasible <strong>{side.data.feasible_cells}</strong>/{side.data.total_cells}
                    </div>
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <div className="text-[10px] text-gray-500 uppercase font-semibold mb-1">권장 변수값</div>
                      <ul className="space-y-0.5 text-[11px]">
                        {Object.entries(side.data.best.vars).map(([k, v]) => (
                          <li key={k} className="flex items-baseline gap-1">
                            <code className={"text-[10px] " + (side.color === "amber" ? "text-amber-800" : "text-gray-700")}>{k}</code>
                            <span className="text-gray-400">=</span>
                            <strong className={"font-mono " + (side.color === "amber" ? "text-amber-900" : "text-gray-900")}>
                              {Number(v).toLocaleString()}
                            </strong>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : (
                  <span className="text-[12px] text-red-700">feasible 조합 없음 — 제약 위반</span>
                )}
              </div>
            ))}
          </div>

          {/* 차이 요약 — 크게 */}
          {sweepBefore?.best && sweepAfter?.best && (() => {
            const delta = sweepAfter.best.projected_slab_wgt - sweepBefore.best.projected_slab_wgt;
            const pct = sweepBefore.best.projected_slab_wgt > 0
              ? (delta / sweepBefore.best.projected_slab_wgt) * 100 : 0;
            const goingUp = delta > 0;
            const trendCls = delta === 0 ? "text-gray-500"
              : goingUp ? "text-emerald-700" : "text-orange-700";
            return (
              <div className="bg-gradient-to-br from-emerald-50 to-teal-50 border-2 border-emerald-300 rounded-lg p-3">
                <div className="text-[11px] font-bold text-emerald-800 mb-1.5">변경 전·후 단중 변화</div>
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span className="text-[13px] font-mono text-gray-700">{sweepBefore.best.projected_slab_wgt.toLocaleString()} kg</span>
                  <span className="text-gray-400">→</span>
                  <span className={"text-2xl font-extrabold " + trendCls}>
                    {sweepAfter.best.projected_slab_wgt.toLocaleString()} kg
                  </span>
                  <span className={"text-[14px] font-bold " + trendCls}>
                    ({goingUp ? "+" : ""}{delta.toLocaleString()} kg · {goingUp ? "+" : ""}{pct.toFixed(1)}%)
                  </span>
                </div>
                <div className="text-[11.5px] text-gray-700 mt-1.5">{sweepAfter.summary}</div>
              </div>
            );
          })()}

          {/* 계산식·근거 */}
          <div className="bg-white/80 rounded-lg border border-teal-200 p-3 space-y-2">
            <div className="text-[11px] font-bold text-teal-800">최적 조합 계산 근거</div>
            <div className="text-[11.5px] text-gray-800 leading-relaxed">
              각 변수 조합마다 다음 식으로 예상 slab 단중을 계산합니다
            </div>
            <pre className="text-[11px] bg-teal-50/60 border border-teal-200 rounded p-2 text-teal-900 font-mono overflow-x-auto leading-relaxed">
{`# 1) 단중 상하한 결정 (외부 제약 ∩ 주문 제약)
wgt_cap   = min(ORDER_WGT_HIGH, HR_MAX_WGT)
wgt_floor = max(ORDER_WGT_LOW,  HR_MIN_WGT)

# 2) 최소 split 수로 1 slab 단중 최대화
split_count = ceil(DESIGN_PEND_QTY / wgt_cap)
slab_wgt    = DESIGN_PEND_QTY / split_count

# 3) split_wgt 가 하한 미만이면 split 줄여 보정
while slab_wgt < wgt_floor and split_count > 1:
    split_count -= 1
    slab_wgt    = DESIGN_PEND_QTY / split_count

# 4) wgt_floor ≤ slab_wgt ≤ wgt_cap 만족하면 feasible`}
            </pre>
            <ul className="text-[11px] text-gray-700 space-y-1 pl-1">
              <li>• 변수 3개 × 각 5점 = 125 조합 평가 (cartesian grid)</li>
              <li>• 제약 위반 조합 제외 → feasible 조합 중 slab_wgt 최대값을 best 로 추천</li>
              <li>• 이 식은 ontology business_rules (rule.scm.slab.wgt_range) + ORDER_OM 컬럼 정의 기반</li>
            </ul>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStage(2)} className="text-[11px] text-gray-600 hover:text-gray-900 underline">
              ← 다른 값으로 다시 시도
            </button>
          </div>
        </div>
      )}

      {err && (
        <div className="text-[11px] text-red-700 bg-red-50 border border-red-200 rounded p-2">{err}</div>
      )}
    </div>
  );
}
