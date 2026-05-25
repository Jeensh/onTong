"use client";

/**
 * 큐 row 클릭 시 RightPanel 에 표시되는 미리보기 패널.
 *
 * 정책:
 * - 단일 accent (primary) + neutral surface 로 통일. 색상 over-stimulation 제거.
 * - Term 후보: 풀 detail.
 * - Action 후보: detail + realizations/params/effects 상위 3개 압축 표시.
 * - Realization 후보: code_type + term 양쪽 concurrent fetch → 양쪽 context 카드.
 * - Confirm/Reject 는 좌측 row 와 동일한 action mirror.
 */

import { useEffect, useState } from "react";
import { Check, X as XIcon, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ontologyApi,
  type TermDTO, type ActionDTO, type CodeTypeDTO, type QueueRealizationDTO,
} from "@/lib/api/ontology";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";

export function QueuePreviewPanel() {
  const repoId = useWorkbench((s) => s.activeRepoId);
  const selectedQueueItem = useWorkbench((s) => s.selectedQueueItem);
  const setSelectedQueueItem = useWorkbench((s) => s.setSelectedQueueItem);
  const setSelectedAction = useWorkbench((s) => s.setSelectedAction);
  const setSelectedTerm = useWorkbench((s) => s.setSelectedTerm);
  const setSelectedCodeType = useWorkbench((s) => s.setSelectedCodeType);
  const setMainMode = useWorkbench((s) => s.setMainMode);
  const setLeftTab = useWorkbench((s) => s.setLeftTab);
  const bumpQueueRefresh = useWorkbench((s) => s.bumpQueueRefresh);

  const [term, setTerm] = useState<TermDTO | null>(null);
  const [action, setAction] = useState<ActionDTO | null>(null);
  const [realization, setRealization] = useState<QueueRealizationDTO | null>(null);
  // Realization 양쪽 context
  const [realCodeType, setRealCodeType] = useState<CodeTypeDTO | null>(null);
  const [realTerm, setRealTerm] = useState<TermDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<"confirm" | "reject" | null>(null);

  useEffect(() => {
    if (!selectedQueueItem) {
      setTerm(null); setAction(null); setRealization(null);
      setRealCodeType(null); setRealTerm(null); setErr(null);
      return;
    }
    let cancelled = false;
    setLoading(true); setErr(null);
    setTerm(null); setAction(null); setRealization(null);
    setRealCodeType(null); setRealTerm(null);

    const { kind, id } = selectedQueueItem;

    const run = async () => {
      if (kind === "term") {
        const t = await ontologyApi.getTerm(id);
        if (!cancelled) setTerm(t);
      } else if (kind === "action") {
        const a = await ontologyApi.getAction(id);
        if (!cancelled) setAction(a);
      } else {
        // realization: id 는 numeric tr_id. queue list 에서 다시 가져오기
        const q = await ontologyApi.getMappingQueue(repoId);
        const r = q.type_realizations.find((x) => String(x.id) === id) ?? null;
        if (cancelled) return;
        setRealization(r);
        if (r) {
          // 양쪽 context concurrent fetch
          const [ct, tm] = await Promise.all([
            ontologyApi.getCodeType(r.code_type_fqn).catch(() => null),
            ontologyApi.getTerm(r.term_fqn).catch(() => null),
          ]);
          if (cancelled) return;
          setRealCodeType(ct);
          setRealTerm(tm);
        }
      }
    };

    run()
      .catch((e) => { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [selectedQueueItem, repoId]);

  if (!selectedQueueItem) return null;

  const confirm = async () => {
    if (!selectedQueueItem) return;
    setActionBusy("confirm");
    try {
      if (selectedQueueItem.kind === "term") {
        await ontologyApi.confirmTerm(repoId, selectedQueueItem.id);
      } else if (selectedQueueItem.kind === "action") {
        await ontologyApi.confirmActionCandidate(repoId, selectedQueueItem.id);
      } else {
        await ontologyApi.confirmRealization(repoId, Number(selectedQueueItem.id));
      }
      bumpQueueRefresh();
      setSelectedQueueItem(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setActionBusy(null);
    }
  };

  const reject = async () => {
    if (!selectedQueueItem) return;
    setActionBusy("reject");
    try {
      if (selectedQueueItem.kind === "term") {
        await ontologyApi.rejectTerm(repoId, selectedQueueItem.id);
      } else if (selectedQueueItem.kind === "action") {
        await ontologyApi.rejectActionCandidate(repoId, selectedQueueItem.id);
      } else {
        await ontologyApi.rejectRealization(repoId, Number(selectedQueueItem.id));
      }
      bumpQueueRefresh();
      setSelectedQueueItem(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setActionBusy(null);
    }
  };

  const openDetail = () => {
    if (selectedQueueItem.kind === "term") {
      setSelectedTerm(selectedQueueItem.id);
      setLeftTab("ontology");
    } else if (selectedQueueItem.kind === "action") {
      setSelectedAction(selectedQueueItem.id);
      setLeftTab("ontology");
    } else if (realization) {
      setSelectedCodeType(realization.code_type_fqn);
      setLeftTab("code");
    }
    setMainMode("detail");
    setSelectedQueueItem(null);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header — neutral surface, primary accent text */}
      <div className="px-3 py-2 border-b border-border flex items-center gap-2 bg-muted/40">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-primary" />
          큐 미리보기 · {labelOf(selectedQueueItem.kind)}
        </span>
        <button onClick={() => setSelectedQueueItem(null)} className="ml-auto text-muted-foreground hover:text-foreground">
          <XIcon className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 text-[11px] space-y-3">
        {loading && (
          <div className="text-muted-foreground flex items-center gap-1">
            <Loader2 className="w-3 h-3 animate-spin" /> 로딩중…
          </div>
        )}
        {err && (
          <div className="px-2 py-1.5 rounded bg-destructive/10 border border-destructive/40 text-destructive text-[11px]">
            로드 실패: {err}
          </div>
        )}

        {term && <TermPreview term={term} />}
        {action && <ActionPreview action={action} />}
        {realization && (
          <RealizationPreview
            realization={realization}
            codeType={realCodeType}
            term={realTerm}
          />
        )}
      </div>

      <div className="px-3 py-2 border-t border-border space-y-1.5">
        {(term || action || realization) && (
          <Button
            size="sm"
            variant="outline"
            className="w-full justify-center gap-1 h-7 text-[11px]"
            onClick={openDetail}
          >
            Detail 탭으로 이동 <ArrowRight className="w-3 h-3" />
          </Button>
        )}
        <div className="flex gap-1.5">
          <Button
            size="sm"
            className="flex-1 h-7 text-[11px] gap-1"
            onClick={confirm}
            disabled={actionBusy !== null}
            title="confirmed=True 로 변경 (Action 은 verification_level: draft → signature_locked)"
          >
            {actionBusy === "confirm" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Confirm
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 h-7 text-[11px] gap-1 text-destructive border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
            onClick={reject}
            disabled={actionBusy !== null}
            title="후보 row 삭제 (recommend 다시 돌리면 재생성)"
          >
            {actionBusy === "reject" ? <Loader2 className="w-3 h-3 animate-spin" /> : <XIcon className="w-3 h-3" />}
            Reject
          </Button>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Term preview
// ────────────────────────────────────────────────────────────────────
function TermPreview({ term }: { term: TermDTO }) {
  return (
    <div className="space-y-1.5">
      <Field k="FQN" v={term.fqn} mono />
      <Field k="Label" v={term.label} bold />
      <Field k="Kind" v={term.kind} />
      <Field k="Domain" v={term.domain || "—"} />
      {term.aliases.length > 0 && <Field k="Aliases" v={term.aliases.join(", ")} />}
      {term.is_root_entity && <Field k="Root" v="✓ root entity" />}
      {term.struct_like_hint && <Field k="Struct" v="✓ struct-like" />}
      {term.value_type && <Field k="Value type" v={`${term.value_type}${term.unit ? " " + term.unit : ""}`} />}
      {term.enum_values && <Field k="Enum" v={term.enum_values.join(" | ")} />}
      {term.description && <Block k="Description" body={term.description} />}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Action preview
// ────────────────────────────────────────────────────────────────────
function ActionPreview({ action }: { action: ActionDTO }) {
  return (
    <div className="space-y-1.5">
      <Field k="FQN" v={action.fqn} mono />
      <Field k="Label" v={action.label} bold />
      <Field k="Kind" v={action.kind} />
      <Field k="Domain" v={action.domain || "—"} />
      <Field k="Verification" v={action.verification_level} />
      {action.declared_on_term && <Field k="On term" v={action.declared_on_term} mono />}
      {action.aliases.length > 0 && <Field k="Aliases" v={action.aliases.join(", ")} />}

      {action.params.length > 0 && (
        <ListSection
          title={`Params · ${action.params.length}`}
          items={action.params.slice(0, 3).map((p, i) => ({
            key: `p${i}`,
            main: `${p.name}: ${p.type}`,
            sub: p.object_ref_term || p.unit || (p.range ? `range ${p.range.join("~")}` : ""),
          }))}
          rest={action.params.length - 3}
        />
      )}
      {action.effects.length > 0 && (
        <ListSection
          title={`Effects · ${action.effects.length}`}
          items={action.effects.slice(0, 3).map((e, i) => ({
            key: `e${i}`,
            main: `${e.op} → ${e.target_term.split(".").pop() ?? e.target_term}${e.target_attr ? "." + e.target_attr : ""}`,
            sub: e.description || "",
          }))}
          rest={action.effects.length - 3}
        />
      )}
      {action.realizations.length > 0 && (
        <ListSection
          title={`Realizations · ${action.realizations.length}`}
          items={action.realizations.slice(0, 3).map((r, i) => ({
            key: `r${i}`,
            main: r.code_method_fqn.split(".").slice(-2).join("."),
            sub: `${r.scope} · conf ${r.confidence.toFixed(2)}${r.applies_to_code_type_fqn ? " · " + (r.applies_to_code_type_fqn.split(".").pop() ?? "") : ""}`,
          }))}
          rest={action.realizations.length - 3}
        />
      )}
      {action.description && <Block k="Description" body={action.description} />}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Realization preview — code_type + term context 양쪽 카드
// ────────────────────────────────────────────────────────────────────
function RealizationPreview({
  realization, codeType, term,
}: {
  realization: QueueRealizationDTO;
  codeType: CodeTypeDTO | null;
  term: TermDTO | null;
}) {
  return (
    <div className="space-y-2">
      {/* 매핑 헤더 */}
      <div className="bg-muted/40 rounded p-2 space-y-1 min-w-0">
        <div className="flex items-center gap-2 text-[10.5px] min-w-0">
          <span className="font-mono text-foreground truncate min-w-0 flex-1" title={realization.code_type_fqn}>
            {realization.code_type_fqn.split(".").pop()}
          </span>
          <ArrowRight className="w-3 h-3 text-muted-foreground shrink-0" />
          <span className="font-mono text-foreground truncate min-w-0 flex-1" title={realization.term_fqn}>
            {realization.term_fqn.split(".").pop()}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
          <span className={cn(
            "px-1.5 py-0.5 rounded font-medium",
            realization.scope === "primary"
              ? "bg-primary/15 text-primary"
              : "bg-muted text-foreground",
          )}>
            {realization.scope.toUpperCase()}
          </span>
          <span>confidence {realization.confidence.toFixed(2)}</span>
        </div>
      </div>

      {/* 양쪽 context */}
      <ContextCard
        heading="Code type"
        loading={codeType === null}
        empty={codeType === null ? "정보 없음" : null}
      >
        {codeType && (
          <>
            <Field k="Name" v={codeType.simple_name} bold />
            <Field k="Package" v={codeType.package || "—"} mono />
            <Field k="Kind" v={codeType.kind} />
            <Field k="Role" v={codeType.role || "unknown"} />
            <Field k="Methods" v={codeType.methods.length === 0 ? "—" : String(codeType.methods.length)} />
            {codeType.methods.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {codeType.methods.slice(0, 4).map((m) => (
                  <div key={m.fqn} className="text-[10px] font-mono text-muted-foreground truncate min-w-0" title={m.fqn}>
                    · {m.name}({m.params.map((p) => p.type).join(", ")})
                  </div>
                ))}
                {codeType.methods.length > 4 && (
                  <div className="text-[10px] text-muted-foreground/70">+ {codeType.methods.length - 4} more</div>
                )}
              </div>
            )}
          </>
        )}
      </ContextCard>

      <ContextCard
        heading="Term"
        loading={term === null}
        empty={term === null ? "정보 없음" : null}
      >
        {term && (
          <>
            <Field k="Label" v={term.label} bold />
            <Field k="Kind" v={term.kind} />
            <Field k="Domain" v={term.domain || "—"} />
            {term.aliases.length > 0 && <Field k="Aliases" v={term.aliases.join(", ")} />}
            {term.is_root_entity && <Field k="Root" v="✓ root entity" />}
            {term.description && (
              <div className="bg-background/60 rounded p-1.5 mt-1 text-[10.5px] whitespace-pre-wrap">
                {term.description}
              </div>
            )}
          </>
        )}
      </ContextCard>

      {realization.rationale && <Block k="Rationale" body={realization.rationale} />}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// 공통 building blocks
// ────────────────────────────────────────────────────────────────────
function Field({ k, v, mono, bold }: { k: string; v: string; mono?: boolean; bold?: boolean }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2 items-baseline min-w-0">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider font-medium truncate min-w-0" title={k}>{k}</div>
      <div
        className={cn(
          "truncate min-w-0",
          mono && "font-mono text-[10.5px]",
          bold ? "font-semibold text-foreground" : "text-foreground",
        )}
        title={v}
      >
        {v}
      </div>
    </div>
  );
}

function Block({ k, body }: { k: string; body: string }) {
  return (
    <div className="bg-muted/40 rounded p-2 mt-1 min-w-0">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider mb-0.5 font-medium">{k}</div>
      <div className="whitespace-pre-wrap break-words text-[11px]">{body}</div>
    </div>
  );
}

function ListSection({
  title, items, rest,
}: {
  title: string;
  items: { key: string; main: string; sub?: string }[];
  rest: number;
}) {
  return (
    <div className="bg-muted/40 rounded p-2 mt-1 min-w-0">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider mb-1 font-medium">
        {title}
      </div>
      <ul className="space-y-0.5 min-w-0">
        {items.map((it) => (
          <li key={it.key} className="text-[10.5px] min-w-0">
            <div className="font-mono truncate min-w-0" title={it.main}>· {it.main}</div>
            {it.sub && <div className="text-[10px] text-muted-foreground truncate min-w-0 pl-2.5" title={it.sub}>{it.sub}</div>}
          </li>
        ))}
        {rest > 0 && (
          <li className="text-[10px] text-muted-foreground/80 pl-2.5">+ {rest} more (Detail 탭에서 전체 확인)</li>
        )}
      </ul>
    </div>
  );
}

function ContextCard({
  heading, loading, empty, children,
}: {
  heading: string;
  loading?: boolean;
  empty?: string | null;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-border rounded p-2 space-y-1 min-w-0">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider font-medium flex items-center gap-1">
        {heading}
        {loading && <Loader2 className="w-2.5 h-2.5 animate-spin shrink-0" />}
      </div>
      {empty ? (
        <div className="text-[10.5px] text-muted-foreground italic">{empty}</div>
      ) : (
        <div className="min-w-0">{children}</div>
      )}
    </div>
  );
}

function labelOf(kind: "term" | "action" | "realization"): string {
  if (kind === "term") return "Term 후보";
  if (kind === "action") return "Action 후보";
  return "Realization 후보";
}
