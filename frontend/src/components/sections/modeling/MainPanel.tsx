"use client";

import { useEffect, useMemo, useState } from "react";
import { useWorkbench, type MainMode } from "./store";
import {
  ontologyApi,
  type ActionDTO,
  type AnchorBindingDTO,
  type BusinessRuleDTO,
  type CodeTypeDTO,
  type CompositionDTO,
  type TermDTO,
} from "@/lib/api/ontology";
import { cn } from "@/lib/utils";
import { prettyFqn, shortName, methodTail, anchorTail } from "@/lib/modeling/fqn";
import { stripPlaceholderTrailer } from "@/lib/modeling/description";
import { Button } from "@/components/ui/button";
import { AuthoringMode } from "./AuthoringMode";
import { HelpHint } from "./HelpHint";
import { JavaCode } from "./JavaCode";
import {
  ChevronRight, FileText, Columns2, Network as NetworkIcon, PenLine,
  Atom, Scale, Anchor as AnchorIcon, MapPin, Shield, Compass, Search, GitBranch,
  type LucideIcon,
} from "lucide-react";
import { ConfirmToggle } from "./ConfirmToggle";
import { InlineEditList, InlineEditSelect, InlineEditText, InlineEditTextArea } from "./InlineEdit";

const MODE_LABELS: { id: MainMode | "graph"; label: string; Icon: LucideIcon }[] = [
  { id: "detail",    label: "Detail",    Icon: FileText },
  { id: "split",     label: "Split",     Icon: Columns2 },
  { id: "graph",     label: "Graph",     Icon: NetworkIcon },
  { id: "authoring", label: "Authoring", Icon: PenLine },
];

