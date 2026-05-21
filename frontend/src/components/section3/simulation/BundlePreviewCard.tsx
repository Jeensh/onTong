"use client";

/** bundle_prepared 게이트 카드 — Java 원본 + Python 변환 + fixture 표. */
import { Check, Ban } from "lucide-react";

interface Props {
  payload: Record<string, unknown>;
  onConfirm: () => void;
  onAbort: () => void;
  busy: boolean;
}

export function BundlePreviewCard({ payload, onConfirm, onAbort, busy }: Props) {
  const error = payload.error as string | undefined;
  const java = (payload.java_source as string | undefined) ?? "";
  const python = (payload.python_source as string | undefined) ?? "";
  const fixtures = (payload.fixtures as Array<Record<string, unknown>> | undefined) ?? [];
  const confidence = (payload.confidence as number | undefined) ?? 0;
  const idiomDiffs = (payload.idiom_diffs as Array<Record<string, unknown>> | undefined) ?? [];

  return (
    <div className="border border-gray-300 rounded-lg bg-white p-4 space-y-3 overflow-y-auto">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">Bundle 합성 (2/3)</h3>
        <span className="text-xs text-gray-400">confidence {confidence.toFixed(2)}</span>
      </header>

      {error && (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          ⚠ {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div className="border border-gray-200 rounded">
          <div className="px-2 py-1 bg-gray-50 border-b border-gray-200 text-[11px] text-gray-600">
            Java 원본 ({java.length} chars)
          </div>
          <pre className="p-2 text-[10px] bg-white max-h-64 overflow-auto text-gray-800">
            {java || "(빈 결과)"}
          </pre>
        </div>
        <div className="border border-emerald-300 rounded">
          <div className="px-2 py-1 bg-emerald-50 border-b border-emerald-200 text-[11px] text-emerald-800">
            Python 변환 ({python.length} chars)
          </div>
          <pre className="p-2 text-[10px] bg-white max-h-64 overflow-auto text-emerald-900">
            {python || "(빈 결과 — sim_v2 transpile 실패)"}
          </pre>
        </div>
      </div>

      {idiomDiffs.length > 0 && (
        <details className="text-[11px]">
          <summary className="cursor-pointer text-gray-600">idiom 변환 {idiomDiffs.length}건</summary>
          <ul className="mt-2 space-y-1">
            {idiomDiffs.slice(0, 10).map((d, i) => (
              <li key={i} className="text-gray-700">
                <code className="bg-amber-50 px-1 rounded">{String(d.idiom_name)}</code> ·{" "}
                {String(d.summary ?? "")}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div>
        <div className="text-[11px] text-gray-600 mb-1">Order fixture ({fixtures.length}건)</div>
        {fixtures.length === 0 && (
          <div className="text-[11px] text-gray-400 border border-gray-200 rounded p-2">(빈 결과)</div>
        )}
        <div className="max-h-32 overflow-auto">
          {fixtures.slice(0, 3).map((f, i) => (
            <pre key={i} className="text-[10px] bg-gray-50 border border-gray-200 rounded p-2 mb-1 overflow-x-auto">
              {JSON.stringify(f, null, 2).slice(0, 500)}
            </pre>
          ))}
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-200">
        <button onClick={onAbort} disabled={busy} className="px-3 py-1.5 text-xs rounded border border-gray-300 hover:bg-gray-50">
          <Ban size={11} className="inline mr-1" /> 중단
        </button>
        <button
          onClick={onConfirm} disabled={busy}
          className="px-3 py-1.5 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          <Check size={11} className="inline mr-1" /> 이 bundle 로 실행
        </button>
      </div>
    </div>
  );
}
