"use client";

/**
 * Excel 추출 다이얼로그 — 현업 자율화 핵심 UX.
 *
 * 1) /export/preview/:sid 호출 → backend 가 마지막 executed payload 에서 추출 가능한
 *    rows + columns 자동 식별 (intent / kind 별), ontology business_terms 에서 한국어 라벨 lookup.
 * 2) 사용자가 multi-select 로 추출할 컬럼 고르기 (전체 선택 / 해제 가능).
 * 3) /export/xlsx POST → 컬럼명 한국어\n영어 2줄 표기 xlsx 다운로드.
 */
import { useEffect, useState } from "react";
import { X, Download, FileSpreadsheet, Check } from "lucide-react";

interface PreviewColumn {
  key: string;
  label_ko: string | null;
  sample: unknown;
}

interface PreviewResponse {
  intent: string | null;
  kind: string;
  rows: Record<string, unknown>[];
  columns: PreviewColumn[];
  row_count: number;
}

interface Props {
  sessionId: string;
  payload: Record<string, unknown>;
  intent: string;
  onClose: () => void;
}

export function ExcelExportDialog({ sessionId, intent, onClose }: Props) {
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [err, setErr] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    fetch(`/api/section3/simulation/export/preview/${sessionId}`)
      .then((r) => r.json())
      .then((d: PreviewResponse) => {
        setData(d);
        // default — 모든 컬럼 선택
        setPicked(new Set(d.columns.map((c) => c.key)));
      })
      .catch((e) => setErr(String(e)));
  }, [sessionId]);

  function toggle(k: string) {
    setPicked((s) => {
      const n = new Set(s);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  }

  function pickAll() {
    if (!data) return;
    setPicked(new Set(data.columns.map((c) => c.key)));
  }

  function pickNone() {
    setPicked(new Set());
  }

  async function download() {
    if (!data || picked.size === 0) return;
    setDownloading(true);
    setErr(null);
    try {
      const fields = data.columns
        .filter((c) => picked.has(c.key))
        .map((c) => ({ key: c.key, label_ko: c.label_ko, sample: c.sample }));
      const rows = data.rows.map((r) => {
        const out: Record<string, unknown> = {};
        for (const f of fields) out[f.key] = r[f.key];
        return out;
      });
      const r = await fetch("/api/section3/simulation/export/xlsx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          fields,
          rows,
        }),
      });
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        throw new Error(`HTTP ${r.status}: ${t}`);
      }
      const blob = await r.blob();
      const cd = r.headers.get("Content-Disposition") || "";
      const m = cd.match(/filename="([^"]+)"/);
      const fname = m ? m[1] : `sim_${intent}_${Date.now()}.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-2xl w-full max-w-3xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <FileSpreadsheet size={18} className="text-emerald-600" />
          <h3 className="text-base font-semibold text-gray-900">Excel 추출 — 항목 선택</h3>
          {data && (
            <span className="text-xs text-gray-500">
              · {data.row_count}행 / {data.columns.length}컬럼 (intent={data.intent ?? intent})
            </span>
          )}
          <button onClick={onClose} className="ml-auto text-gray-400 hover:text-gray-700">
            <X size={18} />
          </button>
        </header>

        {!data && !err && (
          <div className="p-6 text-center text-sm text-gray-500">불러오는 중…</div>
        )}
        {err && (
          <div className="p-4 text-sm text-red-700 bg-red-50 m-3 rounded border border-red-200">
            {err}
          </div>
        )}

        {data && (
          <>
            <div className="px-4 py-2 border-b border-gray-100 bg-gray-50 flex items-center gap-2 text-xs">
              <span className="text-gray-600">
                추출할 컬럼 ({picked.size}/{data.columns.length})
              </span>
              <button onClick={pickAll} className="ml-auto px-2 py-1 rounded border border-gray-300 hover:bg-white">
                전체 선택
              </button>
              <button onClick={pickNone} className="px-2 py-1 rounded border border-gray-300 hover:bg-white">
                전체 해제
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-1">
              {data.columns.length === 0 && (
                <div className="text-sm text-gray-500 text-center py-6">
                  이 결과에는 추출 가능한 컬럼이 없습니다.
                </div>
              )}
              {data.columns.map((c) => {
                const isPicked = picked.has(c.key);
                return (
                  <label
                    key={c.key}
                    className={
                      "flex items-center gap-2 px-2 py-1.5 rounded border cursor-pointer transition " +
                      (isPicked
                        ? "border-emerald-300 bg-emerald-50 hover:bg-emerald-100"
                        : "border-gray-200 bg-white hover:bg-gray-50")
                    }
                  >
                    <input
                      type="checkbox"
                      checked={isPicked}
                      onChange={() => toggle(c.key)}
                      className="accent-emerald-600"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm font-semibold text-gray-900">
                          {c.label_ko ?? "(ontology 미등록)"}
                        </span>
                        <code className="text-[10.5px] text-gray-500 font-mono">{c.key}</code>
                      </div>
                      {c.sample !== null && c.sample !== undefined && (
                        <div className="text-[10.5px] text-gray-500 truncate">
                          샘플: <code className="text-gray-700">{String(c.sample).slice(0, 80)}</code>
                        </div>
                      )}
                    </div>
                    {isPicked && <Check size={14} className="text-emerald-600" />}
                  </label>
                );
              })}
            </div>

            {/* 미리보기 — 상위 3 row */}
            {data.rows.length > 0 && (
              <div className="px-3 py-2 border-t border-gray-200 bg-gray-50 text-[10.5px] max-h-32 overflow-auto">
                <div className="text-gray-600 mb-1">데이터 미리보기 (상위 {Math.min(3, data.rows.length)}행)</div>
                <table className="w-full">
                  <thead>
                    <tr>
                      {data.columns.filter((c) => picked.has(c.key)).slice(0, 6).map((c) => (
                        <th key={c.key} className="text-left text-gray-700 pr-3 border-b border-gray-300 pb-1">
                          {c.label_ko ?? c.key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.slice(0, 3).map((r, i) => (
                      <tr key={i}>
                        {data.columns.filter((c) => picked.has(c.key)).slice(0, 6).map((c) => (
                          <td key={c.key} className="pr-3 py-0.5 text-gray-800 font-mono">
                            {String(r[c.key] ?? "").slice(0, 30)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        <footer className="px-4 py-3 border-t border-gray-200 flex items-center justify-end gap-2 bg-gray-50">
          <button onClick={onClose} className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-white">
            취소
          </button>
          <button
            onClick={download}
            disabled={!data || picked.size === 0 || downloading}
            className="px-4 py-1.5 text-sm rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 flex items-center gap-1"
          >
            <Download size={14} />
            {downloading ? "다운로드 중…" : `xlsx 다운로드 (${picked.size}컬럼)`}
          </button>
        </footer>
      </div>
    </div>
  );
}
