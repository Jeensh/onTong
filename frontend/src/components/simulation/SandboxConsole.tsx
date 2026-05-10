"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Activity, ChevronDown, ChevronRight } from "lucide-react";
import type { CaseLogEntry, CaseType } from "@/lib/simulation/useAgent2Stream";

interface Props {
  cases: CaseLogEntry[];
  progress: { received: number; total: number };
  running: boolean;
}

const STATUS_GLYPH = {
  running: "○",
  done: "✓",
  failed: "✗",
} as const;

const STATUS_COLOR = {
  running: "text-primary",
  done: "text-emerald-600 dark:text-emerald-400",
  failed: "text-destructive",
} as const;

const TYPE_TONE: Record<CaseType, string> = {
  normal: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  boundary: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/30",
  error: "bg-red-500/10 text-red-700 dark:text-red-300 border-red-500/30",
  performance: "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/30",
};

const TYPE_LABEL: Record<CaseType, string> = {
  normal: "정상",
  boundary: "경계",
  error: "오류",
  performance: "성능",
};

// 사용자가 도메인 의미를 빠르게 파악할 수 있는 핵심 입력 필드 (slab-design.md 기준)
const KEY_ORDER_FIELDS: { key: string; label: string; unit?: string }[] = [
  { key: "stockCode", label: "재고코드" },
  { key: "orderWidth", label: "주문폭", unit: "mm" },
  { key: "orderLength", label: "주문길이", unit: "mm" },
  { key: "orderWgtLow", label: "주문단중하한", unit: "kg" },
  { key: "orderWgtHigh", label: "주문단중상한", unit: "kg" },
  { key: "pkgWgtLow", label: "포장단중하한", unit: "kg" },
  { key: "pkgWgtHigh", label: "포장단중상한", unit: "kg" },
  { key: "designPendQty", label: "설계대기량", unit: "kg" },
  { key: "designPendQtyLow", label: "설계대기량하한", unit: "kg" },
  { key: "designPendQtyHigh", label: "설계대기량상한", unit: "kg" },
  { key: "confirmedPlantCd", label: "확정통과공장(SM/HR/HRF/CR/ANL1/ANL2/GAL/CRF)" },
  { key: "workDue", label: "작업기한일" },
];

function fmt(v: unknown, unit?: string): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") {
    // confirmedPlantCd 처럼 공백 포함 문자열은 그대로 (8자리 가시화)
    if (unit) {
      const n = Number(v);
      if (!Number.isNaN(n)) return `${n.toLocaleString()}${unit ? " " + unit : ""}`;
    }
    return `"${v}"`;
  }
  if (typeof v === "number") return `${v.toLocaleString()}${unit ? " " + unit : ""}`;
  return JSON.stringify(v);
}

/** 입력에서 핵심 필드만 추출. 미설정 / null 은 생략. */
function summarizeOrder(input?: Record<string, unknown>): { label: string; raw: unknown; unit?: string }[] {
  if (!input) return [];
  const order = (input.order ?? input) as Record<string, unknown>;
  return KEY_ORDER_FIELDS
    .filter((f) => order[f.key] !== undefined && order[f.key] !== null)
    .map((f) => ({ label: f.label, raw: order[f.key], unit: f.unit }));
}

/** 결과 (actual_output) 에서 stage / error_code / 핵심 slab 필드 추출. */
function summarizeOutput(actual?: Record<string, unknown>, error?: Record<string, unknown> | null): {
  stage?: string; errorCode?: string; errorMessage?: string;
  slab?: Record<string, unknown>;
  sandboxError?: { type?: string; message?: string };
} {
  const out: ReturnType<typeof summarizeOutput> = {};
  if (error && typeof error === "object") {
    out.sandboxError = { type: error.type as string, message: error.message as string };
  }
  if (!actual) return out;
  const stage = actual.stage as string | undefined;
  if (stage) out.stage = stage;
  const errObj = actual.error as Record<string, unknown> | undefined;
  if (errObj) {
    out.errorCode = errObj.error_code as string | undefined;
    out.errorMessage = errObj.message as string | undefined;
  }
  const slab = actual.slab as Record<string, unknown> | undefined;
  if (slab) out.slab = slab;
  return out;
}

const KEY_SLAB_FIELDS = [
  "slabThickness", "secondWgtLow", "secondWgtHigh", "maxSplitCountUpper",
  "splitWgtLow", "splitWgtHigh", "slabCountInProgress", "slabWgtInProgress",
  "finalWidthLow", "finalWidthHigh", "finalLengthLow", "finalLengthHigh",
  "targetWidth", "targetLength",
];

