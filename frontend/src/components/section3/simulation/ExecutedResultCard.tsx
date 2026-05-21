"use client";

/** executed 게이트 카드 — intent 별 차별 레이아웃. */
import { useEffect, useState } from "react";
import { RotateCcw, Plus, ChevronRight, ChevronDown, Loader2, Code } from "lucide-react";
import { simulationApi, type MethodBodyView, type HypothesisResponse } from "@/lib/section3/simulation";

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
      {!error && intent === "locate" && <_LocateView payload={payload} />}
      {!error && intent === "explain" && <_ExplainView payload={payload} />}
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

/** locate — VSCode 스타일 파일 트리 + 코드 viewer. */
function _LocateView({ payload }: { payload: Record<string, unknown> }) {
  const target = payload.target as Record<string, unknown> | undefined;
  const body = (payload.body as string | undefined) ?? "";
  const summary = payload.summary as string | undefined;
  const fqn = String(target?.code_method_fqn ?? "");

  // FQN → file tree path 추출 (com.example.x.y.Class.method → com/example/x/y/Class.java)
  const classPart = fqn.split("(")[0].split(".").slice(0, -1).join(".");
  const pkgs = classPart.split(".");
  const className = pkgs.pop() ?? "";
  const filePath = pkgs.join("/") + "/" + className + ".java";

  return (
    <>
      <div className="text-[11px] text-sky-800 bg-sky-50 border border-sky-200 rounded p-2 flex items-center gap-2">
        <span>🔍</span>
        <span>{summary || "코드 위치 검색 결과"}</span>
      </div>

      <div className="grid grid-cols-[200px_1fr] gap-2 border border-gray-300 rounded overflow-hidden">
        {/* 좌: 파일 트리 */}
        <div className="bg-slate-50 border-r border-gray-200 p-2 text-[10px]">
          <div className="text-gray-500 uppercase tracking-wide mb-1">파일 트리</div>
          <div className="font-mono space-y-0.5">
            {pkgs.map((seg, i) => (
              <div key={i} style={{ paddingLeft: i * 8 }} className="text-gray-600">
                📁 {seg}
              </div>
            ))}
            <div style={{ paddingLeft: pkgs.length * 8 }} className="text-sky-700 font-semibold">
              📄 {className}.java
            </div>
            <div style={{ paddingLeft: (pkgs.length + 1) * 8 }} className="text-emerald-700">
              ⚡ {fqn.split(".").pop()?.split("(")[0]}
            </div>
          </div>
        </div>

        {/* 우: 코드 본문 */}
        <div className="bg-white">
          <div className="px-2 py-1 bg-gray-50 border-b border-gray-200 text-[10px] flex items-center justify-between">
            <code className="text-gray-700">{filePath}</code>
            <span className="text-gray-400">{body.split("\n").length} lines</span>
          </div>
          <pre className="p-2 text-[10px] max-h-72 overflow-auto text-gray-800 font-mono leading-relaxed">
            {body || "(코드 본문 없음)"}
          </pre>
        </div>
      </div>

      <div className="text-[10px] text-gray-500">
        💡 좌측 패키지 경로 클릭 시 다른 위치로 이동하는 기능은 후속 작업 예정.
      </div>
    </>
  );
}

