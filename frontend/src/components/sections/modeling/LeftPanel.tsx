"use client";

import { useEffect, useState } from "react";
import { useWorkbench, type LeftTab } from "./store";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type AmbiguousCallSiteDTO,
  type UnmappedMethodDTO,
  type MappingQueueDTO,
} from "@/lib/api/ontology";
import {
  Check, X as XIcon, Loader2, Sparkles, Plus,
  FolderTree, Network, Inbox, RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { ModuleTree } from "./ModuleTree";
import { OntologyTab } from "./OntologyTab";
import { NewEntityModal } from "./NewEntityModal";
import { HelpHint } from "./HelpHint";

// 좌측 탭 — 코드 (패키지 트리) / 온톨로지 (Term/Action/BR/Anchor 모음) / 큐 (자동 추천 confirm).
const TABS: { id: LeftTab; label: string; Icon: LucideIcon }[] = [
  { id: "code", label: "코드", Icon: FolderTree },
  { id: "ontology", label: "온톨로지", Icon: Network },
  { id: "queue", label: "큐", Icon: Inbox },
];

export function LeftPanel() {
  const { leftTab, setLeftTab } = useWorkbench();
  const [newOpen, setNewOpen] = useState(false);
  // V7 마이그레이션 — 옛 leftTab 들어와 있으면 code 로 매핑
  const effectiveTab = (leftTab === "code" || leftTab === "ontology" || leftTab === "queue")
    ? leftTab
    : "code";

  return (
    <aside
      className="bg-card border-r border-border flex flex-col overflow-hidden"
      style={{ gridArea: "left" }}
    >
      {/* Main tab strip — VSCode-style: 모든 항목 같은 baseline, active 만 bottom underline */}
      <div className="flex items-stretch h-9 px-1 border-b border-border bg-card">
        {TABS.map((t) => {
          const active = effectiveTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setLeftTab(t.id)}
              className={cn(
                "relative flex items-center gap-1.5 px-3 text-[12px] transition-colors",
                active
                  ? "text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <t.Icon className="w-3.5 h-3.5" />
              {t.label}
              {active && (
                <span className="absolute inset-x-1 -bottom-px h-0.5 bg-primary rounded-full" />
              )}
            </button>
          );
        })}
        <div className="flex-1" />
        <button
          onClick={() => setNewOpen(true)}
          className="my-1.5 flex items-center gap-1 px-2 text-[11px] text-primary hover:bg-primary/10 rounded border border-primary/30 hover:border-primary/60 transition-colors"
          title="새 entity (Term / Action / BR / Anchor) 직접 추가"
        >
          <Plus className="w-3 h-3" />
          새로
        </button>
      </div>
      <div className="flex-1 overflow-hidden flex flex-col">
        {effectiveTab === "code" && <ModuleTree />}
        {effectiveTab === "ontology" && <OntologyTab />}
        {effectiveTab === "queue" && <QueueTab />}
      </div>
      <NewEntityModal open={newOpen} onOpenChange={setNewOpen} />
    </aside>
  );
}

// ── Queue Tab — Unmapped + Ambiguous ─────────────────────────────────
// ---------------------------------------------------------------------------
// QueueTab — P3-6 자동 매핑 추천 큐 + confirm/reject
// ---------------------------------------------------------------------------
type QueueSection = "term" | "action" | "realization" | "legacy";

function QueueTab() {
  const {
    activeRepoId, queueRefreshTick,
    selectedQueueItem, setSelectedQueueItem,
    setSelectedCodeType, setLeftTab,
    selectedCodeTypeFqn,
  } = useWorkbench();
  const [data, setData] = useState<MappingQueueDTO | null>(null);
  const [legacy, setLegacy] = useState<{
    unmapped: UnmappedMethodDTO[];
    ambig: AmbiguousCallSiteDTO[];
  }>({ unmapped: [], ambig: [] });
  const [section, setSection] = useState<QueueSection>("term");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);  // 진행 중인 row key
  const [recommendBusy, setRecommendBusy] = useState(false);
  const [recommendError, setRecommendError] = useState<string | null>(null);

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
  }, [activeRepoId, queueRefreshTick]);

  const rerecommend = async () => {
    setRecommendBusy(true);
    setRecommendError(null);
    try {
      await ontologyApi.recommendForRepo(activeRepoId, { persist: true });
      await reload();
    } catch (e) {
      setRecommendError(e instanceof Error ? e.message : String(e));
    } finally {
      setRecommendBusy(false);
    }
  };

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

  const sectionTabs: { id: QueueSection; label: string; count: number; color: string; helpTerm: string }[] = [
    { id: "term", label: "Term", count: data?.summary.terms ?? 0, color: "text-violet-400", helpTerm: "queue_term" },
    { id: "action", label: "Action", count: data?.summary.actions ?? 0, color: "text-orange-400", helpTerm: "queue_action" },
    { id: "realization", label: "Real", count: data?.summary.type_realizations ?? 0, color: "text-emerald-500", helpTerm: "queue_realization" },
    { id: "legacy", label: "Code", count: legacy.unmapped.length + legacy.ambig.length, color: "text-amber-500", helpTerm: "queue_legacy_code" },
  ];

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Queue subnav — 2-row. 배경/패딩 통일 + row 2 actions 는 segmented 그룹으로 묶어 떠있는 느낌 제거 */}
      <div className="border-b border-border bg-muted/30">
        {/* Row 1: 4 section pills (h=28) */}
        <div className="flex items-center h-7 px-1.5 gap-0.5">
          {sectionTabs.map((t) => {
            const active = section === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setSection(t.id)}
                className={cn(
                  "h-6 flex-1 min-w-0 px-1.5 rounded text-[11px] flex items-center justify-center gap-1 transition-colors",
                  active
                    ? "bg-card text-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-card/60 hover:text-foreground",
                )}
                title={`${t.label} 큐 · ${t.count}개 대기`}
              >
                <span>{t.label}</span>
                <span className={cn("font-mono text-[10px] tabular-nums", active ? t.color : "opacity-60")}>
                  {t.count}
                </span>
              </button>
            );
          })}
        </div>
        {/* Row 2: 큐 status summary 좌측 + utility actions 우측 — 폭 균형, 박스 제거 */}
        <div className="flex items-center justify-between h-6 px-2 text-[10px] text-muted-foreground">
          <span className="font-mono tabular-nums">
            <span className="text-foreground/80">{(data?.summary.total ?? 0) + (legacy.unmapped.length + legacy.ambig.length)}</span>
            <span className="text-muted-foreground/70"> 대기</span>
          </span>
          <div className="flex items-center gap-0.5">
            <HelpHint
              inline
              custom={{
                label: "큐 (Queue) 사용법",
                short: [
                  `Term ${data?.summary.terms ?? 0} — 추천된 BusinessTerm 후보 (confirm 대기)`,
                  `Action ${data?.summary.actions ?? 0} — Java method 추출 Action + Realization`,
                  `Real ${data?.summary.type_realizations ?? 0} — Term ↔ CodeType 매핑 (primary/partial)`,
                  `Code ${legacy.unmapped.length + legacy.ambig.length} — 정적 분석 미해결 (Unmapped + Ambiguous)`,
                  "",
                  "⚡ 재추천 — 자동 매핑 추천 재실행. confirmed entity 는 보존.",
                  "↻ — 백엔드에서 큐 데이터 새로고침.",
                ].join("\n"),
                example: "confirm → 즉시 ontology 편입 / reject → 후보 삭제",
              }}
            />
            <button
              onClick={() => void rerecommend()}
              disabled={recommendBusy}
              className="h-5 px-1.5 rounded inline-flex items-center gap-1 text-[10.5px] text-primary hover:bg-primary/10 transition-colors disabled:opacity-50"
              title="재추천 — 자동 매핑 추천 재실행 (confirmed entity 는 보존)"
            >
              {recommendBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              <span className="font-medium">재추천</span>
            </button>
            <button
              onClick={() => void reload()}
              className="h-5 w-5 rounded inline-flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
              title="새로고침"
            >
              {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>
      {recommendError && (
        <div className="px-2 py-1 bg-rose-500/10 border-b border-rose-500/30 text-[10px] text-rose-300">
          추천 실패: {recommendError}
        </div>
      )}

      <div className="overflow-y-auto flex-1">
        {section === "term" && (data?.terms ?? []).map((t) => (
          <QueueRow
            key={`term:${t.fqn}`}
            kind="🟣"
            title={t.label}
            subtitle={`${t.kind}${t.is_root_entity ? " · root" : ""}${t.struct_like_hint ? " · struct-like" : ""} · ${t.aliases.slice(0,2).join(", ")}`}
            tag={t.fqn}
            busy={busy === `term:${t.fqn}`}
            selected={selectedQueueItem?.kind === "term" && selectedQueueItem.id === t.fqn}
            onSelect={() => setSelectedQueueItem({ kind: "term", id: t.fqn })}
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
            selected={selectedQueueItem?.kind === "action" && selectedQueueItem.id === a.fqn}
            onSelect={() => setSelectedQueueItem({ kind: "action", id: a.fqn })}
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
            selected={selectedQueueItem?.kind === "realization" && selectedQueueItem.id === String(r.id)}
            onSelect={() => setSelectedQueueItem({ kind: "realization", id: String(r.id) })}
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
            {legacy.ambig.map((a) => {
              // ambig callsite → caller method 의 parent type 으로 navigate
              const parentType = a.call_site.caller_method_fqn.split("(")[0].split(".").slice(0, -1).join(".");
              const selected = parentType === selectedCodeTypeFqn;
              return (
                <button
                  key={a.call_site.id}
                  type="button"
                  onClick={() => {
                    if (parentType) {
                      setSelectedCodeType(parentType);
                      setLeftTab("code");
                    }
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 border-b border-border hover:bg-muted/40 transition-colors",
                    selected && "bg-primary/10 border-l-2 border-l-primary",
                  )}
                  title={`${a.call_site.caller_method_fqn} → ${a.call_site.callee_simple_name}`}
                >
                  <div className="text-[9.5px] text-amber-400 mb-1">🟡 CALLSITE</div>
                  <div className="text-[12px] truncate">{a.call_site.callee_simple_name} 모호 dispatch</div>
                  <div className="text-[10.5px] text-muted-foreground mt-0.5 truncate">
                    후보 {a.call_site.possible_runtime_types.length} · {a.call_site.analysis_source}
                  </div>
                  <div className="text-[9px] text-muted-foreground/70 font-mono truncate mt-0.5">
                    {a.call_site.caller_method_fqn.split(".").slice(-2).join(".")}
                  </div>
                </button>
              );
            })}
            {legacy.unmapped.map((u) => {
              const parentType = u.code_method.parent_type_fqn;
              const selected = parentType === selectedCodeTypeFqn;
              return (
                <button
                  key={u.code_method.fqn}
                  type="button"
                  onClick={() => {
                    if (parentType) {
                      setSelectedCodeType(parentType);
                      setLeftTab("code");
                    }
                  }}
                  className={cn(
                    "w-full text-left px-3 py-2 border-b border-border hover:bg-muted/40 transition-colors",
                    selected && "bg-primary/10 border-l-2 border-l-primary",
                  )}
                  title={u.code_method.fqn}
                >
                  <div className="text-[9.5px] text-orange-400 mb-1">🟠 UNMAPPED</div>
                  <div className="text-[12px] truncate">{u.code_method.fqn.split(".").pop()}</div>
                  <div className="text-[10.5px] text-muted-foreground mt-0.5 truncate">{u.reason}</div>
                  <div className="text-[9px] text-muted-foreground/70 font-mono truncate mt-0.5">
                    {parentType.split(".").pop()}
                  </div>
                </button>
              );
            })}
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
  kind, title, subtitle, tag, busy, onConfirm, onReject, onSelect, selected,
}: {
  kind: string;
  title: string;
  subtitle: string;
  tag: string;
  busy: boolean;
  onConfirm: () => void;
  onReject: () => void;
  onSelect?: () => void;
  selected?: boolean;
}) {
  return (
    <div className={cn(
      "px-2 py-1.5 border-b border-border hover:bg-muted/40 group",
      selected && "bg-primary/10 border-l-2 border-l-primary",
    )}>
      <div className="flex items-start gap-1.5">
        <span className="text-[10px] mt-0.5">{kind}</span>
        <button
          type="button"
          onClick={onSelect}
          className="flex-1 min-w-0 text-left cursor-pointer"
          title="우측 패널에 미리보기"
        >
          <div className="text-[12px] font-medium truncate">{title}</div>
          <div className="text-[10px] text-muted-foreground truncate">{subtitle}</div>
          <div className="text-[9px] text-muted-foreground/70 font-mono truncate" title={tag}>
            {tag}
          </div>
        </button>
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
