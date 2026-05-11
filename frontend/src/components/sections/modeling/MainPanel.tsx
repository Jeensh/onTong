"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Eye, ArrowUpRight } from "lucide-react";
import { useWorkbench, type MainMode } from "./store";
import {
  ontologyApi,
  type ActionDTO,
  type ActionParamDTO,
  type AnchorBindingDTO,
  type AnchorCandidateDTO,
  type BusinessRuleDTO,
  type CodeTypeDTO,
  type CodeTypeRole,
  type CompositionDTO,
  type TermDTO,
  type VerificationLevel,
} from "@/lib/api/ontology";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BackwardMode } from "./BackwardMode";
import { AuthoringMode } from "./AuthoringMode";
import { HelpHint } from "./HelpHint";
import { JavaCode } from "./JavaCode";
import { ConfirmToggle } from "./ConfirmToggle";
import { InlineEditList, InlineEditSelect, InlineEditText, InlineEditTextArea } from "./InlineEdit";
import { InlineEditRange } from "./InlineEditRange";
import { InlineEditAutocomplete, type AutocompleteSuggestion } from "./InlineEditAutocomplete";
import { ParamDrawer } from "./ParamDrawer";
import { FlagsRow, PanelStripe } from "./_panel_helpers";
import { CodePeekModal } from "./CodePeekModal";

const MODE_LABELS: { id: MainMode | "graph"; label: string }[] = [
  { id: "detail", label: "Detail" },
  { id: "split", label: "↕ Split" },
  { id: "graph", label: "🌐 Graph" },
  { id: "authoring", label: "✏️ Authoring" },
];