/** explain — 자연어 답변 + 관련 객체 카드 grid. */
function _ExplainView({ payload }: { payload: Record<string, unknown> }) {
  const target = payload.target as Record<string, unknown> | undefined;
  const body = (payload.body as string | undefined) ?? "";
  const summary = payload.summary as string | undefined;
  const callers = (payload.callers as Array<Record<string, unknown>> | undefined) ?? [];
  const rules = (payload.business_rules as Array<Record<string, unknown>> | undefined) ?? [];

  const targetClass = String(target?.code_method_fqn ?? "").split("(")[0].split(".").slice(-2, -1)[0] ?? "";
  const targetMethod = String(target?.code_method_fqn ?? "").split("(")[0].split(".").pop() ?? "";

  return (
    <>
      {/* 큰 답변 박스 — chat 이 더 수용 */}
      <div className="bg-gradient-to-br from-violet-50 to-purple-50 border-2 border-violet-200 rounded-lg p-3 shadow-sm">
        <div className="flex items-start gap-2">
          <div className="text-xl">💬</div>
          <div className="flex-1">
            <div className="text-[10px] uppercase tracking-wide text-violet-700 font-semibold mb-1">답변</div>
            <div className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {summary ||
                (target ? `${targetClass}.${targetMethod} 에 대한 설명입니다. 본문은 아래 코드 카드를 참고하세요.` :
                  "해당 의미에 대한 정확한 답변을 ontology 가 합성하지 못했습니다. 다른 표현으로 다시 시도해 주세요.")}
            </div>
          </div>
        </div>
      </div>

      {/* 관련 객체 카드 grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* code 카드 */}
        {target && (
          <div className="border-2 border-emerald-200 bg-emerald-50/50 rounded p-2 col-span-2">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-600 text-white font-semibold">CODE</span>
              <code className="text-[11px] font-mono text-emerald-900">
                {targetClass}.{targetMethod}
              </code>
            </div>
            <pre className="text-[10px] bg-white border border-emerald-200 rounded p-2 max-h-40 overflow-auto text-gray-800">
              {body.slice(0, 600) || "(본문 없음)"}
            </pre>
          </div>
        )}

        {/* business rules 카드 */}
        {rules.length > 0 && (
          <div className="border-2 border-rose-200 bg-rose-50/50 rounded p-2">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-600 text-white font-semibold">RULES</span>
              <span className="text-[10px] text-gray-500">{rules.length}건</span>
            </div>
            <ul className="text-[10px] space-y-1 max-h-32 overflow-y-auto">
              {rules.slice(0, 5).map((r, i) => (
                <li key={i}>
                  <code className="text-[9px] bg-rose-100 px-1 rounded text-rose-800">{String(r.severity ?? "?")}</code>
                  <span className="text-gray-700 ml-1">{String(r.statement ?? "")}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* callers 카드 */}
        {callers.length > 0 && (
          <div className="border-2 border-sky-200 bg-sky-50/50 rounded p-2">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-600 text-white font-semibold">CALLERS</span>
              <span className="text-[10px] text-gray-500">{callers.length}건</span>
            </div>
            <ul className="text-[10px] space-y-0.5 max-h-32 overflow-y-auto">
              {callers.slice(0, 8).map((c, i) => (
                <li key={i} className="font-mono text-sky-800 truncate" title={String(c.method_fqn ?? c)}>
                  ← {String(c.method_fqn ?? c).split(".").slice(-2).join(".")}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
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

  const statusCounts: Record<string, number> = {};
  for (const t of trace) {
    const s = String(t.status);
    statusCounts[s] = (statusCounts[s] || 0) + 1;
  }

  return (
    <>
      <div className="bg-gradient-to-r from-emerald-600 to-emerald-700 text-white rounded-lg p-3 shadow">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wide opacity-80">주문</div>
            <div className="text-lg font-mono font-bold">{orderNo}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wide opacity-80">설계 결과</div>
            <div className="text-lg font-bold">
              {ok && !errorCode ? `Slab ${slabResults.length}매 SUCCESS` : `FAIL ${errorCode || ""}`}
            </div>
          </div>
        </div>
      </div>

      {!ok && errorCode && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {errorCode}: {errorMessage}
        </div>
      )}

      {slabResults.map((slab, i) => (
        <_SlabResultCard key={i} slab={slab} index={i + 1} />
      ))}

      {trace.length > 0 && (
        <div className="border border-gray-200 rounded">
          <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <strong className="text-xs text-gray-800">21-step 알고리즘 실행 진행도</strong>
            <div className="flex gap-1.5 text-[10px]">
              {Object.entries(statusCounts).map(([s, n]) => (
                <span key={s} className={
                  "px-1.5 py-0.5 rounded font-semibold " + (
                    s === "OK" ? "bg-emerald-100 text-emerald-800" :
                    s === "RETRY" ? "bg-amber-100 text-amber-800" :
                    s === "FAIL" ? "bg-red-100 text-red-800" :
                    s === "SKIP" ? "bg-gray-100 text-gray-600" : "bg-gray-100 text-gray-600"
                  )
                }>{s} {n}</span>
              ))}
            </div>
          </div>
          <_TraceGantt trace={trace} />
        </div>
      )}

      <div className="text-[10px] text-gray-400 mt-2">
        Java :8080 /api/sd/working/single?trace=true · 21-step 알고리즘 전체 실행
      </div>
    </>
  );
}

/** Slab 1매 — SVG 원면도 + KPI 4종 + 허용범위 미니바 + 전체 필드. */
function _SlabResultCard({ slab, index }: { slab: Record<string, unknown>; index: number }) {
  const thickness = Number(slab.slabThickness ?? 0);
  const width = Number(slab.slabWidth ?? 0);
  const length = Number(slab.slabLength ?? 0);
  const wgt = Number(slab.slabWgt ?? 0);
  const splitCount = Number(slab.splitCount ?? 0);
  const status = String(slab.designStatus ?? "?");

  const maxDim = Math.max(width, length, 1);
  const scale = 200 / maxDim;
  const l = length * scale;
  const w = Math.max(width * scale * 0.3, 20);
  const t = Math.max(thickness * 0.06, 6);

  const RangeBar = ({ label, value, low, high, unit }: {
    label: string; value: number; low: number; high: number; unit: string;
  }) => {
    const range = high - low || 1;
    const pct = Math.max(0, Math.min(100, ((value - low) / range) * 100));
    return (
      <div>
        <div className="flex items-baseline justify-between text-[10px]">
          <span className="text-gray-500">{label}</span>
          <span className="text-emerald-700 font-mono font-semibold">
            {value.toLocaleString(undefined,{maximumFractionDigits:1})}{unit}
          </span>
        </div>
        <div className="h-2 bg-gray-100 rounded relative">
          <div className="absolute h-2 bg-emerald-500 rounded-sm" style={{ left: `${pct}%`, width: 4 }} />
        </div>
        <div className="flex justify-between text-[9px] text-gray-400 font-mono mt-0.5">
          <span>{low.toLocaleString(undefined,{maximumFractionDigits:0})}</span>
          <span>{high.toLocaleString(undefined,{maximumFractionDigits:0})}{unit}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="border-2 border-emerald-300 rounded-lg bg-white shadow-sm">
      <div className="px-3 py-2 bg-emerald-50 border-b border-emerald-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <strong className="text-emerald-900 text-sm">Slab #{index}</strong>
          <code className="text-[10px] text-emerald-700">slabNo {String(slab.slabNo)}</code>
        </div>
        <span className={
          "text-[10px] px-2 py-0.5 rounded font-semibold " +
          (status === "SUCCESS" ? "bg-emerald-600 text-white" : "bg-red-600 text-white")
        }>{status}</span>
      </div>

      <div className="grid grid-cols-[210px_1fr] gap-3 p-3">
        <div className="flex flex-col items-center">
          <svg viewBox="0 0 240 200" width="200" height="170">
            <defs>
              <linearGradient id={`g${index}`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#fbbf24" />
                <stop offset="100%" stopColor="#d97706" />
              </linearGradient>
            </defs>
            <rect x={(240 - l) / 2} y="70" width={l} height={t} fill={`url(#g${index})`} stroke="#92400e" strokeWidth="1" />
            <text x="120" y="66" textAnchor="middle" fontSize="9" fill="#92400e">길이 {length.toLocaleString()} mm</text>
            <text x={(240 - l) / 2 - 3} y={75 + t / 2} textAnchor="end" fontSize="8" fill="#92400e">↑{thickness}mm</text>
            <rect x={(240 - l) / 2} y="105" width={l} height={w} fill="#fef3c7" stroke="#92400e" strokeWidth="1" strokeDasharray="2 2" />
            <text x="120" y={105 + w + 12} textAnchor="middle" fontSize="9" fill="#92400e">폭 {width.toLocaleString()} mm</text>
          </svg>
          <div className="text-[9px] text-gray-400 mt-1">schematic · 비율 아님</div>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-2 text-center">
            <div className="bg-amber-50 rounded p-2 border border-amber-200">
              <div className="text-[9px] text-amber-700">두께</div>
              <div className="text-sm font-mono font-bold text-amber-900">{thickness}</div>
              <div className="text-[9px] text-amber-600">mm</div>
            </div>
            <div className="bg-sky-50 rounded p-2 border border-sky-200">
              <div className="text-[9px] text-sky-700">폭</div>
              <div className="text-sm font-mono font-bold text-sky-900">{width.toLocaleString()}</div>
              <div className="text-[9px] text-sky-600">mm</div>
            </div>
            <div className="bg-violet-50 rounded p-2 border border-violet-200">
              <div className="text-[9px] text-violet-700">길이</div>
              <div className="text-sm font-mono font-bold text-violet-900">{length.toLocaleString()}</div>
              <div className="text-[9px] text-violet-600">mm</div>
            </div>
            <div className="bg-emerald-50 rounded p-2 border border-emerald-200">
              <div className="text-[9px] text-emerald-700">단중</div>
              <div className="text-sm font-mono font-bold text-emerald-900">
                {wgt.toLocaleString(undefined,{maximumFractionDigits:1})}
              </div>
              <div className="text-[9px] text-emerald-600">kg · {splitCount}분할</div>
            </div>
          </div>

          {slab.slabWidthLow !== undefined && slab.slabWidthHigh !== undefined && (
            <RangeBar label="폭 허용범위 안 위치" value={width}
              low={Number(slab.slabWidthLow)} high={Number(slab.slabWidthHigh)} unit="mm" />
          )}
          {slab.slabWgtLow !== undefined && slab.slabWgtHigh !== undefined && (
            <RangeBar label="단중 허용범위 안 위치" value={wgt}
              low={Number(slab.slabWgtLow)} high={Number(slab.slabWgtHigh)} unit="kg" />
          )}
        </div>
      </div>

      <details className="border-t border-emerald-200">
        <summary className="px-3 py-1.5 text-[11px] text-emerald-800 cursor-pointer hover:bg-emerald-50/80">
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
                     typeof v === "number" ? v.toLocaleString(undefined,{maximumFractionDigits:6}) :
                     String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/** 21-step gantt 스타일 진행도. */
function _TraceGantt({ trace }: { trace: Array<Record<string, unknown>> }) {
  type StepBar = { step: number; stepName: string; rows: Array<Record<string, unknown>>; finalStatus: string };
  const byStep: Record<number, StepBar> = {};
  for (const t of trace) {
    const n = Number(t.step);
    if (!byStep[n]) byStep[n] = { step: n, stepName: String(t.stepName), rows: [], finalStatus: String(t.status) };
    byStep[n].rows.push(t);
    byStep[n].finalStatus = String(t.status);
  }
  const steps = Object.values(byStep).sort((a, b) => a.step - b.step);

  return (
    <div className="p-2 space-y-0.5 max-h-72 overflow-y-auto">
      {steps.map((s) => {
        const color =
          s.finalStatus === "OK" ? "bg-emerald-500" :
          s.finalStatus === "RETRY" ? "bg-amber-500" :
          s.finalStatus === "FAIL" ? "bg-red-500" :
          s.finalStatus === "SKIP" ? "bg-gray-300" : "bg-gray-400";
        const hasRetry = s.rows.length > 1;
        return (
          <div key={s.step} className="flex items-center gap-2 text-[10px]" title={s.stepName}>
            <code className="w-7 text-right text-gray-500">{s.step}</code>
            <div className="w-40 truncate text-gray-700">{s.stepName.replace(/Action$/, "")}</div>
            <div className="flex-1 h-3 rounded bg-gray-100 relative overflow-hidden">
              <div className={"h-full " + color} style={{ width: "100%" }} />
              {hasRetry && (
                <div className="absolute inset-0 flex items-center justify-center text-[8px] font-bold text-white">
                  {s.rows.length}× iter
                </div>
              )}
            </div>
            <span className={
              "w-12 text-right font-semibold " + (
                s.finalStatus === "OK" ? "text-emerald-700" :
                s.finalStatus === "RETRY" ? "text-amber-700" :
                s.finalStatus === "FAIL" ? "text-red-700" :
                s.finalStatus === "SKIP" ? "text-gray-400" : "text-gray-500"
              )
            }>{s.finalStatus}</span>
          </div>
        );
      })}
    </div>
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
  // legacy multiturn hypothesis payload + 신규 hypothesis workflow 둘 다 처리
  const verdict = payload.verdict as string | undefined;
  const reasoning = payload.reasoning as string | undefined;

  const [hyp, setHyp] = useState<HypothesisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [params, setParams] = useState({
    base_grade: "SS400", new_grade: "SS500",
    productivity_multiplier: 0.95, base_order_no: "ORD20260510001",
  });
  const [error, setError] = useState<string | null>(null);

  // 자동 1회 호출 (default 파라미터)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    simulationApi.hypothesis(params)
      .then((d) => { if (!cancelled) setHyp(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function _rerun() {
    setLoading(true); setError(null);
    try {
      const d = await simulationApi.hypothesis(params);
      setHyp(d);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* 시나리오 헤더 */}
      <div className="bg-gradient-to-r from-rose-600 to-rose-700 text-white rounded-lg p-3 shadow">
        <div className="text-[10px] uppercase tracking-wide opacity-80">가설 검증</div>
        <div className="text-sm font-semibold mt-0.5">
          신규 강종 <code className="bg-white/20 px-1.5 py-0.5 rounded">{params.new_grade}</code> 가 추가되면
          <span className="opacity-80">
            {" "}({params.base_grade} 대비 productivity ×{params.productivity_multiplier})
          </span>
          {" "}→ <code className="bg-white/20 px-1.5 py-0.5 rounded">{params.base_order_no}</code> 의 Slab 결과는?
        </div>
      </div>

      {/* legacy multiturn 응답이 있으면 같이 표시 */}
      {(verdict || reasoning) && (
        <div className="text-xs bg-gray-50 border border-gray-200 rounded p-2">
          <div className="font-semibold text-gray-700">multiturn verdict: <span className={
            verdict === "passes" ? "text-emerald-700" :
            verdict === "fails" ? "text-red-700" : "text-amber-700"
          }>{verdict ?? "?"}</span></div>
          {reasoning && <div className="text-gray-600 mt-1">{reasoning}</div>}
        </div>
      )}

      {/* 파라미터 컨트롤 */}
      <details className="border border-gray-200 rounded text-[11px]">
        <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-700">파라미터 조정</summary>
        <div className="p-2 grid grid-cols-2 gap-2">
          {(["base_grade","new_grade","base_order_no"] as const).map((k) => (
            <label key={k} className="flex flex-col">
              <span className="text-gray-500">{k}</span>
              <input value={params[k] as string}
                onChange={(e) => setParams({...params, [k]: e.target.value})}
                className="px-1 py-0.5 border border-gray-300 rounded font-mono"/>
            </label>
          ))}
          <label className="flex flex-col">
            <span className="text-gray-500">productivity_multiplier</span>
            <input type="number" step="0.01" min="0.5" max="1.5"
              value={params.productivity_multiplier}
              onChange={(e) => setParams({...params, productivity_multiplier: parseFloat(e.target.value)})}
              className="px-1 py-0.5 border border-gray-300 rounded font-mono"/>
          </label>
          <button onClick={_rerun} disabled={loading}
            className="col-span-2 px-2 py-1 bg-rose-600 text-white rounded hover:bg-rose-500 disabled:opacity-50">
            {loading ? "분석 중..." : "재실행"}
          </button>
        </div>
      </details>

      {loading && (
        <div className="text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded p-2 flex items-center gap-1">
          <Loader2 size={12} className="animate-spin" /> 기존 데이터 분석 + 가상 합성 + 추론 진행 중...
        </div>
      )}
      {error && <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</div>}

      {hyp && (
        <>
          {/* 4-step section */}
          <_HypoStep n={1} title="기존 데이터 분석" color="sky">
            <div className="text-[10px] text-gray-600 mb-1">
              <code className="bg-sky-100 px-1 rounded">{hyp.base_grade}</code> 강종의 SD_PRODUCTIVITY_STD {hyp.existing_productivity_rows.length}건
            </div>
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-sky-200">
                <th className="text-left p-0.5">PROC_CD</th>
                <th className="text-left p-0.5">CUSTOMER_CD</th>
                <th className="text-right p-0.5">PRODUCTIVITY</th>
              </tr></thead>
              <tbody>
                {hyp.existing_productivity_rows.slice(0, 12).map((r, i) => (
                  <tr key={i} className="border-b border-sky-100">
                    <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                    <td className="p-0.5 font-mono text-gray-500">{String(r.CUSTOMER_CD)}</td>
                    <td className="p-0.5 font-mono text-right">{String(r.PRODUCTIVITY)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </_HypoStep>

          <_HypoStep n={2} title="가상 강종 합성" color="amber">
            <div className="text-[10px] text-gray-600 mb-1">
              <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> ×{hyp.productivity_multiplier}
            </div>
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-amber-200">
                <th className="text-left p-0.5">PROC_CD</th>
                <th className="text-right p-0.5">기존</th>
                <th className="text-right p-0.5">가상</th>
              </tr></thead>
              <tbody>
                {hyp.virtual_productivity_rows.slice(0, 12).map((r, i) => {
                  const orig = hyp.existing_productivity_rows[i];
                  return (
                    <tr key={i} className="border-b border-amber-100">
                      <td className="p-0.5 font-mono">{String(r.PROC_CD)}</td>
                      <td className="p-0.5 font-mono text-right text-gray-500">{String(orig?.PRODUCTIVITY ?? "?")}</td>
                      <td className="p-0.5 font-mono text-right text-amber-700 font-semibold">{String(r.PRODUCTIVITY)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </_HypoStep>

          <_HypoStep n={3} title="가상 주문 합성" color="violet">
            <div className="text-[10px] text-gray-600">
              <code className="bg-violet-100 px-1 rounded">{hyp.base_order_no}</code> 4 table 복제 →
              ORDER_QD.GRADE_CD = <code className="bg-amber-100 px-1 rounded">{hyp.new_grade}</code> 만 변경
            </div>
            <ul className="text-[10px] mt-1 space-y-0.5">
              {Object.entries(hyp.virtual_order_rows).map(([t, row]) => (
                <li key={t} className="font-mono">
                  <span className="text-violet-700">{t}</span>
                  <span className="text-gray-400 ml-1">
                    {t === "ORDER_QD" ? `GRADE_CD=${row.GRADE_CD}` :
                     t === "ORDER_OM" ? `width=${row.ORDER_WIDTH} len=${row.ORDER_LENGTH} wgt=${row.ORDER_WGT_LOW}~${row.ORDER_WGT_HIGH}` :
                     `${Object.keys(row).length} 필드 복제`}
                  </span>
                </li>
              ))}
            </ul>
          </_HypoStep>

          <_HypoStep n={4} title="Slab 결과 비교 (추론)" color="emerald">
            {hyp.baseline_slab ? (
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-2 text-[10px]">
                  <div className="border border-gray-300 rounded p-1.5">
                    <div className="text-gray-500">기존 ({hyp.base_grade})</div>
                    <div className="font-mono">
                      두께 {hyp.baseline_slab.slabThickness as number} · 폭 {hyp.baseline_slab.slabWidth as number}
                    </div>
                    <div className="font-mono text-emerald-700 font-semibold">
                      단중 {Number(hyp.baseline_slab.slabWgt).toFixed(1)}kg
                    </div>
                  </div>
                  <div className="border border-amber-300 bg-amber-50 rounded p-1.5">
                    <div className="text-amber-700">가상 ({hyp.new_grade})</div>
                    <div className="font-mono">
                      두께 {hyp.projected_slab?.slabThickness as number} · 폭 {hyp.projected_slab?.slabWidth as number}
                    </div>
                    <div className="font-mono text-amber-800 font-semibold">
                      단중 {Number(hyp.projected_slab?.slabWgt ?? 0).toFixed(1)}kg
                    </div>
                  </div>
                  <div className="border border-red-300 bg-red-50 rounded p-1.5">
                    <div className="text-red-700">DIFF</div>
                    <div className="font-mono">두께 0 · 폭 0 (강종 무관)</div>
                    <div className="font-mono text-red-800 font-semibold">
                      단중 {hyp.diff_summary.find((d) => d.field === "slabWgt")?.delta_pct ?? 0}%
                    </div>
                  </div>
                </div>
                {hyp.diff_summary.length > 0 && (
                  <details className="text-[10px]">
                    <summary className="cursor-pointer text-gray-600">전체 diff ({hyp.diff_summary.length}건)</summary>
                    <table className="w-full mt-1">
                      <thead><tr className="border-b border-gray-300">
                        <th className="text-left p-0.5">field</th>
                        <th className="text-right p-0.5">before</th>
                        <th className="text-right p-0.5">after</th>
                        <th className="text-right p-0.5">%</th>
                      </tr></thead>
                      <tbody>
                        {hyp.diff_summary.map((d) => (
                          <tr key={d.field} className="border-b border-gray-100">
                            <td className="p-0.5 font-mono">{d.field}</td>
                            <td className="p-0.5 font-mono text-right">{d.before.toFixed(2)}</td>
                            <td className="p-0.5 font-mono text-right text-emerald-700">{d.after.toFixed(2)}</td>
                            <td className="p-0.5 font-mono text-right text-red-700">{d.delta_pct}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}
              </div>
            ) : (
              <div className="text-[10px] text-gray-400">baseline 실행 결과 없음</div>
            )}
          </_HypoStep>

          {hyp.notes.length > 0 && (
            <details className="text-[10px] border border-gray-200 rounded">
              <summary className="px-2 py-1 bg-gray-50 cursor-pointer text-gray-600">분석 노트 ({hyp.notes.length})</summary>
              <ul className="p-2 space-y-1">
                {hyp.notes.map((n, i) => <li key={i} className="text-gray-700">· {n}</li>)}
              </ul>
            </details>
          )}
        </>
      )}
    </>
  );
}

function _HypoStep({ n, title, color, children }: {
  n: number; title: string; color: "sky"|"amber"|"violet"|"emerald"; children: React.ReactNode;
}) {
  const colorMap = {
    sky:     "border-sky-300 bg-sky-50/40",
    amber:   "border-amber-300 bg-amber-50/40",
    violet:  "border-violet-300 bg-violet-50/40",
    emerald: "border-emerald-300 bg-emerald-50/40",
  };
  const badge = {
    sky:     "bg-sky-600",
    amber:   "bg-amber-600",
    violet:  "bg-violet-600",
    emerald: "bg-emerald-600",
  };
  return (
    <div className={"border-2 rounded p-2 " + colorMap[color]}>
      <div className="flex items-center gap-2 mb-2">
        <span className={"text-[10px] w-5 h-5 rounded-full text-white font-bold flex items-center justify-center " + badge[color]}>{n}</span>
        <strong className="text-xs text-gray-800">{title}</strong>
      </div>
      {children}
    </div>
  );
}
