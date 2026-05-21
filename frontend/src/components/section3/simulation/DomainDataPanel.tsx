"use client";

/**
 * 도메인 데이터 패널 — slab-design-real_v2 의 H2 schema + seed 를 surface.
 *
 * 우측 패널 하단에 표시. category 별 (std/order/result/history) 로 묶어
 * table 목록 → click → schema + sample rows.
 */
import { useEffect, useState } from "react";
import { Database, Loader2, X } from "lucide-react";
import { simulationApi, type DomainTableView, type DomainTableDetail } from "@/lib/section3/simulation";

const CATEGORY_COLOR: Record<string, string> = {
  std:     "border-amber-300 bg-amber-50 text-amber-800",
  order:   "border-emerald-300 bg-emerald-50 text-emerald-800",
  result:  "border-sky-300 bg-sky-50 text-sky-800",
  history: "border-violet-300 bg-violet-50 text-violet-800",
  other:   "border-gray-300 bg-gray-50 text-gray-700",
};
const CATEGORY_LABEL: Record<string, string> = {
  std: "기준 데이터", order: "주문", result: "슬랩 결과", history: "이력", other: "기타",
};

export function DomainDataPanel() {
  const [tables, setTables] = useState<DomainTableView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [detail, setDetail] = useState<DomainTableDetail | null>(null);

  useEffect(() => {
    simulationApi.listTables()
      .then(setTables)
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!picked) { setDetail(null); return; }
    simulationApi.getTable(picked)
      .then(setDetail)
      .catch((e) => setError(String(e)));
  }, [picked]);

  if (error) {
    return (
      <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
        도메인 데이터 로드 실패: {error}
      </div>
    );
  }
  if (!tables) {
    return (
      <div className="text-xs text-gray-500 flex items-center gap-1">
        <Loader2 size={12} className="animate-spin" /> 도메인 데이터 로드 중...
      </div>
    );
  }

  const grouped: Record<string, DomainTableView[]> = {};
  for (const t of tables) (grouped[t.category] ||= []).push(t);

  return (
    <>
      <div className="flex items-center gap-2 border-t border-gray-200 pt-2 mt-2">
        <Database size={14} className="text-emerald-600" />
        <h3 className="text-sm font-semibold text-gray-700">slab-design 도메인 데이터</h3>
        <span className="text-[10px] text-gray-400 ml-auto">{tables.length} tables</span>
      </div>

      <div className="space-y-2 max-h-80 overflow-y-auto">
        {Object.entries(grouped).map(([cat, ts]) => (
          <div key={cat}>
            <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-1">
              {CATEGORY_LABEL[cat] ?? cat} ({ts.length})
            </div>
            <div className="flex flex-wrap gap-1">
              {ts.sort((a, b) => a.table_name.localeCompare(b.table_name)).map((t) => (
                <button
                  key={t.table_name}
                  onClick={() => setPicked(t.table_name)}
                  className={
                    "text-[10px] px-1.5 py-1 rounded border font-mono " +
                    CATEGORY_COLOR[t.category] +
                    (picked === t.table_name ? " ring-1 ring-emerald-500" : "")
                  }
                  title={`${t.jpa_class} · cols ${t.column_count} · rows ${t.row_count}`}
                >
                  {t.table_name} <span className="text-gray-400">·{t.row_count}</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {detail && (
        <div className="border border-gray-300 rounded mt-2">
          <div className="flex items-center gap-2 px-2 py-1.5 bg-gray-50 border-b border-gray-200">
            <code className="text-xs font-semibold text-gray-800">{detail.table_name}</code>
            <span className="text-[10px] text-gray-500">{detail.jpa_class}</span>
            <button
              onClick={() => setPicked(null)}
              className="ml-auto text-gray-400 hover:text-gray-700"
              title="close"
            >
              <X size={12} />
            </button>
          </div>
          <div className="p-2 space-y-2 max-h-72 overflow-y-auto text-[10px]">
            {/* schema */}
            <div>
              <div className="text-gray-500 mb-1">schema ({detail.columns.length} cols)</div>
              <ul className="space-y-0.5">
                {detail.columns.map((c) => (
                  <li key={c.name} className="font-mono">
                    {c.is_pk && <span className="text-amber-700 mr-1">★</span>}
                    <span className="text-gray-900">{c.name}</span>
                    <span className="text-gray-400 ml-1">
                      {c.type_hint}
                      {c.length ? `(${c.length})` : ""}
                      {c.precision ? `(${c.precision},${c.scale ?? 0})` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* rows */}
            {detail.rows.length > 0 ? (
              <div>
                <div className="text-gray-500 mb-1">
                  seed rows ({detail.rows.length}{detail.row_count_total > detail.rows.length ? ` / ${detail.row_count_total}` : ""})
                </div>
                <div className="overflow-x-auto">
                  <table className="text-[9px] border-collapse">
                    <thead>
                      <tr className="border-b border-gray-300 bg-gray-50">
                        {detail.columns.slice(0, 8).map((c) => (
                          <th key={c.name} className="px-1.5 py-0.5 text-left font-mono text-gray-600">
                            {c.name}
                          </th>
                        ))}
                        {detail.columns.length > 8 && <th className="px-1 text-gray-400">+{detail.columns.length - 8}</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {detail.rows.slice(0, 6).map((row, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          {detail.columns.slice(0, 8).map((c) => (
                            <td key={c.name} className="px-1.5 py-0.5 font-mono text-gray-800">
                              {row[c.name] === null || row[c.name] === undefined
                                ? <span className="text-gray-300">null</span>
                                : String(row[c.name])}
                            </td>
                          ))}
                          {detail.columns.length > 8 && <td className="text-gray-400">…</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {detail.rows.length > 6 && (
                  <div className="text-gray-400 mt-1">+{detail.rows.length - 6} more rows</div>
                )}
              </div>
            ) : (
              <div className="text-gray-400 italic">seed row 없음 (런타임에 생성)</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
