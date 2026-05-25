"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";
import {
  ontologyApi,
  type ActionDTO,
  type AnchorBindingDTO,
  type BusinessRuleDTO,
  type CallSiteDTO,
  type CodeMethodDTO,
  type CodeTypeDTO,
  type MemoKind,
} from "@/lib/api/ontology";
import {
  Loader2, FileCode, PhoneOutgoing, Waves, StickyNote, Columns2,
  Layers, Target, ArrowRight,
  type LucideIcon,
} from "lucide-react";
import { HelpHint } from "./HelpHint";
import { JavaCode } from "./JavaCode";
import { QueuePreviewPanel } from "./QueuePreviewPanel";
import { prettyFqn, shortName } from "@/lib/modeling/fqn";
import { stripPlaceholderTrailer } from "@/lib/modeling/description";

const TABS: { id: string; label: string; sub?: string; Icon: LucideIcon; hint: string | null; title?: string }[] = [
  { id: "code",     label: "코드",                       Icon: FileCode,      hint: null,        title: "이 entity 의 코드 본체" },
  { id: "callsite", label: "호출",                       Icon: PhoneOutgoing, hint: "call_site", title: "이 메서드를 부르는 곳 (caller, 영향 반경) + 이 메서드가 부르는 곳 (callee, 의존)" },
  { id: "impact",   label: "관련",                       Icon: Waves,         hint: null,        title: "이 entity 와 연결된 다른 ontology 노드 (Action / BR / Term / Anchor)" },
  { id: "memo",     label: "메모",                       Icon: StickyNote,    hint: null,        title: "사용자 자유 메모 (ontology 본체 무관)" },
];

/**
 * 우측 사이드바 — 좌측 selection 에 따라 4 탭 content 가 바뀜.
 *
 * - Action 선택 시: 코드/호출지점/영향/매뉴얼 모두 의미 있음
 * - Term/CodeType/BR/Anchor 선택 시: 일부 탭만 활성, 나머지 "이 entity 에 적용 안 됨"
 * - 미선택: "선택 후 표시" 안내
 */
export function RightPanel() {
  const {
    rightWidth, setRightWidth, setMainMode,
    selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn, selectedRuleFqn, selectedAnchorId,
    selectedQueueItem,
  } = useWorkbench();
  const [activeTab, setActiveTab] = useState<string>("code");
  const dragRef = useRef<HTMLDivElement>(null);

  const selection = useMemo(() => {
    if (selectedActionFqn) return { kind: "action" as const, id: selectedActionFqn };
    if (selectedCodeTypeFqn) return { kind: "codeType" as const, id: selectedCodeTypeFqn };
    if (selectedTermFqn) return { kind: "term" as const, id: selectedTermFqn };
    if (selectedRuleFqn) return { kind: "rule" as const, id: selectedRuleFqn };
    if (selectedAnchorId) return { kind: "anchor" as const, id: selectedAnchorId };
    return null;
  }, [selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn, selectedRuleFqn, selectedAnchorId]);

  useEffect(() => {
    const handle = dragRef.current;
    if (!handle) return;
    let dragging = false;
    const onDown = (e: MouseEvent) => {
      dragging = true;
      document.body.style.cursor = "col-resize";
      e.preventDefault();
    };
    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      setRightWidth(window.innerWidth - e.clientX);
    };
    const onUp = () => {
      dragging = false;
      document.body.style.cursor = "";
    };
    handle.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      handle.removeEventListener("mousedown", onDown);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [setRightWidth]);

  // 큐 row 가 선택된 상태면 QueuePreviewPanel 이 RightPanel 전체 차지 (탭/breadcrumb 모두 숨김).
  if (selectedQueueItem) {
    return (
      <aside
        className="bg-card border-l border-border flex flex-col overflow-hidden relative min-w-0"
        style={{ gridArea: "right", width: rightWidth }}
      >
        <div
          ref={dragRef}
          className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary z-10"
          title="드래그로 너비 조정"
        />
        <QueuePreviewPanel />
      </aside>
    );
  }

  return (
    <aside
      className="bg-card border-l border-border flex flex-col overflow-hidden relative min-w-0"
      style={{ gridArea: "right", width: rightWidth }}
    >
      <div
        ref={dragRef}
        className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary z-10"
        title="드래그로 너비 조정"
      />
      {/* 탭 strip — MainPanel mode tabs / LeftPanel tab strip 과 동일 패턴 (h-9 + 아이콘 + underline active) */}
      <div className="flex items-stretch h-9 px-1 border-b border-border shrink-0">
        {TABS.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              title={t.title}
              className={cn(
                "relative flex items-center gap-1 px-2 text-[11.5px] transition-colors",
                active
                  ? "text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <t.Icon className={cn("w-3.5 h-3.5", active ? "text-primary" : "text-muted-foreground/70")} />
              {t.label}
              {t.sub && (
                <span className={cn(
                  "text-[9px] tracking-tight",
                  active ? "text-primary/70" : "text-muted-foreground/60",
                )}>{t.sub}</span>
              )}
              {t.hint && <HelpHint term={t.hint} inline />}
              {active && (
                <span className="absolute inset-x-1 -bottom-px h-0.5 bg-primary rounded-full" />
              )}
            </button>
          );
        })}
      </div>

      {/* selection breadcrumb (선택 있을 때만 노출 — 비어있으면 hero 만) */}
      {selection && (
        <div className="h-7 px-2.5 border-b border-border bg-muted/40 flex gap-1.5 items-center text-[10.5px] shrink-0">
          <span className="truncate min-w-0 flex-1" title={selection.id}>
            <span className="text-muted-foreground">선택</span>{" "}
            <span className="font-mono text-foreground">{shortName(selection.id)}</span>{" "}
            <span className="text-muted-foreground/70">({selection.kind})</span>
          </span>
          {selectedActionFqn && (
            <button
              onClick={() => setMainMode("split")}
              className="h-5 px-2 rounded text-[10.5px] border border-primary/40 text-primary hover:bg-primary/10 hover:border-primary shrink-0 inline-flex items-center gap-1 transition-colors"
              title="↕ Split mode 로"
            >
              <Columns2 className="w-3 h-3" />
              Split
            </button>
          )}
        </div>
      )}

      {/* 본문 */}
      <div className={cn("overflow-y-auto flex-1 min-w-0", selection ? "p-2.5 text-xs" : "")}>
        {!selection && <RightPanelEmptyState />}
        {selection && activeTab === "code" && <TabCode selection={selection} />}
        {selection && activeTab === "callsite" && <TabCallSite selection={selection} />}
        {selection && activeTab === "impact" && <TabImpact selection={selection} />}
        {selection && activeTab === "memo" && <TabMemo selection={selection} />}
      </div>
    </aside>
  );
}

function RightPanelEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 py-10 text-center">
      <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-2.5">
        <FileCode className="w-4 h-4 text-primary/70" />
      </div>
      <div className="text-[12px] font-medium text-foreground mb-1">컨텍스트 패널</div>
      <div className="text-[11px] text-muted-foreground max-w-[200px] leading-relaxed">
        좌측 트리에서 entity 선택 시
        <span className="font-medium text-foreground"> 코드 · 호출지점 · 영향 · 메모</span> 가 표시됩니다.
      </div>
    </div>
  );
}

