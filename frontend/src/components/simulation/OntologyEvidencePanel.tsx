"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Loader2,
  Network,
  Anchor as AnchorIcon,
  Cpu,
  ShieldCheck,
} from "lucide-react";

interface OntologyTrace {
  evidence_kind: "action" | "realized_method" | "br" | "anchor";
  evidence_id: string;
  ontology_source: string;
  ontology_facade_call: string;
  ontology_data: Record<string, unknown>;
  explanation: string;
}

interface RunOntologyEvidence {
  run_id: string;
  action_fqn: string;
  ontology_facade: string;
  ontology_transport: string;
  traces: OntologyTrace[];
  summary: Record<string, number>;
}

interface Props {
  /** spec 03 run 의 run_id — 우선. 없으면 actionFqn 사용. */
  runId?: string;
  /** run_id 없이 action_fqn 만으로 조회. */
  actionFqn?: string;
  /** 자동 expand 여부 (default true). */
  autoOpen?: boolean;
  /** UI 톤 — 메인 / inline. */
  variant?: "card" | "inline";
}

const KIND_META: Record<
  OntologyTrace["evidence_kind"],
  {
    label: string;
    chipTone: string;       // 작은 chip
    cardTone: string;       // 펼친 카드 배경 (강한 색)
    icon: React.ReactNode;
    desc: string;
    emoji: string;
  }
> = {
  action: {
    label: "Action 노드",
    chipTone: "border-blue-600 bg-blue-100 text-blue-800 dark:border-blue-400 dark:bg-blue-900/40 dark:text-blue-200",
    cardTone: "border-l-4 border-blue-600 bg-blue-50 dark:bg-blue-900/20",
    icon: <Network size={16} />,
    desc: "온톨로지 모델링 (Section 2) 의 Action 클래스 — 시뮬레이션의 root entity",
    emoji: "🧩",
  },
  realized_method: {
    label: "Realization → Java method",
    chipTone: "border-emerald-600 bg-emerald-100 text-emerald-800 dark:border-emerald-400 dark:bg-emerald-900/40 dark:text-emerald-200",
    cardTone: "border-l-4 border-emerald-600 bg-emerald-50 dark:bg-emerald-900/20",
    icon: <Cpu size={16} />,
    desc: "Action.realizations[] 의 매핑 — 실제 Java 코드 메서드와 confirmed/confidence 메타",
    emoji: "⚙️",
  },
  br: {
    label: "BusinessRule",
    chipTone: "border-amber-600 bg-amber-100 text-amber-800 dark:border-amber-400 dark:bg-amber-900/40 dark:text-amber-200",
    cardTone: "border-l-4 border-amber-600 bg-amber-50 dark:bg-amber-900/20",
    icon: <ShieldCheck size={16} />,
    desc: "Action.preconditions / postconditions 에 enumerate 된 비즈니스 룰",
    emoji: "📋",
  },
  anchor: {
    label: "AnchorBinding",
    chipTone: "border-purple-600 bg-purple-100 text-purple-800 dark:border-purple-400 dark:bg-purple-900/40 dark:text-purple-200",
    cardTone: "border-l-4 border-purple-600 bg-purple-50 dark:bg-purple-900/20",
    icon: <AnchorIcon size={16} />,
    desc: "AnchorBinding — Java 코드 라인에 anchor 된 실 측정점",
    emoji: "⚓",
  },
};