export function SandboxConsole({ cases, progress, running }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [cases.length]);

  const pct = progress.total > 0 ? Math.round((progress.received / progress.total) * 100) : 0;

  // case_type 별 통과/실패 분포
  const stat = useMemo(() => {
    const m: Record<CaseType, { total: number; done: number; failed: number }> = {
      normal: { total: 0, done: 0, failed: 0 },
      boundary: { total: 0, done: 0, failed: 0 },
      error: { total: 0, done: 0, failed: 0 },
      performance: { total: 0, done: 0, failed: 0 },
    };
    for (const c of cases) {
      m[c.case_type].total += 1;
      if (c.status === "done") m[c.case_type].done += 1;
      else if (c.status === "failed") m[c.case_type].failed += 1;
    }
    return m;
  }, [cases]);

  const activeTypes = (Object.keys(stat) as CaseType[]).filter((t) => stat[t].total > 0);

  return (
    <div className="flex flex-col h-full overflow-hidden rounded-lg border border-border bg-card">
      <div className="border-b border-border bg-muted/40 px-4 py-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
            <Activity size={12} className="text-primary" />
            샌드박스 콘솔
          </h3>
          <div className="text-[11px] text-muted-foreground tabular-nums">
            {progress.received} / {progress.total} ({pct}%)
            {running && <span className="ml-2 text-primary">● 실행 중</span>}
          </div>
        </div>
        <div className="mt-2 h-1 w-full rounded bg-muted overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
        {/* case_type 별 분포 stat */}
        {activeTypes.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
            {activeTypes.map((t) => {
              const s = stat[t];
              return (
                <span
                  key={t}
                  className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 ${TYPE_TONE[t]}`}
                  title={`${TYPE_LABEL[t]} 케이스 ${s.total}건 — 통과 ${s.done}, 실패 ${s.failed}`}
                >
                  <span className="font-medium">{TYPE_LABEL[t]}</span>
                  <span className="tabular-nums">{s.done}/{s.total}</span>
                  {s.failed > 0 && <span className="text-destructive tabular-nums">✗{s.failed}</span>}
                </span>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2 font-mono text-[11px]">
        {cases.length === 0 && (
          <div className="text-muted-foreground/60 py-8 text-center">
            "실행" 버튼을 눌러 케이스 생성·실행 시작
          </div>
        )}
        {cases.map((c) => {
          const isOpen = expanded === c.case_id;
          const inputs = summarizeOrder(c.input_data);
          const out = summarizeOutput(c.actual_output, c.error);
          const expectedDg = (c.expected as { dg?: string } | undefined)?.dg;
          const hasDetail = inputs.length > 0 || out.stage || out.errorCode || out.sandboxError;
          return (
            <Fragment key={c.case_id}>
              <button
                type="button"
                onClick={() => hasDetail && setExpanded(isOpen ? null : c.case_id)}
                className={`w-full flex items-center gap-2 py-1 px-1 text-left border-b border-border/40 last:border-0 ${
                  hasDetail ? "hover:bg-muted/40 cursor-pointer" : "cursor-default"
                }`}
              >
                <span className="w-3 shrink-0 text-muted-foreground/50">
                  {hasDetail ? (isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />) : ""}
                </span>
                <span className={STATUS_COLOR[c.status]}>{STATUS_GLYPH[c.status]}</span>
                <span className="text-muted-foreground/60 w-14 shrink-0">{c.case_id}</span>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium shrink-0 border ${TYPE_TONE[c.case_type]}`}>
                  {TYPE_LABEL[c.case_type]}
                </span>
                <span className="flex-1 text-foreground/80 truncate">{c.description}</span>
                {c.elapsed_ms > 0 && (
                  <span className="text-muted-foreground/60 text-[9px] tabular-nums shrink-0">
                    {c.elapsed_ms}ms
                  </span>
                )}
              </button>
              {isOpen && hasDetail && (
                <div className="bg-muted/20 border-b border-border/40 px-3 py-2 text-[10px] space-y-2">
                  {/* 핵심 입력 필드 */}
                  {inputs.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                        📥 입력값 (이 케이스가 받은 주문 데이터)
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-3 gap-y-0.5">
                        {inputs.map((f) => (
                          <div key={f.label} className="flex items-baseline gap-2">
                            <span className="text-muted-foreground/70 shrink-0">{f.label}:</span>
                            <span className="text-foreground tabular-nums break-all">
                              {fmt(f.raw, f.unit)}
                            </span>
                          </div>
                        ))}
                      </div>
                      {expectedDg && (
                        <div className="mt-1 text-amber-700 dark:text-amber-300">
                          🎯 의도된 트리거: <b>{expectedDg}</b>
                          {!c.matches_expectation && c.status === "failed" && (
                            <span className="ml-2 text-destructive">— 실제로는 트리거 안 됨</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 결과 */}
                  <div className="border-t border-border/40 pt-1.5">
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">
                      📤 결과
                    </div>
                    {out.sandboxError ? (
                      <div className="text-destructive">
                        <b>샌드박스 오류:</b> {out.sandboxError.type} — {out.sandboxError.message}
                      </div>
                    ) : (
                      <div className="space-y-0.5">
                        <div>
                          <span className="text-muted-foreground/70">stage:</span>{" "}
                          <span className={out.errorCode ? "text-destructive" : "text-emerald-700 dark:text-emerald-400"}>
                            {out.stage ?? "ok"}
                          </span>
                          {out.errorCode && (
                            <span className="ml-2 font-medium text-red-600">
                              {out.errorCode}
                            </span>
                          )}
                        </div>
                        {out.errorMessage && (
                          <div className="text-muted-foreground/80 text-[10px] italic">
                            {out.errorMessage}
                          </div>
                        )}
                        {out.slab && (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-3 gap-y-0.5 mt-1">
                            {KEY_SLAB_FIELDS
                              .filter((k) => out.slab![k] !== null && out.slab![k] !== undefined)
                              .map((k) => (
                                <div key={k} className="flex items-baseline gap-2">
                                  <span className="text-muted-foreground/70 shrink-0">{k}:</span>
                                  <span className="text-foreground tabular-nums">
                                    {fmt(out.slab![k])}
                                  </span>
                                </div>
                              ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </Fragment>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
