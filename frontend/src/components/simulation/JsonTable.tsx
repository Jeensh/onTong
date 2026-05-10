"use client";

/**
 * JSON 객체를 평탄화된 path → value 테이블로 표시.
 *
 * 예:
 *   { stage: "validate", validation: { passed: false, error_code: "DG004" } }
 * →
 *   field                  | value
 *   stage                  | validate
 *   validation.passed      | false
 *   validation.error_code  | DG004
 *
 * 디자인 토큰 (border / bg-card / muted) 만 사용. 다크모드 호환.
 */

import { useMemo } from "react";

interface Props {
  data: unknown;
  /** 테이블 위에 작게 표시할 라벨 (예: "expected" / "actual"). 비워두면 미표시. */
  caption?: string;
  /** 깊이 제한 (기본 4). 너무 깊으면 JSON 그대로 표시. */
  maxDepth?: number;
  /** 빈 데이터일 때 출력할 텍스트. */
  emptyText?: string;
  /** 행 최대 표시 개수 (초과 시 "+N more" 표시). 기본 30. */
  maxRows?: number;
  /** 값 셀 최대 길이 (초과 시 truncate). 기본 200자. */
  maxValueLen?: number;
}

interface Row {
  path: string;
  value: unknown;
  /** 원시값 / 짧은 배열 등 → "scalar". 긴 객체 등 → "json". */
  kind: "scalar" | "json" | "null" | "bool";
}

function flatten(d: unknown, prefix: string, depth: number, max: number, out: Row[]): void {
  if (d === null || d === undefined) {
    out.push({ path: prefix || "(root)", value: d, kind: "null" });
    return;
  }
  if (typeof d === "boolean") {
    out.push({ path: prefix || "(root)", value: d, kind: "bool" });
    return;
  }
  if (typeof d !== "object") {
    out.push({ path: prefix || "(root)", value: d, kind: "scalar" });
    return;
  }
  if (depth >= max) {
    out.push({ path: prefix || "(root)", value: d, kind: "json" });
    return;
  }
  if (Array.isArray(d)) {
    if (d.length === 0) {
      out.push({ path: prefix || "(root)", value: "[]", kind: "scalar" });
      return;
    }
    // 짧은 array of primitives → 한 행으로
    const allPrim = d.every((x) => x === null || ["string", "number", "boolean"].includes(typeof x));
    if (allPrim && d.length <= 8) {
      out.push({ path: prefix || "(root)", value: d.join(", "), kind: "scalar" });
      return;
    }
    d.forEach((v, i) => flatten(v, `${prefix}[${i}]`, depth + 1, max, out));
    return;
  }
  // dict
  const obj = d as Record<string, unknown>;
  const keys = Object.keys(obj);
  if (keys.length === 0) {
    out.push({ path: prefix || "(root)", value: "{}", kind: "scalar" });
    return;
  }
  for (const k of keys) {
    const sub = prefix ? `${prefix}.${k}` : k;
    flatten(obj[k], sub, depth + 1, max, out);
  }
}

function valueCell(row: Row, maxLen: number): { text: string; tone: string } {
  if (row.kind === "null") {
    return { text: row.value === null ? "null" : "undefined", tone: "text-muted-foreground italic" };
  }
  if (row.kind === "bool") {
    const b = row.value as boolean;
    return {
      text: String(b),
      tone: b ? "text-emerald-700 dark:text-emerald-300" : "text-red-700 dark:text-red-300",
    };
  }
  if (row.kind === "json") {
    let txt: string;
    try {
      txt = JSON.stringify(row.value);
    } catch {
      txt = String(row.value);
    }
    const sliced = txt.length > maxLen ? `${txt.slice(0, maxLen)}…` : txt;
    return { text: sliced, tone: "text-muted-foreground" };
  }
  // scalar
  const txt = typeof row.value === "string" ? row.value : String(row.value);
  const sliced = txt.length > maxLen ? `${txt.slice(0, maxLen)}…` : txt;
  return { text: sliced, tone: "text-foreground" };
}

export function JsonTable({
  data,
  caption,
  maxDepth = 4,
  emptyText = "(빈 데이터)",
  maxRows = 30,
  maxValueLen = 200,
}: Props) {
  const rows = useMemo(() => {
    const out: Row[] = [];
    flatten(data, "", 0, maxDepth, out);
    return out;
  }, [data, maxDepth]);

  if (rows.length === 0) {
    return (
      <div className="text-[11px] text-muted-foreground italic px-2 py-1">{emptyText}</div>
    );
  }

  const visible = rows.slice(0, maxRows);
  const hidden = rows.length - visible.length;

  return (
    <div className="rounded-md border border-border overflow-hidden bg-background">
      {caption && (
        <div className="border-b border-border bg-muted/40 px-2 py-1 text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          {caption}
        </div>
      )}
      <table className="w-full text-[11px]">
        <thead className="bg-muted/25 text-muted-foreground">
          <tr>
            <th className="text-left font-medium px-2 py-1 w-[42%] border-b border-border">필드</th>
            <th className="text-left font-medium px-2 py-1 border-b border-border">값</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row, i) => {
            const cell = valueCell(row, maxValueLen);
            return (
              <tr
                key={`${row.path}-${i}`}
                className="border-t border-border/50 hover:bg-muted/30"
              >
                <td className="px-2 py-1 font-mono text-[10px] text-muted-foreground align-top break-all">
                  {row.path}
                </td>
                <td className={`px-2 py-1 font-mono align-top break-all ${cell.tone}`}>
                  {cell.text}
                </td>
              </tr>
            );
          })}
          {hidden > 0 && (
            <tr>
              <td colSpan={2} className="px-2 py-1 text-[10px] text-muted-foreground italic text-center bg-muted/20 border-t border-border/50">
                +{hidden} 항목 더 있음
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