export function MainPanel() {
  const {
    mainMode, setMainMode, direction, setDirection, setGraphMode,
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
      <div className="h-8 px-3 bg-card border-b border-border flex items-center gap-2 flex-shrink-0">
        <div className="flex-1" />
        {/* Direction indicator (Forward only — Backward is a future phase) */}
        <div className="flex bg-muted border border-border rounded overflow-hidden mr-2">
          <button
            onClick={() => setDirection("fwd")}
            className={cn(
              "px-2.5 py-0.5 text-[11px]",
              direction === "fwd" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
            )}
          >
            🔍 Forward
          </button>
        </div>
        {/* Mode toggle */}
        <div className="flex bg-muted border border-border rounded overflow-hidden">
          {MODE_LABELS.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                if (m.id === "graph") setGraphMode(true);
                else setMainMode(m.id);
              }}
              className={cn(
                "px-2.5 py-0.5 text-[11px] border-r border-border last:border-r-0",
                m.id !== "graph" && mainMode === m.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div
        className={cn(
          "flex-1 overflow-auto",
          direction === "bwd" && "bg-amber-500/[0.02]",
        )}
      >
        {direction === "fwd" && mainMode === "detail" && <ForwardDetail activeKind={activeKind} />}
        {direction === "fwd" && mainMode === "split" && <SplitMode />}
        {direction === "fwd" && mainMode === "authoring" && <AuthoringMode />}
        {direction === "bwd" && <BackwardMode />}
      </div>
      <PeekModalHost />
    </>
  );
}

/**
 * Single global CodePeekModal driver — reads peek target from Zustand and
 * renders a modal so any FqnLink (deep in a panel) can open it without
 * disturbing the active Detail selection.
 */
function PeekModalHost() {
  const peekTarget = useWorkbench((s) => s.peekTarget);
  const closePeek = useWorkbench((s) => s.closePeek);
  return (
    <CodePeekModal
      open={peekTarget !== null}
      onClose={closePeek}
      kind={peekTarget?.kind ?? "code_type"}
      fqn={peekTarget?.fqn ?? ""}
      repoId={peekTarget?.repoId ?? ""}
      highlightLine={peekTarget?.highlightLine}
    />
  );
}

type ActiveKind =
  | { kind: "action";   id: string }
  | { kind: "term";     id: string }
  | { kind: "codeType"; id: string }
  | { kind: "rule";     id: string }
  | { kind: "anchor";   id: string };

// ── Forward Detail — 5 entity router (Action/Term/CodeType/BR/Anchor) ──
function ForwardDetail({ activeKind }: { activeKind: ActiveKind | null }) {
  if (!activeKind) {
    return (
      <div className="p-6 text-muted-foreground text-sm">
        선택 없음 — 좌측 트리의 <strong>코드</strong> 또는 <strong>온톨로지</strong> 탭에서 entity 선택.
      </div>
    );
  }
  if (activeKind.kind === "action")   return <ActionDetail fqn={activeKind.id} />;
  if (activeKind.kind === "term")     return <TermDetail fqn={activeKind.id} />;
  if (activeKind.kind === "codeType") return <CodeTypeDetail fqn={activeKind.id} />;
  if (activeKind.kind === "rule")     return <BusinessRuleDetail fqn={activeKind.id} />;
  if (activeKind.kind === "anchor")   return <AnchorDetail id={activeKind.id} />;
  return null;
}

// ── Action Detail (기존 ForwardDetail 의 본체) ─────────────────────────
function ActionDetail({ fqn }: { fqn: string }) {
  const { setMainMode } = useWorkbench();
  const selectedActionFqn = fqn;
  const [action, setAction] = useState<ActionDTO | null>(null);
  const [anchors, setAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(false);
  // #9 — ParamDrawer state.
  const [drawerParam, setDrawerParam] = useState<{ p: ActionParamDTO; i: number } | null>(null);

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

  // Action h1-area boolean flags (only `is_abstract` so far). Use FlagsRow so
  // false values render nothing.
  const actionFlags = [
    { key: "abstract", value: !!action.is_abstract, tooltip: "abstract Action — 직접 호출되지 않고 realization 통해 dispatch" },
  ];

  return (
    <PanelStripe color="primary">
    <div className="p-5 max-w-[920px]">
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <InlineEditText
          value={action.label}
          onSave={(v) => patch({ label: v })}
          placeholder="(label 미지정)"
        />
        <span className="text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border shrink-0 inline-flex items-center">
          {action.kind}
          <HelpHint term={action.kind} inline />
        </span>
        <FlagsRow flags={actionFlags} />
        <span className="ml-auto">
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
      <div className="text-xs text-muted-foreground mb-2 font-mono">
        {action.fqn}
        {action.declared_on_term && (
          <>
            {" "}
            · declared on <FqnLink kind="term" fqn={action.declared_on_term} />
          </>
        )}
      </div>
      {/* Wave C-B Change 1 — 6-step verification stepper. Replaces tiny amber pill. */}
      <VerificationStepper level={action.verification_level} />
      {/* #5 — Action.domain (derived, read-only). Render only if set. */}
      {action.domain && (
        <div className="text-xs text-muted-foreground italic mb-4">
          domain (derived): <span className="font-mono not-italic">{action.domain}</span>
        </div>
      )}
      {!action.domain && <div className="mb-4" />}

      <Section title="설명">
        <InlineEditTextArea
          value={action.description ?? ""}
          onSave={(v) => patch({ description: v })}
          placeholder="(설명 미지정 — 클릭해서 편집)"
          rows={3}
          className="text-[12.5px] text-foreground leading-relaxed"
        />
      </Section>

      {action.aliases.length > 0 && (
        <Section title={`Aliases · ${action.aliases.length}`}>
          <InlineEditList
            value={action.aliases}
            onSave={(v) => patch({ aliases: v })}
            placeholder="(alias 미등록 — 클릭해서 추가)"
          />
        </Section>
      )}

      <Section title={<>Parameters · {action.params.length} <HelpHint term="action" inline /></>}>
        {action.params.map((p, i) => (
          <ParamRow
            key={i}
            k={`params[${i}]`}
            name={p.name}
            refTerm={p.object_ref_term ?? null}
            confirmed={p.confirmed}
            // #9 — click opens ParamDrawer with all 9 fields.
            onClick={() => setDrawerParam({ p, i })}
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

      {action.realizations.length > 0 && (
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
            <div className="text-[11px] text-muted-foreground mt-0.5 break-all">
              applies to{" "}
              {r.applies_to_code_type_fqn
                ? <FqnLink kind="code_type" fqn={r.applies_to_code_type_fqn} />
                : <><span className="font-mono">(base)</span><HelpHint term="realization" inline /></>} ·{" "}
              {r.dispatch_source} <HelpHint term="dispatch_source" inline /> · conf {r.confidence} <HelpHint term="confidence" inline />
            </div>
          </div>
        ))}
      </Section>
      )}

      {/* #7 — Postconditions (read-only string list). Hidden when empty. */}
      {action.postconditions.length > 0 && (
      <Section title={<>Postconditions · {action.postconditions.length} <HelpHint term="business_rule" inline /></>}>
        <ul className="list-disc pl-5 space-y-0.5 text-[12px] text-foreground">
          {action.postconditions.map((p, i) => (
            <li key={i} className="font-mono break-all">{p}</li>
          ))}
        </ul>
      </Section>
      )}

      {/* #7 — Effects (read-only ActionEffectDTO list, color-coded by op). Hidden when empty. */}
      {action.effects.length > 0 && (
      <Section title={<>Effects · {action.effects.length} <HelpHint term="effectful" inline /></>}>
        {action.effects.map((e, i) => (
          <div key={i} className="bg-muted px-3 py-1.5 rounded my-1 text-xs flex items-start gap-2">
            <span className={cn(
              "text-[10px] px-1.5 py-px rounded-full border shrink-0 font-semibold uppercase",
              e.op === "create" && "border-emerald-400 text-emerald-700 bg-emerald-50",
              e.op === "mutate" && "border-amber-400 text-amber-700 bg-amber-50",
              e.op === "read"   && "border-sky-400 text-sky-700 bg-sky-50",
              e.op === "delete" && "border-rose-400 text-rose-700 bg-rose-50",
            )}>
              {e.op}
            </span>
            <span className="min-w-0 flex-1">
              <FqnLink kind="term" fqn={e.target_term} className="text-[11.5px]" />
              {e.target_attr && (
                <span className="font-mono text-[11px] text-muted-foreground">.{e.target_attr}</span>
              )}
              {e.description && (
                <div className="text-[11px] text-muted-foreground mt-0.5">{e.description}</div>
              )}
            </span>
          </div>
        ))}
      </Section>
      )}

      {action.preconditions.length > 0 && (
        <Section title={<>Preconditions · {action.preconditions.length} <HelpHint term="business_rule" inline /></>}>
          {action.preconditions.map((p, i) => (
            <div key={i} className="flex items-center gap-2 text-xs my-1">
              <span className="font-mono text-[10px] text-muted-foreground/70 shrink-0">[{i}]</span>
              {/* Subtle 8px dot replacing the heavier pink "rule" pill — keeps
                  the row recognisable as a precondition without competing with
                  the condition text. */}
              <span
                className="w-2 h-2 rounded-full bg-pink-400/70 shrink-0"
                aria-label="precondition"
                title="precondition (rule)"
              />
              <span className="font-mono text-muted-foreground break-all">{p}</span>
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
              "bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs",
              !ab.confirmed && "border-l-2 border-amber-400 pl-2",
            )}
          >
            <span className="font-mono text-primary">{ab.anchor_locator}</span>
            <span className="font-mono text-[11px] truncate">{ab.target_slot}</span>
            {ab.confirmed ? (
              <span className="text-[10px] text-emerald-400 border border-emerald-400 bg-emerald-400/10 px-1 rounded text-center">
                ✓
              </span>
            ) : (
              <span className="inline-flex items-center gap-1">
                <Button size="sm" className="text-[11px] h-6">
                  매핑
                </Button>
                <HelpHint term="binding" inline />
              </span>
            )}
          </div>
        ))}
        {anchors.length === 0 && (
          <p className="text-muted-foreground text-[11.5px]">
            anchor 미등록 (Java 분석 + Action 매핑 후 표시)
          </p>
        )}
      </Section>

      <AuthoringBridge note="Action params / output / sub_actions / anchor mapping 의 대량 변경은 Authoring 모드에서 LLM 도움 받아." />

      {/* #9 — ParamDrawer (slide-in from right). Renders nothing when drawerParam is null. */}
      <ParamDrawer
        param={drawerParam?.p ?? null}
        index={drawerParam?.i ?? null}
        onClose={() => setDrawerParam(null)}
        onOpenAuthoring={() => { setDrawerParam(null); setMainMode("authoring"); }}
      />
    </div>
    </PanelStripe>
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
    <section className="bg-card border border-border rounded-md my-3 p-3">
      <h3 className="text-[12.5px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center justify-between">
        <span>{title}</span>
        {action}
      </h3>
      {children}
    </section>
  );
}

function ParamRow({
  k,
  name,
  refTerm,
  confirmed,
  onClick,
}: {
  k: string;
  name: string;
  refTerm: string | null;
  confirmed: boolean;
  onClick?: () => void;
}) {
  // #9 — when onClick is supplied, the whole row becomes clickable to open
  // the ParamDrawer. Note: avoid nested <button> (FqnLink is a button).
  // Use role="button" on a <div> so we can keep the FqnLink interactive.
  const interactive = !!onClick;
  return (
    <div
      className={cn(
        "bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs",
        interactive && "cursor-pointer hover:bg-muted/70 transition-colors",
      )}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (!interactive) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.();
        }
      }}
      title={interactive ? "클릭 → param 상세 (drawer)" : undefined}
    >
      <span className="font-mono text-primary inline-flex items-center gap-0.5">
        {k}
        <HelpHint term="action" inline />
      </span>
      <span className="min-w-0 break-all">
        <strong>{name}</strong>
        {refTerm && (
          <span
            className="ml-2 text-[10px] border border-violet-300 bg-violet-50 px-1 rounded"
            // Don't bubble FqnLink clicks to the row's onClick.
            onClick={(e) => e.stopPropagation()}
          >
            → <FqnLink kind="term" fqn={refTerm} className="text-[10px]" />
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

// ─────────────────────────────────────────────────────────────────────────
// Wave C-B Change 1 — VerificationStepper
//
// Compact 6-step horizontal progress indicator for Action.verification_level.
// Past steps = filled muted dot. Current = larger amber filled dot + label.
// Future steps = empty bordered dot. Each dot has a tooltip via HelpHint.
// ─────────────────────────────────────────────────────────────────────────
const VERIFICATION_STEPS: Array<{
  level: VerificationLevel;
  shortLabel: string;
  glossaryKey: string;
}> = [
  { level: "unmapped",         shortLabel: "미매핑",  glossaryKey: "verification_level" },
  { level: "draft",            shortLabel: "초안",    glossaryKey: "draft" },
  { level: "signature_locked", shortLabel: "시그니처", glossaryKey: "signature_locked" },
  { level: "body_anchored",    shortLabel: "본체",    glossaryKey: "body_anchored" },
  { level: "sim_verified",     shortLabel: "시뮬",    glossaryKey: "sim_verified" },
  { level: "pr_proven",        shortLabel: "PR",      glossaryKey: "pr_proven" },
];

function VerificationStepper({ level }: { level: VerificationLevel }) {
  const currentIdx = VERIFICATION_STEPS.findIndex((s) => s.level === level);
  return (
    <div className="mb-4 flex items-center gap-0 select-none" role="group" aria-label="Verification level progress">
      {VERIFICATION_STEPS.map((step, idx) => {
        const isCurrent = idx === currentIdx;
        const isPast = idx < currentIdx;
        const isFuture = idx > currentIdx;
        return (
          <div key={step.level} className="flex items-center flex-1 min-w-0 last:flex-initial">
            {/* dot + label */}
            <div className="flex flex-col items-center gap-0.5 shrink-0">
              <span
                className={cn(
                  "rounded-full inline-flex items-center justify-center transition-colors",
                  isCurrent && "w-3.5 h-3.5 bg-amber-500 ring-2 ring-amber-200",
                  isPast && "w-2.5 h-2.5 bg-amber-400/70",
                  isFuture && "w-2.5 h-2.5 border border-muted-foreground/40 bg-card",
                )}
                title={step.level}
              />
              <span
                className={cn(
                  "text-[10px] leading-none whitespace-nowrap inline-flex items-center gap-0.5",
                  isCurrent && "text-amber-700 font-semibold",
                  isPast && "text-muted-foreground",
                  isFuture && "text-muted-foreground/50",
                )}
              >
                {step.shortLabel}
                <HelpHint term={step.glossaryKey} inline />
              </span>
            </div>
            {/* connector line (not after last) */}
            {idx < VERIFICATION_STEPS.length - 1 && (
              <span
                className={cn(
                  "h-px flex-1 min-w-[12px] mx-1.5 mt-[-12px]",
                  idx < currentIdx ? "bg-amber-400/60" : "bg-muted-foreground/20",
                )}
              />
            )}
          </div>
        );
      })}
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
        <div className="px-3 py-1.5 border-b border-border bg-muted/40 text-[11px] flex items-center gap-2 sticky top-0">
          <span className="font-semibold">📦 {parentClass?.simple_name ?? "?"}</span>
          <span className="text-muted-foreground font-mono truncate">{primaryReal?.code_method_fqn}</span>
          {method?.line_start && (
            <span className="ml-auto text-muted-foreground">L{method.line_start}–{method.line_end}</span>
          )}
        </div>
        {!method ? (
          <div className="p-6 text-muted-foreground text-[12px]">
            method body 를 못 찾음. parent class = {parentClass?.fqn ?? "(미찾음)"}.
            method fqn = {primaryReal?.code_method_fqn}.
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
          <div className="font-mono text-[12.5px] text-foreground break-all">{action.fqn}</div>
          <div className="text-[11px] text-foreground mt-1">{action.label}</div>
          <div className="flex gap-1 mt-2">
            <span className="text-[10px] px-1.5 py-px rounded-full border border-orange-300 text-orange-700 bg-orange-50">
              {action.kind}
            </span>
          </div>
          {/* Wave C cleanup — same VerificationStepper as Detail mode so the
              same Action shows the same verification UI everywhere. */}
          <div className="mt-2">
            <VerificationStepper level={action.verification_level} />
          </div>
        </div>

        {/* Semantic AnchorBinding (Action slot 매핑) — 핵심 차별점 */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1">
            ⚓ Semantic Anchors (Action ↔ slot) · {methodAnchors.length}
            <HelpHint term="anchor" inline />
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
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-sky-700 font-semibold">L{a.line ?? "?"}</span>
                <span className="font-mono text-foreground truncate flex-1">{a.anchor_locator}</span>
                {a.confirmed && <span className="text-[9.5px] text-emerald-700">✓</span>}
              </div>
              <div className="text-[10.5px] text-muted-foreground mt-0.5">
                slot: <span className="font-mono">{a.target_slot}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Static parser anchors — param/return 자동 추출 */}
        {method && method.anchors.length > 0 && (
          <div className="bg-card border border-border rounded p-3">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1">
              📍 Static Parser Anchors · {method.anchors.length}
              <HelpHint term="anchor" inline />
            </div>
            <div className="space-y-0.5">
              {method.anchors.slice(0, 12).map((a, i) => (
                <div
                  key={i}
                  onMouseEnter={() => setHoverLine(a.line ?? null)}
                  onMouseLeave={() => setHoverLine(null)}
                  className="grid grid-cols-[40px_60px_1fr] gap-1 text-[10.5px] cursor-pointer hover:bg-amber-50 px-1 rounded"
                >
                  <span className="font-mono text-amber-700">L{a.line ?? "?"}</span>
                  <span className="text-muted-foreground">{a.kind}</span>
                  <span className="font-mono text-foreground truncate">{a.locator}</span>
                </div>
              ))}
              {method.anchors.length > 12 && (
                <div className="text-[10px] text-muted-foreground">… {method.anchors.length - 12} 더</div>
              )}
            </div>
          </div>
        )}

        {/* BR enforced */}
        <div className="bg-card border border-border rounded p-3">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
            ⚖ BR enforced by 이 method · {enforcedRules.length}
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
                <span className="font-mono text-rose-800 truncate">{r.fqn}</span>
              </div>
              <div className="text-[10.5px] text-foreground mt-0.5 line-clamp-2">{r.statement}</div>
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
            <div key={i} className="text-[11px] my-0.5 grid grid-cols-[100px_1fr] gap-2">
              <span className="font-mono text-primary">[{i}] {p.name}</span>
              <span className="font-mono text-foreground truncate">
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
// #3 — Term.value_type editor.
//
// Common Java-ish types as a typed enum, with "기타..." fallback that swaps
// to free-text input. Backend stores plain str; any text is accepted.
// ─────────────────────────────────────────────────────────────────────────
const VALUE_TYPE_OPTIONS = [
  "int", "long", "double", "float",
  "boolean", "String", "BigDecimal",
  "LocalDate", "LocalDateTime",
  "기타...",            // sentinel — fallback to free-text input
] as const;
type ValueTypeOption = typeof VALUE_TYPE_OPTIONS[number];

function ValueTypeEdit({
  value,
  onSave,
}: {
  value: string;
  onSave: (v: string) => Promise<void>;
}) {
  // If current value is a known option, show it directly. Otherwise the value
  // came from a previous "기타" save — pre-select the fallback so the user can
  // re-edit it as text. We use the saved value as the displayed text.
  const isKnown = (VALUE_TYPE_OPTIONS as readonly string[]).includes(value) && value !== "기타...";
  const display: ValueTypeOption = isKnown ? (value as ValueTypeOption) : "기타...";
  return (
    <InlineEditSelect<ValueTypeOption>
      value={display}
      options={VALUE_TYPE_OPTIONS}
      // The Save handler receives the picked enum value. If user picked the
      // sentinel "기타...", the InlineEditSelect's fallbackText branch already
      // swapped to text mode and will dispatch the typed string here directly
      // (so the only way "기타..." reaches us is the no-op identity case).
      onSave={async (v) => {
        if (v === "기타...") return;       // sentinel itself never persisted
        await onSave(v);
      }}
      fallbackText={{ value: "기타...", label: "직접 입력" }}
    />
  );
}

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
    <PanelStripe color="violet">
    <div className="p-5 max-w-[920px]">
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <InlineEditText
          value={term.label}
          onSave={(v) => patch({ label: v })}
          placeholder="(label 미지정)"
          className="truncate"
        />
        <span className="text-[11px] px-1.5 py-px rounded-full border border-violet-400 text-violet-700 bg-violet-50 shrink-0">
          {term.kind}
          <HelpHint term={term.kind} inline />
        </span>
        {term.is_root_entity && (
          <span className="text-[11px] px-1.5 py-px rounded-full border border-emerald-400 text-emerald-700 bg-emerald-50 shrink-0">
            root_entity
            <HelpHint term="root_entity" inline />
          </span>
        )}
        <span className="ml-auto">
          <ConfirmToggle
            kind="term"
            id={term.fqn}
            repoId={term.repo_id}
            confirmed={term.confirmed}
            onChanged={(v) => setTerm({ ...term, confirmed: v })}
          />
        </span>
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono flex items-center gap-2 flex-wrap">
        <span>{term.fqn}</span>
        <span>·</span>
        <span className="inline-flex items-center gap-1">
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
          value={term.description ?? ""}
          onSave={(v) => patch({ description: v })}
          placeholder="(설명 미지정 — 클릭해서 편집)"
          rows={3}
          className="text-[12.5px] text-foreground leading-relaxed"
        />
      </Section>

      {term.kind === "atomic" && (
        <Section title={<>값 형식 (atomic) <HelpHint term="atomic" inline /></>}>
          {/* #3 — value_type as a typed select with "기타..." free-text fallback. */}
          <KV k="value_type" v={
            <ValueTypeEdit
              value={term.value_type ?? ""}
              onSave={(v) => patch({ value_type: v })}
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
          {/* #6 — range edit (min → max). NOTE: backend `queue_actions_api.TermPatch`
                may not yet expose `range` (W2-A regenerating in parallel). If so the
                save will surface a 422 inline. */}
          <KV k={<>range <HelpHint term="atomic" inline /></>} v={
            <InlineEditRange
              value={term.range ?? null}
              onSave={async (v) => { await patch({ range: v }); }}
            />
          } />
          <KV k={<>enum_values <HelpHint term="atomic" inline /></>} v={
            <InlineEditList
              value={term.enum_values ?? []}
              onSave={(v) => patch({ enum_values: v })}
              placeholder="(없음)"
            />
          } />
        </Section>
      )}

      {term.aliases.length > 0 && (
        <Section title={`Aliases · ${term.aliases.length}`}>
          <InlineEditList
            value={term.aliases}
            onSave={(v) => patch({ aliases: v })}
            placeholder="(alias 미등록 — 클릭해서 추가)"
          />
        </Section>
      )}

      {term.kind === "composite" && parts.length > 0 && (
        <Section title={<>Composition Parts · {parts.length} <HelpHint term="composition" inline /></>}>
          {parts.map((p, i) => (
            <button
              key={i}
              onClick={() => setSelectedTerm(p.child_fqn)}
              className="w-full text-left bg-muted hover:bg-muted/70 px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs transition-colors"
              title={`이 part 의 detail 로 이동: ${p.child_fqn}`}
            >
              <span className="font-mono text-primary">{p.role_name}</span>
              <span>
                <strong>{p.child_fqn.split(".").pop()}</strong>
                <span className="ml-2 text-[10px] text-muted-foreground font-mono">{p.child_fqn}</span>
              </span>
              <span className="text-[10px] text-muted-foreground text-center">{p.cardinality}{p.required ? " req" : ""}</span>
            </button>
          ))}
        </Section>
      )}

      {/* Flags — only TRUE flags render. If all false, the section disappears. */}
      {(term.is_abstract || term.is_interface || term.struct_like_hint) && (
        <Section title="Flags">
          <FlagsRow
            flags={[
              { key: "abstract",         label: "abstract",         value: !!term.is_abstract,      tooltip: "추상 Term — 자식 Term 의 공통 골격" },
              { key: "interface",        label: "interface",        value: !!term.is_interface,     tooltip: "인터페이스성 Term — 행위 계약" },
              { key: "struct_like_hint", label: "struct_like_hint", value: !!term.struct_like_hint, tooltip: "Java struct 처럼 단순 데이터 묶음 hint", glossaryKey: "struct_like_hint" },
            ]}
          />
        </Section>
      )}

      <AuthoringBridge note="Term 의 label / aliases / facets 등 대량 변경은 Authoring 모드에서 LLM 도움 받아 진행." />
    </div>
    </PanelStripe>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// CodeType Detail
// ─────────────────────────────────────────────────────────────────────────
function CodeTypeDetail({ fqn }: { fqn: string }) {
  const { setSelectedAction } = useWorkbench();
  const [ct, setCt] = useState<CodeTypeDTO | null>(null);
  const [loading, setLoading] = useState(true);
  // Wave C-B Change 2 — track which method bodies are expanded (lazy JavaCode render).
  const [expandedMethods, setExpandedMethods] = useState<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Reset expansion when switching to a different CodeType to avoid carrying
    // stale fqns from the previous class.
    setExpandedMethods(new Set());
    ontologyApi.getCodeType(fqn).then((t) => {
      if (cancelled) return;
      setCt(t); setLoading(false);
    }).catch(() => { if (!cancelled) { setCt(null); setLoading(false); }});
    return () => { cancelled = true; };
  }, [fqn]);

  if (loading) return <div className="p-6 text-muted-foreground text-sm">Loading…</div>;
  if (!ct)     return <div className="p-6 text-muted-foreground text-sm">CodeType 찾을 수 없음</div>;

  const visibleMethods = ct.methods.slice(0, 50);
  const allExpanded =
    visibleMethods.length > 0 && visibleMethods.every((m) => expandedMethods.has(m.fqn));
  const toggleMethod = (mfqn: string) =>
    setExpandedMethods((prev) => {
      const next = new Set(prev);
      if (next.has(mfqn)) next.delete(mfqn);
      else next.add(mfqn);
      return next;
    });
  const expandAll = () =>
    setExpandedMethods(new Set(visibleMethods.map((m) => m.fqn)));
  const collapseAll = () => setExpandedMethods(new Set());

  return (
    <PanelStripe color="primary">
    <div className="p-5 max-w-[1000px]">
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        {ct.simple_name}
        <span className="text-[11px] px-1.5 py-px rounded-full border border-primary/40 text-primary bg-primary/10">
          {ct.kind}
        </span>
        {/* #8 — role as inline select with confirm modal (impactful change). */}
        <span className="text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground inline-flex items-center gap-1">
          role:
          <HelpHint term="role" inline />
          <InlineEditSelect<CodeTypeRole>
            value={ct.role}
            options={["domain", "framework", "infra", "unknown"] as const}
            onSave={async (v) => {
              await ontologyApi.patchCodeType(ct.repo_id, ct.fqn, { role: v });
              setCt({ ...ct, role: v });
            }}
            confirmModal={{
              body: (v) => `type role 을 ${v} 로 바꿉니다. classification 결과가 달라질 수 있습니다.`,
            }}
          />
        </span>
        {ct.is_abstract && (
          <span className="text-[11px] px-1.5 py-px rounded-full border border-amber-400 text-amber-700 bg-amber-50">abstract</span>
        )}
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono">
        {ct.fqn}
        {ct.line_start && <> · {ct.source_file}:{ct.line_start}{ct.line_end ? `–${ct.line_end}` : ""}</>}
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
            <div key={i} className="bg-muted px-3 py-1 rounded my-0.5 text-xs grid grid-cols-[160px_1fr_60px] gap-2 items-center">
              <span className="font-mono text-primary truncate">{f.name}</span>
              <span className="font-mono text-foreground truncate">{f.type}</span>
              <span className="text-[9.5px] text-muted-foreground font-mono">{f.line ? `L${f.line}` : ""}</span>
            </div>
          ))}
          {ct.fields.length > 30 && (
            <p className="text-[11px] text-muted-foreground mt-1">… {ct.fields.length - 30} 더</p>
          )}
        </Section>
      )}

      <Section
        title={<>Methods · {ct.methods.length} <HelpHint term="code_method" inline /></>}
        action={
          visibleMethods.length > 0 && (
            <div className="flex gap-1 normal-case tracking-normal">
              <button
                type="button"
                onClick={allExpanded ? collapseAll : expandAll}
                className="text-[10.5px] px-2 py-0.5 rounded border border-border text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                title={allExpanded ? "모든 method 본체 접기" : "모든 method 본체 펼치기"}
              >
                {allExpanded ? "Collapse all" : "Expand all"}
              </button>
            </div>
          )
        }
      >
        {ct.methods.length === 0 && (
          <p className="text-[11.5px] text-muted-foreground">메서드 없음</p>
        )}
        {visibleMethods.map((m, i) => {
          const expanded = expandedMethods.has(m.fqn);
          const hasBody = !!(m.body_text && m.body_text.trim().length > 0);
          return (
            <div key={i} className="bg-muted rounded my-0.5 text-xs overflow-hidden">
              <div
                role="button"
                tabIndex={0}
                onClick={() => toggleMethod(m.fqn)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleMethod(m.fqn);
                  }
                }}
                className="px-2.5 py-1 flex items-center gap-2 cursor-pointer hover:bg-muted/70 transition-colors"
                title={expanded ? "본체 접기" : "본체 펼치기"}
              >
                <span className="shrink-0 text-muted-foreground">
                  {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                </span>
                <span className={cn(
                  "text-[9.5px] px-1 rounded border shrink-0 inline-flex items-center gap-0.5",
                  m.role === "business" ? "text-emerald-700 border-emerald-300 bg-emerald-50"
                  : m.role === "helper" ? "text-amber-700 border-amber-300 bg-amber-50"
                  : "text-muted-foreground border-border bg-card"
                )}>
                  {m.role}
                  <HelpHint term="role" inline />
                </span>
                <span className="font-mono truncate flex-1">
                  {m.name}({m.params.map(p => p.type).join(", ")}) → {m.return_type}
                </span>
                {m.line_start && <span className="text-[9.5px] text-muted-foreground font-mono shrink-0">L{m.line_start}</span>}
                {m.is_override && <span className="text-[9px] text-muted-foreground border border-border px-1 rounded shrink-0">@Override</span>}
              </div>
              {expanded && (
                <div className="border-t border-border/60 bg-card pl-5 pr-2 py-1">
                  <div className="text-[10px] text-muted-foreground mb-1 font-mono">
                    L{m.line_start ?? "?"}-{m.line_end ?? "?"}
                  </div>
                  {hasBody ? (
                    <JavaCode
                      source={m.body_text ?? ""}
                      startLine={m.line_start ?? 1}
                    />
                  ) : (
                    <div className="text-[11px] text-muted-foreground italic px-2 py-1">
                      (body 없음)
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
        {ct.methods.length > 50 && (
          <p className="text-[11px] text-muted-foreground mt-1">… {ct.methods.length - 50} 더</p>
        )}
      </Section>

      <AuthoringBridge note="CodeType 자체는 Java 코드의 mirror — 직접 수정 ❌. role 분류 / Action 매핑 추가는 Authoring 모드에서." />
    </div>
    </PanelStripe>
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
    <PanelStripe color="rose">
    <div className="p-5 max-w-[920px]">
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <span className="font-mono text-foreground text-[15px] truncate">{rule.fqn}</span>
        <span className={cn(
          "text-[11px] px-1.5 py-px rounded-full border",
          rule.severity === "hard"
            ? "border-rose-400 text-rose-700 bg-rose-50"
            : "border-amber-400 text-amber-700 bg-amber-50"
        )}>
          <InlineEditSelect
            value={rule.severity as "hard" | "soft"}
            options={["hard", "soft"] as const}
            onSave={(v) => patch({ severity: v })}
            // #1 — confirm modal for severity (impacts code guard behavior).
            confirmModal={{
              body: (v) => `severity 를 ${v} 로 바꿉니다. 관련 코드 가드 거동에 영향이 있을 수 있습니다.`,
            }}
          />
        </span>
        <span className="ml-auto">
          <ConfirmToggle
            kind="rule"
            id={rule.fqn}
            repoId={rule.repo_id}
            confirmed={rule.confirmed}
            onChanged={(v) => setRule({ ...rule, confirmed: v })}
          />
        </span>
      </h1>

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
            <div key={i} className="bg-muted px-3 py-1.5 rounded my-1 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-rose-700 border border-rose-300 bg-rose-50 px-1 rounded font-mono">{h.incident_id ?? "?"}</span>
                <span className="font-semibold">{h.summary}</span>
                {h.occurred_at && <span className="text-[10px] text-muted-foreground ml-auto">{h.occurred_at}</span>}
              </div>
              {(h.triggered_by || h.fixed_at_commit) && (
                <div className="text-[10.5px] text-muted-foreground mt-1">
                  {h.triggered_by && <>by {h.triggered_by} </>}
                  {h.fixed_at_commit && <>· commit {h.fixed_at_commit}</>}
                </div>
              )}
            </div>
          ))}
        </Section>
      )}

      {rule.violated_at_call.length > 0 && (
        <Section title={<>Violated-At Call Sites · {rule.violated_at_call.length} <HelpHint term="violated_at_call" inline /></>}>
          {rule.violated_at_call.map((v, i) => {
            const callerFqn = typeof v.caller_method_fqn === "string" ? v.caller_method_fqn : null;
            const line = typeof v.line === "number" ? v.line : null;
            const reason = typeof v.reason === "string" ? v.reason : null;
            const severity = typeof v.severity === "string" ? v.severity : null;
            const at = typeof v.at === "string" ? v.at : null;
            const knownKeys = new Set(["caller_method_fqn", "line", "reason", "severity", "at"]);
            const extras = Object.entries(v).filter(([k]) => !knownKeys.has(k));
            return (
              <div key={i} className="bg-muted px-3 py-1.5 rounded my-1 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  {severity && (
                    <span className={cn(
                      "text-[10px] px-1 rounded border",
                      severity === "hard"
                        ? "border-rose-300 text-rose-700 bg-rose-50"
                        : "border-amber-300 text-amber-700 bg-amber-50"
                    )}>{severity}</span>
                  )}
                  {callerFqn ? (
                    <FqnLink kind="code_method" fqn={callerFqn} className="text-[12px]" />
                  ) : (
                    <span className="text-muted-foreground italic">caller 미상</span>
                  )}
                  {line !== null && (
                    <span className="text-[10.5px] text-muted-foreground font-mono">L{line}</span>
                  )}
                  {at && <span className="text-[10px] text-muted-foreground ml-auto">{at}</span>}
                </div>
                {reason && (
                  <div className="text-[11px] text-muted-foreground mt-1">{reason}</div>
                )}
                {extras.length > 0 && (
                  <dl className="text-[10.5px] text-muted-foreground/80 mt-1 pl-2 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
                    {extras.map(([k, val]) => (
                      <span key={k} className="contents">
                        <dt className="font-mono">{k}</dt>
                        <dd className="font-mono break-all">{renderExtraValue(val)}</dd>
                      </span>
                    ))}
                  </dl>
                )}
              </div>
            );
          })}
        </Section>
      )}

      {rule.source && (
        <Section title="Source / Origin">
          <KV k="source" v={rule.source} />
        </Section>
      )}

      <AuthoringBridge note="BR statement / severity / enforced_by 의 대량 보강은 Authoring 모드에서 LLM 도움 받아." />
    </div>
    </PanelStripe>
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
    <PanelStripe color="sky">
    <div className="p-5 max-w-[920px]">
      <h1 className="text-lg font-semibold mb-0.5 flex items-center gap-2">
        <span className="font-mono text-foreground text-[15px] truncate min-w-0">
          {anchor.anchor_locator || "(locator 미지정)"}
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-sky-400 text-sky-700 bg-sky-50 shrink-0 inline-flex items-center">
          conf {anchor.confidence.toFixed(2)}
          <HelpHint term="confidence" inline />
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground shrink-0">
          src: {anchor.source}
        </span>
        <span className="ml-auto">
          <ConfirmToggle
            kind="anchor"
            id={anchor.id}
            repoId={anchor.repo_id}
            confirmed={anchor.confirmed}
            onChanged={(v) => setAnchor({ ...anchor, confirmed: v })}
          />
        </span>
      </h1>
      <div className="text-xs text-muted-foreground font-mono mb-3 truncate" title={anchor.id}>
        id: {anchor.id}
      </div>

      <Section title={<>Anchor Locator (편집) <HelpHint term="anchor_locator" inline /> <span className="text-[10px] text-muted-foreground normal-case font-normal tracking-normal ml-1">↑ h1 와 동일</span></>}>
        <div className="font-mono text-[13px] text-foreground bg-muted px-3 py-2 rounded break-all">
          {/* #2 — autocomplete dropdown sourced from `getAnchorCandidates`. */}
          <InlineEditAutocomplete
            value={anchor.anchor_locator ?? ""}
            onSave={(v) => patch({ anchor_locator: v })}
            placeholder="(locator 미지정)"
            inputClassName="text-[13px] font-mono w-full min-w-[400px]"
            fetchSuggestions={async (): Promise<AutocompleteSuggestion[]> => {
              const cands: AnchorCandidateDTO[] = await ontologyApi
                .getAnchorCandidates(anchor.code_method_fqn, anchor.repo_id)
                .catch(() => [] as AnchorCandidateDTO[]);
              return cands.map((c) => ({
                value: c.locator,
                kind: c.kind,
                description: c.description || c.snippet,
                line: c.line,
              }));
            }}
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

      <Section title={<>Rationale <HelpHint term="confidence" inline /></>}>
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
    </PanelStripe>
  );
}

// ─────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────

/**
 * Renders an arbitrary value coming from a server payload's "extras" bucket
 * (e.g. unknown keys on `BR.violated_at_call`). Avoids dumping raw JSON for
 * common shapes like arrays-of-primitives and shallow objects so the user
 * sees a readable key:value, not `[{"x":1,"y":2}]`. JSON.stringify is only
 * the last-ditch fallback for deeply nested or opaque shapes.
 */
function renderExtraValue(val: unknown): React.ReactNode {
  if (val === null || val === undefined) {
    return <span className="text-muted-foreground/60 italic">{val === null ? "null" : "—"}</span>;
  }
  if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
    return String(val);
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return <span className="text-muted-foreground/60 italic">[]</span>;
    const allPrim = val.every(
      (x) =>
        x === null ||
        typeof x === "string" ||
        typeof x === "number" ||
        typeof x === "boolean",
    );
    if (allPrim) return val.map((x) => (x === null ? "null" : String(x))).join(", ");
    // Heterogeneous / nested array — fall back, but keep it short.
    return <span className="text-muted-foreground/70">{JSON.stringify(val)}</span>;
  }
  if (typeof val === "object") {
    const entries = Object.entries(val as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-muted-foreground/60 italic">{"{}"}</span>;
    // Render shallow objects as a nested key:value list. Anything with object
    // children gets compacted to JSON to keep the row scannable.
    const allShallow = entries.every(
      ([, v]) =>
        v === null ||
        typeof v === "string" ||
        typeof v === "number" ||
        typeof v === "boolean",
    );
    if (allShallow) {
      return (
        <span className="inline-flex flex-wrap gap-x-2 gap-y-0">
          {entries.map(([ek, ev]) => (
            <span key={ek}>
              <span className="text-muted-foreground/70">{ek}:</span>{" "}
              <span>{ev === null ? "null" : String(ev)}</span>
            </span>
          ))}
        </span>
      );
    }
    return <span className="text-muted-foreground/70">{JSON.stringify(val)}</span>;
  }
  return <span className="text-muted-foreground/70">{String(val)}</span>;
}

function KV({ k, v }: { k: React.ReactNode; v: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2 my-0.5 text-xs">
      <span className="text-muted-foreground inline-flex items-center gap-0.5">{k}</span>
      <span className="text-foreground min-w-0 break-all">{v}</span>
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
 *
 * Wave C-B Change 3:
 *   - code_type: primary click → navigate to Detail (unchanged); small Eye icon
 *     opens CodePeekModal without losing current selection.
 *   - code_method: primary click → opens CodePeekModal (methods have no
 *     dedicated Detail). Small ↗ icon = secondary "go to parent class" nav.
 *   - All other kinds (term/action/rule/anchor): unchanged.
 *
 * Hydration safety: nested <button> inside another <button> would crash. We
 * render the outer trigger as a `role="button"` `<span>` for code kinds so the
 * Eye / ↗ children can be real <button>s (and stop event propagation).
 */
function FqnLink({
  kind, fqn, label, className,
}: {
  kind: "term" | "action" | "code_type" | "code_method" | "rule" | "anchor";
  fqn: string;
  label?: string;
  className?: string;
}) {
  const {
    setSelectedTerm, setSelectedAction, setSelectedCodeType, setSelectedRule, setSelectedAnchor,
    activeRepoId, openPeek,
  } = useWorkbench();

  const navigate = () => {
    if (kind === "term") setSelectedTerm(fqn);
    else if (kind === "action") setSelectedAction(fqn);
    else if (kind === "code_type") setSelectedCodeType(fqn);
    else if (kind === "code_method") {
      // Secondary affordance: jump to parent class Detail.
      const parent = parentTypeFqnOfMethod(fqn);
      if (parent) setSelectedCodeType(parent);
    }
    else if (kind === "rule") setSelectedRule(fqn);
    else if (kind === "anchor") setSelectedAnchor(fqn);
  };

  const peek = () => {
    if (kind !== "code_type" && kind !== "code_method") return;
    openPeek({ kind, fqn, repoId: activeRepoId });
  };

  const colorClass: Record<typeof kind, string> = {
    term:        "text-violet-700 hover:bg-violet-50",
    action:      "text-orange-700 hover:bg-orange-50",
    code_type:   "text-primary hover:bg-primary/10",
    code_method: "text-primary hover:bg-primary/10",
    rule:        "text-rose-700 hover:bg-rose-50",
    anchor:      "text-sky-700 hover:bg-sky-50",
  };

  // For non-code kinds: simple <button> as before.
  if (kind !== "code_type" && kind !== "code_method") {
    return (
      <button
        onClick={navigate}
        className={cn(
          "font-mono break-all hover:underline transition-colors px-1 -mx-1 rounded",
          colorClass[kind],
          className,
        )}
        title={`${kind} detail 로 이동: ${fqn}`}
      >
        {label ?? fqn}
      </button>
    );
  }

  // For code_type / code_method: render a span container with multiple
  // interactive children (so we can nest <button>s safely).
  const isMethod = kind === "code_method";
  // Primary click on code_method = peek; on code_type = navigate.
  const primaryClick = isMethod ? peek : navigate;
  const primaryTitle = isMethod
    ? `code body 미리보기 (현재 선택 유지): ${fqn}`
    : `code_type detail 로 이동: ${fqn}`;

  return (
    <span className={cn("inline-flex items-center gap-0.5 min-w-0", className)}>
      <span
        role="button"
        tabIndex={0}
        onClick={primaryClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            primaryClick();
          }
        }}
        className={cn(
          "font-mono break-all hover:underline transition-colors px-1 -mx-1 rounded cursor-pointer min-w-0",
          colorClass[kind],
        )}
        title={primaryTitle}
      >
        {label ?? fqn}
      </span>
      {/* Eye = peek. Always rendered for code kinds. For code_method, this is
          redundant with the primary click (also peek) but it gives a stable
          affordance + keyboard target. */}
      {!isMethod && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            peek();
          }}
          className="shrink-0 inline-flex items-center justify-center w-4 h-4 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
          title="코드 미리보기 (현재 선택 유지)"
          aria-label="코드 미리보기"
        >
          <Eye className="w-3 h-3" />
        </button>
      )}
      {/* code_method: secondary "go to parent class" nav as an arrow icon. */}
      {isMethod && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            navigate();
          }}
          className="shrink-0 inline-flex items-center justify-center w-4 h-4 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors"
          title="parent class detail 로 이동"
          aria-label="parent class 로 이동"
        >
          <ArrowUpRight className="w-3 h-3" />
        </button>
      )}
    </span>
  );
}
