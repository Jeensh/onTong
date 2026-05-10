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
  { label: string; tone: string; icon: React.ReactNode; desc: string }
> = {
  action: {
    label: "Action 노드",
    tone: "border-blue-500/40 bg-blue-500/10 text-blue-700 dark:text-blue-300",
    icon: <Network size={14} />,
    desc: "온톨로지 모델링 (Section 2) 의 Action 클래스 — 시뮬레이션의 root entity",
  },
  realized_method: {
    label: "Realization → Java method",
    tone: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    icon: <Cpu size={14} />,
    desc: "Action.realizations[] 의 매핑 — 실제 Java 코드 메서드와 confirmed/confidence 메타",
  },
  br: {
    label: "BusinessRule (precondition / postcondition)",
    tone: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    icon: <ShieldCheck size={14} />,
    desc: "Action.preconditions / postconditions 에 enumerate 된 비즈니스 룰",
  },
  anchor: {
    label: "AnchorBinding",
    tone: "border-purple-500/40 bg-purple-500/10 text-purple-700 dark:text-purple-300",
    icon: <AnchorIcon size={14} />,
    desc: "AnchorBinding — Java 코드 라인에 anchor 된 실 측정점",
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
      ? "rounded-lg border border-border bg-card p-4 space-y-3"
      : "rounded-md border border-border/60 bg-muted/30 p-3 space-y-2";

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
      <div className="flex items-start gap-2">
        <BookOpen size={16} className="text-primary mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">
            온톨로지 근거 (Section 2 ontology trace)
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">
            <code className="text-[10px]">{data.action_fqn}</code> ·{" "}
            <span>{data.ontology_transport}</span>
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">
            facade: <code className="text-[10px]">{data.ontology_facade}</code>
          </div>
        </div>
      </div>

      {/* summary chips */}
      <div className="flex flex-wrap gap-1.5">
        {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
          const count = data.summary[kind] ?? 0;
          const meta = KIND_META[kind];
          return (
            <span
              key={kind}
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] ${meta.tone}`}
            >
              {meta.icon}
              <span className="font-medium">{meta.label.split(" ")[0]}</span>
              <span className="opacity-70">×{count}</span>
            </span>
          );
        })}
      </div>

      {/* per-kind grouped trace */}
      <div className="space-y-2">
        {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
          const traces = grouped[kind] ?? [];
          if (traces.length === 0) return null;
          const meta = KIND_META[kind];
          const isOpen = expandedKind === kind;
          return (
            <div key={kind} className="rounded border border-border/60">
              <button
                onClick={() => setExpandedKind(isOpen ? null : kind)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/40 text-left"
              >
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] border ${meta.tone}`}>
                  {meta.icon}
                  {meta.label}
                </span>
                <span className="text-[10px] text-muted-foreground ml-auto">
                  {traces.length}건
                </span>
              </button>
              {isOpen && (
                <div className="px-3 pb-3 space-y-2">
                  <div className="text-[11px] text-muted-foreground italic">
                    {meta.desc}
                  </div>
                  {traces.map((t, i) => (
                    <div
                      key={i}
                      className="rounded border border-border/40 bg-muted/20 p-2 space-y-1"
                    >
                      <div className="text-[11px] text-foreground">
                        {t.explanation}
                      </div>
                      <div className="text-[10px] text-muted-foreground space-y-0.5">
                        <div>
                          <b>id:</b> <code>{t.evidence_id}</code>
                        </div>
                        <div>
                          <b>source:</b> {t.ontology_source}
                        </div>
                        <div>
                          <b>facade call:</b>{" "}
                          <code className="text-[9px]">{t.ontology_facade_call}</code>
                        </div>
                      </div>
                      {Object.keys(t.ontology_data).length > 0 && (
                        <details className="text-[10px]">
                          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                            ontology data ({Object.keys(t.ontology_data).length} 필드)
                          </summary>
                          <pre className="mt-1 p-1.5 rounded bg-background border border-border/40 overflow-x-auto text-[9px]">
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
    <div className="space-y-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] border border-primary/30 bg-primary/5 hover:bg-primary/10 text-primary"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
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
