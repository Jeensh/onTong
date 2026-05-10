"use client";

import { useEffect, useState } from "react";
import { useWorkbench, type LeftTab } from "./store";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ActionDTO,
  type CodeTypeDTO,
  type TermDTO,
  type AmbiguousCallSiteDTO,
  type UnmappedMethodDTO,
  type MappingQueueDTO,
} from "@/lib/api/ontology";
import { Check, X as XIcon, Loader2 } from "lucide-react";
import { ModuleTree } from "./ModuleTree";
import { OntologyTab } from "./OntologyTab";

// 좌측 탭 — 코드 (패키지 트리) / 온톨로지 (Term/Action/BR/Anchor 모음) / 큐 (자동 추천 confirm).
const TABS: { id: LeftTab; label: string; icon: string }[] = [
  { id: "code", label: "코드", icon: "🗂" },
  { id: "ontology", label: "온톨로지", icon: "🧬" },
  { id: "queue", label: "큐", icon: "📥" },
];

export function LeftPanel() {
  const { leftTab, setLeftTab } = useWorkbench();
  // V7 마이그레이션 — 옛 leftTab 들어와 있으면 code 로 매핑
  const effectiveTab = (leftTab === "code" || leftTab === "ontology" || leftTab === "queue")
    ? leftTab
    : "code";

  return (
    <aside
      className="bg-card border-r border-border flex flex-col overflow-hidden"
      style={{ gridArea: "left" }}
    >
      <div className="flex border-b border-border px-1.5 pt-1.5 gap-0">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setLeftTab(t.id)}
            className={cn(
              "rounded-t px-2 py-1 text-[11px] border-b-2 transition-colors",
              effectiveTab === t.id
                ? "text-foreground border-primary bg-card"
                : "text-muted-foreground border-transparent hover:text-foreground",
            )}
          >
            <span className="mr-0.5">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-hidden flex flex-col">
        {effectiveTab === "code" && <ModuleTree />}
        {effectiveTab === "ontology" && <OntologyTab />}
        {effectiveTab === "queue" && <QueueTab />}
      </div>
    </aside>
  );
}