export function OntologyEvidencePanel({
  runId,
  actionFqn,
  autoOpen = true,
  variant = "card",
}: Props) {
  const [data, setData] = useState<RunOntologyEvidence | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expandedKind, setExpandedKind] = useState<string | null>(
    autoOpen ? "action" : null,
  );

  useEffect(() => {
    let aborted = false;
    const url = runId
      ? `/api/simulation/runs/${encodeURIComponent(runId)}/ontology-evidence`
      : actionFqn
        ? `/api/simulation/ontology-evidence/by-action?action_fqn=${encodeURIComponent(actionFqn)}`
        : null;
    if (!url) {
      setErr("run_id 또는 action_fqn 둘 중 하나가 필요합니다.");
      return;
    }
    setLoading(true);
    setErr(null);
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} — ${await r.text()}`);
        return r.json();
      })
      .then((d) => {
        if (!aborted) setData(d);
      })
      .catch((e) => {
        if (!aborted) setErr(String(e));
      })
      .finally(() => {
        if (!aborted) setLoading(false);
      });
    return () => {
      aborted = true;
    };
  }, [runId, actionFqn]);

  const wrapperClass =
    variant === "card"
      ? "rounded-xl border-2 border-primary/30 bg-gradient-to-br from-primary/5 via-card to-card p-5 space-y-4 shadow-sm"
      : "rounded-lg border-2 border-primary/40 bg-gradient-to-br from-primary/8 to-primary/3 p-4 space-y-3 shadow-sm";

  if (loading) {
    return (
      <div className={wrapperClass}>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          ontology evidence 조회 중...
        </div>
      </div>
    );
  }
  if (err) {
    return (
      <div className={wrapperClass}>
        <div className="text-xs text-red-600 dark:text-red-400">
          ⚠ ontology evidence 조회 실패: {err}
        </div>
      </div>
    );
  }
  if (!data) return null;

  // group traces by kind
  const grouped: Record<string, OntologyTrace[]> = {};
  for (const t of data.traces) {
    if (!grouped[t.evidence_kind]) grouped[t.evidence_kind] = [];
    grouped[t.evidence_kind].push(t);
  }

  return (
    <div className={wrapperClass}>
      {/* ── Header — strongly emphasized ─────────────────────── */}
      <div className="flex items-start gap-3 pb-3 border-b border-primary/20">
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
          <BookOpen size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-base font-bold text-foreground flex items-center gap-2 flex-wrap">
            📚 온톨로지 근거
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30">
              Section 2 ontology trace
            </span>
          </div>
          <div className="text-[12px] text-foreground/80 mt-1 font-mono break-all">
            <span className="text-muted-foreground">action:</span>{" "}
            <span className="font-semibold">{data.action_fqn}</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">
            <span className="font-medium text-foreground/70">{data.ontology_transport}</span>
            {" · facade: "}<code className="text-[9px]">{data.ontology_facade}</code>
          </div>
        </div>
      </div>

      {/* ── Summary chips — bigger and more colorful ─────── */}
      <div>
        <div className="text-[11px] font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
          📊 4 evidence kind 카운트
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
            const count = data.summary[kind] ?? 0;
            const meta = KIND_META[kind];
            const dimmed = count === 0;
            return (
              <button
                key={kind}
                onClick={() => count > 0 && setExpandedKind(kind)}
                disabled={count === 0}
                className={`flex items-center gap-2 rounded-lg border-2 px-3 py-2 text-left transition-all ${meta.chipTone} ${
                  dimmed ? "opacity-40 cursor-not-allowed" : "hover:scale-[1.02] cursor-pointer"
                } ${expandedKind === kind && !dimmed ? "ring-2 ring-offset-1 ring-primary/40" : ""}`}
              >
                <span className="text-xl">{meta.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] font-bold leading-tight">
                    {meta.label}
                  </div>
                  <div className="text-[10px] opacity-80 mt-0.5">
                    {count > 0 ? `${count} 건` : "—"}
                  </div>
                </div>
                <span className="text-lg font-bold">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── per-kind grouped trace — colorful expandable cards ── */}
      <div className="space-y-2">
        <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
          🔍 trace 상세 (클릭해 펼치기)
        </div>
        {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
          const traces = grouped[kind] ?? [];
          if (traces.length === 0) return null;
          const meta = KIND_META[kind];
          const isOpen = expandedKind === kind;
          return (
            <div key={kind} className={`rounded-lg overflow-hidden ${meta.cardTone}`}>
              <button
                onClick={() => setExpandedKind(isOpen ? null : kind)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 text-left"
              >
                <span className="text-xl">{meta.emoji}</span>
                {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                <span className="font-semibold text-sm">{meta.label}</span>
                <span className="ml-auto inline-flex items-center justify-center min-w-[28px] h-6 px-2 rounded-full bg-white/70 dark:bg-black/30 text-xs font-bold">
                  {traces.length}
                </span>
              </button>
              {isOpen && (
                <div className="px-4 pb-4 space-y-2 bg-white/40 dark:bg-black/20">
                  <div className="text-[11px] text-foreground/70 italic pt-2">
                    {meta.desc}
                  </div>
                  {traces.map((t, i) => (
                    <div
                      key={i}
                      className="rounded-md border border-foreground/10 bg-white dark:bg-black/30 p-3 space-y-1.5 shadow-sm"
                    >
                      <div className="text-[12px] text-foreground font-medium leading-relaxed">
                        {t.explanation}
                      </div>
                      <div className="text-[10px] text-muted-foreground space-y-0.5 pt-1 border-t border-border/40">
                        <div>
                          <b className="text-foreground/70">id:</b>{" "}
                          <code className="text-[10px] break-all">{t.evidence_id}</code>
                        </div>
                        <div>
                          <b className="text-foreground/70">source:</b>{" "}
                          <span className="font-mono text-[10px]">{t.ontology_source}</span>
                        </div>
                        <div>
                          <b className="text-foreground/70">facade call:</b>{" "}
                          <code className="text-[10px] break-all">{t.ontology_facade_call}</code>
                        </div>
                      </div>
                      {Object.keys(t.ontology_data).length > 0 && (
                        <details className="text-[10px] pt-1">
                          <summary className="cursor-pointer text-primary hover:underline font-medium">
                            ▶ ontology data ({Object.keys(t.ontology_data).length} 필드)
                          </summary>
                          <pre className="mt-1 p-2 rounded bg-muted border border-border overflow-x-auto text-[10px]">
{JSON.stringify(t.ontology_data, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** 토글 가능한 evidence 박스 — 다른 panel 에 임베드용. */
export function OntologyEvidenceToggle({
  runId,
  actionFqn,
  label = "📚 온톨로지 근거 보기",
}: {
  runId?: string;
  actionFqn?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`w-full sm:w-auto inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold border-2 transition-all ${
          open
            ? "border-primary bg-primary text-primary-foreground shadow-md"
            : "border-primary/40 bg-primary/10 hover:bg-primary/20 hover:border-primary text-primary hover:shadow-sm"
        }`}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        {label}
      </button>
      {open && (
        <OntologyEvidencePanel
          runId={runId}
          actionFqn={actionFqn}
          variant="inline"
          autoOpen
        />
      )}
    </div>
  );
}
