"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ActionDTO,
  type AnchorBindingDTO,
  type BusinessRuleDTO,
  type TermDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";

/**
 * 좌측 트리의 "온톨로지" 탭 — Term / Action / BR / Anchor 4 영역을 도메인별로 모음.
 *
 * ModuleTree (코드) 가 패키지 ↔ class ↔ Action 관점이라면, 본 탭은
 *   "Phase A/B/C archive 합의의 ground truth 검수" 관점.
 * 사용자가 인계 전 모든 매핑된 내용을 한 화면에서 확인할 수 있도록.
 */
type Section = "terms" | "actions" | "rules" | "anchors";

const SECTION_LABEL: Record<Section, string> = {
  terms: "Term",
  actions: "Action",
  rules: "BusinessRule",
  anchors: "AnchorBinding",
};

const SECTION_COLOR: Record<Section, string> = {
  terms: "text-violet-700",
  actions: "text-orange-700",
  rules: "text-rose-700",
  anchors: "text-sky-700",
};

export function OntologyTab() {
  const { activeRepoId, setSelectedTerm, setSelectedAction } = useWorkbench();

  const [terms, setTerms] = useState<TermDTO[]>([]);
  const [actions, setActions] = useState<ActionDTO[]>([]);
  const [rules, setRules] = useState<BusinessRuleDTO[]>([]);
  const [anchors, setAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // 섹션 expand 상태
  const [expanded, setExpanded] = useState<Set<Section>>(
    new Set(["terms", "actions", "rules", "anchors"]),
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    Promise.all([
      ontologyApi.listTerms({ repo_id: activeRepoId }),
      ontologyApi.listActions({ repo_id: activeRepoId }),
      ontologyApi.listBusinessRules({ repo_id: activeRepoId }),
      ontologyApi.listAnchorBindings({ repo_id: activeRepoId }),
    ])
      .then(([t, a, r, ab]) => {
        if (cancelled) return;
        setTerms(t);
        setActions(a);
        setRules(r);
        setAnchors(ab);
      })
      .catch((e) => {
        if (cancelled) return;
        setErr(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [activeRepoId]);

  // 도메인 별 그루핑 (terms / actions). domain 비어있으면 "(도메인 없음)" 으로.
  const termsByDomain = useMemo(() => groupBy(terms, (t) => t.domain || "(도메인 없음)"), [terms]);
  const actionsByDomain = useMemo(() => groupBy(actions, (a) => a.domain || "(도메인 없음)"), [actions]);

  const atomicTerms = terms.filter((t) => t.kind === "atomic");
  const compositeTerms = terms.filter((t) => t.kind === "composite");

  const toggle = (s: Section) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(s) ? next.delete(s) : next.add(s);
      return next;
    });

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-[11px] text-muted-foreground p-3">
        <Loader2 className="w-3 h-3 animate-spin" />
        <span>온톨로지 로딩…</span>
      </div>
    );
  }
  if (err) {
    return <div className="text-[11px] text-rose-700 p-3">에러: {err}</div>;
  }

  return (
    <div className="overflow-y-auto flex-1 text-[11.5px]">
      {/* 헤더 — 합계 카운트 */}
      <div className="px-2 py-1.5 border-b border-border bg-muted/30 text-[10.5px] text-muted-foreground">
        {atomicTerms.length} atomic · {compositeTerms.length} composite · {actions.length} action ·{" "}
        {rules.length} rule · {anchors.length} anchor
      </div>

      {/* === Terms === */}
      <SectionHeader
        section="terms"
        count={terms.length}
        sub={`atomic ${atomicTerms.length} / composite ${compositeTerms.length}`}
        expanded={expanded.has("terms")}
        onToggle={() => toggle("terms")}
      />
      {expanded.has("terms") && (
        <div className="pl-2">
          {/* atomic group */}
          <div className="px-1 pt-1 text-[10px] text-emerald-700 font-mono">
            atomic ({atomicTerms.length})
          </div>
          {atomicTerms.map((t) => (
            <TermRow key={t.fqn} t={t} onClick={() => setSelectedTerm(t.fqn)} />
          ))}
          {/* composite group — domain 별 */}
          <div className="px-1 pt-1 text-[10px] text-violet-700 font-mono">
            composite ({compositeTerms.length})
          </div>
          {Array.from(termsByDomain.entries())
            .filter(([, list]) => list.some((t) => t.kind === "composite"))
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([domain, list]) => {
              const composites = list.filter((t) => t.kind === "composite");
              if (composites.length === 0) return null;
              return (
                <div key={domain}>
                  <div className="pl-2 pt-0.5 text-[10px] text-muted-foreground font-mono">
                    {domain} · {composites.length}
                  </div>
                  {composites.map((t) => (
                    <TermRow key={t.fqn} t={t} onClick={() => setSelectedTerm(t.fqn)} />
                  ))}
                </div>
              );
            })}
        </div>
      )}

      {/* === Actions === */}
      <SectionHeader
        section="actions"
        count={actions.length}
        sub={`confirmed ${actions.filter((a) => a.verification_level !== "unmapped" && a.verification_level !== "draft").length} / draft ${actions.filter((a) => a.verification_level === "draft").length}`}
        expanded={expanded.has("actions")}
        onToggle={() => toggle("actions")}
      />
      {expanded.has("actions") && (
        <div className="pl-2">
          {Array.from(actionsByDomain.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([domain, list]) => (
              <div key={domain}>
                <div className="pl-1 pt-1 text-[10px] text-muted-foreground font-mono">
                  {domain} · {list.length}
                </div>
                {list.map((a) => (
                  <ActionRow key={a.fqn} a={a} onClick={() => setSelectedAction(a.fqn)} />
                ))}
              </div>
            ))}
        </div>
      )}

      {/* === BusinessRules === */}
      <SectionHeader
        section="rules"
        count={rules.length}
        sub={`hard ${rules.filter((r) => r.severity === "hard").length}`}
        expanded={expanded.has("rules")}
        onToggle={() => toggle("rules")}
      />
      {expanded.has("rules") && (
        <div className="pl-2 pb-1">
          {rules.map((r) => (
            <BRRow key={r.fqn} r={r} />
          ))}
        </div>
      )}

      {/* === AnchorBindings === */}
      <SectionHeader
        section="anchors"
        count={anchors.length}
        sub={`confirmed ${anchors.filter((a) => a.confirmed).length}`}
        expanded={expanded.has("anchors")}
        onToggle={() => toggle("anchors")}
      />
      {expanded.has("anchors") && (
        <div className="pl-2 pb-1">
          {anchors.map((a) => (
            <AnchorRow key={a.id} a={a} onClick={() => setSelectedAction(a.target_action_fqn)} />
          ))}
        </div>
      )}
    </div>
  );
}

