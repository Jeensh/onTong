"use client";

/** executed 게이트 카드 — intent 별 차별 레이아웃. */
import { RotateCcw, Plus } from "lucide-react";

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

      {!error && intent === "simulate" && <_SimulateView payload={payload} />}
      {!error && intent === "impact" && <_ImpactView payload={payload} />}
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

  return (
    <>
      <div className="text-[11px] text-gray-700">
        영향받는 method {methods.length}건 · sim_v2 findings {findings.length}건 · confidence {confidence.toFixed(2)}
      </div>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left p-1.5 text-gray-600">method_fqn</th>
              <th className="text-left p-1.5 text-gray-600">via</th>
              <th className="text-right p-1.5 text-gray-600">score</th>
            </tr>
          </thead>
          <tbody>
            {methods.slice(0, 20).map((m, i) => (
              <tr key={i} className="border-b border-gray-100">
                <td className="p-1.5 font-mono text-gray-800 truncate max-w-[280px]" title={String(m.method_fqn)}>
                  {String(m.method_fqn)}
                </td>
                <td className="p-1.5 text-gray-500">{String(m.via ?? "—")}</td>
                <td className="p-1.5 text-right text-gray-700">{Number(m.score ?? 0).toFixed(2)}</td>
              </tr>
            ))}
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
