"use client";

// 변경 전/후 비교 테이블 — 스냅샷과 현재 파라미터 비교

import type { SlabSizeParams, SlabDesignResult } from "@/lib/simulation/types";

interface Props {
  before: SlabSizeParams | null;
  after: SlabSizeParams;
  beforeResult: SlabDesignResult | null;
  afterResult: SlabDesignResult | null;
}

interface CompareRow {
  label: string;
  unit: string;
  beforeVal: string | number | null;
  afterVal: string | number;
  changed: boolean;
  direction: "up" | "down" | "none";
}

function formatVal(val: number, key: string): string {
  if (key === "yield_rate") return (val * 100).toFixed(1) + "%";
  if (val > 1000) return val.toLocaleString();
  return String(val);
}

function buildRows(
  before: SlabSizeParams | null,
  after: SlabSizeParams,
  beforeRes: SlabDesignResult | null,
  afterRes: SlabDesignResult | null,
): CompareRow[] {
  const paramRows: CompareRow[] = [
    { key: "target_width", label: "목표폭", unit: "mm" },
    { key: "thickness", label: "두께", unit: "mm" },
    { key: "target_length", label: "목표길이", unit: "mm" },
    { key: "unit_weight", label: "단중", unit: "kg" },
    { key: "split_count", label: "분할수", unit: "개" },
    { key: "yield_rate", label: "실수율", unit: "" },
  ].map(({ key, label, unit }) => {
    const bv = before?.[key as keyof SlabSizeParams] as number ?? null;
    const av = after[key as keyof SlabSizeParams] as number;
    const changed = bv !== null && bv !== av;
    return {
      label,
      unit,
      beforeVal: bv !== null ? formatVal(bv, key) : null,
      afterVal: formatVal(av, key),
      changed,
      direction: changed && bv !== null ? (av > bv ? "up" : "down") : "none",
    };
  });

  // 요약 결과 행
  const summaryRows: CompareRow[] = [];
  if (beforeRes && afterRes) {
    const bS = beforeRes.summary;
    const aS = afterRes.summary;

    summaryRows.push({
      label: "1차 폭범위",
      unit: "mm",
      beforeVal: `${bS.width_range.lower}~${bS.width_range.upper}`,
      afterVal: `${aS.width_range.lower}~${aS.width_range.upper}`,
      changed: bS.width_range.lower !== aS.width_range.lower || bS.width_range.upper !== aS.width_range.upper,
      direction: "none",
    });
    summaryRows.push({
      label: "설계 가부",
      unit: "",
      beforeVal: beforeRes.feasible ? "✅ 가능" : "🔴 불가",
      afterVal: afterRes.feasible ? "✅ 가능" : "🔴 불가",
      changed: beforeRes.feasible !== afterRes.feasible,
      direction: "none",
    });
    summaryRows.push({
      label: "산정 매수",
      unit: "매",
      beforeVal: bS.slab_count,
      afterVal: aS.slab_count,
      changed: bS.slab_count !== aS.slab_count,
      direction: bS.slab_count !== aS.slab_count
        ? aS.slab_count > bS.slab_count ? "up" : "down"
        : "none",
    });
  }

  return [...paramRows, ...summaryRows];
}

export function SlabCompareTable({ before, after, beforeResult, afterResult }: Props) {
  if (!before) {
    return (
      <div className="text-center text-slate-500 text-xs py-4">
        [이 설정 저장] 버튼을 클릭하면 변경 전/후 비교가 표시됩니다
      </div>
    );
  }

  const rows = buildRows(before, after, beforeResult, afterResult);
  const changedCount = rows.filter((r) => r.changed).length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500 font-medium uppercase tracking-wide">
          변경 전/후 비교
        </span>
        {changedCount > 0 && (
          <span className="text-[10px] bg-indigo-900/60 text-indigo-300 px-2 py-0.5 rounded">
            {changedCount}개 변경됨
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left text-slate-500 font-medium py-1.5 pr-2">항목</th>
              <th className="text-right text-slate-500 font-medium py-1.5 px-2">변경 전</th>
              <th className="text-right text-slate-500 font-medium py-1.5 px-2">현재</th>
              <th className="text-right text-slate-500 font-medium py-1.5 pl-2">변화</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.label}
                className={`border-b border-slate-800/50 ${row.changed ? "bg-slate-800/30" : ""}`}
              >
                <td className="py-1.5 pr-2 text-slate-400">{row.label}</td>
                <td className="py-1.5 px-2 text-right text-slate-400 font-mono">
                  {row.beforeVal !== null
                    ? `${row.beforeVal}${row.unit ? " " + row.unit : ""}`
                    : "—"}
                </td>
                <td className={`py-1.5 px-2 text-right font-mono ${
                  row.changed ? "text-white font-semibold" : "text-slate-400"
                }`}>
                  {row.afterVal}{row.unit ? " " + row.unit : ""}
                </td>
                <td className="py-1.5 pl-2 text-right">
                  {row.changed ? (
                    <span className={row.direction === "up"
                      ? "text-green-400"
                      : row.direction === "down"
                      ? "text-red-400"
                      : "text-yellow-400"
                    }>
                      {row.direction === "up" ? "↑ 증가" : row.direction === "down" ? "↓ 감소" : "변경됨"}
                    </span>
                  ) : (
                    <span className="text-slate-600">변화 없음</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
