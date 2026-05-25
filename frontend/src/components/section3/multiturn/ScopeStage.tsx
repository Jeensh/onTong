"use client";

/**
 * Phase 18 — Stage 2 (영향 영역) scope panel.
 *
 * 사용자 vision: 선택한 candidate (Gate I confirm 후) 의 영향 영역을 한 눈에.
 * 단일 method 가 아니라 *모든 관련 entity*:
 *   - primary action (선택된 것)
 *   - declared_on_term (BusinessTerm)
 *   - sibling actions (같은 term 의 다른 action 들)
 *   - callers (caller graph)
 *   - related business_rules (term 기반)
 *
 * MVP (Phase 18a): list view only + 자동 Test/Mock 제외 (16D W4 동기화)
 * 후속 (Phase 18b): graph view toggle + check/uncheck 으로 simulate scope 조정
 */

import { useEffect, useState } from "react";
import { GitBranch, Link2, Users, BookOpen, FlaskConical, AlertTriangle, Loader2, ChevronRight, ChevronDown } from "lucide-react";
import { getScope, type ScopeEntityView } from "@/lib/section3/multiturn";

const KIND_META: Record<
  string, { label: string; Icon: typeof Link2; cls: string }
> = {
  action: { label: "Action",  Icon: GitBranch, cls: "text-purple-700 bg-purple-50 border-purple-200" },
  caller: { label: "Caller",  Icon: Users,     cls: "text-sky-700 bg-sky-50 border-sky-200" },
  term:   { label: "Term",    Icon: Link2,     cls: "text-pink-700 bg-pink-50 border-pink-200" },
  rule:   { label: "Rule",    Icon: BookOpen,  cls: "text-amber-700 bg-amber-50 border-amber-200" },
};

interface Props {
  selected: {
    action_fqn: string;
    code_method_fqn: string;
    declared_on_term: string | null;
  };
  repoId: string;
  /** Stage 3 이미 진행됐는지 → true 면 collapsed. */
  collapsed: boolean;
}

export function ScopeStage({ selected, repoId, collapsed }: Props) {
  const [entities, setEntities] = useState<ScopeEntityView[] | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["action", "caller", "term", "rule"]));

  useEffect(() => {
    let alive = true;
    setEntities(null);
    setErr(null);
    getScope({
      action_fqn: selected.action_fqn,
      code_method_fqn: selected.code_method_fqn,
      declared_on_term: selected.declared_on_term,
      repo_id: repoId,
    })
      .then((r) => { if (alive) { setEntities(r.entities); setCounts(r.counts); } })
      .catch((e) => { if (alive) setErr(String(e)); });
    return () => { alive = false; };
  }, [selected.action_fqn, selected.code_method_fqn, selected.declared_on_term, repoId]);

  const toggleKind = (kind: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
  };

  if (collapsed) {
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <ChevronRight size={12} className="shrink-0" />
        <span className="text-emerald-600 font-medium">✓ Stage 2 영향 영역</span>
        <span>·</span>
        <span className="font-mono">
          {Object.entries(counts).map(([k, v]) => `${k}:${v}`).join(" / ")}
          {total === 0 && "0 entities"}
        </span>
      </div>
    );
  }

  if (err) {
    return (
      <div className="text-[11px] text-red-600 px-3 py-2 border border-red-200 bg-red-50 rounded">
        영향 영역 로딩 실패: {err}
      </div>
    );
  }

  if (entities === null) {
    return (
      <div className="flex items-center gap-2 text-[12px] text-muted-foreground px-3 py-2">
        <Loader2 size={14} className="animate-spin" />
        영향 영역 분석 중…
      </div>
    );
  }

  // group by kind
  const byKind: Record<string, ScopeEntityView[]> = {};
  for (const e of entities) {
    if (!byKind[e.kind]) byKind[e.kind] = [];
    byKind[e.kind].push(e);
  }

  const total = entities.length;
  const inScope = entities.filter((e) => e.in_scope_default).length;
  const excluded = total - inScope;

  return (
    <div className="space-y-2">
      {/* Summary line */}
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground border-b border-border/30 pb-2">
        <span className="font-medium text-foreground">총 {total} 엔티티</span>
        {Object.entries(counts).map(([k, v]) => {
          const meta = KIND_META[k];
          if (!meta) return null;
          return (
            <span key={k} className="flex items-center gap-1">
              <meta.Icon size={11} />
              <span>{meta.label} {v}</span>
            </span>
          );
        })}
        {excluded > 0 && (
          <span className="ml-auto flex items-center gap-1 text-rose-600">
            <FlaskConical size={11} />
            Test 의심 {excluded}건 자동 제외
          </span>
        )}
      </div>

      {/* Grouped list */}
      {Object.entries(byKind).map(([kind, items]) => {
        const meta = KIND_META[kind] ?? KIND_META.action;
        const isOpen = expanded.has(kind);
        return (
          <div key={kind} className="border border-border/40 rounded bg-card/30">
            <button
              type="button"
              onClick={() => toggleKind(kind)}
              className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-muted/30 transition-colors"
            >
              {isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
              <meta.Icon size={12} />
              <span className="text-[11px] font-semibold">{meta.label}</span>
              <span className="text-[10px] text-muted-foreground">({items.length})</span>
            </button>
            {isOpen && (
              <div className="border-t border-border/30">
                {items.map((e) => (
                  <div
                    key={`${e.kind}-${e.fqn}`}
                    className={`flex items-baseline gap-2 px-3 py-1.5 text-[11px] border-b border-border/20 last:border-b-0 ${
                      e.in_scope_default ? "" : "opacity-50"
                    }`}
                  >
                    <input
                      type="checkbox"
                      defaultChecked={e.in_scope_default}
                      className="shrink-0"
                      title="(Phase 18b — 후속에서 simulate scope 조정에 연결)"
                      readOnly
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="font-mono text-foreground truncate">
                          {e.label}
                        </span>
                        {Boolean(e.meta?.primary) && (
                          <span className="text-[9px] uppercase text-purple-600 font-semibold tracking-wider shrink-0">
                            primary
                          </span>
                        )}
                        {Boolean(e.meta?.test_suspect) && (
                          <span className="text-[9px] inline-flex items-center gap-0.5 px-1 py-0.5 rounded border bg-rose-50 text-rose-700 border-rose-200 shrink-0">
                            <FlaskConical size={9} />
                            Test
                          </span>
                        )}
                        {e.meta?.severity != null && (
                          <span className="text-[9px] uppercase text-amber-600 font-mono shrink-0">
                            {String(e.meta.severity)}
                          </span>
                        )}
                      </div>
                      {e.detail && (
                        <div className="text-[10px] font-mono text-muted-foreground/80 truncate">
                          {e.detail}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      <div className="text-[10px] text-muted-foreground flex items-center gap-1 pt-1">
        <AlertTriangle size={10} />
        Phase 18 MVP — 영역 visualization 만. Phase 18b 에서 체크박스가 simulate scope 에 반영.
      </div>
    </div>
  );
}