type Selection = {
  kind: "action" | "codeType" | "term" | "rule" | "anchor";
  id: string;
};

// ─────────────────────────────────────────────────────────────────────────
// 탭 1 — 코드 본체
// ─────────────────────────────────────────────────────────────────────────
function TabCode({ selection }: { selection: Selection }) {
  const [content, setContent] = useState<{ method?: CodeMethodDTO; codeType?: CodeTypeDTO; action?: ActionDTO } | null>(null);
  const [loading, setLoading] = useState(false);
  const { activeRepoId } = useWorkbench();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setContent(null);
    (async () => {
      try {
        if (selection.kind === "action") {
          const a = await ontologyApi.getAction(selection.id);
          if (!a) return;
          const r = a.realizations.find(x => x.scope === "primary") ?? a.realizations[0];
          // workflow action 은 realizations=[] 가 정상 — sub_actions chain 으로 fallback.
          // description 에 "자동 추론 — com.example..." 형식이 있으면 그 fqn 으로도 시도.
          if (!r) {
            // description 에서 method fqn 추출 시도 — "자동 추론 — com.example.X.Y(...)"
            const m = a.description?.match(/—\s*([\w.$]+\.[\w$]+\([^)]*\))/);
            const inferredMethodFqn = m?.[1];
            if (inferredMethodFqn) {
              const parent = parentTypeFqnOfMethod(inferredMethodFqn);
              if (parent) {
                const ct = await ontologyApi.getCodeType(parent);
                const mm = ct?.methods.find(x => x.fqn === inferredMethodFqn);
                if (!cancelled) setContent({ method: mm, codeType: ct ?? undefined, action: a });
                return;
              }
            }
            // 그래도 못 찾으면 action 만 setContent — WorkflowBrief 가 렌더링.
            if (!cancelled) setContent({ action: a });
            return;
          }
          const parent = parentTypeFqnOfMethod(r.code_method_fqn);
          if (!parent) return;
          const ct = await ontologyApi.getCodeType(parent);
          const m = ct?.methods.find(mm => mm.fqn === r.code_method_fqn);
          if (!cancelled) setContent({ method: m, codeType: ct ?? undefined, action: a });
        } else if (selection.kind === "codeType") {
          const ct = await ontologyApi.getCodeType(selection.id);
          if (!cancelled) setContent({ codeType: ct ?? undefined });
        } else if (selection.kind === "anchor") {
          const all = await ontologyApi.listAnchorBindings({ repo_id: activeRepoId });
          const a = all.find(x => x.id === selection.id);
          if (!a) return;
          const parent = parentTypeFqnOfMethod(a.code_method_fqn);
          if (!parent) return;
          const ct = await ontologyApi.getCodeType(parent);
          const m = ct?.methods.find(mm => mm.fqn === a.code_method_fqn);
          if (!cancelled) setContent({ method: m, codeType: ct ?? undefined });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id]);

  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;

  if (selection.kind === "term" || selection.kind === "rule") {
    return (
      <p className="text-muted-foreground p-2">
        {selection.kind === "term" ? "Term" : "BusinessRule"} 은 코드 method 와 직접 매핑 안 됨.
        대신 <strong className="text-foreground">호출지점</strong> 또는 <strong className="text-foreground">영향</strong> 탭 참고.
      </p>
    );
  }

  if (!content) return <p className="text-muted-foreground p-2">코드 정보 없음.</p>;

  // workflow action 판정 — kind=workflow 또는 sub_actions 가 있으면 chain 우선.
  // 페르소나 C 가 짚은 R2-1: 이전 gate `!content.method` 가 wrapper method
  // (3줄짜리 SdDesigner.design 같은) 가진 workflow 를 차단해서 21 step UI 가 한 번도
  // surface 안 됐음. 이제 wrapper method 가 있어도 chain 을 method body 위에 prepend.
  const isWorkflow = content.action && (
    content.action.kind === "workflow" || content.action.sub_actions.length > 0
  );

  if (isWorkflow && content.action) {
    // R3-7: workflow action 의 21-step chain 은 main 패널의 SubActionsChain 이 이미 노출.
    // 우측 코드 탭은 chain 을 다시 list 하지 않고 — 헤더 (verification / declared_on_term)
    // + entry wrapper method body + "관련 정보는 호출/관련 탭" 안내로 정리.
    return (
      <div className="min-w-0 space-y-2">
        <WorkflowHeader action={content.action} />
        {content.method?.body_text && (
          <div className="space-y-1">
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold px-1">
              Entry method (wrapper)
            </div>
            <div className="text-[10.5px] text-muted-foreground px-1 truncate" title={content.method.parent_type_fqn}>
              {shortName(content.method.parent_type_fqn)}.{content.method.name}
            </div>
            <div className="bg-muted border border-border rounded text-[11px] overflow-x-auto">
              <JavaCode source={content.method.body_text} startLine={content.method.line_start ?? 1} />
            </div>
          </div>
        )}
        <div className="text-[10.5px] text-muted-foreground px-1 leading-relaxed">
          21-step chain은 가운데 패널 <strong className="text-foreground">구성 단계 (CHAIN)</strong> section 참조.
          호출자 / 연결 BR / Term 은 <strong className="text-foreground">호출</strong> / <strong className="text-foreground">관련</strong> 탭에서.
        </div>
      </div>
    );
  }

  if (content.method?.body_text) {
    const m = content.method;
    return (
      <div className="min-w-0 space-y-2">
        {content.action && <MethodBrief action={content.action} method={m} />}
        {!content.action && (
          <>
            <div className="text-[10.5px] text-muted-foreground mb-1 truncate" title={m.parent_type_fqn}>
              {shortName(m.parent_type_fqn)}
            </div>
            <div
              className="text-[11px] text-foreground mb-1.5 font-semibold truncate"
              title={`${m.name}(${m.params.map(p => p.type).join(", ")}) → ${m.return_type}`}
            >
              {m.name}({m.params.map(p => p.type).join(", ")}) → {m.return_type}
            </div>
            <div className="text-[10px] text-muted-foreground mb-2">
              line {m.line_start}–{m.line_end} · role: {m.role}
            </div>
          </>
        )}
        <div className="bg-muted border border-border rounded text-[11px] overflow-x-auto">
          <JavaCode source={m.body_text ?? ""} startLine={m.line_start ?? 1} />
        </div>
      </div>
    );
  }

  if (content.codeType) {
    const ct = content.codeType;
    return (
      <div className="min-w-0">
        <div className="text-[10.5px] text-muted-foreground truncate mb-1" title={ct.fqn}>
          {ct.package}
        </div>
        <div className="text-[11px] text-foreground mb-1.5 font-semibold truncate" title={ct.fqn}>
          {ct.simple_name}
        </div>
        <div className="text-[10px] text-muted-foreground mb-2">
          {ct.kind} · role {ct.role} · {ct.fields.length} field · {ct.methods.length} method
        </div>
        <div className="text-[10px] text-muted-foreground mt-2 truncate" title={ct.source_file}>
          {ct.source_file.split("/").pop()}
        </div>
        <p className="text-[11px] text-muted-foreground mt-2">
          (전체 detail 은 가운데 패널 참고. 우측은 요약.)
        </p>
      </div>
    );
  }

  return <p className="text-muted-foreground p-2">코드 본체 없음.</p>;
}

// ─────────────────────────────────────────────────────────────────────────
// Method brief — Action 선택 시 코드 본체 위에 노출되는 "이게 무엇인가" 카드.
// 페르소나 P3-F5: "코드만 보면 클래스/메서드 만 보이고, 도메인 의미는 안 보임".
// where (class) · what (signature) · for-what (domain + declared_on_term) · affects (effects).
// ─────────────────────────────────────────────────────────────────────────
function MethodBrief({ action, method }: { action: ActionDTO; method: CodeMethodDTO }) {
  const { setSelectedTerm } = useWorkbench();
  const sig = `${method.name}(${method.params.map((p) => p.type).join(", ")}) → ${method.return_type}`;
  return (
    <div className="rounded-md border border-border bg-muted/40 p-2 space-y-1.5">
      {/* 1) 위치 — 클래스명 */}
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground min-w-0">
        <Layers className="w-3 h-3 shrink-0 text-muted-foreground/60" />
        <span className="truncate min-w-0" title={method.parent_type_fqn}>
          {shortName(method.parent_type_fqn)}
        </span>
      </div>

      {/* 2) 이름 — 메서드 시그니처 */}
      <div
        className="text-[12px] font-semibold text-foreground truncate"
        title={sig}
      >
        {method.name}
        <span className="text-muted-foreground/70 font-normal">
          ({method.params.map((p) => p.type).join(", ")})
        </span>
        <span className="text-muted-foreground/50 font-normal"> → {method.return_type}</span>
      </div>

      {/* 3) 메타 — line / role / verification level */}
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground flex-wrap">
        <span>line {method.line_start}–{method.line_end}</span>
        <span className="text-muted-foreground/30">·</span>
        <span>
          role <span className="text-foreground/80 font-medium">{method.role}</span>
        </span>
        <span className="text-muted-foreground/30">·</span>
        <span>
          {action.verification_level === "body_anchored" || action.verification_level === "sim_verified" || action.verification_level === "pr_proven" ? (
            <span className="text-emerald-700 font-medium">{action.verification_level}</span>
          ) : action.verification_level === "signature_locked" ? (
            <span className="text-sky-700 font-medium">{action.verification_level}</span>
          ) : (
            <span className="text-amber-700 font-medium">{action.verification_level}</span>
          )}
        </span>
      </div>

      {/* 4) 도메인 — Action name + domain + declared_on_term (있으면 클릭 가능) */}
      <div className="flex items-start gap-1.5 text-[10.5px] pt-1 border-t border-border/50">
        <Target className="w-3 h-3 shrink-0 mt-0.5 text-violet-600/70" />
        <div className="min-w-0 flex-1">
          <div className="text-[10px] text-muted-foreground">도메인 Action</div>
          <div className="text-[11px] text-foreground truncate" title={action.fqn}>
            {action.label}
            {action.domain && (
              <span className="ml-1.5 text-[10px] text-muted-foreground">/{action.domain}/</span>
            )}
            <span className="ml-1.5 text-[10px] text-muted-foreground">{action.kind}</span>
          </div>
          {action.declared_on_term && (
            <div className="text-[10px] text-muted-foreground mt-0.5">
              on{" "}
              <button
                onClick={() => setSelectedTerm(action.declared_on_term!)}
                className="text-violet-700 hover:underline font-mono"
                title={action.declared_on_term}
              >
                {shortName(action.declared_on_term)}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 5) 영향 — effects (있을 때만) */}
      {action.effects && action.effects.length > 0 && (
        <div className="flex items-start gap-1.5 text-[10.5px] pt-1 border-t border-border/50">
          <ArrowRight className="w-3 h-3 shrink-0 mt-0.5 text-amber-600/70" />
          <div className="min-w-0 flex-1">
            <div className="text-[10px] text-muted-foreground">바꾸는 것 (effects)</div>
            <div className="space-y-0.5 mt-0.5">
              {action.effects.slice(0, 4).map((e, i) => (
                <div key={i} className="text-[10.5px] flex items-center gap-1.5 min-w-0">
                  <span className={cn(
                    "text-[9px] uppercase tracking-wider px-1 rounded shrink-0 font-medium",
                    e.op === "create" ? "text-emerald-700 bg-emerald-50" :
                    e.op === "mutate" ? "text-amber-700 bg-amber-50" :
                    e.op === "delete" ? "text-rose-700 bg-rose-50" :
                    "text-sky-700 bg-sky-50",
                  )}>{e.op}</span>
                  <button
                    onClick={() => e.target_term && setSelectedTerm(e.target_term)}
                    className="text-foreground hover:text-violet-700 hover:underline truncate min-w-0 font-mono"
                    title={`${e.target_term}${e.target_attr ? "." + e.target_attr : ""}`}
                  >
                    {shortName(e.target_term)}{e.target_attr && <span className="text-muted-foreground/70">.{e.target_attr}</span>}
                  </button>
                </div>
              ))}
              {action.effects.length > 4 && (
                <div className="text-[10px] text-muted-foreground">… +{action.effects.length - 4}</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// R3-7: WorkflowHeader — chain list 없는 compact 헤더 (RightPanel 용).
// MainPanel 의 SubActionsChain 이 이미 chain 을 노출하므로 우측은 중복 제거.
function WorkflowHeader({ action }: { action: ActionDTO }) {
  const { setSelectedTerm } = useWorkbench();
  return (
    <div className="rounded-md border border-border bg-muted/40 p-2 space-y-1.5">
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <Layers className="w-3 h-3 shrink-0 text-muted-foreground/60" />
        <span>{action.domain ? `/${action.domain}/` : ""} workflow · {action.sub_actions.length} step</span>
      </div>
      <div className="text-[12px] font-semibold text-foreground truncate" title={action.fqn}>
        {action.label}
      </div>
      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground flex-wrap">
        <span>
          {action.verification_level === "body_anchored" || action.verification_level === "sim_verified" || action.verification_level === "pr_proven" ? (
            <span className="text-emerald-700 font-medium">{action.verification_level}</span>
          ) : action.verification_level === "signature_locked" ? (
            <span className="text-sky-700 font-medium">{action.verification_level}</span>
          ) : (
            <span className="text-amber-700 font-medium">{action.verification_level}</span>
          )}
        </span>
        {action.declared_on_term && (
          <>
            <span className="text-muted-foreground/30">·</span>
            <span>
              on{" "}
              <button
                onClick={() => setSelectedTerm(action.declared_on_term!)}
                className="text-violet-700 hover:underline font-mono"
              >
                {shortName(action.declared_on_term)}
              </button>
            </span>
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Workflow brief — workflow action (예: slab design) 은 realizations=[] 가 정상.
// 21개 sub_actions 의 chain 을 단순 list 로 surface — 페르소나 A 의 "코드 정보 없음"
// dead-end 회피. 각 sub_action 은 클릭해서 step 별 detail 로 hop 가능.
// ─────────────────────────────────────────────────────────────────────────
function WorkflowBrief({ action }: { action: ActionDTO }) {
  const { setSelectedAction, setSelectedTerm } = useWorkbench();
  return (
    <div className="space-y-2 min-w-0">
      {/* Workflow header */}
      <div className="rounded-md border border-border bg-muted/40 p-2 space-y-1.5">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Layers className="w-3 h-3 shrink-0 text-muted-foreground/60" />
          <span>{action.domain ? `/${action.domain}/` : ""} workflow · {action.sub_actions.length} step</span>
        </div>
        <div className="text-[12px] font-semibold text-foreground truncate" title={action.fqn}>
          {action.label}
        </div>
        {/* R3-4 + R4-3: description placeholder "자동 추천 — com.example..." 처리.
            (a) 전체가 placeholder → workflow 면 sub_actions 첫 4단계로 narrative 합성.
            (b) trailing 만 placeholder → strip 후 real text 만 표시.  */}
        {(() => {
          const raw = action.description ?? "";
          const real = stripPlaceholderTrailer(raw);
          if (!real) {
            if (action.sub_actions.length > 0) {
              const preview = action.sub_actions.slice(0, 4).map(s => shortName(s)).join(" → ");
              const more = action.sub_actions.length > 4 ? ` … (+${action.sub_actions.length - 4} more)` : "";
              return (
                <div className="text-[10.5px] text-muted-foreground leading-relaxed">
                  {preview}{more}
                </div>
              );
            }
            return null;
          }
          return (
            <div className="text-[10.5px] text-muted-foreground leading-relaxed line-clamp-3">
              {real}
            </div>
          );
        })()}
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground flex-wrap">
          <span>
            {action.verification_level === "body_anchored" || action.verification_level === "sim_verified" || action.verification_level === "pr_proven" ? (
              <span className="text-emerald-700 font-medium">{action.verification_level}</span>
            ) : action.verification_level === "signature_locked" ? (
              <span className="text-sky-700 font-medium">{action.verification_level}</span>
            ) : (
              <span className="text-amber-700 font-medium">{action.verification_level}</span>
            )}
          </span>
          {action.declared_on_term && (
            <>
              <span className="text-muted-foreground/30">·</span>
              <span>
                on{" "}
                <button
                  onClick={() => setSelectedTerm(action.declared_on_term!)}
                  className="text-violet-700 hover:underline font-mono"
                >
                  {shortName(action.declared_on_term)}
                </button>
              </span>
            </>
          )}
        </div>
      </div>

      {/* Sub-actions chain */}
      {action.sub_actions.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold px-1">
            구성 단계 (chain)
          </div>
          {action.sub_actions.map((subFqn, i) => (
            <button
              key={subFqn}
              onClick={() => setSelectedAction(subFqn)}
              className="w-full text-left bg-muted hover:bg-orange-50 hover:border-orange-200 border border-transparent px-2 py-1 rounded text-[11px] min-w-0 flex items-center gap-1.5 transition-colors"
              title={subFqn}
            >
              <span className="text-[9.5px] font-mono text-muted-foreground w-6 shrink-0 text-right">
                {String(i + 1).padStart(2, "0")}
              </span>
              <ArrowRight className="w-2.5 h-2.5 text-muted-foreground/50 shrink-0" />
              <span className="font-mono text-foreground truncate min-w-0 flex-1">
                {shortName(subFqn)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 2 — 호출지점 (이 method/action 을 호출하는 caller, 또는 이 method 가 호출하는 callee)
// ─────────────────────────────────────────────────────────────────────────
type CallerInfo = { fqn: string; distance: number; via: string; match_kind: string; strength: number };

// R4-7: codeType 선택 시 호출 탭이 "Action 선택 시만 표시" 로 막혀있던 dead-end —
// 이 codeType 을 realize 하는 Action 목록으로 jump 가능하게.
function CodeTypeCallSiteRedirect({ selection }: { selection: Selection }) {
  const { activeRepoId, setSelectedAction } = useWorkbench();
  const [mappedActions, setMappedActions] = useState<ActionDTO[]>([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (selection.kind !== "codeType") return;
    let cancelled = false;
    setLoading(true);
    ontologyApi.listActions({ repo_id: activeRepoId })
      .then((actions) => {
        if (cancelled) return;
        const mine = actions.filter(a =>
          a.realizations.some(r => {
            const parent = r.code_method_fqn.includes("(")
              ? r.code_method_fqn.slice(0, r.code_method_fqn.indexOf("(")).split(".").slice(0, -1).join(".")
              : r.code_method_fqn;
            return parent === selection.id || r.applies_to_code_type_fqn === selection.id;
          })
        );
        setMappedActions(mine);
      })
      .catch(() => setMappedActions([]))
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [selection.kind, selection.id, activeRepoId]);

  if (selection.kind === "term" || selection.kind === "rule") {
    return (
      <p className="text-muted-foreground p-2 text-[11px]">
        호출 정보는 Action 선택 시 표시. 현재 {selection.kind}.
        <span className="block mt-1 text-muted-foreground/70">대신 <strong className="text-foreground">관련</strong> 탭에서 연결된 Action / Anchor / Rule 참조.</span>
      </p>
    );
  }
  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;
  return (
    <div className="space-y-1.5">
      <p className="text-muted-foreground p-2 text-[11px]">
        호출 정보는 Action 선택 시 표시. 현재 <strong className="text-foreground">{selection.kind}</strong>.
      </p>
      {mappedActions.length > 0 ? (
        <div className="space-y-0.5">
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1 px-1">
            이 클래스를 realize 하는 Action · {mappedActions.length}
          </div>
          {mappedActions.map(a => (
            <button
              key={a.fqn}
              onClick={() => setSelectedAction(a.fqn)}
              className="w-full text-left bg-muted hover:bg-orange-50 px-2 py-1 rounded text-[11px] min-w-0 block transition-colors"
              title={a.fqn}
            >
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="font-mono text-foreground truncate flex-1 min-w-0">{prettyFqn(a.fqn, "action")}</span>
                <span className="text-[9.5px] text-muted-foreground shrink-0">{a.kind}</span>
              </div>
              <div className="text-[10px] text-muted-foreground truncate">{a.label}</div>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground px-2 text-[11px]">
          이 클래스에 매핑된 Action 없음. <strong className="text-foreground">관련</strong> 탭에서 다른 연결 확인.
        </p>
      )}
    </div>
  );
}

// R4-5 + R5-2: callee 측 stdlib 호출 (java.*, BigDecimal.compareTo 등) 은 노이즈.
// 우선 FQ prefix 로 1차 매칭, 그래도 안 잡히면 SimpleName fallback — extractor 가
// unresolved type 을 caller package 로 잘못 prepend 하는 시드 케이스 보완 (페르소나 C 발견).
const STDLIB_PREFIXES = ["java.", "javax.", "kotlin.", "scala.", "groovy."];
const STDLIB_SIMPLE_NAMES = new Set([
  // java.lang
  "String", "Integer", "Long", "Double", "Float", "Boolean", "Byte", "Short",
  "Character", "Object", "Class", "Throwable", "Exception", "RuntimeException",
  "StringBuilder", "StringBuffer", "System", "Math", "Number",
  // java.math
  "BigDecimal", "BigInteger",
  // java.util
  "List", "ArrayList", "LinkedList", "Map", "HashMap", "TreeMap", "LinkedHashMap",
  "Set", "HashSet", "TreeSet", "LinkedHashSet", "Collection", "Collections",
  "Iterator", "Iterable", "Optional", "Objects", "Arrays", "Comparator",
  "Date", "Calendar", "UUID",
  // java.time
  "LocalDate", "LocalDateTime", "LocalTime", "ZonedDateTime", "Instant",
  "Duration", "Period", "ChronoUnit", "DayOfWeek", "Month",
  // java.util.stream
  "Stream", "IntStream", "LongStream", "Collectors",
  // java.util.function
  "Function", "BiFunction", "Predicate", "Consumer", "Supplier",
  // java.io
  "File", "InputStream", "OutputStream", "Reader", "Writer",
]);
function isStdlibCallee(cs: CallSiteDTO): boolean {
  const recv = cs.callee_receiver_static_type ?? "";
  if (STDLIB_PREFIXES.some(p => recv.startsWith(p))) return true;
  // FQ 가 wrong package 로 prepend 된 케이스 — SimpleName 만으로 stdlib 분류.
  const simpleName = recv.includes(".") ? recv.slice(recv.lastIndexOf(".") + 1) : recv;
  return STDLIB_SIMPLE_NAMES.has(simpleName);
}

// R4-2 + R5-6: 페르소나 B (인시던트 SRE) — caller 가 테스트 only 인 경우 "운영 영향 0건"
// 인지 "분석 못 잡음" 인지 구분 안 됨. 비표준 test naming (Spec/Fixture/Stub/Demo/IT_) 도 포함.
const TEST_FQN_PATTERNS = [
  /Test\b/, /Tests\b/, /\.test\./,
  /IT_Test/, /\bIT\d*\b/,           // integration test (IT, IT12 etc.)
  /Spec\b/, /Specs\b/,              // Spock / Kotest 스타일
  /Fixture\b/, /Stub\b/, /Demo\b/,
  /Mock\b/, /\.spec\./,
];
function isTestCaller(fqn: string): boolean {
  return TEST_FQN_PATTERNS.some(re => re.test(fqn));
}

function TabCallSite({ selection }: { selection: Selection }) {
  const { activeRepoId, setSelectedCodeType } = useWorkbench();
  // R3-1: 페르소나 B (인시던트 SRE) 가 "변경 영향 3개+" 답 불가 — caller graph 누락.
  // 탭 1개 안에 두 방향 토글: callers (불리는, incoming) | callees (부르는, outgoing).
  // incident triage 의 핵심은 caller 라 default = 불리는.
  const [direction, setDirection] = useState<"callers" | "callees">("callers");
  const [callSites, setCallSites] = useState<CallSiteDTO[]>([]);
  const [callers, setCallers] = useState<CallerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // R4-5: callee stdlib 필터 — default = hide (page 진입 시 자동으로 도메인 callee 만).
  const [showStdlibCallees, setShowStdlibCallees] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCallSites([]);
    setCallers([]);
    setErr(null);
    (async () => {
      try {
        let methodFqn: string | null = null;
        if (selection.kind === "action") {
          const a = await ontologyApi.getAction(selection.id);
          const r = a?.realizations.find(x => x.scope === "primary") ?? a?.realizations[0];
          methodFqn = r?.code_method_fqn ?? null;
        }
        if (methodFqn) {
          if (direction === "callees") {
            const cs = await ontologyApi.getCallSites(methodFqn);
            if (!cancelled) setCallSites(cs);
          } else {
            const r = await ontologyApi.getMethodCallers(methodFqn, { repo_id: activeRepoId, min_strength: 0.5 });
            if (!cancelled) setCallers(r.callers);
          }
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id, direction, activeRepoId]);

  if (err) {
    return (
      <div className="p-2 text-[11px]">
        <div className="text-rose-700 mb-1">호출 정보 로드 실패</div>
        <div className="text-muted-foreground break-words">{err}</div>
      </div>
    );
  }

  if (selection.kind !== "action") {
    // R4-7: codeType 선택 시 dead-end — 그 type 을 realize 하는 Action 으로 jump 링크.
    return <CodeTypeCallSiteRedirect selection={selection} />;
  }

  const dirToggle = (
    <div className="flex items-center gap-0.5 p-0.5 bg-muted/50 border border-border rounded text-[10.5px] mb-1.5">
      <button
        onClick={() => setDirection("callers")}
        className={cn(
          "flex-1 px-2 py-1 rounded transition-colors text-left",
          direction === "callers"
            ? "bg-card text-foreground shadow-sm font-medium"
            : "text-muted-foreground hover:text-foreground",
        )}
        title="이 메서드를 호출하는 곳 (변경 영향 반경)"
      >
        ← 불리는 곳 <span className="text-muted-foreground/70 text-[10px]">(caller)</span>
      </button>
      <button
        onClick={() => setDirection("callees")}
        className={cn(
          "flex-1 px-2 py-1 rounded transition-colors text-left",
          direction === "callees"
            ? "bg-card text-foreground shadow-sm font-medium"
            : "text-muted-foreground hover:text-foreground",
        )}
        title="이 메서드가 호출하는 다른 메서드"
      >
        → 부르는 곳 <span className="text-muted-foreground/70 text-[10px]">(callee)</span>
      </button>
    </div>
  );

  if (loading) {
    return (
      <div>
        {dirToggle}
        <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (direction === "callers") {
    return (
      <div className="space-y-1">
        {dirToggle}
        {callers.length === 0 ? (
          <p className="text-muted-foreground p-2 text-[11px]">
            <span className="font-medium text-foreground">이 메서드를 호출하는</span> 다른 메서드 없음
            (또는 분석 strength &lt; 0.5).
          </p>
        ) : (
          <>
            {(() => {
              const prodCount = callers.filter(c => !isTestCaller(c.fqn)).length;
              const testCount = callers.length - prodCount;
              return (
                <div className="text-[10.5px] text-muted-foreground mb-1 leading-relaxed flex items-baseline gap-2 flex-wrap">
                  <span>
                    <span className="font-medium text-foreground">이 메서드를 호출하는</span> 곳 (변경 시 영향)
                    <span className="mx-1 text-muted-foreground/50">·</span>
                    {/* R4-2: 운영 caller vs 테스트 caller 분리 표시 */}
                    <span className={prodCount === 0 ? "text-amber-700 font-medium" : "text-foreground"}>
                      운영 {prodCount}
                    </span>
                    {testCount > 0 && (
                      <>
                        <span className="text-muted-foreground/40 mx-1">/</span>
                        <span className="text-muted-foreground">테스트 {testCount}</span>
                      </>
                    )}
                  </span>
                  {prodCount === 0 && testCount > 0 && (
                    <span className="text-[10px] text-amber-700/80">
                      ⚠ 운영 caller 0 — DI/reflection 호출은 정적 분석에 안 잡힐 수 있음 (시드 갭)
                    </span>
                  )}
              </div>
              );
            })()}
            <div className="text-[10px] text-muted-foreground mb-1 leading-relaxed">
              {/* R4-4: match_kind 5단계 + strength 의미를 inline details 로 노출.
                  페르소나 C: "strength 숫자만 두면 추측해야 함". */}
              <details>
                <summary className="cursor-pointer text-muted-foreground/70 hover:text-foreground select-none">
                  match 강도?
                </summary>
                <div className="mt-1 p-1.5 bg-muted/40 border border-border rounded space-y-0.5 max-w-[260px]">
                  <div><span className="inline-block w-3 h-3 align-middle rounded-sm bg-emerald-100 border border-emerald-300 mr-1.5"></span><span className="font-mono">receiver_exact</span> 0.95 — 수신자 타입까지 일치 (가장 확실)</div>
                  <div><span className="inline-block w-3 h-3 align-middle rounded-sm bg-emerald-50 border border-emerald-200 mr-1.5"></span><span className="font-mono">runtime_type</span> 0.85 — 런타임 타입 추론 일치</div>
                  <div><span className="inline-block w-3 h-3 align-middle rounded-sm bg-sky-50 border border-sky-200 mr-1.5"></span><span className="font-mono">receiver_short</span> 0.80 — 짧은 이름 매칭</div>
                  <div><span className="inline-block w-3 h-3 align-middle rounded-sm bg-amber-50 border border-amber-200 mr-1.5"></span><span className="font-mono">package_proximity</span> 0.70 — 같은 패키지</div>
                  <div><span className="inline-block w-3 h-3 align-middle rounded-sm bg-amber-50 border border-amber-200 mr-1.5"></span><span className="font-mono">name_only</span> 0.50 — 메서드 이름만 일치 (약함)</div>
                </div>
              </details>
            </div>
            {/* R4-2: 운영 caller 가 위로 — sort stable + test 는 아래로. */}
            {[...callers]
              .sort((a, b) => {
                const aTest = isTestCaller(a.fqn) ? 1 : 0;
                const bTest = isTestCaller(b.fqn) ? 1 : 0;
                if (aTest !== bTest) return aTest - bTest;
                return b.strength - a.strength;
              })
              .slice(0, 30)
              .map((c) => {
                const parent = c.fqn.includes("(") ? c.fqn.slice(0, c.fqn.indexOf("(")).split(".").slice(0, -1).join(".") : null;
                const methodName = c.fqn.includes("(") ? c.fqn.slice(c.fqn.lastIndexOf(".", c.fqn.indexOf("(")) + 1) : shortName(c.fqn);
                const isTest = isTestCaller(c.fqn);
                return (
                  <button
                    key={c.fqn}
                    onClick={() => parent && setSelectedCodeType(parent)}
                    className={cn(
                      "w-full text-left px-2 py-1 rounded text-[11px] min-w-0 block transition-colors",
                      isTest ? "bg-muted/60 hover:bg-muted opacity-70" : "bg-muted hover:bg-orange-50",
                    )}
                    title={c.fqn}
                  >
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="font-mono text-foreground truncate flex-1 min-w-0">{methodName}</span>
                      {isTest && (
                        <span className="text-[9px] px-1 rounded shrink-0 bg-muted text-muted-foreground border border-border">
                          test
                        </span>
                      )}
                      <span className={cn(
                        "text-[9px] px-1 rounded shrink-0",
                        c.strength >= 0.85 ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                        c.strength >= 0.70 ? "bg-sky-50 text-sky-700 border border-sky-200" :
                        "bg-amber-50 text-amber-700 border border-amber-200"
                      )} title={`match strength ${c.strength.toFixed(2)}`}>
                        {c.match_kind}
                      </span>
                    </div>
                    {parent && (
                      <div className="text-[10px] text-muted-foreground mt-0.5 truncate" title={parent}>
                        on {shortName(parent)} · via {c.via}
                      </div>
                    )}
                  </button>
                );
              })}
            {callers.length > 30 && (
              <p className="text-[10px] text-muted-foreground">… {callers.length - 30} 더</p>
            )}
          </>
        )}
      </div>
    );
  }

  // direction === "callees" — stdlib 필터 적용 후 표시.
  const stdlibCount = callSites.filter(isStdlibCallee).length;
  const visibleCallees = showStdlibCallees
    ? callSites
    : callSites.filter(cs => !isStdlibCallee(cs));

  if (callSites.length === 0) {
    return (
      <div>
        {dirToggle}
        <p className="text-muted-foreground p-2 text-[11px]">
          <span className="font-medium text-foreground">이 메서드가 호출하는</span> 다른 메서드 없음 (분석 미수행).
        </p>
      </div>
    );
  }
  return (
    <div className="space-y-1">
      {dirToggle}
      <div className="text-[10.5px] text-muted-foreground mb-1 leading-relaxed flex items-baseline gap-2 flex-wrap">
        <span>
          <span className="font-medium text-foreground">이 메서드가 호출하는</span> 곳 (의존성)
          <span className="mx-1 text-muted-foreground/50">·</span>
          {visibleCallees.length}건
          {stdlibCount > 0 && !showStdlibCallees && (
            <span className="text-muted-foreground/60"> (stdlib {stdlibCount}건 숨김)</span>
          )}
        </span>
        {/* R4-5: java.* / BigDecimal 같은 stdlib 호출 노이즈 토글 */}
        {stdlibCount > 0 && (
          <button
            onClick={() => setShowStdlibCallees(v => !v)}
            className="text-[10px] text-muted-foreground/70 hover:text-foreground underline-offset-2 hover:underline"
          >
            {showStdlibCallees ? "stdlib 숨기기" : `stdlib ${stdlibCount}건 보기`}
          </button>
        )}
        <HelpHint term="call_site" inline />
      </div>
      {visibleCallees.slice(0, 50).map((cs) => (
        <div key={cs.id} className="bg-muted px-2 py-1 rounded text-[11px] min-w-0">
          <div className="flex items-center gap-1.5 min-w-0">
            <span
              className="font-mono text-foreground truncate flex-1 min-w-0"
              title={cs.callee_simple_name}
            >
              {cs.callee_simple_name}
            </span>
            {cs.line && <span className="font-mono text-[9.5px] text-muted-foreground shrink-0">L{cs.line}</span>}
          </div>
          <div
            className="text-[10px] text-muted-foreground mt-0.5 truncate"
            title={cs.callee_receiver_static_type}
          >
            on {shortName(cs.callee_receiver_static_type)} · {cs.analysis_source}
            {cs.needs_user_confirm && <span className="ml-1 text-amber-700">(모호)</span>}
          </div>
          {cs.user_confirmed_type && (
            <div className="text-[10px] text-emerald-700 mt-0.5 truncate" title={cs.user_confirmed_type}>
              ✓ confirmed: {shortName(cs.user_confirmed_type)}
            </div>
          )}
        </div>
      ))}
      {visibleCallees.length > 50 && (
        <p className="text-[10px] text-muted-foreground">… {visibleCallees.length - 50} 더</p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 3 — 영향 (이 entity 와 연결된 다른 ontology 노드들)
// ─────────────────────────────────────────────────────────────────────────
function TabImpact({ selection }: { selection: Selection }) {
  const { activeRepoId } = useWorkbench();
  const [data, setData] = useState<{
    actions?: ActionDTO[];
    rules?: BusinessRuleDTO[];
    enforcedRuleFqns?: Set<string>;  // R4-8: 직접 enforced 인 rule fqn 집합
    anchors?: AnchorBindingDTO[];
    relatedTerms?: string[];
  } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    (async () => {
      try {
        if (selection.kind === "action") {
          // R4-8 + R5-1: enforced_by 만으로는 BR 연결이 빈약. action.declared_on_term +
          // FQN 형식의 effects.target_term 을 ref 하는 BR 도 같이 surface. effects 의
          // simple-name target (e.g., "SDSlabEntity") 은 시드가 Java class name 으로 들어가
          // 있어 rule.terms_ref FQN 과 join 안 됨 — FQN-shape 만 포함하고, 매칭 0건이면
          // statement 본문 substring 으로 backup 매칭 시도.
          const a = await ontologyApi.getAction(selection.id);
          if (!a) return;
          const ans = await ontologyApi.getAnchorBindingsForAction(selection.id).catch(() => []);
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const r = a.realizations.find(x => x.scope === "primary") ?? a.realizations[0];
          // 직접 enforced (1차 신호)
          const enforced = r ? allRules.filter(rr => rr.enforced_by.includes(r.code_method_fqn)) : [];
          // 간접 — terms 공유 (2차 신호). FQN shape 만 사용 (term. 접두).
          const relatedTermFqns = new Set<string>();
          if (a.declared_on_term?.startsWith("term.")) {
            relatedTermFqns.add(a.declared_on_term);
          }
          for (const eff of a.effects) {
            if (eff.target_term?.startsWith("term.")) {
              relatedTermFqns.add(eff.target_term);
            }
          }
          let indirectRules = allRules.filter(rr =>
            !enforced.some(e => e.fqn === rr.fqn) &&
            rr.terms_ref.some(t => relatedTermFqns.has(t))
          );
          // R5-1 fallback: 직접/FQN-join 0건이면 statement 본문 substring 매칭 — term 의
          // simple name (마지막 segment, 4글자 이상) 이 rule.statement 안에 나오면 관련.
          if (indirectRules.length === 0 && relatedTermFqns.size > 0) {
            indirectRules = allRules.filter(rr => {
              if (enforced.some(e => e.fqn === rr.fqn)) return false;
              const stmtLow = rr.statement.toLowerCase();
              return Array.from(relatedTermFqns).some(t => {
                const seg = t.includes(".") ? t.slice(t.lastIndexOf(".") + 1) : t;
                return seg.length >= 4 && stmtLow.includes(seg.toLowerCase());
              });
            });
          }
          if (!cancelled) setData({
            rules: [...enforced, ...indirectRules],
            enforcedRuleFqns: new Set(enforced.map(e => e.fqn)),
            anchors: ans,
            relatedTerms: Array.from(relatedTermFqns),
          });
        } else if (selection.kind === "term") {
          // 이 term 을 사용하는 actions (declared_on 또는 params)
          const actions = await ontologyApi.listActions({ repo_id: activeRepoId, declared_on_term: selection.id }).catch(() => []);
          // 이 term 을 ref 하는 BR
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const refRules = allRules.filter(r => r.terms_ref.includes(selection.id));
          if (!cancelled) setData({ actions, rules: refRules });
        } else if (selection.kind === "rule") {
          const allRules = await ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => []);
          const r = allRules.find(rr => rr.fqn === selection.id);
          if (!cancelled) setData({ relatedTerms: r?.terms_ref ?? [] });
        } else if (selection.kind === "anchor") {
          const ans = await ontologyApi.listAnchorBindings({ repo_id: activeRepoId });
          const a = ans.find(x => x.id === selection.id);
          if (!a) return;
          const action = await ontologyApi.getAction(a.target_action_fqn).catch(() => null);
          if (!cancelled) setData({ actions: action ? [action] : [] });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selection.kind, selection.id, activeRepoId]);

  const { setSelectedAction, setSelectedTerm, setSelectedRule } = useWorkbench();

  if (loading) return <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" />;
  if (!data) return <p className="text-muted-foreground p-2">데이터 없음.</p>;

  return (
    <div className="space-y-3">
      {data.actions && data.actions.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 Actions · {data.actions.length}
          </div>
          {data.actions.map((a) => (
            <button
              key={a.fqn}
              onClick={() => setSelectedAction(a.fqn)}
              className="w-full text-left bg-muted hover:bg-orange-50 px-2 py-1 rounded text-[11px] my-0.5 block min-w-0"
              title={a.fqn}
            >
              <div className="flex items-center gap-1 min-w-0">
                <span className="font-mono text-foreground truncate flex-1 min-w-0">{prettyFqn(a.fqn, "action")}</span>
              </div>
              <div className="text-[10px] text-muted-foreground truncate">{a.label} · {a.kind}</div>
            </button>
          ))}
        </div>
      )}
      {data.rules && data.rules.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 BR · {data.rules.length}
            {data.enforcedRuleFqns && data.enforcedRuleFqns.size > 0 && (
              <span className="ml-1 text-rose-700/80 normal-case font-normal">
                (직접 enforced {data.enforcedRuleFqns.size})
              </span>
            )}
          </div>
          {data.rules.map((r) => {
            const isDirect = data.enforcedRuleFqns?.has(r.fqn);
            return (
              <button
                key={r.fqn}
                onClick={() => setSelectedRule(r.fqn)}
                className={cn(
                  "w-full text-left px-2 py-1 rounded text-[11px] my-0.5 block min-w-0 transition-colors",
                  isDirect
                    ? "bg-rose-50 hover:bg-rose-100 border border-rose-200"
                    : "bg-muted hover:bg-rose-50",
                )}
                title={r.fqn}
              >
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={cn(
                    "w-1.5 h-1.5 rounded-sm shrink-0",
                    r.severity === "hard" ? "bg-rose-500" : "bg-amber-500"
                  )} />
                  <span className="font-mono text-foreground truncate flex-1 min-w-0">{prettyFqn(r.fqn, "rule")}</span>
                  {isDirect ? (
                    <span className="text-[9px] px-1 rounded shrink-0 bg-rose-100 text-rose-800 border border-rose-300 font-medium">
                      enforced
                    </span>
                  ) : (
                    <span className="text-[9px] px-1 rounded shrink-0 bg-muted text-muted-foreground border border-border">
                      term 공유
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-muted-foreground line-clamp-1">{r.statement}</div>
              </button>
            );
          })}
        </div>
      )}
      {data.anchors && data.anchors.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            연결 Anchor · {data.anchors.length}
          </div>
          {data.anchors.map((a) => (
            <div key={a.id} className="bg-muted px-2 py-1 rounded text-[11px] my-0.5 min-w-0">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="font-mono text-[9.5px] text-sky-700 shrink-0">L{a.line ?? "?"}</span>
                <span
                  className="font-mono truncate flex-1 min-w-0"
                  title={a.anchor_locator}
                >
                  {a.anchor_locator}
                </span>
              </div>
              <div className="text-[10px] text-muted-foreground truncate" title={a.target_slot}>
                → {a.target_slot}
              </div>
            </div>
          ))}
        </div>
      )}
      {data.relatedTerms && data.relatedTerms.length > 0 && (
        <div>
          <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
            참조 Terms · {data.relatedTerms.length}
          </div>
          {data.relatedTerms.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedTerm(t)}
              className="w-full text-left bg-muted hover:bg-violet-50 px-2 py-1 rounded text-[11px] my-0.5 font-mono truncate block"
              title={t}
            >
              {prettyFqn(t, "term")}
            </button>
          ))}
        </div>
      )}
      {!data.actions?.length && !data.rules?.length && !data.anchors?.length && !data.relatedTerms?.length && (
        <p className="text-muted-foreground text-[11px]">연결된 ontology 노드 없음.</p>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// 탭 4 — 메모 (사용자 자유 참고용. ontology 본체 무관)
// ─────────────────────────────────────────────────────────────────────────
type LoadState = "loading" | "ready" | "load_error";
type SaveState = "idle" | "saving" | "saved" | "save_error";

function TabMemo({ selection }: { selection: Selection }) {
  const { activeRepoId } = useWorkbench();
  const [body, setBody] = useState("");
  const [savedBody, setSavedBody] = useState("");           // 서버와 일치하는 마지막 값
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // (kind, id) 바뀔 때마다 fetch — 진행 중 dirty 는 자동 폐기 (사용자가 다른 entity 로 이동)
  useEffect(() => {
    let cancelled = false;
    setLoadState("loading");
    setSaveState("idle");
    setUpdatedAt(null);
    setErrMsg(null);
    ontologyApi.getMemo(activeRepoId, selection.kind as MemoKind, selection.id)
      .then((m) => {
        if (cancelled) return;
        const initial = m?.body ?? "";
        setBody(initial);
        setSavedBody(initial);
        setUpdatedAt(m?.updated_at ?? null);
        setLoadState("ready");
      })
      .catch((e) => {
        if (cancelled) return;
        setBody("");
        setSavedBody("");
        setErrMsg(e instanceof Error ? e.message : String(e));
        setLoadState("load_error");
      });
    return () => { cancelled = true; };
  }, [activeRepoId, selection.kind, selection.id]);

  const isDirty = body !== savedBody;
  const canSave = loadState === "ready" && isDirty && saveState !== "saving";

  const handleSave = async () => {
    if (!canSave) return;
    setSaveState("saving");
    setErrMsg(null);
    try {
      const saved = await ontologyApi.putMemo(
        activeRepoId,
        selection.kind as MemoKind,
        selection.id,
        body,
      );
      setSavedBody(body);
      setUpdatedAt(saved.updated_at);
      setSaveState("saved");
    } catch (e) {
      setSaveState("save_error");
      setErrMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const handleRevert = () => {
    setBody(savedBody);
    setSaveState("idle");
    setErrMsg(null);
  };

  // ⌘S / Ctrl+S 단축키
  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (canSave) void handleSave();
    }
  };

  // 미저장 변경 + 페이지 닫기 경고
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  if (loadState === "loading") {
    return (
      <div className="text-muted-foreground text-[11px] p-2 flex items-center gap-1.5">
        <Loader2 className="w-3 h-3 animate-spin" /> 메모 로드 중…
      </div>
    );
  }

  if (loadState === "load_error") {
    return (
      <div className="space-y-2 p-1">
        <div className="text-[11px] text-rose-700">메모 로드 실패</div>
        <div className="text-[10.5px] text-muted-foreground break-words">{errMsg}</div>
        <button
          type="button"
          onClick={() => {
            // 다시 시도 — selection 그대로지만 effect 재실행 위해 dummy state 변경 못함
            // 가장 단순: 사용자가 다른 entity 갔다 오게 안내, 또는 새로고침
            // 여기선 retry 단순 구현: fetch 다시 트리거
            setLoadState("loading");
            ontologyApi.getMemo(activeRepoId, selection.kind as MemoKind, selection.id)
              .then((m) => {
                setBody(m?.body ?? "");
                setSavedBody(m?.body ?? "");
                setUpdatedAt(m?.updated_at ?? null);
                setErrMsg(null);
                setLoadState("ready");
              })
              .catch((e) => {
                setErrMsg(e instanceof Error ? e.message : String(e));
                setLoadState("load_error");
              });
          }}
          className="text-[11px] px-2 py-1 rounded border border-border hover:bg-muted"
        >
          다시 시도
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center gap-2 text-[10.5px]">
        <span className="text-muted-foreground">📝 자유 메모 — ontology 매핑에 영향 없음</span>
        <span className="ml-auto shrink-0">
          {isDirty && saveState !== "saving" && (
            <span className="text-amber-700">● 미저장</span>
          )}
          {!isDirty && saveState === "saved" && (
            <span className="text-emerald-700">✓ 저장됨</span>
          )}
          {!isDirty && saveState === "idle" && updatedAt && (
            <span className="text-muted-foreground/60">변경 없음</span>
          )}
        </span>
      </div>

      <textarea
        ref={textareaRef}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={`이 ${selection.kind} 에 대한 참고 메모를 자유롭게 작성하세요.\n\n(예: 운영 시 주의사항, 과거 이슈, TODO 등)\n\n저장: 아래 [저장] 버튼 또는 ⌘S / Ctrl+S`}
        className="flex-1 resize-none border border-border rounded p-2 text-[12px] font-sans bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary/40 min-h-[180px]"
      />

      {/* Action bar */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={!canSave}
          className={cn(
            "text-[11px] px-3 py-1 rounded font-medium transition-colors",
            canSave
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed",
          )}
          title="⌘S / Ctrl+S 로도 저장 가능"
        >
          {saveState === "saving" ? "저장 중…" : "저장"}
        </button>
        <button
          type="button"
          onClick={handleRevert}
          disabled={!isDirty || saveState === "saving"}
          className={cn(
            "text-[11px] px-2 py-1 rounded border transition-colors",
            isDirty && saveState !== "saving"
              ? "border-border hover:bg-muted text-foreground"
              : "border-border/40 text-muted-foreground/40 cursor-not-allowed",
          )}
          title="저장되지 않은 변경을 마지막 저장 상태로 되돌림"
        >
          되돌리기
        </button>
        <span className="ml-auto text-[10px] text-muted-foreground/80 truncate" title={updatedAt ?? ""}>
          {updatedAt ? `마지막 저장: ${new Date(updatedAt).toLocaleString()}` : "아직 저장된 메모 없음"}
        </span>
      </div>

      {/* Error display */}
      {saveState === "save_error" && (
        <div className="text-[11px] bg-rose-50 border border-rose-200 rounded px-2 py-1.5 space-y-1">
          <div className="text-rose-700 font-medium">저장 실패</div>
          <div className="text-[10.5px] text-rose-800 break-words">{errMsg}</div>
          <div className="flex items-center gap-2 pt-0.5">
            <button
              type="button"
              onClick={() => void handleSave()}
              className="text-[10.5px] px-2 py-0.5 rounded border border-rose-300 hover:bg-rose-100 text-rose-800"
            >
              다시 시도
            </button>
            <span className="text-[10px] text-rose-700/80">
              네트워크 / 백엔드 확인 후 다시 [저장] 누르세요. 입력 내용은 보존됨.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/** "com.foo.Bar.method(Args)" → "com.foo.Bar". */
function parentTypeFqnOfMethod(methodFqn: string): string | null {
  const parenIdx = methodFqn.indexOf("(");
  const beforeParen = parenIdx >= 0 ? methodFqn.slice(0, parenIdx) : methodFqn;
  const lastDot = beforeParen.lastIndexOf(".");
  if (lastDot < 0) return null;
  return beforeParen.slice(0, lastDot);
}
