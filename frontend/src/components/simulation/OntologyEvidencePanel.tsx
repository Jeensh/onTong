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

/** Java FQN 을 ClassName.method(...) + 패키지 분리. */
function shortenJavaFqn(fqn: string): { className: string; method: string; pkg: string } {
  const parenIdx = fqn.indexOf("(");
  const before = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
  const args = parenIdx >= 0 ? fqn.slice(parenIdx) : "";
  const parts = before.split(".");
  if (parts.length < 2) return { className: "", method: fqn, pkg: "" };
  const method = parts[parts.length - 1];
  const className = parts[parts.length - 2];
  const pkg = parts.slice(0, -2).join(".");
  return { className, method: method + args, pkg };
}

/** action.scm.foo.bar_실행 → bar_실행 + 패키지 prefix. */
function shortenActionFqn(fqn: string): { name: string; ns: string } {
  const parts = fqn.split(".");
  if (parts.length < 2) return { name: fqn, ns: "" };
  return { name: parts[parts.length - 1], ns: parts.slice(0, -1).join(".") };
}

/** facade call 의 마지막 method 만 추출 (예: get_action(...).realizations → realizations). */
function shortenFacadeCall(call: string): { method: string; full: string } {
  const m = call.match(/\.([a-zA-Z_][a-zA-Z0-9_]*)$/);
  if (m) return { method: m[1], full: call };
  // 또는 함수형: OntologyQueryClient.get_action('...')
  const m2 = call.match(/([a-zA-Z_][a-zA-Z0-9_]*)\(/);
  if (m2) return { method: m2[1] + "(...)", full: call };
  return { method: call, full: call };
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
    shortLabel: string;     // 좁은 영역 chip 용
    chipTone: string;       // 작은 chip
    cardTone: string;       // 펼친 카드 배경 (강한 색)
    icon: React.ReactNode;
    desc: string;
    emoji: string;
  }
> = {
  action: {
    label: "Action 노드",
    shortLabel: "Action",
    chipTone: "border-blue-600 bg-blue-100 text-blue-800 dark:border-blue-400 dark:bg-blue-900/40 dark:text-blue-200",
    cardTone: "border-l-4 border-blue-600 bg-blue-50 dark:bg-blue-900/20",
    icon: <Network size={16} />,
    desc: "온톨로지 모델링 (Section 2) 의 Action 클래스 — 시뮬레이션의 root entity",
    emoji: "🧩",
  },
  realized_method: {
    label: "Realization → Java",
    shortLabel: "Realization",
    chipTone: "border-emerald-600 bg-emerald-100 text-emerald-800 dark:border-emerald-400 dark:bg-emerald-900/40 dark:text-emerald-200",
    cardTone: "border-l-4 border-emerald-600 bg-emerald-50 dark:bg-emerald-900/20",
    icon: <Cpu size={16} />,
    desc: "Action.realizations[] 의 매핑 — 실제 Java 코드 메서드와 confirmed/confidence 메타",
    emoji: "⚙️",
  },
  br: {
    label: "BusinessRule",
    shortLabel: "BR",
    chipTone: "border-amber-600 bg-amber-100 text-amber-800 dark:border-amber-400 dark:bg-amber-900/40 dark:text-amber-200",
    cardTone: "border-l-4 border-amber-600 bg-amber-50 dark:bg-amber-900/20",
    icon: <ShieldCheck size={16} />,
    desc: "Action.preconditions / postconditions 에 enumerate 된 비즈니스 룰",
    emoji: "📋",
  },
  anchor: {
    label: "AnchorBinding",
    shortLabel: "Anchor",
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
      ? "rounded-xl border-2 border-primary/30 bg-gradient-to-br from-primary/5 via-card to-card p-5 space-y-4 shadow-sm overflow-hidden"
      : "rounded-lg border-2 border-primary/40 bg-gradient-to-br from-primary/8 to-primary/3 p-3 space-y-3 shadow-sm overflow-hidden";

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
      <div className="flex items-start gap-2.5 pb-3 border-b border-primary/20 min-w-0">
        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary text-primary-foreground flex items-center justify-center shadow-sm">
          <BookOpen size={18} />
        </div>
        <div className="flex-1 min-w-0 overflow-hidden">
          <div className="text-sm font-bold text-foreground flex items-center gap-2 flex-wrap">
            <span>📚 온톨로지 근거</span>
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30 whitespace-nowrap">
              Section 2 trace
            </span>
          </div>
          <div className="text-[11px] text-foreground/80 mt-1 font-mono break-all" style={{ wordBreak: "break-all", overflowWrap: "anywhere" }}>
            <span className="text-muted-foreground">action:</span>{" "}
            <span className="font-semibold">{data.action_fqn}</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5 break-all" style={{ overflowWrap: "anywhere" }}>
            <span className="font-medium text-foreground/70">{data.ontology_transport}</span>
          </div>
        </div>
      </div>

      {/* ── Summary chips — bigger and more colorful ─────── */}
      <div className="min-w-0">
        <div className="text-[11px] font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
          📊 4 evidence kind 카운트
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
            const count = data.summary[kind] ?? 0;
            const meta = KIND_META[kind];
            const dimmed = count === 0;
            return (
              <button
                key={kind}
                onClick={() => count > 0 && setExpandedKind(kind)}
                disabled={count === 0}
                className={`flex items-center gap-1.5 rounded-md border px-2 py-1.5 text-left transition-all min-w-0 ${meta.chipTone} ${
                  dimmed ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:shadow-sm"
                } ${expandedKind === kind && !dimmed ? "ring-2 ring-offset-1 ring-primary/40" : ""}`}
              >
                <span className="text-base flex-shrink-0">{meta.emoji}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold leading-tight truncate">
                    {meta.shortLabel}
                  </div>
                  <div className="text-[9px] opacity-80">
                    {count > 0 ? `${count} 건` : "—"}
                  </div>
                </div>
                <span className="text-base font-bold flex-shrink-0">{count}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── per-kind grouped trace — colorful expandable cards ── */}
      <div className="space-y-2 min-w-0">
        <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
          🔍 trace 상세 (클릭해 펼치기)
        </div>
        {(["action", "realized_method", "br", "anchor"] as const).map((kind) => {
          const traces = grouped[kind] ?? [];
          if (traces.length === 0) return null;
          const meta = KIND_META[kind];
          const isOpen = expandedKind === kind;
          return (
            <div key={kind} className={`rounded-lg overflow-hidden min-w-0 ${meta.cardTone}`}>
              <button
                onClick={() => setExpandedKind(isOpen ? null : kind)}
                className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-black/5 dark:hover:bg-white/5 text-left min-w-0"
              >
                <span className="text-lg flex-shrink-0">{meta.emoji}</span>
                {isOpen ? <ChevronDown size={14} className="flex-shrink-0" /> : <ChevronRight size={14} className="flex-shrink-0" />}
                <span className="font-semibold text-[13px] flex-1 min-w-0 truncate">{meta.label}</span>
                <span className="flex-shrink-0 inline-flex items-center justify-center min-w-[24px] h-5 px-1.5 rounded-full bg-white/70 dark:bg-black/30 text-[11px] font-bold">
                  {traces.length}
                </span>
              </button>
              {isOpen && (
                <div className="px-3 pb-3 space-y-2 bg-white/40 dark:bg-black/20 min-w-0">
                  <div className="text-[10px] text-foreground/70 italic pt-2 break-words" style={{ overflowWrap: "anywhere" }}>
                    {meta.desc}
                  </div>
                  {traces.map((t, i) => (
                    <TraceCard key={i} trace={t} />
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

/** 작은 칩. */
function Chip({
  tone = "neutral",
  children,
}: {
  tone?: "neutral" | "ok" | "warn" | "info" | "muted";
  children: React.ReactNode;
}) {
  const toneClass = {
    neutral: "bg-foreground/10 text-foreground border-foreground/15",
    ok: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    warn: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
    info: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30",
    muted: "bg-muted text-muted-foreground border-border",
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium whitespace-nowrap ${toneClass}`}>
      {children}
    </span>
  );
}

/** 한 trace 의 가독성 좋은 표시 — kind 별로 핵심만 prominent + chip + 풀 정보는 접힘. */
function TraceCard({ trace }: { trace: OntologyTrace }) {
  const t = trace;
  const data = t.ontology_data as Record<string, any>;

  return (
    <div className="rounded-md border border-foreground/10 bg-white dark:bg-black/30 p-3 space-y-2 shadow-sm min-w-0 overflow-hidden">
      {/* ── 핵심 식별자 — kind 별 다른 렌더 ─────── */}
      {t.evidence_kind === "action" && (() => {
        const { name, ns } = shortenActionFqn(t.evidence_id);
        const label = data.label as string | undefined;
        return (
          <>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-base">🧩</span>
              <span className="text-[13px] font-bold text-foreground break-all" style={{ overflowWrap: "anywhere" }}>
                {name}
              </span>
              {label && label !== name && (
                <span className="text-[11px] text-muted-foreground">"{label}"</span>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {data.kind && <Chip tone="info">{String(data.kind)}</Chip>}
              {typeof data.realizations_count === "number" && (
                <Chip tone={data.realizations_count > 0 ? "ok" : "muted"}>
                  realizations × {data.realizations_count}
                </Chip>
              )}
              {typeof data.sub_actions_count === "number" && data.sub_actions_count > 0 && (
                <Chip tone="info">sub-actions × {data.sub_actions_count}</Chip>
              )}
              {data.declared_on_term && (
                <Chip tone="muted">term: {String(data.declared_on_term).split(".").pop()}</Chip>
              )}
            </div>
            <div className="text-[9px] text-muted-foreground font-mono break-all" style={{ overflowWrap: "anywhere" }}>
              {ns}
            </div>
          </>
        );
      })()}

      {t.evidence_kind === "realized_method" && (() => {
        const { className, method, pkg } = shortenJavaFqn(t.evidence_id);
        const confirmed = data.confirmed as boolean | undefined;
        const confidence = data.confidence as number | undefined;
        const scope = data.scope as string | undefined;
        return (
          <>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-base">⚙️</span>
              <span className="text-[13px] font-bold font-mono text-foreground break-all" style={{ overflowWrap: "anywhere" }}>
                {className ? `${className}.${method}` : method}
              </span>
            </div>
            <div className="flex flex-wrap gap-1">
              <Chip tone={confirmed ? "ok" : "warn"}>
                {confirmed ? "✓ confirmed" : "✗ unconfirmed"}
              </Chip>
              {confidence !== undefined && (
                <Chip tone={confidence >= 0.9 ? "ok" : confidence >= 0.5 ? "warn" : "muted"}>
                  conf {confidence.toFixed(2)}
                </Chip>
              )}
              {scope && <Chip tone="info">{scope}</Chip>}
              {data.applies_to_code_type_fqn && (
                <Chip tone="muted">
                  applies to: {String(data.applies_to_code_type_fqn).split(".").pop()}
                </Chip>
              )}
            </div>
            {pkg && (
              <div className="text-[9px] text-muted-foreground font-mono break-all" style={{ overflowWrap: "anywhere" }}>
                📦 {pkg}
              </div>
            )}
          </>
        );
      })()}

      {t.evidence_kind === "br" && (() => {
        const brName = t.evidence_id.split(".").pop() || t.evidence_id;
        const kind = data.kind as string | undefined;
        return (
          <>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-base">📋</span>
              <span className="text-[13px] font-bold font-mono text-foreground break-all" style={{ overflowWrap: "anywhere" }}>
                {brName}
              </span>
            </div>
            <div className="flex flex-wrap gap-1">
              {kind && (
                <Chip tone={kind.includes("pre") ? "info" : "warn"}>
                  {kind.includes("unknown") ? "unknown" : kind}
                </Chip>
              )}
            </div>
          </>
        );
      })()}

      {t.evidence_kind === "anchor" && (() => {
        const anchorId = t.evidence_id.split(".").pop() || t.evidence_id;
        const locator = data.anchor_locator as string | undefined;
        const codeMethodFqn = data.code_method_fqn as string | undefined;
        const targetSlot = data.target_slot as string | undefined;
        const codeShort = codeMethodFqn ? shortenJavaFqn(codeMethodFqn) : null;
        return (
          <>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="text-base">⚓</span>
              <span className="text-[13px] font-bold font-mono text-foreground break-all" style={{ overflowWrap: "anywhere" }}>
                {anchorId}
              </span>
              {locator && <Chip tone="info">{locator}</Chip>}
            </div>
            <div className="flex flex-wrap gap-1">
              {targetSlot && <Chip tone="muted">slot: {targetSlot}</Chip>}
              {data.confirmed !== undefined && (
                <Chip tone={data.confirmed ? "ok" : "warn"}>
                  {data.confirmed ? "✓ confirmed" : "✗ unconfirmed"}
                </Chip>
              )}
            </div>
            {codeShort && (
              <div className="text-[10px] text-muted-foreground font-mono break-all" style={{ overflowWrap: "anywhere" }}>
                ⚙️ {codeShort.className}.{codeShort.method}
              </div>
            )}
          </>
        );
      })()}

      {/* ── 풀 정보 — 접힘 (raw 정보 추적용) ─────── */}
      <details className="text-[10px] pt-1 border-t border-border/40">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none">
          ▶ 원본 (id / source / facade / data 전체)
        </summary>
        <div className="mt-2 space-y-1.5 text-[10px] text-muted-foreground bg-muted/40 rounded p-2">
          <div className="break-all" style={{ overflowWrap: "anywhere" }}>
            <b className="text-foreground/70">id:</b>{" "}
            <code className="text-[9px]">{t.evidence_id}</code>
          </div>
          <div className="break-all" style={{ overflowWrap: "anywhere" }}>
            <b className="text-foreground/70">source:</b> {t.ontology_source}
          </div>
          <div className="break-all" style={{ overflowWrap: "anywhere" }}>
            <b className="text-foreground/70">facade:</b>{" "}
            <code className="text-[9px]">{t.ontology_facade_call}</code>
          </div>
          {Object.keys(t.ontology_data).length > 0 && (
            <div className="pt-1">
              <b className="text-foreground/70">ontology data:</b>
              <pre className="mt-1 p-1.5 rounded bg-background border border-border text-[9px] whitespace-pre-wrap break-all" style={{ overflowWrap: "anywhere" }}>
{JSON.stringify(t.ontology_data, null, 2)}
              </pre>
            </div>
          )}
          <div className="pt-1 italic text-foreground/60 break-words" style={{ overflowWrap: "anywhere" }}>
            {t.explanation}
          </div>
        </div>
      </details>
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
        className={`w-full inline-flex items-start gap-2 px-3 py-2 rounded-lg text-[13px] font-semibold border-2 transition-all text-left ${
          open
            ? "border-primary bg-primary text-primary-foreground shadow-md"
            : "border-primary/40 bg-primary/10 hover:bg-primary/20 hover:border-primary text-primary hover:shadow-sm"
        }`}
      >
        <span className="flex-shrink-0 mt-0.5">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span className="flex-1 min-w-0 break-words leading-snug" style={{ overflowWrap: "anywhere" }}>
          {label}
        </span>
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
