"use client";

/**
 * Gate III sim — executed_simulation.
 * Case 별 결과 + invariant 배지.
 */

import { Beaker, CheckCircle2, AlertTriangle, XCircle, MinusCircle } from "lucide-react";
import type { CaseResult, GateExecutedSimulation, InvariantStatus } from "@/lib/section3/multiturn";
import { ProvenanceRow } from "./ProvenanceBadge";

const INVARIANT_META: Record<
  InvariantStatus,
  { label: string; cls: string; icon: React.ReactNode }
> = {
  clean: {
    label: "clean (모두 PASS)",
    cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
    icon: <CheckCircle2 size={11} />,
  },
  fail_nondeterministic: {
    label: "fail_nondeterministic",
    cls: "bg-amber-50 text-amber-700 border-amber-200",
    icon: <AlertTriangle size={11} />,
  },
  fail_unexpected_throw: {
    label: "fail_unexpected_throw",
    cls: "bg-rose-50 text-rose-700 border-rose-200",
    icon: <XCircle size={11} />,
  },
  fail_return_type: {
    label: "fail_return_type",
    cls: "bg-rose-50 text-rose-700 border-rose-200",
    icon: <XCircle size={11} />,
  },
  error: {
    label: "error (실행 자체 실패)",
    cls: "bg-gray-100 text-gray-700 border-gray-300",
    icon: <MinusCircle size={11} />,
  },
};

const STATUS_META: Record<
  CaseResult["status"],
  { cls: string; icon: React.ReactNode }
> = {
  PASS: { cls: "text-emerald-600", icon: <CheckCircle2 size={11} /> },
  FAIL: { cls: "text-rose-600", icon: <XCircle size={11} /> },
  ERROR: { cls: "text-gray-500", icon: <MinusCircle size={11} /> },
  SKIPPED: { cls: "text-amber-600", icon: <AlertTriangle size={11} /> },
};

interface Props {
  payload: GateExecutedSimulation;
  turn_no: number;
}

export function GateExecutedSimulationCard({ payload, turn_no }: Props) {
  const inv = INVARIANT_META[payload.invariant_status];
  const counts: Record<CaseResult["status"], number> = {
    PASS: 0, FAIL: 0, ERROR: 0, SKIPPED: 0,
  };
  for (const r of payload.results) counts[r.status]++;

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Beaker size={14} className="text-primary" />
          <span className="text-sm font-semibold">Gate III — 시뮬레이션 실행</span>
          <span className="text-[10px] text-muted-foreground">turn {turn_no}</span>
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-[10px] font-medium ${inv.cls}`}
        >
          {inv.icon} {inv.label}
        </span>
      </div>

      {/* status counts */}
      <div className="flex gap-3 text-[11px] mb-3 px-2 py-1.5 bg-muted/40 rounded">
        {(["PASS", "FAIL", "ERROR", "SKIPPED"] as const).map((s) => (
          <div key={s} className={`flex items-center gap-1 ${STATUS_META[s].cls}`}>
            {STATUS_META[s].icon}
            <span className="font-mono font-semibold">{counts[s]}</span>
            <span className="text-muted-foreground/70">{s}</span>
          </div>
        ))}
      </div>

      {/* results table */}
      {payload.results.length === 0 ? (
        <p className="text-[11px] text-muted-foreground italic p-2 border border-dashed border-border rounded">
          case 결과 없음 — Gate II 의 fixture / Python 부재로 인한 실행 차단
        </p>
      ) : (
        <div className="overflow-auto max-h-72 border border-border rounded">
          <table className="text-[11px] w-full">
            <thead className="bg-muted sticky top-0">
              <tr>
                <th className="px-2 py-1 text-left font-medium">fixture_id</th>
                <th className="px-2 py-1 text-left font-medium">status</th>
                <th className="px-2 py-1 text-left font-medium">output</th>
                <th className="px-2 py-1 text-left font-medium">error</th>
              </tr>
            </thead>
            <tbody>
              {payload.results.map((r) => (
                <tr key={r.fixture_id} className="border-t border-border">
                  <td className="px-2 py-1 font-mono">{r.fixture_id}</td>
                  <td className="px-2 py-1">
                    <span className={`inline-flex items-center gap-1 font-mono font-medium ${STATUS_META[r.status].cls}`}>
                      {STATUS_META[r.status].icon}
                      {r.status}
                    </span>
                  </td>
                  <td className="px-2 py-1 font-mono text-muted-foreground truncate max-w-[200px]">
                    {r.output === null || r.output === undefined
                      ? "—"
                      : JSON.stringify(r.output).slice(0, 80)}
                  </td>
                  <td className="px-2 py-1 font-mono text-rose-600 truncate max-w-[200px]" title={r.error_message ?? ""}>
                    {r.error_message ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-3 pt-2 text-[11px] text-emerald-600 font-medium">
        ✓ 세션 완료
      </div>

      <ProvenanceRow sources={payload.sources} />
    </div>
  );
}
