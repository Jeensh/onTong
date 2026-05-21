"use client";

/** executed 게이트 카드 — intent 별 차별 레이아웃. */
import { useEffect, useState } from "react";
import { RotateCcw, Plus, ChevronRight, ChevronDown, Loader2, Code } from "lucide-react";
import { simulationApi, type MethodBodyView } from "@/lib/section3/simulation";

interface Props {
  payload: Record<string, unknown>;
  intent: string;
  onRerun: () => void;
  onNew: () => void;
  busy: boolean;
}

export function ExecutedResultCard({ payload, intent, onRerun, onNew, busy }: Props) {
  const error = payload.error as string | undefined;

  return (
    <div className="border border-gray-300 rounded-lg bg-white p-4 space-y-3 overflow-y-auto">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">실행 결과 (3/3)</h3>
        <span className="text-xs text-gray-400">intent={intent}</span>
      </header>

      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {error}
        </div>
      )}

      {!error && payload.kind === "executed_full_design" && <_FullDesignView payload={payload} />}
      {!error && payload.kind === "executed_compare" && <_CompareView payload={payload} />}
      {!error && payload.kind !== "executed_compare" && payload.kind !== "executed_full_design" && intent === "simulate" && <_SimulateView payload={payload} />}
      {!error && payload.kind !== "executed_compare" && payload.kind !== "executed_full_design" && intent === "impact" && <_ImpactView payload={payload} />}
      {!error && (intent === "locate" || intent === "explain") && <_LookupView payload={payload} intent={intent} />}
      {!error && intent === "hypothesis" && <_HypothesisView payload={payload} />}

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200">
        {intent === "simulate" && (
          <button onClick={onRerun} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
            <RotateCcw size={11} className="inline mr-1" /> 재실행
          </button>
        )}
        <button onClick={onNew} className="px-3 py-1.5 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-500">
          <Plus size={11} className="inline mr-1" /> 새 질문
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// intent 별 sub-view
// ─────────────────────────────────────────────────────────────────────────────

function _SimulateView({ payload }: { payload: Record<string, unknown> }) {
  const results = (payload.results as Array<Record<string, unknown>> | undefined) ?? [];
  const invariant = payload.invariant_status as string | undefined;
  const baselineDiff = payload.baseline_diff as Record<string, unknown> | null;

  return (
    <>
      <div className="text-[11px] text-gray-700">
        실행 결과 {results.length}건 · invariant <code className="text-emerald-700">{invariant ?? "?"}</code>
      </div>
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {results.slice(0, 5).map((r, i) => (
          <pre key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded p-2 overflow-x-auto">
            {JSON.stringify(r, null, 2).slice(0, 600)}
          </pre>
        ))}
      </div>
      {baselineDiff && (
        <div className="border border-amber-200 bg-amber-50 rounded p-2">
          <div className="text-[11px] text-amber-800 mb-1">baseline diff</div>
          <pre className="text-[10px] overflow-x-auto">{JSON.stringify(baselineDiff, null, 2).slice(0, 600)}</pre>
        </div>
      )}
    </>
  );
}

