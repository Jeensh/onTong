"use client";

/**
 * 가변 데이터 테이블 — list[dict] → auto column 추출 + 정렬.
 *
 * modeling response 의 process_locations / source_locations / direct_impact.methods /
 * indirect_impact.downstream_steps 등 list 형태 데이터를 그대로 받아 표시.
 */

import { useMemo, useState } from "react";
import { ArrowUpDown, ArrowDown, ArrowUp } from "lucide-react";

interface Props {
  rows: Array<Record<string, unknown>>;
  /** 표시 순서 우선 컬럼 (없으면 첫 row 의 key 순서). */
  preferredColumns?: string[];
  /** 숨길 컬럼 */
  hiddenColumns?: string[];
  /** 컬럼별 라벨 override */
  labels?: Record<string, string>;
  /** 컬럼별 셀 커스텀 렌더 */
  renderCell?: Record<string, (val: unknown, row: Record<string, unknown>) => React.ReactNode>;
  /** 행 클릭 핸들러 */
  onRowClick?: (row: Record<string, unknown>) => void;
  /** 최대 표시 행 (이후 "+N more") */
  maxRows?: number;
  /** 빈 상태 메시지 */
  emptyText?: string;
  /** 컴팩트 모드 (작은 폰트) */
  compact?: boolean;
}

const DEFAULT_LABELS: Record<string, string> = {
  step_number: "#",
  korean_name: "단계명",
  class_name: "Class",
  method_name: "Method",
  class: "Class",
  name: "Method",
  file_path: "파일",
  table_name: "테이블",
  standard_code: "기준",
  schema_name: "스키마",
  roles: "역할",
  case_id: "ID",
  case_type: "유형",
  description: "설명",
};

export function DataTable({
  rows,
  preferredColumns,
  hiddenColumns,
  labels,
  renderCell,
  onRowClick,
  maxRows = 50,
  emptyText = "데이터 없음",
  compact = false,
}: Props) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const columns = useMemo(() => {
    if (!rows?.length) return [] as string[];
    const all = new Set<string>();
    rows.forEach((r) => Object.keys(r).forEach((k) => all.add(k)));
    const hidden = new Set(hiddenColumns ?? []);
    const ordered: string[] = [];
    (preferredColumns ?? []).forEach((c) => {
      if (all.has(c) && !hidden.has(c)) {
        ordered.push(c);
        all.delete(c);
      }
    });
    Array.from(all)
      .filter((c) => !hidden.has(c))
      .forEach((c) => ordered.push(c));
    return ordered;
  }, [rows, preferredColumns, hiddenColumns]);

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (va === vb) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortKey, sortDir]);

  const visible = sortedRows.slice(0, maxRows);
  const hiddenCount = sortedRows.length - visible.length;

  if (!rows?.length) {
    return <div className="text-xs text-muted-foreground italic py-3">{emptyText}</div>;
  }

  const toggleSort = (col: string) => {
    if (sortKey === col) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(col);
      setSortDir("asc");
    }
  };

  const labelOf = (col: string) => labels?.[col] ?? DEFAULT_LABELS[col] ?? col;
  const textSize = compact ? "text-[10px]" : "text-[11px]";

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className={`w-full ${textSize}`}>
          <thead className="bg-muted/60">
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  onClick={() => toggleSort(c)}
                  className="px-3 py-2 text-left font-semibold cursor-pointer hover:bg-muted text-foreground select-none whitespace-nowrap"
                >
                  <span className="inline-flex items-center gap-1">
                    {labelOf(c)}
                    {sortKey === c ? (
                      sortDir === "asc" ? <ArrowUp size={10} /> : <ArrowDown size={10} />
                    ) : (
                      <ArrowUpDown size={10} className="opacity-30" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr
                key={i}
                onClick={() => onRowClick?.(row)}
                className={`border-t border-border/40 ${onRowClick ? "cursor-pointer hover:bg-muted/40" : ""} transition-colors`}
              >
                {columns.map((c) => (
                  <td key={c} className="px-3 py-2 align-top whitespace-nowrap">
                    {renderCell?.[c] ? renderCell[c](row[c], row) : formatCell(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hiddenCount > 0 && (
        <div className="px-3 py-1.5 bg-muted/30 text-[10px] text-muted-foreground text-center border-t border-border">
          ... 추가 {hiddenCount}개 행 숨김 (정렬해서 보기)
        </div>
      )}
    </div>
  );
}

function formatCell(v: unknown): React.ReactNode {
  if (v == null) return <span className="text-muted-foreground">—</span>;
  if (typeof v === "boolean") {
    return <span className={v ? "text-emerald-600" : "text-red-600"}>{v ? "✓" : "✗"}</span>;
  }
  if (typeof v === "number") return <span className="font-mono">{v}</span>;
  if (Array.isArray(v)) {
    return (
      <div className="flex flex-wrap gap-1">
        {v.slice(0, 4).map((x, i) => (
          <span key={i} className="rounded bg-muted px-1.5 py-0.5 text-[9px]">{String(x)}</span>
        ))}
        {v.length > 4 && <span className="text-muted-foreground text-[9px]">+{v.length - 4}</span>}
      </div>
    );
  }
  if (typeof v === "object") {
    return <code className="text-[10px] text-muted-foreground">{JSON.stringify(v).slice(0, 60)}</code>;
  }
  const s = String(v);
  return <span className={s.length > 60 ? "break-all" : ""}>{s}</span>;
}