// ── Map landing — Top-down 진입점 ─────────────────────────────────────
function MapTab() {
  const { activeRepoId, setGraphMode } = useWorkbench();
  const [terms, setTerms] = useState<TermDTO[]>([]);
  const [actions, setActions] = useState<ActionDTO[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      ontologyApi.listTerms({ repo_id: activeRepoId }).catch(() => [] as TermDTO[]),
      ontologyApi.listActions({ repo_id: activeRepoId }).catch(() => [] as ActionDTO[]),
    ]).then(([t, a]) => {
      if (!cancelled) {
        setTerms(t);
        setActions(a);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [activeRepoId]);

  const domains = Array.from(
    new Set([...terms.map((t) => t.domain), ...actions.map((a) => a.domain)]),
  ).filter(Boolean);

  // 실제 데이터 비어있으면 mock domains 표시
  const displayDomains: { name: string; color: string; label: string }[] =
    domains.length > 0
      ? domains.map((d) => ({ name: d, color: "primary", label: d }))
      : [
          { name: "scm", color: "primary", label: "공급망 관리 (SCM)" },
          { name: "quality", color: "violet-400", label: "품질 관리 (Quality)" },
          { name: "production", color: "orange-400", label: "생산 관리 (Production)" },
          { name: "logistics", color: "pink-400", label: "물류 (Logistics)" },
        ];

  return (
    <div className="overflow-y-auto p-2 flex-1">
      <p className="px-2 py-1 text-[11px] text-muted-foreground">
        📍 Top-down 진입 — 도메인 → 그룹 → Action
      </p>
      {displayDomains.map((d) => {
        const dActions = actions.filter((a) => a.domain === d.name);
        const dTerms = terms.filter((t) => t.domain === d.name);
        return (
          <div
            key={d.name}
            onClick={() => setGraphMode(true)}
            className="bg-background border border-border rounded-md p-3 my-1.5 cursor-pointer hover:border-primary"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs px-1.5 py-px rounded-full border text-primary border-primary bg-primary/10">
                {d.name.toUpperCase()}
              </span>
              <span className="text-[12.5px] font-semibold">{d.label}</span>
              <span className="ml-auto text-[10.5px] text-muted-foreground">
                {dActions.length} actions · {dTerms.length} terms
              </span>
            </div>
            <div className="flex flex-wrap gap-1">
              {dActions.slice(0, 4).map((a) => (
                <span
                  key={a.fqn}
                  className="text-[10.5px] bg-muted border border-border px-1.5 py-px rounded text-muted-foreground"
                >
                  {a.label}
                </span>
              ))}
              {dActions.length > 4 && (
                <span className="text-[10.5px] text-muted-foreground">+{dActions.length - 4}</span>
              )}
            </div>
          </div>
        );
      })}
      <div className="px-2 mt-2 text-[10.5px] text-muted-foreground leading-relaxed">
        💡 클릭 → 🌐 Graph 모드 (Top-down 탐색)
        <br />
        💡 ⌘K 로 직접 검색
      </div>
    </div>
  );
}

// ── Code Tree ────────────────────────────────────────────────────────
function CodeTreeTab() {
  const { activeRepoId, setSelectedCodeType, selectedCodeTypeFqn } = useWorkbench();
  const [types, setTypes] = useState<CodeTypeDTO[]>([]);
  const [filter, setFilter] = useState<string>("domain");

  useEffect(() => {
    let cancelled = false;
    ontologyApi
      .listCodeTypes({ repo_id: activeRepoId, role: filter === "all" ? undefined : filter })
      .catch(() => [] as CodeTypeDTO[])
      .then((d) => !cancelled && setTypes(d));
    return () => {
      cancelled = true;
    };
  }, [activeRepoId, filter]);

  return (
    <>
      <div className="px-2 py-1 border-b border-border flex flex-wrap gap-1">
        {["domain", "framework", "infra", "all"].map((r) => (
          <button
            key={r}
            onClick={() => setFilter(r)}
            className={cn(
              "text-[10px] px-1.5 py-0.5 rounded border",
              filter === r ? "border-primary text-primary" : "border-border text-muted-foreground",
            )}
          >
            {r}
          </button>
        ))}
      </div>
      <div className="p-1 overflow-y-auto flex-1 text-[12px]">
        {types.length === 0 && (
          <p className="text-muted-foreground p-2">
            (Java repo import 후 표시 — backend 에서 데이터 가져옵니다)
          </p>
        )}
        {types.map((t) => (
          <div
            key={t.fqn}
            onClick={() => setSelectedCodeType(t.fqn)}
            className={cn(
              "flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-muted",
              selectedCodeTypeFqn === t.fqn && "bg-primary/15 text-primary",
            )}
          >
            <span className="text-[10px] text-amber-400 border border-amber-400 bg-amber-400/10 px-1 rounded">
              {t.kind === "interface" ? "I" : t.kind === "abstract_class" ? "A" : "C"}
            </span>
            <span className="truncate">{t.simple_name}</span>
            {t.role !== "domain" && (
              <span className="ml-auto text-[10px] text-muted-foreground">{t.role}</span>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

// ── Domain Tree ──────────────────────────────────────────────────────
function DomainTreeTab() {
  const { activeRepoId, setSelectedTerm, selectedTermFqn } = useWorkbench();
  const [terms, setTerms] = useState<TermDTO[]>([]);

  useEffect(() => {
    let cancelled = false;
    ontologyApi
      .listTerms({ repo_id: activeRepoId })
      .catch(() => [] as TermDTO[])
      .then((d) => !cancelled && setTerms(d));
    return () => {
      cancelled = true;
    };
  }, [activeRepoId]);

  return (
    <div className="p-1 overflow-y-auto flex-1 text-[12px]">
      {terms.length === 0 && (
        <p className="text-muted-foreground p-2">(매뉴얼 import 후 표시)</p>
      )}
      {terms.map((t) => (
        <div
          key={t.fqn}
          onClick={() => setSelectedTerm(t.fqn)}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-muted",
            selectedTermFqn === t.fqn && "bg-primary/15 text-primary",
          )}
        >
          <span className="text-[10px] text-violet-400 border border-violet-400 bg-violet-400/10 px-1 rounded">
            {t.kind === "atomic" ? "a" : "T"}
          </span>
          <span className="truncate">{t.label}</span>
          {t.is_root_entity && <span className="ml-auto text-[9.5px] text-muted-foreground">root</span>}
        </div>
      ))}
    </div>
  );
}

// ── Action Tree ──────────────────────────────────────────────────────
function ActionTreeTab() {
  const { activeRepoId, setSelectedAction, selectedActionFqn } = useWorkbench();
  const [actions, setActions] = useState<ActionDTO[]>([]);

  useEffect(() => {
    let cancelled = false;
    ontologyApi
      .listActions({ repo_id: activeRepoId })
      .catch(() => [] as ActionDTO[])
      .then((d) => !cancelled && setActions(d));
    return () => {
      cancelled = true;
    };
  }, [activeRepoId]);

  return (
    <div className="p-1 overflow-y-auto flex-1 text-[12px]">
      {actions.length === 0 && (
        <p className="text-muted-foreground p-2">(코드 분석 + 매핑 후 표시)</p>
      )}
      {actions.map((a) => (
        <div
          key={a.fqn}
          onClick={() => setSelectedAction(a.fqn)}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-muted",
            selectedActionFqn === a.fqn && "bg-primary/15 text-primary",
          )}
        >
          <span className="text-[10px] text-orange-400 border border-orange-400 bg-orange-400/10 px-1 rounded">
            act
          </span>
          <span className="truncate">{a.label}</span>
          <span className="ml-auto text-[9px] text-muted-foreground">
            {a.verification_level
              .split("_")
              .map((s) => s[0])
              .join("")
              .toUpperCase()}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Queue Tab — Unmapped + Ambiguous ─────────────────────────────────
// ---------------------------------------------------------------------------
// QueueTab — P3-6 자동 매핑 추천 큐 + confirm/reject
// ---------------------------------------------------------------------------
type QueueSection = "term" | "action" | "realization" | "legacy";

function QueueTab() {
  const { activeRepoId } = useWorkbench();
  const [data, setData] = useState<MappingQueueDTO | null>(null);
  const [legacy, setLegacy] = useState<{
    unmapped: UnmappedMethodDTO[];
    ambig: AmbiguousCallSiteDTO[];
  }>({ unmapped: [], ambig: [] });
  const [section, setSection] = useState<QueueSection>("term");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);  // 진행 중인 row key

  const reload = async () => {
    setLoading(true);
    try {
      const [q, u, a] = await Promise.all([
        ontologyApi.getMappingQueue(activeRepoId).catch(() => null),
        ontologyApi.listUnmappedMethods(activeRepoId).catch(() => [] as UnmappedMethodDTO[]),
        ontologyApi.listAmbiguousCallSites(activeRepoId).catch(() => [] as AmbiguousCallSiteDTO[]),
      ]);
      setData(q);
      setLegacy({ unmapped: u, ambig: a });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRepoId]);

  const doAction = async (
    key: string,
    fn: () => Promise<unknown>,
    optimistic: () => void,
  ) => {
    setBusy(key);
    optimistic();   // 큐에서 즉시 제거 (UI 반응성)
    try {
      await fn();
    } catch (e) {
      console.error("queue action failed", e);
      void reload(); // 실패 시 서버 진실로 복구
    } finally {
      setBusy(null);
    }
  };

  const sectionTabs: { id: QueueSection; label: string; count: number; color: string }[] = [
    { id: "term", label: "Term", count: data?.summary.terms ?? 0, color: "text-violet-400" },
    { id: "action", label: "Action", count: data?.summary.actions ?? 0, color: "text-orange-400" },
    { id: "realization", label: "Real", count: data?.summary.type_realizations ?? 0, color: "text-emerald-500" },
    { id: "legacy", label: "Code", count: legacy.unmapped.length + legacy.ambig.length, color: "text-amber-500" },
  ];

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="px-2 py-1 border-b border-border flex items-center gap-1 text-[10px]">
        {sectionTabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setSection(t.id)}
            className={cn(
              "px-1.5 py-0.5 rounded border transition-colors flex items-center gap-1",
              section === t.id
                ? "bg-muted border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            <span>{t.label}</span>
            <span className={cn("font-mono", section === t.id && t.color)}>{t.count}</span>
          </button>
        ))}
        <button
          onClick={() => void reload()}
          className="ml-auto px-1.5 py-0.5 rounded text-muted-foreground hover:text-foreground text-[10px]"
          title="새로고침"
        >
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : "↻"}
        </button>
      </div>

      <div className="overflow-y-auto flex-1">
        {section === "term" && (data?.terms ?? []).map((t) => (
          <QueueRow
            key={`term:${t.fqn}`}
            kind="🟣"
            title={t.label}
            subtitle={`${t.kind}${t.is_root_entity ? " · root" : ""}${t.struct_like_hint ? " · struct-like" : ""} · ${t.aliases.slice(0,2).join(", ")}`}
            tag={t.fqn}
            busy={busy === `term:${t.fqn}`}
            onConfirm={() => doAction(
              `term:${t.fqn}`,
              () => ontologyApi.confirmTerm(activeRepoId, t.fqn),
              () => setData((d) => d && ({ ...d, terms: d.terms.filter((x) => x.fqn !== t.fqn), summary: { ...d.summary, terms: d.summary.terms - 1, total: d.summary.total - 1 } })),
            )}
            onReject={() => doAction(
              `term:${t.fqn}`,
              () => ontologyApi.rejectTerm(activeRepoId, t.fqn),
              () => setData((d) => d && ({ ...d, terms: d.terms.filter((x) => x.fqn !== t.fqn), summary: { ...d.summary, terms: d.summary.terms - 1, total: d.summary.total - 1 } })),
            )}
          />
        ))}
        {section === "action" && (data?.actions ?? []).map((a) => (
          <QueueRow
            key={`action:${a.fqn}`}
            kind="🟠"
            title={a.label}
            subtitle={`${a.kind}${a.declared_on_term ? ` · on ${a.declared_on_term.split(".").pop()}` : ""} · ${a.realization_count} real · ${a.verification_level}`}
            tag={a.fqn}
            busy={busy === `action:${a.fqn}`}
            onConfirm={() => doAction(
              `action:${a.fqn}`,
              () => ontologyApi.confirmActionCandidate(activeRepoId, a.fqn),
              () => setData((d) => d && ({ ...d, actions: d.actions.filter((x) => x.fqn !== a.fqn), summary: { ...d.summary, actions: d.summary.actions - 1, total: d.summary.total - 1 } })),
            )}
            onReject={() => doAction(
              `action:${a.fqn}`,
              () => ontologyApi.rejectActionCandidate(activeRepoId, a.fqn),
              () => setData((d) => d && ({ ...d, actions: d.actions.filter((x) => x.fqn !== a.fqn), summary: { ...d.summary, actions: d.summary.actions - 1, total: d.summary.total - 1 } })),
            )}
          />
        ))}
        {section === "realization" && (data?.type_realizations ?? []).map((r) => (
          <QueueRow
            key={`real:${r.id}`}
            kind={r.scope === "partial" ? "🟡" : "🟢"}
            title={`${r.code_type_fqn.split(".").pop()} → ${r.term_fqn.split(".").pop()}`}
            subtitle={`${r.scope.toUpperCase()} · conf=${r.confidence.toFixed(2)} · ${r.rationale.slice(0, 60)}`}
            tag={`tr#${r.id}`}
            busy={busy === `real:${r.id}`}
            onConfirm={() => doAction(
              `real:${r.id}`,
              () => ontologyApi.confirmRealization(activeRepoId, r.id),
              () => setData((d) => d && ({ ...d, type_realizations: d.type_realizations.filter((x) => x.id !== r.id), summary: { ...d.summary, type_realizations: d.summary.type_realizations - 1, total: d.summary.total - 1 } })),
            )}
            onReject={() => doAction(
              `real:${r.id}`,
              () => ontologyApi.rejectRealization(activeRepoId, r.id),
              () => setData((d) => d && ({ ...d, type_realizations: d.type_realizations.filter((x) => x.id !== r.id), summary: { ...d.summary, type_realizations: d.summary.type_realizations - 1, total: d.summary.total - 1 } })),
            )}
          />
        ))}
        {section === "legacy" && (
          <>
            {legacy.ambig.map((a) => (
              <div key={a.call_site.id} className="px-3 py-2 border-b border-border">
                <div className="text-[9.5px] text-amber-400 mb-1">🟡 CALLSITE</div>
                <div className="text-[12px]">{a.call_site.callee_simple_name} 모호 dispatch</div>
                <div className="text-[10.5px] text-muted-foreground mt-0.5 truncate">
                  후보 {a.call_site.possible_runtime_types.length} · {a.call_site.analysis_source}
                </div>
              </div>
            ))}
            {legacy.unmapped.map((u) => (
              <div key={u.code_method.fqn} className="px-3 py-2 border-b border-border">
                <div className="text-[9.5px] text-orange-400 mb-1">🟠 UNMAPPED</div>
                <div className="text-[12px] truncate">{u.code_method.fqn}</div>
                <div className="text-[10.5px] text-muted-foreground mt-0.5">{u.reason}</div>
              </div>
            ))}
            {legacy.unmapped.length === 0 && legacy.ambig.length === 0 && (
              <p className="text-muted-foreground p-3 text-[12px]">코드 큐 비어있음</p>
            )}
          </>
        )}
        {!loading && section !== "legacy" && currentSectionEmpty(data, section) && (
          <p className="text-muted-foreground p-3 text-[12px]">
            {section === "term" && "Term 후보 없음 — Import + 추천 매핑 persist 후 표시"}
            {section === "action" && "Action 후보 없음 — Import + 추천 매핑 persist 후 표시"}
            {section === "realization" && "TypeRealization 후보 없음"}
          </p>
        )}
      </div>
    </div>
  );
}

function currentSectionEmpty(data: MappingQueueDTO | null, section: QueueSection): boolean {
  if (!data) return true;
  if (section === "term") return data.terms.length === 0;
  if (section === "action") return data.actions.length === 0;
  if (section === "realization") return data.type_realizations.length === 0;
  return false;
}

function QueueRow({
  kind, title, subtitle, tag, busy, onConfirm, onReject,
}: {
  kind: string;
  title: string;
  subtitle: string;
  tag: string;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  return (
    <div className="px-2 py-1.5 border-b border-border hover:bg-muted/40 group">
      <div className="flex items-start gap-1.5">
        <span className="text-[10px] mt-0.5">{kind}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[12px] font-medium truncate">{title}</div>
          <div className="text-[10px] text-muted-foreground truncate">{subtitle}</div>
          <div className="text-[9px] text-muted-foreground/70 font-mono truncate" title={tag}>
            {tag}
          </div>
        </div>
        <div className="flex flex-col gap-0.5 opacity-60 group-hover:opacity-100 transition-opacity">
          <button
            onClick={onConfirm}
            disabled={busy}
            className="rounded p-1 hover:bg-emerald-500/20 hover:text-emerald-500 text-muted-foreground transition disabled:opacity-30"
            title="confirm"
          >
            <Check className="w-3 h-3" />
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="rounded p-1 hover:bg-destructive/20 hover:text-destructive text-muted-foreground transition disabled:opacity-30"
            title="reject"
          >
            <XIcon className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