export function MainPanel() {
  const {
    mainMode, setMainMode, setGraphMode,
    selectedActionFqn, selectedTermFqn, selectedCodeTypeFqn, selectedRuleFqn, selectedAnchorId,
  } = useWorkbench();

  // 어떤 entity 가 활성? (5 selection 중 단 1개만 — store.selectOnly 가 보장)
  const activeKind = useMemo(() => {
    if (selectedActionFqn) return { kind: "action" as const, id: selectedActionFqn };
    if (selectedTermFqn) return { kind: "term" as const, id: selectedTermFqn };
    if (selectedCodeTypeFqn) return { kind: "codeType" as const, id: selectedCodeTypeFqn };
    if (selectedRuleFqn) return { kind: "rule" as const, id: selectedRuleFqn };
    if (selectedAnchorId) return { kind: "anchor" as const, id: selectedAnchorId };
    return null;
  }, [selectedActionFqn, selectedTermFqn, selectedCodeTypeFqn, selectedRuleFqn, selectedAnchorId]);

  return (
    <>
      <div className="h-9 px-3 bg-card border-b border-border flex items-center gap-3 flex-shrink-0">
        <div className="text-[11.5px] text-muted-foreground flex-1 min-w-0 truncate">
          {activeKind ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground/60">현재</span>
              <span className="text-foreground font-medium">{KIND_LABEL[activeKind.kind]}</span>
              <ChevronRight className="w-3 h-3 text-muted-foreground/40" />
              <code className="font-mono text-foreground">{activeKind.id.split(".").pop() ?? activeKind.id}</code>
            </span>
          ) : (
            <span className="text-muted-foreground">좌측 트리에서 Term / Action / CodeType / BR / Anchor 선택</span>
          )}
        </div>
        {/* Mode toggle — segmented control, underline active */}
        <div className="flex items-center gap-0.5 shrink-0">
          {MODE_LABELS.map((m) => {
            const active = m.id !== "graph" && mainMode === m.id;
            return (
              <button
                key={m.id}
                onClick={() => {
                  if (m.id === "graph") setGraphMode(true);
                  else setMainMode(m.id);
                }}
                className={cn(
                  "relative h-7 px-2.5 rounded text-[11.5px] inline-flex items-center gap-1.5 transition-colors",
                  active
                    ? "text-foreground bg-muted font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                )}
              >
                <m.Icon className={cn("w-3.5 h-3.5", active ? "text-primary" : "text-muted-foreground/70")} />
                {m.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {mainMode === "detail" && <ForwardDetail activeKind={activeKind} />}
        {mainMode === "split" && <SplitMode />}
        {mainMode === "authoring" && <AuthoringMode />}
      </div>
    </>
  );
}

const KIND_LABEL: Record<"action" | "term" | "codeType" | "rule" | "anchor", string> = {
  action:   "Action",
  term:     "Term",
  codeType: "CodeType",
  rule:     "BusinessRule",
  anchor:   "AnchorBinding",
};

type ActiveKind =
  | { kind: "action";   id: string }
  | { kind: "term";     id: string }
  | { kind: "codeType"; id: string }
  | { kind: "rule";     id: string }
  | { kind: "anchor";   id: string };

// ── Forward Detail — 5 entity router (Action/Term/CodeType/BR/Anchor) ──
function ForwardDetail({ activeKind }: { activeKind: ActiveKind | null }) {
  if (!activeKind) {
    return <EntryHero />;
  }
  if (activeKind.kind === "action")   return <ActionDetail fqn={activeKind.id} />;
  if (activeKind.kind === "term")     return <TermDetail fqn={activeKind.id} />;
  if (activeKind.kind === "codeType") return <CodeTypeDetail fqn={activeKind.id} />;
  if (activeKind.kind === "rule")     return <BusinessRuleDetail fqn={activeKind.id} />;
  if (activeKind.kind === "anchor")   return <AnchorDetail id={activeKind.id} />;
  return null;
}

// ── Entry Hero — 첫 진입 시 페르소나별 CTA + 시스템 stats ───────────────
function EntryHero() {
  const { activeRepoId, setLeftTab, setGraphMode, setGraphTopMode, toggleCmdK } = useWorkbench();
  const [stats, setStats] = useState<{
    terms: number; actions: number; codeTypes: number; rules: number;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      ontologyApi.listTerms({ repo_id: activeRepoId }).catch(() => [] as TermDTO[]),
      ontologyApi.listActions({ repo_id: activeRepoId }).catch(() => [] as ActionDTO[]),
      ontologyApi.listCodeTypes({ repo_id: activeRepoId }).catch(() => [] as CodeTypeDTO[]),
      ontologyApi.listBusinessRules({ repo_id: activeRepoId }).catch(() => [] as BusinessRuleDTO[]),
    ]).then(([terms, actions, codeTypes, rules]) => {
      if (cancelled) return;
      setStats({
        terms: terms.length,
        actions: actions.length,
        codeTypes: codeTypes.length,
        rules: rules.length,
      });
    });
    return () => { cancelled = true; };
  }, [activeRepoId]);

  const ctas: { Icon: LucideIcon; title: string; desc: string; onClick: () => void; tone: string }[] = [
    {
      Icon: Compass,
      title: "도메인 큰 그림",
      desc: "도메인별 매핑 커버리지 그래프 + 좌측 Term/Action 카테고리",
      // Coverage 그래프 + 좌측 ontology 탭 동시 진입 — 페르소나 A 가 기대한
      // "system-wide domain map" 을 실제로 보여줌. Graph coverage 가 현재 IA 의
      // 도메인 hierarchy visualization.
      onClick: () => {
        setLeftTab("ontology");
        setGraphTopMode("coverage");
        setGraphMode(true);
      },
      tone: "violet",
    },
    {
      Icon: Search,
      title: "코드/메서드 찾기",
      desc: "클래스명 · 메서드명 · 한국어 용어로 즉시 검색 (⌘K)",
      onClick: () => toggleCmdK(true),
      tone: "sky",
    },
    {
      Icon: GitBranch,
      title: "변경 영향 분석",
      desc: "이 entity 가 어디서 호출/참조되는지 그래프로 추적 (먼저 entity 선택 필요)",
      // Impact 모드는 focus 가 있어야 의미 — entity 미선택 상태로 진입 시 빈 화면.
      // 페르소나 A 지적 ("뭘 봐야 할지 모르겠음") → ⌘K 부터 띄워서 entity 고르게.
      onClick: () => {
        setGraphTopMode("impact");
        toggleCmdK(true);
      },
      tone: "amber",
    },
  ];

  return (
    <div className="h-full overflow-y-auto px-6 py-8">
      <div className="max-w-[680px] mx-auto">
        {/* Title */}
        <div className="text-center mb-6">
          <div className="w-12 h-12 mx-auto rounded-full bg-primary/10 flex items-center justify-center mb-3">
            <Compass className="w-5 h-5 text-primary/70" />
          </div>
          <h2 className="text-[15px] font-semibold text-foreground mb-1">어디서부터 시작할까요?</h2>
          <p className="text-[12px] text-muted-foreground max-w-[420px] mx-auto leading-relaxed">
            <span className="font-mono text-foreground">{activeRepoId}</span> 의
            코드 ↔ 도메인 매핑을 살펴봅니다. 목적에 맞는 entry 를 고르거나, 좌측 트리에서 직접 entity 를 선택하세요.
          </p>
        </div>

        {/* Stats — 시스템 규모 한눈에 */}
        {stats && (
          <div className="grid grid-cols-4 gap-2 mb-6">
            <StatCard label="CodeType" value={stats.codeTypes} icon={FileText} />
            <StatCard label="Term" value={stats.terms} icon={Atom} tone="violet" />
            <StatCard label="Action" value={stats.actions} icon={PenLine} tone="orange" />
            <StatCard label="Business Rule" value={stats.rules} icon={Scale} tone="rose" />
          </div>
        )}

        {/* Persona CTA cards */}
        <div className="grid grid-cols-1 gap-2 mb-4">
          {ctas.map((c) => (
            <button
              key={c.title}
              onClick={c.onClick}
              className="group flex items-center gap-3 p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/30 transition-colors text-left"
            >
              <div className={cn(
                "w-9 h-9 shrink-0 rounded-md flex items-center justify-center",
                c.tone === "violet" && "bg-violet-500/10 text-violet-500",
                c.tone === "sky" && "bg-sky-500/10 text-sky-500",
                c.tone === "amber" && "bg-amber-500/10 text-amber-500",
              )}>
                <c.Icon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-medium text-foreground">{c.title}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5">{c.desc}</div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground/40 group-hover:text-foreground transition-colors shrink-0" />
            </button>
          ))}
        </div>

        {/* 추가 안내 */}
        <div className="text-center text-[10.5px] text-muted-foreground/70 pt-2 border-t border-border/40">
          좌측 트리에서 클래스/메서드/Term/Action/BR/Anchor 직접 선택도 가능합니다.
          단축키 <kbd className="text-[9.5px] px-1 py-0.5 mx-0.5 bg-muted rounded border border-border font-mono">⌘K</kbd>
          로 통합 검색.
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, tone }: {
  label: string; value: number; icon: LucideIcon; tone?: "violet" | "orange" | "rose";
}) {
  return (
    <div className="bg-card border border-border rounded-md px-2.5 py-2">
      <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
        <Icon className={cn(
          "w-3 h-3",
          tone === "violet" && "text-violet-500",
          tone === "orange" && "text-orange-500",
          tone === "rose" && "text-rose-500",
          !tone && "text-muted-foreground",
        )} />
        {label}
      </div>
      <div className="text-[18px] font-semibold tabular-nums text-foreground mt-0.5">{value}</div>
    </div>
  );
}

// ── Action Detail (기존 ForwardDetail 의 본체) ─────────────────────────
function ActionDetail({ fqn }: { fqn: string }) {
  const selectedActionFqn = fqn;
  const [action, setAction] = useState<ActionDTO | null>(null);
  const [anchors, setAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedActionFqn) {
      setAction(null);
      setAnchors([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      ontologyApi.getAction(selectedActionFqn).catch(() => null),
      ontologyApi.getAnchorBindingsForAction(selectedActionFqn).catch(() => []),
    ]).then(([a, b]) => {
      if (cancelled) return;
      setAction(a);
      setAnchors(b);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedActionFqn]);

  if (loading) {
    return <div className="p-6 text-muted-foreground text-sm">Loading...</div>;
  }
  if (!action) {
    return (
      <div className="p-6 text-muted-foreground text-sm">
        Action 선택 또는 backend 에 데이터 없음 (Phase 1 시작 직후 빈 상태가 정상).
      </div>
    );
  }

  const patch = async (p: Parameters<typeof ontologyApi.patchAction>[2]) => {
    await ontologyApi.patchAction(action.repo_id, action.fqn, p);
    setAction({ ...action, ...p } as ActionDTO);
  };

  return (
    <div className="p-5 max-w-[920px]">
      <div className="bg-primary/5 border-l-2 border-primary px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        🔍 <strong className="text-primary">Forward 매핑</strong> — 코드를 도메인 의미로 매핑 (초기 작업)
      </div>

      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2 flex-nowrap min-w-0">
        <span className="min-w-0 flex-1 truncate" title={action.label}>
          <InlineEditText
            value={action.label}
            onSave={(v) => patch({ label: v })}
            placeholder="(label 미지정)"
          />
        </span>
        <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border text-orange-700 border-orange-400 bg-orange-50">
          action
          <HelpHint term="action" inline />
        </span>
        <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
          {action.kind}
          <HelpHint term={action.kind} inline />
        </span>
        {action.is_abstract && (
          <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
            abstract
          </span>
        )}
        <span className="ml-auto shrink-0">
          <ConfirmToggle
            kind="action"
            id={action.fqn}
            repoId={action.repo_id}
            confirmed={!!action.confirmed_by || (action.verification_level !== "unmapped" && action.verification_level !== "draft")}
            onChanged={(v) => setAction({
              ...action,
              confirmed_by: v ? "user" : null,
              verification_level: v
                ? (action.verification_level === "draft" || action.verification_level === "unmapped"
                    ? "signature_locked" : action.verification_level)
                : "draft",
            })}
          />
        </span>
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono flex items-center gap-2 min-w-0">
        <span className="truncate min-w-0 flex-1" title={action.fqn}>{prettyFqn(action.fqn, "action")}</span>
        {action.declared_on_term && (
          <span className="shrink-0 text-muted-foreground">
            · on <FqnLink kind="term" fqn={action.declared_on_term} />
          </span>
        )}
        <span className="ml-auto shrink-0 text-[11px] px-1.5 py-px rounded-full border border-amber-400 text-amber-700 bg-amber-50">
          {action.verification_level.toUpperCase()}
          <HelpHint term={action.verification_level} inline />
        </span>
      </div>

      <Section title="설명">
        {/* R4-3 (R5 follow-up): 메인 Action description 에도 placeholder strip 적용.
            chain step 카드 / WorkflowBrief 는 이미 strip 했지만 여기서 누락되어
            "자동 추천 — FQN" 꼬리표가 가장 눈에 띄는 자리에서 그대로 노출됐었음. */}
        <InlineEditTextArea
          value={stripPlaceholderTrailer(action.description)}
          onSave={(v) => patch({ description: v })}
          placeholder="(설명 미지정 — 클릭해서 편집)"
          rows={3}
          className="text-[12.5px] text-foreground leading-relaxed"
        />
      </Section>

      <Section title={`Aliases · ${action.aliases.length}`}>
        <InlineEditList
          value={action.aliases}
          onSave={(v) => patch({ aliases: v })}
          placeholder="(alias 미등록 — 클릭해서 추가)"
        />
      </Section>

      <Section title={<>Parameters · {action.params.length} <HelpHint term="action" inline /></>}>
        {action.params.map((p, i) => (
          <ParamRow
            key={i}
            k={`params[${i}]`}
            name={p.name}
            refTerm={p.object_ref_term ?? null}
            confirmed={p.confirmed}
          />
        ))}
      </Section>

      {action.output && (
        <Section title="Output">
          <ParamRow
            k="return"
            name={action.output.type}
            refTerm={action.output.object_ref_term ?? null}
            confirmed
          />
        </Section>
      )}

      {/* R2-5: workflow action (slab design 등 sub_actions 21개) 의 step chain.
          페르소나 A: realizations=[] 인 workflow 가 우측 패널 외에 main 패널에서도
          "코드 정보 없음" 처럼 보였던 dead-end 회피. sub_actions 가 있으면 항상 노출. */}
      {action.sub_actions.length > 0 && <SubActionsChain action={action} />}

      <Section title={<>Realizations · {action.realizations.length} (다형성) <HelpHint term="realization" inline /></>}>
        {action.realizations.map((r, i) => (
          <div key={i} className="bg-muted px-3 py-2 rounded my-1.5 min-w-0">
            <div className="flex items-center gap-2 text-xs min-w-0">
              <span className="text-[10px] text-amber-700 border border-amber-300 bg-amber-50 px-1 rounded shrink-0">
                code
              </span>
              <FqnLink kind="code_method" fqn={r.code_method_fqn} className="flex-1 min-w-0" />
              {r.is_override && (
                <span className="text-[10px] px-1.5 py-px rounded-full border border-border text-muted-foreground shrink-0">
                  @Override
                </span>
              )}
              {r.confirmed && (
                <span className="text-[10px] px-1.5 py-px rounded-full border border-emerald-400 text-emerald-700 bg-emerald-50 ml-auto shrink-0">
                  ✓ {r.scope}
                  <HelpHint term={r.scope} inline />
                </span>
              )}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1 min-w-0 flex-wrap">
              <span className="shrink-0">applies to</span>
              {r.applies_to_code_type_fqn
                ? <FqnLink kind="code_type" fqn={r.applies_to_code_type_fqn} />
                : <span className="font-mono">(base)</span>}
              <span className="text-muted-foreground/70">·</span>
              <span className="shrink-0">{r.dispatch_source}<HelpHint term="dispatch_source" inline /></span>
              <span className="text-muted-foreground/70">·</span>
              <span className="shrink-0">conf {r.confidence}<HelpHint term="confidence" inline /></span>
            </div>
          </div>
        ))}
      </Section>

      {action.preconditions.length > 0 && (
        <Section title={`Preconditions · ${action.preconditions.length}`}>
          {action.preconditions.map((p, i) => (
            <div key={i} className="flex items-center gap-2 text-xs my-1">
              <span className="font-mono text-primary">[{i}]</span>
              <span className="text-[10px] text-pink-400 border border-pink-400 bg-pink-400/10 px-1 rounded">
                rule
              </span>
              <span className="font-mono text-muted-foreground">{p}</span>
            </div>
          ))}
        </Section>
      )}

      <Section
        title={<>Anchor Bindings · {anchors.length} <HelpHint term="anchor" inline /></>}
        action={
          <Button
            size="sm"
            variant="outline"
            onClick={() => useWorkbench.setState({ mainMode: "split" })}
          >
            ↕ Split mode 로
          </Button>
        }
      >
        {anchors.map((ab) => (
          <div
            key={ab.id}
            className={cn(
              "bg-muted px-3 py-1.5 rounded my-1 text-xs space-y-1 min-w-0",
              !ab.confirmed && "border-l-2 border-amber-400 pl-2",
            )}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="font-mono text-primary truncate flex-1 min-w-0"
                title={ab.anchor_locator}
              >
                {ab.anchor_locator}
              </span>
              {ab.confirmed ? (
                <span className="shrink-0 text-[10px] text-emerald-700 border border-emerald-400 bg-emerald-50 px-1.5 py-0.5 rounded">
                  ✓ confirmed
                </span>
              ) : (
                <Button size="sm" className="shrink-0 text-[11px] h-6">
                  매핑
                </Button>
              )}
            </div>
            <div className="flex items-center gap-1.5 text-[10.5px] text-muted-foreground min-w-0">
              <span className="shrink-0 uppercase tracking-wider text-[9.5px]">slot</span>
              <span className="font-mono truncate min-w-0 flex-1" title={ab.target_slot}>
                {ab.target_slot}
              </span>
            </div>
          </div>
        ))}
        {anchors.length === 0 && (
          <p className="text-muted-foreground text-[11.5px]">
            anchor 미등록 (Java 분석 + Action 매핑 후 표시)
          </p>
        )}
      </Section>

      <AuthoringBridge note="Action params / output / sub_actions / anchor mapping 의 대량 변경은 Authoring 모드에서 LLM 도움 받아." />
    </div>
  );
}

// R2-5: workflow action 의 sub_actions chain (예: slab design 의 21 step).
// MainPanel ActionDetail 에 인라인 노출 — 페르소나 A 가 "코드 정보 없음" dead-end
// 라며 평가한 회귀 fix. step 별 클릭 시 그 sub_action 으로 selection 이동.
function SubActionsChain({ action }: { action: ActionDTO }) {
  const { setSelectedAction } = useWorkbench();
  const [subActions, setSubActions] = useState<Map<string, ActionDTO>>(new Map());

  useEffect(() => {
    let cancelled = false;
    // 각 sub_action 의 label / kind / verification_level 가져오기 (lookup 풍부화).
    // 실패해도 fqn 만으로도 클릭 가능하므로 best-effort.
    (async () => {
      const results = await Promise.all(
        action.sub_actions.map(fqn =>
          ontologyApi.getAction(fqn).catch(() => null)
        )
      );
      if (cancelled) return;
      const map = new Map<string, ActionDTO>();
      action.sub_actions.forEach((fqn, i) => {
        if (results[i]) map.set(fqn, results[i]!);
      });
      setSubActions(map);
    })();
    return () => { cancelled = true; };
  }, [action.fqn, action.sub_actions]);

  return (
    <Section title={<>구성 단계 (chain) · {action.sub_actions.length} step <HelpHint term="workflow" inline /></>}>
      {/* R4-6: chain 번호 vs description 내 STEP_NO 가 다를 수 있음.
          chain 번호는 sub_actions 배열 순서 (1..N), description 의 "step 14" 같은 표기는
          원본 알고리즘의 STEP_NO. 페르소나 A 가 13→15 jump 로 오해한 케이스. */}
      <p className="text-[10.5px] text-muted-foreground/80 mb-2 leading-relaxed">
        번호는 workflow chain 순서. step description 안의 "step N" 은 원본 알고리즘
        STEP_NO 라 chain 순서와 다를 수 있음 (예: iteration 단계는 합쳐서 표기).
      </p>
      <div className="space-y-1">
        {action.sub_actions.map((subFqn, i) => {
          const sub = subActions.get(subFqn);
          return (
            <button
              key={subFqn}
              onClick={() => setSelectedAction(subFqn)}
              className="w-full text-left bg-muted hover:bg-orange-50 hover:border-orange-300 border border-transparent px-3 py-2 rounded text-[12px] min-w-0 transition-colors group"
              title={subFqn}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-[10.5px] font-mono text-muted-foreground w-7 shrink-0 text-right tabular-nums">
                  {String(i + 1).padStart(2, "0")}.
                </span>
                <span className="font-mono text-foreground truncate min-w-0 flex-1">
                  {sub?.label ?? shortName(subFqn)}
                </span>
                {sub && (
                  <>
                    <span className="text-[10px] text-muted-foreground shrink-0">
                      {sub.kind}
                    </span>
                    {sub.verification_level && (
                      <span className={`text-[10px] px-1.5 py-px rounded-full border shrink-0 ${
                        sub.verification_level === "sim_verified" || sub.verification_level === "pr_proven"
                          ? "border-emerald-400 text-emerald-700 bg-emerald-50"
                          : sub.verification_level === "body_anchored"
                          ? "border-sky-400 text-sky-700 bg-sky-50"
                          : sub.verification_level === "signature_locked"
                          ? "border-violet-400 text-violet-700 bg-violet-50"
                          : "border-amber-400 text-amber-700 bg-amber-50"
                      }`}>
                        {sub.verification_level}
                      </span>
                    )}
                  </>
                )}
              </div>
              {/* R3-4 + R4-3: "자동 추천 — FQN" placeholder 가 description 끝에 trailing
                  으로 붙는 케이스 — stripPlaceholderTrailer 로 real text 만 남기고 표시. */}
              {(() => {
                const real = stripPlaceholderTrailer(sub?.description);
                if (!real) return null;
                return (
                  <div className="text-[10.5px] text-muted-foreground/80 mt-0.5 ml-9 line-clamp-2 leading-relaxed">
                    {real}
                  </div>
                );
              })()}
            </button>
          );
        })}
      </div>
    </Section>
  );
}

function Section({
  title,
  children,
  action,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="bg-card border border-border rounded-md my-3 p-3 min-w-0">
      <h3 className="text-[12.5px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-start justify-between gap-2 min-w-0">
        <span className="min-w-0 break-words flex-1">{title}</span>
        {action && <div className="shrink-0">{action}</div>}
      </h3>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function ParamRow({
  k,
  name,
  refTerm,
  confirmed,
}: {
  k: string;
  name: string;
  refTerm: string | null;
  confirmed: boolean;
}) {
  return (
    <div className="bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[140px_1fr_60px] gap-2 items-center text-xs min-w-0">
      <span className="font-mono text-primary truncate">{k}</span>
      <span className="min-w-0 flex items-center gap-1.5 overflow-hidden" title={refTerm ?? name}>
        <strong className="truncate min-w-0">{name}</strong>
        {refTerm && (
          <span className="text-[10px] border border-violet-300 bg-violet-50 px-1 rounded shrink-0 inline-flex items-center max-w-[60%]">
            → <FqnLink kind="term" fqn={refTerm} className="text-[10px] truncate" />
          </span>
        )}
      </span>
      <span
        className={cn(
          "text-[10px] px-1 rounded text-center",
          confirmed
            ? "text-emerald-400 border border-emerald-400 bg-emerald-400/10"
            : "text-amber-400 border border-amber-400 bg-amber-400/10",
        )}
      >
        {confirmed ? "✓" : "..."}
      </span>
    </div>
  );
}

// ── Split mode — code ↔ ontology side-by-side (real impl) ───────────
function SplitMode() {
  const {
    activeRepoId, selectedActionFqn,
  } = useWorkbench();
  const [action, setAction] = useState<ActionDTO | null>(null);
  const [parentClass, setParentClass] = useState<CodeTypeDTO | null>(null);
  const [allRules, setAllRules] = useState<BusinessRuleDTO[]>([]);
  const [methodAnchors, setMethodAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [hoverLine, setHoverLine] = useState<number | null>(null);

  // Action + 그 primary realization 의 method body fetch + AnchorBinding 페치.
  useEffect(() => {
    if (!selectedActionFqn) {
      setAction(null); setParentClass(null); setMethodAnchors([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    ontologyApi.getAction(selectedActionFqn).then(async (a) => {
      if (cancelled || !a) {
        if (!cancelled) { setAction(null); setLoading(false); }
        return;
      }
      setAction(a);
      const primary = a.realizations.find(r => r.scope === "primary") ?? a.realizations[0];
      if (!primary) { setParentClass(null); setMethodAnchors([]); setLoading(false); return; }
      const parentFqn = parentTypeFqnOfMethod(primary.code_method_fqn);
      if (!parentFqn) { setParentClass(null); setMethodAnchors([]); setLoading(false); return; }
      // 병렬 fetch — parent class body + 해당 method 의 anchor_bindings (semantic)
      try {
        const [ct, abs] = await Promise.all([
          ontologyApi.getCodeType(parentFqn),
          ontologyApi.getAnchorBindingsForMethod(primary.code_method_fqn).catch(() => []),
        ]);
        if (!cancelled) {
          setParentClass(ct);
          setMethodAnchors(abs);
        }
      } catch {
        if (!cancelled) { setParentClass(null); setMethodAnchors([]); }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }).catch(() => { if (!cancelled) { setAction(null); setLoading(false); }});
    return () => { cancelled = true; };
  }, [selectedActionFqn]);

  // BR (이 method 가 enforced_by 에 포함된 것) — list 페치 후 client-side filter.
  useEffect(() => {
    let cancelled = false;
    ontologyApi.listBusinessRules({ repo_id: activeRepoId }).then((rs) => {
      if (!cancelled) setAllRules(rs);
    }).catch(() => { if (!cancelled) setAllRules([]); });
    return () => { cancelled = true; };
  }, [activeRepoId]);

  if (!selectedActionFqn) {
    return (
      <div className="p-6 text-muted-foreground text-sm">
        Split 모드는 Action 선택 시 활성. 좌측 트리에서 Action leaf 클릭.
      </div>
    );
  }
  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!action) return <div className="p-6 text-muted-foreground text-sm">Action 찾을 수 없음</div>;

  const primaryReal = action.realizations.find(r => r.scope === "primary") ?? action.realizations[0];
  const method = parentClass?.methods.find(m => m.fqn === primaryReal?.code_method_fqn);
  // 통합 anchor list — Java parser static anchors (param/return) + semantic AnchorBinding (target Action slot).
  // 둘은 다른 종류이므로 화면에서 시각 구분.
  const enforcedRules = allRules.filter(r => r.enforced_by.includes(primaryReal?.code_method_fqn ?? ""));

  return (
    <div className="grid grid-cols-2 h-full divide-x divide-border">
      {/* === 좌측: Java source === */}
      <div className="overflow-auto bg-card">
        <div className="px-3 py-1.5 border-b border-border bg-muted/40 text-[11px] flex items-center gap-2 sticky top-0 min-w-0">
          <span className="font-semibold shrink-0">📦 {parentClass?.simple_name ?? "?"}</span>
          <span
            className="text-muted-foreground font-mono truncate min-w-0 flex-1"
            title={primaryReal?.code_method_fqn}
          >
            {primaryReal?.code_method_fqn ? methodTail(primaryReal.code_method_fqn) : ""}
          </span>
          {method?.line_start && (
            <span className="ml-auto shrink-0 text-muted-foreground">L{method.line_start}–{method.line_end}</span>
          )}
        </div>
        {!method ? (
          <div className="p-6 text-muted-foreground text-[12px] space-y-1">
            <div>method body 를 못 찾음.</div>
            <div>parent class: <span className="font-mono" title={parentClass?.fqn}>{parentClass?.simple_name ?? "(미찾음)"}</span></div>
            <div>method: <span className="font-mono" title={primaryReal?.code_method_fqn}>{primaryReal?.code_method_fqn ? methodTail(primaryReal.code_method_fqn) : ""}</span></div>
          </div>
        ) : !method.body_text ? (
          <div className="p-6 text-muted-foreground text-[12px]">
            body_text 미저장 — Java parser 가 abstract / interface / @Override-only 경우 body 비어있을 수 있음.
          </div>
        ) : (
          <JavaCode
            source={method.body_text}
            startLine={method.line_start ?? 1}
            markers={buildLineMarkers(method.anchors, methodAnchors)}
            hoverLine={hoverLine}
            setHoverLine={setHoverLine}
          />
        )}
      </div>

      {/* === 우측: 매핑 카드 === */}
      <div className="overflow-auto p-3 space-y-3 bg-background">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
          🔗 매핑 — Action ↔ 코드
        </div>

        {/* Action 본체 */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] text-muted-foreground mb-1">Action</div>
          <div
            className="font-mono text-[12.5px] text-foreground truncate"
            title={action.fqn}
          >
            {prettyFqn(action.fqn, "action")}
          </div>
          <div className="text-[11px] text-foreground mt-1">{action.label}</div>
          <div className="flex gap-1 mt-2">
            <span className="text-[10px] px-1.5 py-px rounded-full border border-orange-300 text-orange-700 bg-orange-50">
              {action.kind}
            </span>
            <span className="text-[10px] px-1.5 py-px rounded-full border border-amber-300 text-amber-700 bg-amber-50">
              {action.verification_level}
            </span>
          </div>
        </div>

        {/* Semantic AnchorBinding (Action slot 매핑) — 핵심 차별점 */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
            ⚓ Semantic Anchors (Action ↔ slot) · {methodAnchors.length}
          </div>
          {methodAnchors.length === 0 && (
            <p className="text-[11px] text-muted-foreground">이 method 에 매핑된 AnchorBinding 없음.</p>
          )}
          {methodAnchors.map((a, i) => (
            <div
              key={i}
              onMouseEnter={() => setHoverLine(a.line ?? null)}
              onMouseLeave={() => setHoverLine(null)}
              className={cn(
                "px-2 py-1.5 rounded my-1 text-[11px] cursor-pointer transition-colors border",
                hoverLine === a.line
                  ? "bg-sky-100 border-sky-400"
                  : "bg-sky-50/40 border-sky-200 hover:border-sky-400"
              )}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="font-mono text-[10px] text-sky-700 font-semibold shrink-0">L{a.line ?? "?"}</span>
                <span
                  className="font-mono text-foreground truncate flex-1 min-w-0"
                  title={a.anchor_locator}
                >
                  {a.anchor_locator}
                </span>
                {a.confirmed && <span className="text-[9.5px] text-emerald-700 shrink-0">✓</span>}
              </div>
              <div className="text-[10.5px] text-muted-foreground mt-0.5">
                slot: <span className="font-mono">{a.target_slot}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Static parser anchors — param/return 자동 추출 (스크롤 가능) */}
        {method && method.anchors.length > 0 && (
          <div className="bg-card border border-border rounded p-3">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              Static Parser Anchors · {method.anchors.length}
            </div>
            <div className="space-y-0.5 max-h-48 overflow-y-auto pr-1">
              {method.anchors.map((a, i) => (
                <div
                  key={i}
                  onMouseEnter={() => setHoverLine(a.line ?? null)}
                  onMouseLeave={() => setHoverLine(null)}
                  className="grid grid-cols-[40px_60px_1fr] gap-1 text-[10.5px] cursor-pointer hover:bg-amber-50 px-1 rounded"
                >
                  <span className="font-mono text-amber-700">L{a.line ?? "?"}</span>
                  <span className="text-muted-foreground">{a.kind}</span>
                  <span className="font-mono text-foreground truncate min-w-0" title={a.locator}>{a.locator}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* BR enforced */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1">
            <Shield className="w-3 h-3" />
            BR enforced by 이 method · {enforcedRules.length}
          </div>
          {enforcedRules.length === 0 && (
            <p className="text-[11px] text-muted-foreground">이 method 가 enforce 하는 BR 없음.</p>
          )}
          {enforcedRules.map((r, i) => (
            <div key={i} className="px-2 py-1.5 rounded bg-rose-50 border border-rose-200 my-1 text-[11px]">
              <div className="flex items-center gap-1">
                <span className={cn(
                  "w-1.5 h-1.5 rounded-sm shrink-0",
                  r.severity === "hard" ? "bg-rose-500" : "bg-amber-500"
                )} />
                <span
                  className="font-mono text-rose-800 truncate min-w-0 flex-1"
                  title={r.fqn}
                >
                  {prettyFqn(r.fqn, "rule")}
                </span>
              </div>
              <div className="text-[10.5px] text-foreground mt-0.5 line-clamp-2 break-words">{r.statement}</div>
              {r.operational_history.length > 0 && (
                <div className="text-[10px] text-rose-700 mt-1">
                  ⚠ history: {r.operational_history.map(h => h.incident_id).join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Action params 요약 */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
            📋 Action params · {action.params.length}
          </div>
          {action.params.length === 0 && (
            <p className="text-[11px] text-muted-foreground">params 없음 (`[]`). method 인자 직접 사용.</p>
          )}
          {action.params.map((p, i) => (
            <div key={i} className="text-[11px] my-0.5 grid grid-cols-[120px_1fr] gap-2 min-w-0">
              <span className="font-mono text-primary truncate min-w-0" title={p.name}>[{i}] {p.name}</span>
              <span className="font-mono text-foreground truncate min-w-0" title={p.object_ref_term ?? p.type ?? ""}>
                {p.object_ref_term ?? p.type ?? "?"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Deprecated — replaced by JavaCode + buildLineMarkers. */
function _CodeViewUnused({
  body, startLine, staticAnchors, semanticAnchors, hoverLine, setHoverLine,
}: {
  body: string;
  startLine: number;
  staticAnchors: { line?: number | null; locator: string; kind: string }[];
  semanticAnchors: AnchorBindingDTO[];
  hoverLine: number | null;
  setHoverLine: (n: number | null) => void;
}) {
  const lines = body.split("\n");
  const semanticByLine = new Map<number, AnchorBindingDTO[]>();
  for (const a of semanticAnchors) {
    if (a.line == null) continue;
    if (!semanticByLine.has(a.line)) semanticByLine.set(a.line, []);
    semanticByLine.get(a.line)!.push(a);
  }
  const staticByLine = new Map<number, typeof staticAnchors[number][]>();
  for (const a of staticAnchors) {
    if (a.line == null) continue;
    if (!staticByLine.has(a.line)) staticByLine.set(a.line, []);
    staticByLine.get(a.line)!.push(a);
  }
  return (
    <div className="font-mono text-[12px] leading-relaxed">
      {lines.map((line, idx) => {
        const lineNo = startLine + idx;
        const semHere = semanticByLine.get(lineNo) ?? [];
        const stHere = staticByLine.get(lineNo) ?? [];
        const hasSemantic = semHere.length > 0;
        const isHover = hoverLine === lineNo;
        return (
          <div
            key={idx}
            onMouseEnter={() => (hasSemantic || stHere.length > 0) && setHoverLine(lineNo)}
            onMouseLeave={() => isHover && setHoverLine(null)}
            className={cn(
              "grid grid-cols-[40px_20px_1fr] gap-1 px-3 transition-colors",
              isHover && "bg-sky-100",
              !isHover && hasSemantic && "bg-sky-50/60",
              !isHover && !hasSemantic && stHere.length > 0 && "bg-amber-50/30"
            )}
            title={[
              ...semHere.map(a => "anchor: " + a.anchor_locator + " -> " + a.target_slot),
              ...stHere.map(a => a.kind + ": " + a.locator),
            ].join("\n") || undefined}
          >
            <span className="text-right text-muted-foreground select-none">{lineNo}</span>
            <span className="select-none text-center text-[11px]">
              {hasSemantic ? <span className="text-sky-600 font-bold">A</span>
                : stHere.length > 0 ? <span className="text-amber-600">·</span> : ""}
            </span>
            <span className="whitespace-pre-wrap break-all text-foreground">{line || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Static parser anchors + semantic AnchorBindings → JavaCode markers Map. */
function buildLineMarkers(
  staticAnchors: { line?: number | null; locator: string; kind: string }[],
  semanticAnchors: AnchorBindingDTO[],
): Map<number, { label: string; tone: "semantic" | "static" | "info" }> {
  const m = new Map<number, { label: string; tone: "semantic" | "static" | "info" }>();
  for (const a of staticAnchors) {
    if (a.line == null) continue;
    if (!m.has(a.line)) m.set(a.line, { label: `${a.kind}: ${a.locator}`, tone: "static" });
  }
  for (const a of semanticAnchors) {
    if (a.line == null) continue;
    // semantic 이 우선 (덮어씀)
    m.set(a.line, {
      label: `anchor: ${a.anchor_locator} → ${a.target_slot}`,
      tone: "semantic",
    });
  }
  return m;
}

/** "com.foo.Bar.method(Args)" → "com.foo.Bar". method() 의 paren 앞 마지막 . 기준. */
function parentTypeFqnOfMethod(methodFqn: string): string | null {
  const parenIdx = methodFqn.indexOf("(");
  const beforeParen = parenIdx >= 0 ? methodFqn.slice(0, parenIdx) : methodFqn;
  const lastDot = beforeParen.lastIndexOf(".");
  if (lastDot < 0) return null;
  return beforeParen.slice(0, lastDot);
}

// Backward — BackwardMode.tsx 로 분리 (Phase 2a 완료)

// ─────────────────────────────────────────────────────────────────────────
// Term Detail
// ─────────────────────────────────────────────────────────────────────────
function TermDetail({ fqn }: { fqn: string }) {
  const { activeRepoId, setSelectedTerm } = useWorkbench();
  const [term, setTerm] = useState<TermDTO | null>(null);
  const [parts, setParts] = useState<CompositionDTO[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      ontologyApi.getTerm(fqn).catch(() => null),
      ontologyApi.effectiveParts(fqn, activeRepoId).catch(() => []),
    ]).then(([t, p]) => {
      if (cancelled) return;
      setTerm(t); setParts(p); setLoading(false);
    });
    return () => { cancelled = true; };
  }, [fqn, activeRepoId]);

  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!term)   return <div className="p-6 text-muted-foreground text-sm">Term 찾을 수 없음 — DB 에 미등록</div>;

  const patch = async (p: Parameters<typeof ontologyApi.patchTerm>[2]) => {
    await ontologyApi.patchTerm(term.repo_id, term.fqn, p);
    setTerm({ ...term, ...p } as TermDTO);
  };

  return (
    <div className="p-5 max-w-[920px]">
      <div className="bg-violet-500/5 border-l-2 border-violet-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground inline-flex items-center gap-1.5">
        <Atom className="w-3.5 h-3.5 text-violet-500" />
        <span><strong className="text-violet-700">BusinessTerm</strong> — 도메인 의미 단위</span>
      </div>
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2 flex-nowrap min-w-0">
        <span className="min-w-0 flex-1 truncate" title={term.label}>
          <InlineEditText
            value={term.label}
            onSave={(v) => patch({ label: v })}
            placeholder="(label 미지정)"
            className="truncate"
          />
        </span>
        <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border border-violet-400 text-violet-700 bg-violet-50">
          {term.kind}
          <HelpHint term={term.kind} inline />
        </span>
        {term.is_root_entity && (
          <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border border-emerald-400 text-emerald-700 bg-emerald-50">
            root_entity
            <HelpHint term="root_entity" inline />
          </span>
        )}
        <span className="ml-auto shrink-0">
          <ConfirmToggle
            kind="term"
            id={term.fqn}
            repoId={term.repo_id}
            confirmed={term.confirmed}
            onChanged={(v) => setTerm({ ...term, confirmed: v })}
          />
        </span>
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono flex items-center gap-2 min-w-0">
        <span className="truncate min-w-0 flex-1" title={term.fqn}>{prettyFqn(term.fqn, "term")}</span>
        <span className="text-muted-foreground/70 shrink-0">·</span>
        <span className="inline-flex items-center gap-1 shrink-0">
          domain
          <InlineEditText
            value={term.domain ?? ""}
            onSave={(v) => patch({ domain: v })}
            placeholder="(미지정)"
            inputClassName="text-xs font-mono"
          />
        </span>
      </div>

      <Section title="설명">
        <InlineEditTextArea
          value={stripPlaceholderTrailer(term.description)}
          onSave={(v) => patch({ description: v })}
          placeholder="(설명 미지정 — 클릭해서 편집)"
          rows={3}
          className="text-[12.5px] text-foreground leading-relaxed"
        />
      </Section>

      {term.kind === "atomic" && (
        <Section title="값 형식 (atomic)">
          <KV k="value_type" v={
            <InlineEditText
              value={term.value_type ?? ""}
              onSave={(v) => patch({ value_type: v })}
              placeholder="(미지정)"
              inputClassName="text-xs font-mono"
            />
          } />
          <KV k="unit" v={
            <InlineEditText
              value={term.unit ?? ""}
              onSave={(v) => patch({ unit: v })}
              placeholder="—"
              inputClassName="text-xs font-mono"
            />
          } />
          <KV k="range" v={term.range ? `[${term.range.join(", ")}]` : "—"} />
          <KV k="enum_values" v={
            <InlineEditList
              value={term.enum_values ?? []}
              onSave={(v) => patch({ enum_values: v })}
              placeholder="(없음)"
            />
          } />
        </Section>
      )}

      <Section title={`Aliases · ${term.aliases.length}`}>
        <InlineEditList
          value={term.aliases}
          onSave={(v) => patch({ aliases: v })}
          placeholder="(alias 미등록 — 클릭해서 추가)"
        />
      </Section>

      {term.kind === "composite" && (
        <Section title={`Composition Parts · ${parts.length}`}>
          {parts.length === 0 && (
            <p className="text-[11.5px] text-muted-foreground">part 미정의 (effective parts 0)</p>
          )}
          {parts.map((p, i) => (
            <button
              key={i}
              onClick={() => setSelectedTerm(p.child_fqn)}
              className="w-full text-left bg-muted hover:bg-muted/70 px-3 py-1.5 rounded my-1 grid grid-cols-[140px_1fr_60px] gap-2 items-center text-xs transition-colors"
              title={`이 part 의 detail 로 이동: ${p.child_fqn}`}
            >
              <span className="font-mono text-primary truncate">{p.role_name}</span>
              <span className="min-w-0 truncate" title={p.child_fqn}>
                <strong>{shortName(p.child_fqn)}</strong>
              </span>
              <span className="text-[10px] text-muted-foreground text-center shrink-0">{p.cardinality}{p.required ? " req" : ""}</span>
            </button>
          ))}
        </Section>
      )}

      <Section title="Flags">
        <KV k="is_abstract" v={term.is_abstract ? "✓" : "—"} />
        <KV k="is_interface" v={term.is_interface ? "✓" : "—"} />
        <KV k="struct_like_hint" v={term.struct_like_hint ? "✓" : "—"} />
      </Section>

      <AuthoringBridge note="Term 의 label / aliases / facets 등 대량 변경은 Authoring 모드에서 LLM 도움 받아 진행." />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// CodeType Detail
// ─────────────────────────────────────────────────────────────────────────
function CodeTypeDetail({ fqn }: { fqn: string }) {
  const { setSelectedAction } = useWorkbench();
  const [ct, setCt] = useState<CodeTypeDTO | null>(null);
  const [loading, setLoading] = useState(true);
  // Method 인라인 펼침 — 여러 개 동시 expand 허용.
  const [expandedMethods, setExpandedMethods] = useState<Set<string>>(new Set());
  const toggleMethod = (mfqn: string) => setExpandedMethods((prev) => {
    const next = new Set(prev);
    if (next.has(mfqn)) next.delete(mfqn);
    else next.add(mfqn);
    return next;
  });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setExpandedMethods(new Set());   // 새 CodeType 진입 시 펼침 상태 초기화
    ontologyApi.getCodeType(fqn).then((t) => {
      if (cancelled) return;
      setCt(t); setLoading(false);
    }).catch(() => { if (!cancelled) { setCt(null); setLoading(false); }});
    return () => { cancelled = true; };
  }, [fqn]);

  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!ct)     return <div className="p-6 text-muted-foreground text-sm">CodeType 찾을 수 없음</div>;

  return (
    <div className="p-5 max-w-[1000px]">
      <div className="bg-primary/5 border-l-2 border-primary px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        📦 <strong className="text-primary">CodeType</strong> — Java 클래스/인터페이스 (mirror)
      </div>
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2 flex-nowrap min-w-0">
        <span className="truncate min-w-0 flex-1" title={ct.simple_name}>{ct.simple_name}</span>
        <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border border-primary/40 text-primary bg-primary/10">
          {ct.kind}
        </span>
        <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground">
          role: {ct.role}
        </span>
        {ct.is_abstract && (
          <span className="shrink-0 text-[11px] px-1.5 py-px rounded-full border border-amber-400 text-amber-700 bg-amber-50">abstract</span>
        )}
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono flex items-center gap-2 min-w-0">
        <span className="truncate min-w-0 flex-1" title={ct.fqn}>{ct.package}</span>
        {ct.line_start && (
          <span className="shrink-0 text-muted-foreground/80" title={ct.source_file}>
            · {ct.source_file.split("/").pop()}:{ct.line_start}{ct.line_end ? `–${ct.line_end}` : ""}
          </span>
        )}
      </div>

      {(ct.extends || ct.implements.length > 0) && (
        <Section title="Inheritance">
          {ct.extends && <KV k="extends" v={<FqnLink kind="code_type" fqn={ct.extends} />} />}
          {ct.implements.map((i, idx) => (
            <KV key={idx} k={idx === 0 ? "implements" : ""} v={<FqnLink kind="code_type" fqn={i} />} />
          ))}
        </Section>
      )}

      {ct.annotations.length > 0 && (
        <Section title={`Annotations · ${ct.annotations.length}`}>
          <div className="flex flex-wrap gap-1">
            {ct.annotations.map((a, i) => (
              <span key={i} className="text-[10.5px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-mono">@{a}</span>
            ))}
          </div>
        </Section>
      )}

      {ct.fields.length > 0 && (
        <Section title={`Fields · ${ct.fields.length}`}>
          {ct.fields.slice(0, 30).map((f, i) => (
            <div key={i} className="bg-muted px-3 py-1 rounded my-0.5 text-xs grid grid-cols-[160px_1fr_60px] gap-2 items-center min-w-0">
              <span className="font-mono text-primary truncate min-w-0" title={f.name}>{f.name}</span>
              <span className="font-mono text-foreground truncate min-w-0" title={f.type}>{f.type}</span>
              <span className="text-[9.5px] text-muted-foreground font-mono text-right shrink-0">{f.line ? `L${f.line}` : ""}</span>
            </div>
          ))}
          {ct.fields.length > 30 && (
            <p className="text-[11px] text-muted-foreground mt-1">… {ct.fields.length - 30} 더</p>
          )}
        </Section>
      )}

      <Section title={`Methods · ${ct.methods.length}`}>
        {ct.methods.length === 0 && (
          <p className="text-[11.5px] text-muted-foreground">메서드 없음</p>
        )}
        {ct.methods.slice(0, 50).map((m, i) => {
          const expanded = expandedMethods.has(m.fqn);
          const hasBody = Boolean(m.body_text && m.body_text.trim());
          return (
            <div key={i} className="my-0.5 rounded overflow-hidden">
              <button
                type="button"
                onClick={() => hasBody && toggleMethod(m.fqn)}
                disabled={!hasBody}
                className={cn(
                  "w-full bg-muted px-3 py-1 text-xs flex items-center gap-2 text-left transition-colors",
                  hasBody ? "hover:bg-muted/70 cursor-pointer" : "cursor-default opacity-80",
                  expanded && "bg-primary/10",
                )}
                title={hasBody ? (expanded ? "접기" : "메서드 본문 펼치기") : "body 가 없음 (abstract / interface / parser 누락)"}
              >
                <ChevronRight className={cn(
                  "w-3 h-3 shrink-0 transition-transform",
                  expanded && "rotate-90",
                  !hasBody && "opacity-30",
                )} />
                <span className={cn(
                  "text-[9.5px] px-1 rounded border shrink-0",
                  m.role === "business" ? "text-emerald-700 border-emerald-300 bg-emerald-50"
                  : m.role === "helper" ? "text-amber-700 border-amber-300 bg-amber-50"
                  : "text-muted-foreground border-border bg-card"
                )}>{m.role}</span>
                <span className="font-mono truncate flex-1 min-w-0">
                  {m.name}({m.params.map(p => p.type).join(", ")}) → {m.return_type}
                </span>
                {m.line_start && <span className="text-[9.5px] text-muted-foreground font-mono shrink-0">L{m.line_start}</span>}
                {m.is_override && <span className="text-[9px] text-muted-foreground border border-border px-1 rounded shrink-0">@Override</span>}
              </button>
              {expanded && hasBody && (
                <div className="border-l-2 border-primary bg-card mt-0.5">
                  <div className="text-[10px] text-muted-foreground px-3 py-1 border-b border-border">
                    line {m.line_start}–{m.line_end}{m.anchors.length > 0 && ` · anchors ${m.anchors.length}`}
                  </div>
                  <div className="text-[11px] overflow-x-auto">
                    <JavaCode source={m.body_text ?? ""} startLine={m.line_start ?? 1} />
                  </div>
                </div>
              )}
            </div>
          );
        })}
        {ct.methods.length > 50 && (
          <p className="text-[11px] text-muted-foreground mt-1">… {ct.methods.length - 50} 더</p>
        )}
      </Section>

      <Section title="원본 파일">
        <p className="text-[11.5px] text-foreground font-mono">{ct.source_file}</p>
      </Section>

      <div className="text-[11px] text-muted-foreground mt-2">
        * 이 CodeType 에 매핑된 Action/Term 이 있는지 확인하려면 좌측 검색에서 simple_name 검색
        또는 미래 phase 의 reverse-lookup endpoint (Phase E #50+) 활용.
      </div>

      <AuthoringBridge note="CodeType 자체는 Java 코드의 mirror — 직접 수정 ❌. role 분류 / Action 매핑 추가는 Authoring 모드에서." />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// BusinessRule Detail
// ─────────────────────────────────────────────────────────────────────────
function BusinessRuleDetail({ fqn }: { fqn: string }) {
  const { activeRepoId } = useWorkbench();
  const [rule, setRule] = useState<BusinessRuleDTO | null>(null);
  const [loading, setLoading] = useState(true);

  // BR 단일 조회 endpoint 미존재 — list 에서 filter (17건이라 부담 없음)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    ontologyApi.listBusinessRules({ repo_id: activeRepoId }).then((rows) => {
      if (cancelled) return;
      setRule(rows.find(r => r.fqn === fqn) ?? null);
      setLoading(false);
    }).catch(() => { if (!cancelled) { setRule(null); setLoading(false); }});
    return () => { cancelled = true; };
  }, [fqn, activeRepoId]);

  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!rule)   return <div className="p-6 text-muted-foreground text-sm">BR 찾을 수 없음</div>;

  const patch = async (p: Parameters<typeof ontologyApi.patchBusinessRule>[2]) => {
    await ontologyApi.patchBusinessRule(rule.repo_id, rule.fqn, p);
    setRule({ ...rule, ...p } as BusinessRuleDTO);
  };

  return (
    <div className="p-5 max-w-[920px]">
      <div className="bg-rose-500/5 border-l-2 border-rose-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground inline-flex items-center gap-1.5">
        <Scale className="w-3.5 h-3.5 text-rose-500" />
        <span><strong className="text-rose-700">BusinessRule</strong> — 도메인 제약 (코드 가드 enforced)</span>
      </div>
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2 flex-nowrap min-w-0">
        <span
          className="font-mono text-foreground text-[15px] truncate min-w-0 flex-1"
          title={rule.fqn}
        >
          {prettyFqn(rule.fqn, "rule")}
        </span>
        <span className={cn(
          "text-[11px] px-1.5 py-px rounded-full border shrink-0",
          rule.severity === "hard"
            ? "border-rose-400 text-rose-700 bg-rose-50"
            : "border-amber-400 text-amber-700 bg-amber-50"
        )}>
          <InlineEditSelect
            value={rule.severity as "hard" | "soft"}
            options={["hard", "soft"] as const}
            onSave={(v) => patch({ severity: v })}
          />
        </span>
        <span className="ml-auto shrink-0">
          <ConfirmToggle
            kind="rule"
            id={rule.fqn}
            repoId={rule.repo_id}
            confirmed={rule.confirmed}
            onChanged={(v) => setRule({ ...rule, confirmed: v })}
          />
        </span>
      </h1>
      <div className="text-[10.5px] text-muted-foreground font-mono mb-3 truncate" title={rule.fqn}>
        {rule.fqn}
      </div>

      <Section title="Statement">
        <InlineEditTextArea
          value={rule.statement ?? ""}
          onSave={(v) => patch({ statement: v })}
          placeholder="(statement 미지정 — 클릭해서 편집)"
          rows={4}
          className="text-[13px] text-foreground leading-relaxed"
        />
      </Section>

      <Section title={<>Enforced By (코드 가드 위치) · {rule.enforced_by.length} <HelpHint term="enforced_by" inline /></>}>
        {rule.enforced_by.length === 0 && (
          <p className="text-[11.5px] text-muted-foreground">미등록 — 운영 시 enforced_by 자동 검출 큐로 보강.</p>
        )}
        {rule.enforced_by.map((m, i) => (
          <div key={i} className="bg-muted px-3 py-1.5 rounded my-1 text-xs">
            <span className="text-[10px] text-amber-700 border border-amber-300 bg-amber-50 px-1 rounded mr-2">code</span>
            <FqnLink kind="code_method" fqn={m} />
          </div>
        ))}
      </Section>

      {rule.terms_ref.length > 0 && (
        <Section title={<>Terms Referenced · {rule.terms_ref.length} <HelpHint term="term" inline /></>}>
          <div className="flex flex-wrap gap-1">
            {rule.terms_ref.map((t, i) => (
              <span key={i} className="text-[10.5px] px-1.5 py-0.5 rounded bg-violet-50 border border-violet-200">
                <FqnLink kind="term" fqn={t} className="text-[10.5px]" />
              </span>
            ))}
          </div>
        </Section>
      )}

      {rule.operational_history.length > 0 && (
        <Section title={<>Operational History (운영 사고) · {rule.operational_history.length} <HelpHint term="operational_history" inline /></>}>
          {rule.operational_history.map((h, i) => (
            <div key={i} className="bg-muted px-3 py-1.5 rounded my-1 text-xs min-w-0">
              <div className="flex items-center gap-2 min-w-0">
                <span className="shrink-0 text-[10px] text-rose-700 border border-rose-300 bg-rose-50 px-1 rounded font-mono">{h.incident_id ?? "?"}</span>
                <span className="font-semibold truncate min-w-0 flex-1" title={h.summary}>{h.summary}</span>
                {h.occurred_at && (
                  <span className="shrink-0 text-[10px] text-muted-foreground" title={h.occurred_at}>
                    {h.occurred_at}
                  </span>
                )}
              </div>
              {(h.triggered_by || h.fixed_at_commit) && (
                <div className="text-[10.5px] text-muted-foreground mt-1 truncate" title={`${h.triggered_by ?? ""} ${h.fixed_at_commit ?? ""}`}>
                  {h.triggered_by && <>by {h.triggered_by} </>}
                  {h.fixed_at_commit && <>· commit {h.fixed_at_commit}</>}
                </div>
              )}
            </div>
          ))}
        </Section>
      )}

      {rule.violated_at_call.length > 0 && (
        <Section title={`Violated-At Call Sites · ${rule.violated_at_call.length}`}>
          {rule.violated_at_call.map((v, i) => (
            <div key={i} className="bg-muted px-3 py-1 rounded my-1 text-xs font-mono">
              {JSON.stringify(v)}
            </div>
          ))}
        </Section>
      )}

      <Section title="Source / Origin">
        <KV k="source" v={rule.source || "(미지정)"} />
      </Section>

      <AuthoringBridge note="BR statement / severity / enforced_by 의 대량 보강은 Authoring 모드에서 LLM 도움 받아." />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// AnchorBinding Detail
// ─────────────────────────────────────────────────────────────────────────
function AnchorDetail({ id }: { id: string }) {
  const { activeRepoId, setSelectedAction } = useWorkbench();
  const [anchor, setAnchor] = useState<AnchorBindingDTO | null>(null);
  const [loading, setLoading] = useState(true);

  // Anchor 단일 조회 endpoint 미존재 — list 에서 filter (9건)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    ontologyApi.listAnchorBindings({ repo_id: activeRepoId }).then((rows) => {
      if (cancelled) return;
      setAnchor(rows.find(a => a.id === id) ?? null);
      setLoading(false);
    }).catch(() => { if (!cancelled) { setAnchor(null); setLoading(false); }});
    return () => { cancelled = true; };
  }, [id, activeRepoId]);

  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!anchor) return <div className="p-6 text-muted-foreground text-sm">Anchor 찾을 수 없음</div>;

  const patch = async (p: Parameters<typeof ontologyApi.patchAnchorBinding>[2]) => {
    await ontologyApi.patchAnchorBinding(anchor.repo_id, anchor.id, p);
    setAnchor({ ...anchor, ...p } as AnchorBindingDTO);
  };

  return (
    <div className="p-5 max-w-[920px]">
      <div className="bg-sky-500/5 border-l-2 border-sky-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground inline-flex items-center gap-1.5">
        <AnchorIcon className="w-3.5 h-3.5 text-sky-500" />
        <span><strong className="text-sky-700">AnchorBinding</strong> — 코드 fragment ↔ Action slot</span>
      </div>
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2 flex-nowrap min-w-0">
        <span
          className="font-mono text-foreground text-[15px] truncate min-w-0 flex-1"
          title={anchor.id}
        >
          {anchorTail(anchor.id)}
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-sky-400 text-sky-700 bg-sky-50 shrink-0">
          conf {anchor.confidence.toFixed(2)}
          <HelpHint term="confidence" inline />
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground shrink-0">
          src: {anchor.source}
        </span>
        <span className="ml-auto shrink-0">
          <ConfirmToggle
            kind="anchor"
            id={anchor.id}
            repoId={anchor.repo_id}
            confirmed={anchor.confirmed}
            onChanged={(v) => setAnchor({ ...anchor, confirmed: v })}
          />
        </span>
      </h1>
      <div className="text-[10.5px] text-muted-foreground font-mono mb-3 truncate" title={anchor.id}>
        {anchor.id}
      </div>

      <Section title={<>Anchor Locator <HelpHint term="anchor_locator" inline /></>}>
        <div className="font-mono text-[13px] text-foreground bg-muted px-3 py-2 rounded break-all">
          <InlineEditText
            value={anchor.anchor_locator ?? ""}
            onSave={(v) => patch({ anchor_locator: v })}
            placeholder="(locator 미지정)"
            inputClassName="text-[13px] font-mono w-full min-w-[400px]"
          />
        </div>
      </Section>

      <Section title={<>Code Method (코드 위치) <HelpHint term="code_method" inline /></>}>
        <FqnLink kind="code_method" fqn={anchor.code_method_fqn} className="text-[12px]" />
        {anchor.line && (
          <p className="text-[11px] text-muted-foreground mt-1">
            line <span className="font-mono text-foreground">{anchor.line}</span> (1-indexed)
          </p>
        )}
      </Section>

      <Section title={<>Target Action / Slot <HelpHint term="target_slot" inline /></>}>
        <div className="bg-muted px-3 py-2 rounded">
          <button
            onClick={() => setSelectedAction(anchor.target_action_fqn)}
            className="font-mono text-[12px] text-primary hover:underline"
            title="Action detail 로 이동"
          >
            → {anchor.target_action_fqn}
          </button>
          <div className="text-[11px] text-muted-foreground mt-1 inline-flex items-center gap-1">
            slot:
            <InlineEditText
              value={anchor.target_slot ?? ""}
              onSave={(v) => patch({ target_slot: v })}
              placeholder="(slot 미지정)"
              inputClassName="text-[11px] font-mono"
            />
          </div>
        </div>
      </Section>

      <Section title="Rationale">
        <InlineEditTextArea
          value={anchor.rationale ?? ""}
          onSave={(v) => patch({ rationale: v })}
          placeholder="(rationale 미지정 — 클릭해서 편집)"
          rows={3}
          className="text-[12px] text-foreground leading-relaxed"
        />
      </Section>

      <AuthoringBridge note="Anchor locator / target_slot 재바인딩은 Authoring 모드 또는 Split mode 에서 직접 코드 fragment 클릭 매핑." />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────
function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 my-0.5 text-xs items-baseline min-w-0">
      <span className="text-muted-foreground truncate min-w-0" title={k}>{k}</span>
      <span className="text-foreground min-w-0 break-words">{v}</span>
    </div>
  );
}

/**
 * 5-ii Stage 3 — Authoring 모드 brigde.
 *
 * Forward Detail 은 inspection + 간단 toggle (5-ii Stage 1) 만. 대량 변경 (entity 신규 작성, 풀 form,
 * LLM 추천 따라 다중 field 갱신) 은 Authoring 모드 (cap 1~12) 의 책임.
 * 이 버튼이 두 흐름의 다리.
 */
function AuthoringBridge({ note }: { note: string }) {
  const { setMainMode } = useWorkbench();
  return (
    <div className="mt-4 p-3 bg-violet-50 border border-violet-200 rounded text-[11.5px] flex items-center gap-2">
      <span className="text-muted-foreground flex-1">{note}</span>
      <button
        onClick={() => setMainMode("authoring")}
        className="text-[11px] px-3 py-1 rounded border border-violet-400 text-violet-700 bg-white hover:bg-violet-100 transition-colors shrink-0"
      >
        ✏️ Authoring 모드로
      </button>
    </div>
  );
}

/**
 * Clickable FQN link — entity 종류별 selectXxx 액션 호출.
 * code_method 의 경우 parent class 로 navigate (method 단일 페이지 미존재).
 */
function FqnLink({
  kind, fqn, label, className, full = false,
}: {
  kind: "term" | "action" | "code_type" | "code_method" | "rule" | "anchor";
  fqn: string;
  label?: string;
  className?: string;
  /** true 면 full FQN 표시 (기본은 prettyFqn 짧은 형태). */
  full?: boolean;
}) {
  const {
    setSelectedTerm, setSelectedAction, setSelectedCodeType, setSelectedRule, setSelectedAnchor,
  } = useWorkbench();
  const onClick = () => {
    if (kind === "term") setSelectedTerm(fqn);
    else if (kind === "action") setSelectedAction(fqn);
    else if (kind === "code_type") setSelectedCodeType(fqn);
    else if (kind === "code_method") {
      const parent = parentTypeFqnOfMethod(fqn);
      if (parent) setSelectedCodeType(parent);
    }
    else if (kind === "rule") setSelectedRule(fqn);
    else if (kind === "anchor") setSelectedAnchor(fqn);
  };
  const colorClass: Record<typeof kind, string> = {
    term:        "text-violet-700 hover:bg-violet-50",
    action:      "text-orange-700 hover:bg-orange-50",
    code_type:   "text-primary hover:bg-primary/10",
    code_method: "text-primary hover:bg-primary/10",
    rule:        "text-rose-700 hover:bg-rose-50",
    anchor:      "text-sky-700 hover:bg-sky-50",
  };
  const display = label ?? (full ? fqn : prettyFqn(fqn, kind));
  return (
    <button
      onClick={onClick}
      className={cn(
        "font-mono truncate max-w-full hover:underline transition-colors px-1 -mx-1 rounded inline-block align-bottom",
        colorClass[kind],
        className,
      )}
      title={`${kind}: ${fqn}\n클릭 → detail 로 이동`}
    >
      {display}
    </button>
  );
}
