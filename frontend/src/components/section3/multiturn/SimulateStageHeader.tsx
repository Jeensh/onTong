"use client";

/**
 * Phase 19 — Stage 3 (시뮬레이션) summary header.
 *
 * 사용자 vision: 영역 선택 / fixture source / 실행 상태 / 결과 한눈에. MVP 는
 * 기존 GateBundleCard + GateExecuted* 카드 위에 1줄 요약 헤더로 surface.
 * 후속 (Phase 19b) 에서 영역 zoom 확장 + fixture 3-source 토글.
 */

import { FlaskConical, Activity, FileSpreadsheet, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import type { DecisionView, GatePayload } from "@/lib/section3/multiturn";

interface Props {
  /** Stage 3 decisions (bundle_prepared + executed_*). */
  decisions: DecisionView[];
  /** Stage 2 에서 선택된 primary code_method_fqn (정보 surface). */
  primaryMethodFqn?: string | null;
}

export function SimulateStageHeader({ decisions, primaryMethodFqn }: Props) {
  const bundle = decisions.find((d) => d.gate_kind === "bundle_prepared");
  const executed = decisions.find((d) =>
    d.gate_kind.startsWith("executed_"),
  );

  const fixtureCount = bundle
    ? (bundle.payload as { fixtures?: unknown[] }).fixtures?.length ?? 0
    : null;

  let status: "pending" | "ready" | "running" | "done" = "pending";
  let resultSummary: string | null = null;
  let resultOk: boolean | null = null;

  if (executed) {
    status = "done";
    const payload = executed.payload as GatePayload;
    if (payload.kind === "executed_simulation") {
      const total = payload.results.length;
      const pass = payload.results.filter((r) => r.status === "PASS").length;
      resultSummary = `${pass}/${total} PASS · invariant=${payload.invariant_status}`;
      resultOk = pass === total && payload.invariant_status === "clean";
    } else if (payload.kind === "executed_impact") {
      const affected = payload.affected_methods?.length ?? 0;
      const findings = payload.sim_v2_findings?.length ?? 0;
      resultSummary = `${affected} affected methods · ${findings} findings`;
      resultOk = findings === 0;
    } else if (payload.kind === "executed_hypothesis") {
      resultSummary = `verdict=${payload.verdict} (${Math.round(payload.confidence * 100)}%)`;
      resultOk = payload.verdict === "yes" || payload.verdict === "likely_yes";
    } else if (payload.kind === "executed_lookup") {
      resultSummary = `mode=${payload.mode}`;
      resultOk = true;
    }
  } else if (bundle) {
    status = "ready";
  }

  return (
    <div className="border border-primary/20 bg-primary/5 rounded p-2.5 space-y-1.5">
      <div className="flex items-center gap-3 text-[11px]">
        <Section icon={<FlaskConical size={12} />} label="영역">
          <span className="font-mono text-foreground truncate">
            {primaryMethodFqn?.split(".").slice(-2).join(".") ?? "—"}
          </span>
          <span className="text-muted-foreground/70 ml-1">(1 method)</span>
        </Section>

        <Section icon={<FileSpreadsheet size={12} />} label="Fixtures">
          {fixtureCount === null ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <span className="font-mono text-foreground">
              {fixtureCount}
              <span className="text-muted-foreground/70 ml-1">
                ({fixtureCount === 0 ? "no data" : "auto W71"})
              </span>
            </span>
          )}
        </Section>

        <Section icon={<Activity size={12} />} label="상태">
          {status === "pending" && (
            <span className="text-muted-foreground italic">번들 준비 중</span>
          )}
          {status === "ready" && (
            <span className="text-amber-600 inline-flex items-center gap-1">
              <Loader2 size={10} /> 실행 대기
            </span>
          )}
          {status === "done" && (
            <span className={resultOk ? "text-emerald-600 inline-flex items-center gap-1" : "text-rose-600 inline-flex items-center gap-1"}>
              {resultOk ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
              완료
            </span>
          )}
        </Section>
      </div>

      {resultSummary && (
        <div className="text-[11px] text-foreground bg-card/50 border border-border/40 rounded px-2 py-1 font-mono">
          ▸ {resultSummary}
        </div>
      )}
    </div>
  );
}

function Section({
  icon, label, children,
}: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1 min-w-0">
      <span className="text-muted-foreground/70">{icon}</span>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground/80">{label}</span>
      <span className="ml-0.5 truncate">{children}</span>
    </div>
  );
}
