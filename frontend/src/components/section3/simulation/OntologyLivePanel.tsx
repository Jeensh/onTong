"use client";

/**
 * 활성 detected term 1건의 ontology API 응답 + 호출 trace 를 실시간 표시.
 *
 * - detected term 들이 바뀌면 첫 번째 term 의 fqn 로 /ontology_inspect 호출
 * - 5종 endpoint 의 fan-out 응답 + 호출 메타데이터 (URL · ms · status) 표시
 * - 우측 패널 위쪽 (DetectedTermsPanel 바로 아래) 에 surface
 */
import { useEffect, useState } from "react";
import { Activity, Database, AlertTriangle, Anchor, GitBranch } from "lucide-react";
import { simulationApi, type DetectedTermView, type OntologyInspectResponse } from "@/lib/section3/simulation";

interface Props {
  detectedTerms: DetectedTermView[];
}

export function OntologyLivePanel({ detectedTerms }: Props) {
  const [active, setActive] = useState<DetectedTermView | null>(null);
  const [data, setData] = useState<OntologyInspectResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // 첫 번째 detected term 으로 자동 활성화 (사용자가 다른 카드 클릭으로 변경 가능)
  useEffect(() => {
    if (detectedTerms.length === 0) {
      setActive(null); setData(null); return;
    }
    if (!active || !detectedTerms.find((t) => t.term_fqn === active.term_fqn)) {
      setActive(detectedTerms[0]);
    }
  }, [detectedTerms, active]);

  useEffect(() => {
    if (!active) { setData(null); return; }
    let cancelled = false;
    setLoading(true); setErr(null);
    simulationApi.ontologyInspect(active.term_fqn)
      .then((r) => { if (!cancelled) setData(r); })
      .catch((e) => { if (!cancelled) setErr(String(e?.message ?? e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [active]);

  if (detectedTerms.length === 0) return null;

  return (
    <div className="border-2 border-cyan-300 bg-gradient-to-br from-cyan-50 to-sky-50 rounded-lg shadow-md flex flex-col overflow-hidden">
      <div className="px-3 py-2 border-b border-cyan-200 bg-cyan-100/50 flex items-center gap-1.5">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-600"></span>
        </span>
        <Activity size={12} className="text-cyan-700" />
        <strong className="text-xs text-cyan-900">ontology 호출 (live)</strong>
        {data && (
          <span className="text-[10px] text-cyan-700 ml-auto">
            total {data.total_ms}ms · {data.calls.length} calls
          </span>
        )}
      </div>

      {/* 활성 term 선택 chip */}
      {detectedTerms.length > 1 && (
        <div className="px-3 py-1.5 border-b border-cyan-200 bg-white/50 flex flex-wrap gap-1">
          {detectedTerms.slice(0, 6).map((t) => (
            <button
              key={t.term_fqn}
              type="button"
              onClick={() => setActive(t)}
              className={`text-[10px] px-1.5 py-0.5 rounded border transition ${
                active?.term_fqn === t.term_fqn
                  ? "bg-cyan-600 text-white border-cyan-700"
                  : "bg-white text-cyan-800 border-cyan-200 hover:bg-cyan-100"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      <div className="p-2.5 space-y-2 text-[12px]">
        {loading && <div className="text-cyan-700 italic">호출 중…</div>}
        {err && <div className="text-red-700">에러: {err}</div>}
        {data && (
          <>
            {/* 호출 trace */}
            <details className="bg-white/80 rounded border border-cyan-200" open>
              <summary className="cursor-pointer px-2 py-1 text-cyan-900 font-semibold text-[10.5px] flex items-center gap-1">
                <Database size={11} /> 호출 trace ({data.calls.length})
              </summary>
              <ul className="px-2 pb-2 space-y-0.5 font-mono text-[10px]">
                {data.calls.map((c, i) => (
                  <li key={i} className="flex items-center gap-1.5">
                    <span className={`px-1 rounded ${
                      c.status === "ok" ? "bg-green-100 text-green-800" :
                      c.status === "empty" ? "bg-gray-100 text-gray-600" :
                      "bg-red-100 text-red-800"
                    }`}>{c.method}</span>
                    <span className="text-gray-800 truncate flex-1" title={c.url}>{c.url}</span>
                    <span className="text-gray-500">{c.elapsed_ms}ms</span>
                    {c.item_count !== null && (
                      <span className="text-cyan-700">×{c.item_count}</span>
                    )}
                  </li>
                ))}
              </ul>
            </details>

            {/* term 본문 */}
            {data.term && (
              <details className="bg-white/80 rounded border border-cyan-200" open>
                <summary className="cursor-pointer px-2 py-1 text-cyan-900 font-semibold text-[10.5px]">
                  term 응답
                </summary>
                <div className="px-2 pb-2">
                  <div className="text-[10.5px] mb-1">
                    <span className="font-semibold text-cyan-800">{(data.term.label as string) ?? ""}</span>
                    <code className="ml-1 text-[9px] text-gray-500">{data.term_fqn}</code>
                  </div>
                  {Array.isArray(data.term.aliases) && (data.term.aliases as string[]).length > 0 && (
                    <div className="mb-1">
                      {(data.term.aliases as string[]).map((a) => (
                        <code key={a} className="inline-block mr-1 mb-0.5 text-[9px] px-1 rounded bg-cyan-100 text-cyan-900">
                          {a}
                        </code>
                      ))}
                    </div>
                  )}
                  {(data.term.description as string) && (
                    <div className="text-[10px] text-gray-700 leading-relaxed">
                      {(data.term.description as string).slice(0, 300)}
                      {(data.term.description as string).length > 300 && "..."}
                    </div>
                  )}
                  <pre className="mt-1 text-[9px] text-gray-500 bg-gray-50 p-1 rounded overflow-auto">
                    {JSON.stringify(data.term, null, 2)}
                  </pre>
                </div>
              </details>
            )}

            {/* related actions */}
            {data.related_actions.length > 0 && (
              <details className="bg-white/80 rounded border border-cyan-200">
                <summary className="cursor-pointer px-2 py-1 text-cyan-900 font-semibold text-[10.5px] flex items-center gap-1">
                  <GitBranch size={11} /> 관련 action ({data.related_actions.length})
                </summary>
                <ul className="px-2 pb-2 space-y-1">
                  {data.related_actions.slice(0, 12).map((a) => (
                    <li key={a.fqn} className="border-l-2 border-cyan-300 pl-1.5">
                      <div className="flex items-baseline gap-1">
                        <span className="text-[9px] px-1 rounded bg-purple-100 text-purple-800">{a.kind}</span>
                        <span className="font-semibold text-[10.5px] text-purple-900">{a.label}</span>
                      </div>
                      <code className="text-[9px] text-gray-500 break-all">{a.fqn}</code>
                      {a.description && (
                        <div className="text-[10px] text-gray-700 mt-0.5">
                          {a.description.length > 160 ? a.description.slice(0, 160) + "..." : a.description}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* business rules */}
            {data.business_rules.length > 0 && (
              <details className="bg-white/80 rounded border border-cyan-200">
                <summary className="cursor-pointer px-2 py-1 text-cyan-900 font-semibold text-[10.5px] flex items-center gap-1">
                  <AlertTriangle size={11} /> business rules ({data.business_rules.length})
                </summary>
                <ul className="px-2 pb-2 space-y-1">
                  {data.business_rules.slice(0, 10).map((r) => (
                    <li key={r.fqn} className="border-l-2 border-amber-300 pl-1.5">
                      <div className="flex items-baseline gap-1">
                        <span className={`text-[9px] px-1 rounded ${
                          r.severity === "hard" ? "bg-red-100 text-red-800" :
                          "bg-amber-100 text-amber-800"
                        }`}>{r.severity}</span>
                        <code className="text-[9px] text-gray-700">{r.fqn}</code>
                      </div>
                      <div className="text-[10px] text-gray-800">{r.statement}</div>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {/* anchor bindings */}
            {data.anchor_bindings.length > 0 && (
              <details className="bg-white/80 rounded border border-cyan-200">
                <summary className="cursor-pointer px-2 py-1 text-cyan-900 font-semibold text-[10.5px] flex items-center gap-1">
                  <Anchor size={11} /> anchor bindings ({data.anchor_bindings.length})
                </summary>
                <ul className="px-2 pb-2 space-y-1">
                  {data.anchor_bindings.slice(0, 10).map((ab) => (
                    <li key={ab.anchor_id} className="border-l-2 border-emerald-300 pl-1.5">
                      <div className="flex items-baseline gap-1 flex-wrap">
                        <code className="text-[9px] text-emerald-800 font-semibold">{ab.anchor_id}</code>
                        {ab.line !== null && (
                          <span className="text-[9px] text-gray-500">L{ab.line}</span>
                        )}
                      </div>
                      <code className="text-[9px] text-gray-600 break-all block">{ab.method_fqn}</code>
                      <div className="text-[10px] text-gray-700">slot: <code>{ab.target_slot}</code></div>
                      {ab.anchor_locator && (
                        <code className="text-[9px] bg-gray-50 px-1 rounded text-gray-700">{ab.anchor_locator}</code>
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {data.related_actions.length === 0 && data.business_rules.length === 0 && data.anchor_bindings.length === 0 && (
              <div className="text-[10px] text-gray-500 italic px-2">
                이 term 은 직접적인 action·rule·anchor 매핑이 없습니다.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
