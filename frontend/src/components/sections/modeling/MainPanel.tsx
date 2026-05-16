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
import { Button } from "@/components/ui/button";
import { BackwardMode } from "./BackwardMode";
import { AuthoringMode } from "./AuthoringMode";
import { HelpHint } from "./HelpHint";
import { JavaCode } from "./JavaCode";
import { ConfirmToggle } from "./ConfirmToggle";
import { InlineEditList, InlineEditSelect, InlineEditText, InlineEditTextArea } from "./InlineEdit";

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
        <div className="text-[11px] text-muted-foreground flex-1 truncate">
          {activeKind ? (
            <>현재 <span className="text-foreground font-semibold">{KIND_LABEL[activeKind.kind]}</span>:{" "}
            <code className="font-mono text-foreground">{activeKind.id.split(".").pop() ?? activeKind.id}</code></>
          ) : (
            "선택 없음 — 좌측 트리에서 Term / Action / CodeType / BR / Anchor 선택"
          )}
        </div>
        {/* Direction toggle (Backward 는 다음 phase) */}
        <div className="flex bg-muted border border-border rounded overflow-hidden mr-2">
          <button
            onClick={() => setDirection("fwd")}
            className={cn(
              "px-2.5 py-0.5 text-[11px] border-r border-border",
              direction === "fwd" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
            )}
          >
            🔍 Forward
          </button>
          <button
            disabled
            className="px-2.5 py-0.5 text-[11px] text-muted-foreground/40 cursor-not-allowed"
            title="Backward 모드 — 다음 phase"
          >
            🔧 Backward
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

      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <InlineEditText
          value={action.label}
          onSave={(v) => patch({ label: v })}
          placeholder="(label 미지정)"
        />
        <span className="text-[11px] px-1.5 py-px rounded-full border text-orange-700 border-orange-400 bg-orange-50">
          action
          <HelpHint term="action" inline />
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
          {action.kind}
          <HelpHint term={action.kind} inline />
        </span>
        {action.is_abstract && (
          <span className="text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
            abstract
          </span>
        )}
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
      <div className="text-xs text-muted-foreground mb-4 font-mono">
        {action.fqn}
        {action.declared_on_term && (
          <>
            {" "}
            · declared on <FqnLink kind="term" fqn={action.declared_on_term} />
          </>
        )}
        <span className="ml-2 text-[11px] px-1.5 py-px rounded-full border border-amber-400 text-amber-700 bg-amber-50">
          {action.verification_level.toUpperCase()}
          <HelpHint term={action.verification_level} inline />
        </span>
      </div>

      <Section title="설명">
        <InlineEditTextArea
          value={action.description ?? ""}
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
                : <span className="font-mono">(base)</span>} ·{" "}
              {r.dispatch_source} <HelpHint term="dispatch_source" inline /> · conf {r.confidence} <HelpHint term="confidence" inline />
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
              <Button size="sm" className="text-[11px] h-6">
                매핑
              </Button>
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
    </div>
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
}: {
  k: string;
  name: string;
  refTerm: string | null;
  confirmed: boolean;
}) {
  return (
    <div className="bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs">
      <span className="font-mono text-primary">{k}</span>
      <span className="min-w-0 break-all">
        <strong>{name}</strong>
        {refTerm && (
          <span className="ml-2 text-[10px] border border-violet-300 bg-violet-50 px-1 rounded">
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
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
              📍 Static Parser Anchors · {method.anchors.length}
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
      <div className="bg-violet-500/5 border-l-2 border-violet-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        🧬 <strong className="text-violet-700">BusinessTerm</strong> — 도메인 의미 단위
      </div>
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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        {ct.simple_name}
        <span className="text-[11px] px-1.5 py-px rounded-full border border-primary/40 text-primary bg-primary/10">
          {ct.kind}
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground">
          role: {ct.role}
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

      <Section title={`Methods · ${ct.methods.length}`}>
        {ct.methods.length === 0 && (
          <p className="text-[11.5px] text-muted-foreground">메서드 없음</p>
        )}
        {ct.methods.slice(0, 50).map((m, i) => (
          <div key={i} className="bg-muted px-3 py-1 rounded my-0.5 text-xs">
            <div className="flex items-center gap-2">
              <span className={cn(
                "text-[9.5px] px-1 rounded border",
                m.role === "business" ? "text-emerald-700 border-emerald-300 bg-emerald-50"
                : m.role === "helper" ? "text-amber-700 border-amber-300 bg-amber-50"
                : "text-muted-foreground border-border bg-card"
              )}>{m.role}</span>
              <span className="font-mono truncate flex-1">
                {m.name}({m.params.map(p => p.type).join(", ")}) → {m.return_type}
              </span>
              {m.line_start && <span className="text-[9.5px] text-muted-foreground font-mono">L{m.line_start}</span>}
              {m.is_override && <span className="text-[9px] text-muted-foreground border border-border px-1 rounded">@Override</span>}
            </div>
          </div>
        ))}
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
      <div className="bg-rose-500/5 border-l-2 border-rose-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        ⚖ <strong className="text-rose-700">BusinessRule</strong> — 도메인 제약 (코드 가드 enforced)
      </div>
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
      <div className="bg-sky-500/5 border-l-2 border-sky-500 px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        ⚓ <strong className="text-sky-700">AnchorBinding</strong> — 코드 fragment ↔ Action slot
      </div>
      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        <span className="font-mono text-foreground text-[15px] truncate">{anchor.id}</span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-sky-400 text-sky-700 bg-sky-50">
          conf {anchor.confidence.toFixed(2)}
          <HelpHint term="confidence" inline />
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border border-border text-muted-foreground">
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
    <div className="grid grid-cols-[120px_1fr] gap-2 my-0.5 text-xs">
      <span className="text-muted-foreground">{k}</span>
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
 * code_method 의 경우 parent class 로 navigate (method 단일 페이지 미존재).
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
  return (
    <button
      onClick={onClick}
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