function _ImpactView({ payload }: { payload: Record<string, unknown> }) {
  const methods = (payload.affected_methods as Array<Record<string, unknown>> | undefined) ?? [];
  const findings = (payload.sim_v2_findings as Array<Record<string, unknown>> | undefined) ?? [];
  const confidence = (payload.confidence as number | undefined) ?? 0;
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (fqn: string) => {
    setExpanded((s) => {
      const n = new Set(s);
      n.has(fqn) ? n.delete(fqn) : n.add(fqn);
      return n;
    });
  };

  return (
    <>
      <div className="text-[11px] text-gray-700 bg-amber-50 border border-amber-200 rounded p-2">
        영향받는 method {methods.length}건 · sim_v2 findings {findings.length}건 · confidence {confidence.toFixed(2)}
        <div className="text-[10px] text-amber-700 mt-1">
          행을 클릭하면 코드 본문 + 호출/피호출 1-hop 이 확장됩니다.
        </div>
      </div>
      <div className="max-h-[400px] overflow-y-auto border border-gray-200 rounded">
        <table className="w-full text-[11px] border-collapse">
          <thead className="sticky top-0">
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-1.5 w-6"></th>
              <th className="text-left p-1.5 text-gray-600">method_fqn</th>
              <th className="text-left p-1.5 text-gray-600">via</th>
              <th className="text-right p-1.5 text-gray-600">score</th>
            </tr>
          </thead>
          <tbody>
            {methods.slice(0, 50).map((m) => {
              const fqn = String(m.method_fqn);
              const isOpen = expanded.has(fqn);
              return (
                <>
                  <tr
                    key={fqn}
                    className="border-b border-gray-100 hover:bg-amber-50/40 cursor-pointer"
                    onClick={() => toggle(fqn)}
                  >
                    <td className="p-1.5 text-gray-400">
                      {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                    </td>
                    <td className="p-1.5 font-mono text-gray-800 truncate max-w-[260px]" title={fqn}>
                      {fqn.split(".").slice(-2).join(".")}
                    </td>
                    <td className="p-1.5 text-gray-500">{String(m.via ?? "—")}</td>
                    <td className="p-1.5 text-right text-gray-700">{Number(m.score ?? 0).toFixed(2)}</td>
                  </tr>
                  {isOpen && (
                    <tr key={`${fqn}-body`} className="border-b border-amber-100">
                      <td colSpan={4} className="p-0">
                        <_MethodBodyRow fqn={fqn} onJumpTo={(f) => { toggle(f); }} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
      {findings.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer text-gray-600">sim_v2 findings {findings.length}건</summary>
          <ul className="mt-2 space-y-1">
            {findings.slice(0, 5).map((f, i) => (
              <li key={i} className="text-gray-700">
                <code className="bg-amber-50 px-1 rounded">{String(f.kind ?? "?")}</code> · {String(f.message ?? "")}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

/** 인터랙티브 expand — method body + callers/callees navigation. */
function _MethodBodyRow({ fqn, onJumpTo }: { fqn: string; onJumpTo: (f: string) => void }) {
  const [data, setData] = useState<MethodBodyView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    simulationApi.methodBody(fqn)
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fqn]);

  if (loading) {
    return (
      <div className="px-3 py-2 text-[11px] text-gray-500 bg-amber-50/30 flex items-center gap-1">
        <Loader2 size={11} className="animate-spin" /> 코드 로드 중...
      </div>
    );
  }
  if (error) {
    return <div className="px-3 py-2 text-[11px] text-red-700 bg-red-50">{error}</div>;
  }
  if (!data) return null;

  return (
    <div className="px-3 py-2 bg-amber-50/30 space-y-2">
      <div className="text-[10px] text-gray-500 font-mono break-all">{fqn}</div>
      {data.line_start && (
        <div className="text-[10px] text-gray-500">
          L{data.line_start}–{data.line_end ?? "?"}
          {data.annotations.length > 0 && (
            <span className="ml-2">
              {data.annotations.map((a) => (
                <code key={a} className="ml-1 text-[9px] px-1 bg-indigo-100 text-indigo-700 rounded">@{a}</code>
              ))}
            </span>
          )}
        </div>
      )}
      {data.body ? (
        <pre className="text-[10px] bg-white border border-amber-200 rounded p-2 max-h-48 overflow-auto text-gray-800">
{data.body.slice(0, 1200)}{data.body.length > 1200 ? "\n..." : ""}
        </pre>
      ) : (
        <div className="text-[10px] text-gray-400 italic">body 없음 (ontology 응답 비어있음)</div>
      )}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div>
          <div className="text-gray-500 mb-1 flex items-center gap-1">
            <Code size={10} /> 호출하는 곳 ({data.callers.length})
          </div>
          <ul className="space-y-0.5">
            {data.callers.slice(0, 6).map((c) => (
              <li key={c}>
                <button
                  onClick={(e) => { e.stopPropagation(); onJumpTo(c); }}
                  className="font-mono text-emerald-700 hover:underline truncate text-left"
                  title={c}
                >
                  ← {c.split(".").slice(-2).join(".")}
                </button>
              </li>
            ))}
            {data.callers.length === 0 && <li className="text-gray-400">없음</li>}
          </ul>
        </div>
        <div>
          <div className="text-gray-500 mb-1 flex items-center gap-1">
            <Code size={10} /> 호출되는 곳 ({data.callees.length})
          </div>
          <ul className="space-y-0.5">
            {data.callees.slice(0, 6).map((c) => (
              <li key={c}>
                <button
                  onClick={(e) => { e.stopPropagation(); onJumpTo(c); }}
                  className="font-mono text-sky-700 hover:underline truncate text-left"
                  title={c}
                >
                  → {c.split(".").slice(-2).join(".")}
                </button>
              </li>
            ))}
            {data.callees.length === 0 && <li className="text-gray-400">없음</li>}
          </ul>
        </div>
      </div>
    </div>
  );
}

function _LookupView({ payload, intent }: { payload: Record<string, unknown>; intent: string }) {
  // executed_lookup 의 shape — locate 와 explain 양쪽 공용
  const target = payload.target as Record<string, unknown> | undefined;
  const body = payload.body as string | undefined;
  const callers = (payload.callers as Array<Record<string, unknown>> | undefined) ?? [];
  const rules = (payload.business_rules as Array<Record<string, unknown>> | undefined) ?? [];
  const summary = payload.summary as string | undefined;

  return (
    <>
      {summary && (
        <div className="text-sm text-gray-800 bg-violet-50 border border-violet-200 rounded p-2">
          {summary}
        </div>
      )}
      {target && (
        <div className="text-[11px] text-gray-600">
          target: <code className="font-mono">{String(target.code_method_fqn ?? "?")}</code>
        </div>
      )}
      {body && (
        <div className="border border-gray-200 rounded">
          <div className="px-2 py-1 bg-gray-50 border-b border-gray-200 text-[11px] text-gray-600">
            method body
          </div>
          <pre className="p-2 text-[10px] max-h-48 overflow-auto text-gray-800">{body.slice(0, 800)}</pre>
        </div>
      )}
      {callers.length > 0 && (
        <div>
          <div className="text-[11px] text-gray-600 mb-1">callers {callers.length}건</div>
          <ul className="text-[10px] space-y-0.5 max-h-32 overflow-y-auto">
            {callers.slice(0, 20).map((c, i) => (
              <li key={i} className="font-mono text-gray-700 truncate">{String(c.method_fqn ?? c)}</li>
            ))}
          </ul>
        </div>
      )}
      {rules.length > 0 && (
        <div>
          <div className="text-[11px] text-gray-600 mb-1">business rules {rules.length}건</div>
          <ul className="text-[11px] space-y-1 max-h-32 overflow-y-auto">
            {rules.slice(0, 6).map((r, i) => (
              <li key={i} className="text-gray-700">
                <code className="bg-red-50 px-1 rounded">{String(r.severity ?? "?")}</code> · {String(r.statement ?? "")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// _FullDesignView — Java :8080 의 /api/sd/working/single 결과
// ─────────────────────────────────────────────────────────────────────────────

function _FullDesignView({ payload }: { payload: Record<string, unknown> }) {
  const orderNo = payload.order_no as string;
  const slabResults = (payload.slab_results as Array<Record<string, unknown>> | undefined) ?? [];
  const trace = (payload.trace as Array<Record<string, unknown>> | undefined) ?? [];
  const errorCode = payload.error_code as string | null;
  const errorMessage = payload.error_message as string | null;
  const ok = payload.ok as boolean;

  // 슬랩 결과의 핵심 필드만 추려서 highlight
  const HIGHLIGHT_FIELDS: { key: string; label: string; unit?: string }[] = [
    { key: "slabThickness", label: "두께", unit: "mm" },
    { key: "slabWidth",     label: "폭",   unit: "mm" },
    { key: "slabLength",    label: "길이", unit: "mm" },
    { key: "slabWgt",       label: "단중", unit: "kg" },
    { key: "splitCount",    label: "분할수" },
    { key: "designStatus",  label: "상태" },
    { key: "slabNo",        label: "슬랩번호" },
  ];

  return (
    <>
      <div className="text-sm">
        <span className="font-semibold">주문 </span>
        <code className="text-emerald-700">{orderNo}</code>
        <span className="text-gray-500 ml-2">→ 슬랩 {slabResults.length}매 설계</span>
      </div>

      {!ok && errorCode && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {errorCode}: {errorMessage}
        </div>
      )}

      {slabResults.map((slab, i) => (
        <div key={i} className="border-2 border-emerald-300 rounded-lg bg-emerald-50/30">
          <div className="px-3 py-2 bg-emerald-100 border-b border-emerald-300 flex items-center justify-between">
            <strong className="text-emerald-900 text-xs">슬랩 #{i + 1}</strong>
            <code className="text-[10px] text-emerald-700">slabNo {String(slab.slabNo)}</code>
          </div>
          <div className="grid grid-cols-4 gap-2 p-3">
            {HIGHLIGHT_FIELDS.map((f) => {
              const v = slab[f.key];
              if (v === undefined || v === null) return null;
              return (
                <div key={f.key} className="text-center">
                  <div className="text-[10px] text-gray-500">{f.label}</div>
                  <div className={"text-sm font-mono mt-0.5 " + (
                    f.key === "designStatus" && v === "SUCCESS" ? "text-emerald-700 font-semibold" :
                    f.key === "designStatus" ? "text-red-700 font-semibold" : "text-gray-900"
                  )}>
                    {typeof v === "number" ? v.toLocaleString(undefined, {maximumFractionDigits: 2}) : String(v)}
                    {f.unit && <span className="text-[10px] text-gray-400 ml-0.5">{f.unit}</span>}
                  </div>
                </div>
              );
            })}
          </div>
          <details className="border-t border-emerald-200">
            <summary className="px-3 py-1.5 text-[11px] text-emerald-800 cursor-pointer hover:bg-emerald-100/50">
              전체 필드 보기 ({Object.keys(slab).length}건)
            </summary>
            <div className="p-2 max-h-64 overflow-auto">
              <table className="w-full text-[10px]">
                <tbody>
                  {Object.entries(slab).map(([k, v]) => (
                    <tr key={k} className="border-b border-emerald-100">
                      <td className="py-0.5 pr-2 text-gray-500 font-mono">{k}</td>
                      <td className="py-0.5 font-mono text-gray-800">
                        {v === null ? <span className="text-gray-300">null</span> :
                         typeof v === "number" ? v.toLocaleString(undefined, {maximumFractionDigits: 6}) :
                         String(v)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ))}

      {trace.length > 0 && (
        <details open className="border border-gray-200 rounded">
          <summary className="px-3 py-2 bg-gray-50 border-b border-gray-200 cursor-pointer text-xs font-semibold text-gray-800">
            21-step 실행 trace ({trace.length} rows)
          </summary>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-[10px] border-collapse">
              <thead className="sticky top-0 bg-gray-50">
                <tr className="border-b border-gray-200">
                  <th className="p-1.5 text-left text-gray-600">step</th>
                  <th className="p-1.5 text-left text-gray-600">action</th>
                  <th className="p-1.5 text-left text-gray-600">phase</th>
                  <th className="p-1.5 text-right text-gray-600">iter</th>
                  <th className="p-1.5 text-left text-gray-600">status</th>
                  <th className="p-1.5 text-left text-gray-600">error</th>
                </tr>
              </thead>
              <tbody>
                {trace.map((t, i) => {
                  const status = String(t.status);
                  return (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="p-1 font-mono">{String(t.step)}</td>
                      <td className="p-1 text-gray-800">{String(t.stepName)}</td>
                      <td className="p-1 text-gray-500">{String(t.phase)}</td>
                      <td className="p-1 text-right text-gray-500">{String(t.iteration)}</td>
                      <td className={"p-1 font-semibold " + (
                        status === "OK" ? "text-emerald-700" :
                        status === "RETRY" ? "text-amber-700" :
                        status === "FAIL" ? "text-red-700" : "text-gray-500"
                      )}>{status}</td>
                      <td className="p-1 text-red-600 font-mono">{t.errorCode ? String(t.errorCode) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <div className="text-[10px] text-gray-400 mt-2">
        Java :8080 의 /api/sd/working/single?trace=true 호출 결과. 21-step 알고리즘 전체 실행.
      </div>
    </>
  );
}


function _CompareView({ payload }: { payload: Record<string, unknown> }) {
  const before = payload.before_result as Record<string, unknown> | null;
  const after = payload.after_result as Record<string, unknown> | null;
  const diffs = (payload.field_diffs as Array<Record<string, unknown>> | undefined) ?? [];
  const summary = payload.summary as string | undefined;
  const changedCount = diffs.filter((d) => d.changed).length;

  return (
    <>
      <div className="text-sm font-semibold text-amber-800 bg-amber-50 border border-amber-300 rounded p-2">
        변경 전·후 비교 · {summary}
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="border border-gray-200 rounded">
          <div className="px-2 py-1 bg-gray-50 text-[11px] text-gray-600">변경 전</div>
          <pre className="p-2 text-[10px] max-h-40 overflow-auto">
            {JSON.stringify(before ?? {}, null, 2).slice(0, 600)}
          </pre>
        </div>
        <div className="border border-emerald-300 rounded">
          <div className="px-2 py-1 bg-emerald-50 text-[11px] text-emerald-800">변경 후</div>
          <pre className="p-2 text-[10px] max-h-40 overflow-auto">
            {JSON.stringify(after ?? {}, null, 2).slice(0, 600)}
          </pre>
        </div>
        <div className="border border-amber-300 rounded">
          <div className="px-2 py-1 bg-amber-50 text-[11px] text-amber-800">
            DIFF (변경 {changedCount}/{diffs.length})
          </div>
          <ul className="p-2 text-[10px] max-h-40 overflow-auto space-y-0.5">
            {diffs.filter((d) => d.changed).slice(0, 20).map((d, i) => (
              <li key={i} className="font-mono">
                <span className="text-gray-500">{String(d.field)}:</span>{" "}
                <span className="text-red-700 line-through">{JSON.stringify(d.before)}</span>{" "}
                →{" "}
                <span className="text-emerald-700">{JSON.stringify(d.after)}</span>
              </li>
            ))}
            {changedCount === 0 && <li className="text-gray-400">변경 없음</li>}
          </ul>
        </div>
      </div>
    </>
  );
}

function _HypothesisView({ payload }: { payload: Record<string, unknown> }) {
  const verdict = payload.verdict as string | undefined;
  const reasoning = payload.reasoning as string | undefined;
  const target = payload.target as Record<string, unknown> | undefined;
  const conditions = (payload.conditions as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <>
      {verdict && (
        <div className="text-sm font-semibold">
          <span className={
            verdict === "passes" ? "text-emerald-700" :
            verdict === "fails" ? "text-red-700" : "text-amber-700"
          }>
            verdict: {verdict}
          </span>
        </div>
      )}
      {reasoning && <div className="text-xs text-gray-800 bg-gray-50 border border-gray-200 rounded p-2">{reasoning}</div>}
      {target && (
        <div className="text-[11px] text-gray-600">
          target: <code className="font-mono">{String(target.code_method_fqn ?? "?")}</code>
        </div>
      )}
      {conditions.length > 0 && (
        <div>
          <div className="text-[11px] text-gray-600 mb-1">conditions {conditions.length}건</div>
          <ul className="text-[11px] space-y-0.5">
            {conditions.map((c, i) => (
              <li key={i} className="font-mono text-gray-700">
                {String(c.var ?? "?")} {String(c.op ?? "=")} {String(c.value ?? "?")} {String(c.unit ?? "")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
