"use client";

/**
 * Gate III impact — executed_impact.
 * Affected methods (caller graph) + sim_v2 findings + confidence.
 */

import { useState } from "react";
import { Flame, GitBranch, Info, AlertTriangle, XCircle, FileCode2 } from "lucide-react";
import type { Finding, GateExecutedImpact } from "@/lib/section3/multiturn";
import { ProvenanceRow } from "./ProvenanceBadge";
import { CodeViewerDrawer } from "./CodeViewerDrawer";

const FINDING_META: Record<
  Finding["severity"],
  { cls: string; icon: React.ReactNode }
> = {
  info:  { cls: "text-blue-600", icon: <Info size={11} /> },
  warn:  { cls: "text-amber-600", icon: <AlertTriangle size={11} /> },
  error: { cls: "text-rose-600", icon: <XCircle size={11} /> },
};

interface Props {
  payload: GateExecutedImpact;
  turn_no: number;
  repoId: string;
}

export function GateExecutedImpactCard({ payload, turn_no, repoId }: Props) {
  const [viewing, setViewing] = useState<string | null>(null);
  const conf = payload.confidence;
  const confColor =
    conf >= 0.7 ? "bg-emerald-500" :
    conf >= 0.4 ? "bg-amber-500" : "bg-rose-500";

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Flame size={14} className="text-primary" />
          <span className="text-sm font-semibold">Gate III — 영향도 검토</span>
          <span className="text-[10px] text-muted-foreground">turn {turn_no}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-24 h-2 bg-muted rounded overflow-hidden">
            <div
              className={`h-full ${confColor}`}
              style={{ width: `${Math.round(conf * 100)}%` }}
            />
          </div>
          <span className="text-[11px] font-semibold">{Math.round(conf * 100)}%</span>
        </div>
      </div>

      {/* affected methods */}
      <div className="mb-3">
        <div className="flex items-center gap-1 text-[11px] font-medium text-muted-foreground mb-1.5">
          <GitBranch size={11} />
          영향 받는 메서드 ({payload.affected_methods.length})
        </div>
        {payload.affected_methods.length === 0 ? (
          <div className="text-[11px] text-muted-foreground italic p-2 border border-dashed border-border rounded">
            caller_graph 데이터 없음 — Section 2 API 미연결 (Phase 4 swap 후 surface).
            Q5 비전: "빠진 내용은 빠진대로".
          </div>
        ) : (
          <div className="overflow-auto max-h-48 border border-border rounded">
            <table className="text-[11px] w-full">
              <thead className="bg-muted sticky top-0">
                <tr>
                  <th className="px-2 py-1 text-left font-medium">fqn</th>
                  <th className="px-2 py-1 text-left font-medium w-16">distance</th>
                  <th className="px-2 py-1 text-left font-medium">via</th>
                  <th className="px-2 py-1 text-left font-medium">match</th>
                  <th className="px-2 py-1 text-left font-medium w-14">신뢰</th>
                </tr>
              </thead>
              <tbody>
                {payload.affected_methods.map((m) => (
                  <tr key={m.fqn} className="border-t border-border hover:bg-muted/30">
                    <td className="px-2 py-1 font-mono max-w-[300px]" title={m.fqn}>
                      <button
                        type="button"
                        onClick={() => setViewing(m.fqn)}
                        className="text-left truncate inline-flex items-center gap-1 text-primary hover:underline w-full"
                      >
                        <FileCode2 size={10} className="shrink-0" />
                        <span className="truncate">{m.fqn}</span>
                      </button>
                    </td>
                    <td className="px-2 py-1 font-mono text-center">{m.distance}</td>
                    <td className="px-2 py-1 font-mono text-muted-foreground">{m.via}</td>
                    <td className="px-2 py-1 font-mono text-muted-foreground">
                      {m.match_kind ?? "—"}
                    </td>
                    <td className="px-2 py-1 font-mono">
                      {m.strength != null ? Math.round(m.strength * 100) + "%" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* findings */}
      <div className="mb-3">
        <div className="text-[11px] font-medium text-muted-foreground mb-1.5">
          sim_v2 진단 ({payload.sim_v2_findings.length})
        </div>
        {payload.sim_v2_findings.length === 0 ? (
          <p className="text-[11px] text-muted-foreground italic p-2">
            진단 결과 없음
          </p>
        ) : (
          <ul className="space-y-1">
            {payload.sim_v2_findings.map((f, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-[11px] px-2 py-1.5 bg-muted/30 rounded"
              >
                <span className={`mt-0.5 ${FINDING_META[f.severity].cls}`}>
                  {FINDING_META[f.severity].icon}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-mono font-semibold uppercase text-[9px] ${FINDING_META[f.severity].cls}`}>
                      {f.severity}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {f.kind}
                    </span>
                  </div>
                  <div className="text-muted-foreground mt-0.5">{f.message}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-3 pt-2 text-[11px] text-emerald-600 font-medium">
        ✓ 세션 완료
      </div>

      <ProvenanceRow sources={payload.sources} />

      {viewing && (
        <CodeViewerDrawer
          open
          fqn={viewing}
          repoId={repoId}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  );
}
