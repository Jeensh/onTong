"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2, ChevronDown, ChevronRight, Search, X as XIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ActionDTO,
  type AnchorBindingDTO,
  type BusinessRuleDTO,
  type TermDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";
import { HelpHint } from "./HelpHint";
import { prettyFqn } from "@/lib/modeling/fqn";

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
  const { activeRepoId, setSelectedTerm, setSelectedAction, setSelectedRule, setSelectedAnchor } = useWorkbench();

  const [terms, setTerms] = useState<TermDTO[]>([]);
  const [actions, setActions] = useState<ActionDTO[]>([]);
  const [rules, setRules] = useState<BusinessRuleDTO[]>([]);
  const [anchors, setAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState("");

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

  // 검색 필터 — 4 entity type 공통 substring (label / fqn / statement) 매치.
  const q = searchQ.trim().toLowerCase();
  const filteredTerms = useMemo(
    () => q ? terms.filter(t =>
      t.fqn.toLowerCase().includes(q) ||
      t.label.toLowerCase().includes(q) ||
      t.aliases.some(a => a.toLowerCase().includes(q))
    ) : terms, [terms, q],
  );
  const filteredActions = useMemo(
    () => q ? actions.filter(a =>
      a.fqn.toLowerCase().includes(q) ||
      a.label.toLowerCase().includes(q) ||
      a.aliases.some(x => x.toLowerCase().includes(q))
    ) : actions, [actions, q],
  );
  const filteredRules = useMemo(
    () => q ? rules.filter(r =>
      r.fqn.toLowerCase().includes(q) ||
      r.statement.toLowerCase().includes(q)
    ) : rules, [rules, q],
  );
  const filteredAnchors = useMemo(
    () => q ? anchors.filter(a =>
      a.id.toLowerCase().includes(q) ||
      a.anchor_locator.toLowerCase().includes(q) ||
      a.target_action_fqn.toLowerCase().includes(q) ||
      a.target_slot.toLowerCase().includes(q)
    ) : anchors, [anchors, q],
  );

  // 도메인 별 그루핑 (filtered terms / actions).
  const termsByDomain = useMemo(() => groupBy(filteredTerms, (t) => t.domain || "(도메인 없음)"), [filteredTerms]);
  const actionsByDomain = useMemo(() => groupBy(filteredActions, (a) => a.domain || "(도메인 없음)"), [filteredActions]);

  const atomicTerms = filteredTerms.filter((t) => t.kind === "atomic");
  const compositeTerms = filteredTerms.filter((t) => t.kind === "composite");

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
    <div className="flex flex-col h-full overflow-hidden text-[11.5px]">
      {/* 검색 바 — ModuleTree 와 동일 스타일 */}
      <div className="px-2 py-1.5 border-b border-border">
        <div className="relative group">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground/70 group-focus-within:text-foreground pointer-events-none transition-colors" />
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Term / Action / BR 검색"
            className="w-full h-7 pl-7 pr-7 text-[11.5px] rounded-md bg-muted/40 border border-transparent hover:border-border focus:border-primary focus:bg-card focus:outline-none transition-colors placeholder:text-muted-foreground/60"
          />
          {searchQ && (
            <button
              type="button"
              onClick={() => setSearchQ("")}
              title="검색어 지우기"
              className="absolute right-1 top-1/2 -translate-y-1/2 h-5 w-5 rounded inline-flex items-center justify-center hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <XIcon className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>
      {/* 헤더 — 합계 카운트 (필터 시 / 전체 표시) */}
      <div className="px-2 py-1.5 border-b border-border bg-muted/30 text-[10.5px] text-muted-foreground flex-shrink-0">
        {q ? (
          <>
            <strong className="text-foreground">{filteredTerms.length}</strong>/{terms.length} term ·{" "}
            <strong className="text-foreground">{filteredActions.length}</strong>/{actions.length} action ·{" "}
            <strong className="text-foreground">{filteredRules.length}</strong>/{rules.length} rule ·{" "}
            <strong className="text-foreground">{filteredAnchors.length}</strong>/{anchors.length} anchor
          </>
        ) : (
          <>
            {atomicTerms.length} atomic <HelpHint term="atomic" inline /> · {compositeTerms.length} composite <HelpHint term="composite" inline /> · {actions.length} action <HelpHint term="action" inline /> ·{" "}
            {rules.length} rule <HelpHint term="business_rule" inline /> · {anchors.length} anchor <HelpHint term="anchor" inline />
          </>
        )}
      </div>
      <div className="overflow-y-auto flex-1">
      {/* 본문 sections */}

      {/* === Terms === */}
      <SectionHeader
        section="terms"
        count={filteredTerms.length}
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
        count={filteredActions.length}
        sub={`confirmed ${filteredActions.filter((a) => a.verification_level !== "unmapped" && a.verification_level !== "draft").length} / draft ${filteredActions.filter((a) => a.verification_level === "draft").length}`}
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
        count={filteredRules.length}
        sub={`hard ${filteredRules.filter((r) => r.severity === "hard").length}`}
        expanded={expanded.has("rules")}
        onToggle={() => toggle("rules")}
      />
      {expanded.has("rules") && (
        <div className="pl-2 pb-1">
          {filteredRules.map((r) => (
            <BRRow key={r.fqn} r={r} onClick={() => setSelectedRule(r.fqn)} />
          ))}
        </div>
      )}

      {/* === AnchorBindings === */}
      <SectionHeader
        section="anchors"
        count={filteredAnchors.length}
        sub={`confirmed ${filteredAnchors.filter((a) => a.confirmed).length}`}
        expanded={expanded.has("anchors")}
        onToggle={() => toggle("anchors")}
      />
      {expanded.has("anchors") && (
        <div className="pl-2 pb-1">
          {filteredAnchors.map((a) => (
            <AnchorRow key={a.id} a={a} onClick={() => setSelectedAnchor(a.id)} />
          ))}
        </div>
      )}
      </div>
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
      <span className="truncate flex-1 min-w-0 font-mono">{t.label}</span>
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
      <span className="truncate flex-1 min-w-0 font-mono text-foreground">{a.label}</span>
      {confirmed ? (
        <span className="text-[9px] text-emerald-700 shrink-0" title={`confirmed (${lvl})`}>✓</span>
      ) : (
        <span className="text-[9px] text-amber-700 shrink-0" title="draft">·</span>
      )}
      <span className="text-[9px] text-muted-foreground font-mono shrink-0">{a.kind.slice(0, 4)}</span>
    </button>
  );
}

function BRRow({ r, onClick }: { r: BusinessRuleDTO; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left pl-3 pr-2 py-0.5 hover:bg-muted/40 transition-colors"
      title={`${r.fqn}\nseverity: ${r.severity}\n${r.statement}`}
    >
      <div className="flex items-center gap-1.5">
        <span className={cn(
          "w-1.5 h-1.5 rounded-sm shrink-0",
          r.severity === "hard" ? "bg-rose-500" : "bg-amber-500",
        )} />
        <span className="truncate flex-1 min-w-0 font-mono text-foreground text-[11px]">{prettyFqn(r.fqn, "rule")}</span>
        {r.confirmed && <span className="text-[9px] text-emerald-700 shrink-0">✓</span>}
      </div>
      <div className="pl-3 text-[10px] text-muted-foreground line-clamp-1 break-words">{r.statement}</div>
    </button>
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
        <span className="truncate flex-1 min-w-0 font-mono text-foreground text-[11px]">{a.anchor_locator}</span>
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