function SectionHeader({
  section, count, sub, expanded, onToggle,
}: {
  section: Section; count: number; sub: string;
  expanded: boolean; onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className="w-full text-left px-2 py-1 flex items-center gap-1 border-b border-border/50 hover:bg-muted/40 transition-colors"
    >
      {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      <span className={cn("font-semibold", SECTION_COLOR[section])}>{SECTION_LABEL[section]}</span>
      <span className="text-[10.5px] text-muted-foreground ml-auto">{count} · {sub}</span>
    </button>
  );
}

function TermRow({ t, onClick }: { t: TermDTO; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left pl-3 pr-2 py-0.5 flex items-center gap-1.5 hover:bg-muted/40 transition-colors"
      title={`${t.fqn}\n${t.description ?? ""}`}
    >
      <span className={cn(
        "w-1.5 h-1.5 rounded-full shrink-0",
        t.kind === "atomic" ? "bg-emerald-500" : "bg-violet-500",
      )} />
      <span className="truncate flex-1 font-mono">{t.label}</span>
      {t.confirmed && <span className="text-[9px] text-emerald-700 shrink-0">✓</span>}
      <span className="text-[9px] text-muted-foreground font-mono shrink-0">
        {(t as { value_type?: string }).value_type ?? ""}
      </span>
    </button>
  );
}

function ActionRow({ a, onClick }: { a: ActionDTO; onClick: () => void }) {
  const lvl = a.verification_level;
  const confirmed = lvl !== "unmapped" && lvl !== "draft";
  return (
    <button
      onClick={onClick}
      className="w-full text-left pl-3 pr-2 py-0.5 flex items-center gap-1.5 hover:bg-muted/40 transition-colors"
      title={`${a.fqn}\nkind: ${a.kind}\nlevel: ${lvl}`}
    >
      <span className="w-1.5 h-1.5 rounded-sm bg-orange-500 shrink-0" />
      <span className="truncate flex-1 font-mono text-foreground">{a.label}</span>
      {confirmed ? (
        <span className="text-[9px] text-emerald-700 shrink-0" title={`confirmed (${lvl})`}>✓</span>
      ) : (
        <span className="text-[9px] text-amber-700 shrink-0" title="draft">·</span>
      )}
      <span className="text-[9px] text-muted-foreground font-mono shrink-0">{a.kind.slice(0, 4)}</span>
    </button>
  );
}

function BRRow({ r }: { r: BusinessRuleDTO }) {
  return (
    <div
      className="pl-3 pr-2 py-0.5 hover:bg-muted/40 transition-colors"
      title={`${r.fqn}\nseverity: ${r.severity}\n${r.statement}`}
    >
      <div className="flex items-center gap-1.5">
        <span className={cn(
          "w-1.5 h-1.5 rounded-sm shrink-0",
          r.severity === "hard" ? "bg-rose-500" : "bg-amber-500",
        )} />
        <span className="truncate flex-1 font-mono text-foreground text-[11px]">{r.fqn}</span>
        {r.confirmed && <span className="text-[9px] text-emerald-700 shrink-0">✓</span>}
      </div>
      <div className="pl-3 text-[10px] text-muted-foreground line-clamp-1">{r.statement}</div>
    </div>
  );
}

function AnchorRow({ a, onClick }: { a: AnchorBindingDTO; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left pl-3 pr-2 py-0.5 hover:bg-muted/40 transition-colors"
      title={`${a.id}\nlocator: ${a.anchor_locator}\nmethod: ${a.code_method_fqn}\n→ ${a.target_action_fqn}.${a.target_slot}`}
    >
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0" />
        <span className="truncate flex-1 font-mono text-foreground text-[11px]">{a.anchor_locator}</span>
        {a.confirmed && <span className="text-[9px] text-emerald-700 shrink-0">✓</span>}
        <span className="text-[9px] text-muted-foreground font-mono shrink-0">{a.confidence.toFixed(2)}</span>
      </div>
    </button>
  );
}

function groupBy<T, K extends string>(arr: T[], key: (x: T) => K): Map<K, T[]> {
  const m = new Map<K, T[]>();
  for (const it of arr) {
    const k = key(it);
    const list = m.get(k) ?? [];
    list.push(it);
    m.set(k, list);
  }
  return m;
}
