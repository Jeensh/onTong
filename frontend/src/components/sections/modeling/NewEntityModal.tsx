"use client";

/**
 * 새 entity 직접 추가 — 코드 import / Recommend / Authoring 경로 외 진입점.
 *
 * 4 kinds: Term / Action / BusinessRule / Anchor.
 * 성공 시 selectedXxxFqn 으로 자동 navigate + queue refresh ping.
 */

import { useEffect, useRef, useState } from "react";
import { X, Loader2, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ontologyApi, type SearchHitDTO } from "@/lib/api/ontology";
import { useWorkbench } from "./store";

type EntityKind = "term" | "action" | "rule" | "anchor";

const KINDS: { id: EntityKind; label: string; emoji: string; hint: string }[] = [
  { id: "term", label: "Term", emoji: "🟣", hint: "비즈니스 용어 (예: VIP 고객)" },
  { id: "action", label: "Action", emoji: "🟠", hint: "행동/메서드 (예: 주문 검증)" },
  { id: "rule", label: "BR", emoji: "⚖", hint: "비즈니스 규칙 (예: 0.10 ≤ C ≤ 0.25)" },
  { id: "anchor", label: "Anchor", emoji: "📍", hint: "코드 ↔ Action slot binding (고급)" },
];

export function NewEntityModal({
  open, onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const repoId = useWorkbench((s) => s.activeRepoId);
  const setSelectedTerm = useWorkbench((s) => s.setSelectedTerm);
  const setSelectedAction = useWorkbench((s) => s.setSelectedAction);
  const setSelectedRule = useWorkbench((s) => s.setSelectedRule);
  const setSelectedAnchor = useWorkbench((s) => s.setSelectedAnchor);
  const bumpQueueRefresh = useWorkbench((s) => s.bumpQueueRefresh);

  const [kind, setKind] = useState<EntityKind>("term");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  // Term/Action 공통
  const [fqn, setFqn] = useState("");
  const [label, setLabel] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [aliases, setAliases] = useState("");
  // Term 전용
  const [termKind, setTermKind] = useState<"atomic" | "composite">("composite");
  const [isRootEntity, setIsRootEntity] = useState(false);
  // Action 전용
  const [actionKind, setActionKind] = useState<"pure_function" | "effectful" | "workflow">("effectful");
  const [declaredOnTerm, setDeclaredOnTerm] = useState("");
  // BR 전용
  const [statement, setStatement] = useState("");
  const [severity, setSeverity] = useState<"hard" | "soft">("hard");
  // Anchor 전용
  const [anchorLocator, setAnchorLocator] = useState("");
  const [codeMethodFqn, setCodeMethodFqn] = useState("");
  const [targetActionFqn, setTargetActionFqn] = useState("");
  const [targetSlot, setTargetSlot] = useState("");
  const [rationale, setRationale] = useState("");

  const reset = () => {
    setFqn(""); setLabel(""); setDomain(""); setDescription(""); setAliases("");
    setTermKind("composite"); setIsRootEntity(false);
    setActionKind("effectful"); setDeclaredOnTerm("");
    setStatement(""); setSeverity("hard");
    setAnchorLocator(""); setCodeMethodFqn(""); setTargetActionFqn(""); setTargetSlot(""); setRationale("");
    setErr(null);
  };

  useEffect(() => {
    if (!open) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Kind 전환 시 모든 입력 초기화 (잘못된 fqn 으로 submit 방지)
  const switchKind = (k: EntityKind) => {
    if (k === kind) return;
    reset();
    setKind(k);
  };

  // 비어있지 않은 입력이 있나? backdrop close 가드 + close 시 confirm 용
  const hasInput = Boolean(
    fqn || label || domain || description || aliases ||
    statement || anchorLocator || codeMethodFqn || targetActionFqn || targetSlot || rationale
  );

  // 기본 fqn prefix 가이드
  const fqnPlaceholder = {
    term: "term.scm.vip_customer",
    action: "action.scm.주문_검증",
    rule: "rule.scm.c_range",
    anchor: "(자동 생성)",
  }[kind];

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      if (kind === "term") {
        if (!fqn.trim() || !label.trim()) throw new Error("FQN 과 Label 은 필수.");
        const res = await ontologyApi.createTerm(repoId, {
          fqn: fqn.trim(), label: label.trim(), kind: termKind,
          domain: domain.trim(), description: description.trim(),
          aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
          is_root_entity: isRootEntity,
        });
        setSelectedTerm(res.fqn);
      } else if (kind === "action") {
        if (!fqn.trim() || !label.trim()) throw new Error("FQN 과 Label 은 필수.");
        const res = await ontologyApi.createAction(repoId, {
          fqn: fqn.trim(), label: label.trim(), kind: actionKind,
          domain: domain.trim(), description: description.trim(),
          aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
          declared_on_term: declaredOnTerm.trim() || null,
        });
        setSelectedAction(res.fqn);
      } else if (kind === "rule") {
        if (!fqn.trim() || !statement.trim()) throw new Error("FQN 과 Statement 은 필수.");
        const res = await ontologyApi.createBusinessRule(repoId, {
          fqn: fqn.trim(), statement: statement.trim(), severity,
        });
        setSelectedRule(res.fqn);
      } else {
        if (!codeMethodFqn.trim() || !targetActionFqn.trim() || !targetSlot.trim() || !anchorLocator.trim()) {
          throw new Error("anchor_locator / code_method_fqn / target_action_fqn / target_slot 모두 필수.");
        }
        const res = await ontologyApi.createAnchorBinding(repoId, {
          anchor_locator: anchorLocator.trim(),
          code_method_fqn: codeMethodFqn.trim(),
          target_action_fqn: targetActionFqn.trim(),
          target_slot: targetSlot.trim(),
          rationale: rationale.trim(),
        });
        setSelectedAnchor(res.fqn);
      }
      bumpQueueRefresh();
      onOpenChange(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={() => {
        if (busy) return;
        // 입력 있을 때 실수 방지 — backdrop click 으로는 안 닫힘.
        if (hasInput) return;
        onOpenChange(false);
      }}
    >
      <div
        className="bg-card border border-border rounded-lg shadow-2xl w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Plus className="w-4 h-4" /> 새 entity 추가
          </h3>
          <button onClick={() => onOpenChange(false)} disabled={busy} className="text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Kind selector */}
        <div className="px-4 py-3 border-b border-border space-y-2">
          <div className="text-[11px] text-muted-foreground">종류</div>
          <div className="grid grid-cols-4 gap-1.5">
            {KINDS.map((k) => (
              <button
                key={k.id}
                onClick={() => switchKind(k.id)}
                title={k.hint}
                className={cn(
                  "px-2 py-1.5 rounded border text-[11px] flex flex-col items-center gap-0.5 transition-colors",
                  kind === k.id ? "border-primary bg-primary/10 text-foreground" : "border-border text-muted-foreground hover:border-muted-foreground",
                )}
              >
                <span className="text-base leading-none">{k.emoji}</span>
                <span>{k.label}</span>
              </button>
            ))}
          </div>
          <div className="text-[10px] text-muted-foreground">{KINDS.find((k) => k.id === kind)?.hint}</div>
        </div>

        {/* Form body */}
        <div className="px-4 py-3 space-y-3 text-[11px]">
          {kind !== "anchor" && (
            <Field label="FQN" required>
              <Input value={fqn} onChange={(e) => setFqn(e.target.value)} placeholder={fqnPlaceholder} className="h-7 text-[11px] font-mono" />
            </Field>
          )}

          {(kind === "term" || kind === "action") && (
            <>
              <Field label="Label" required>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="VIP 고객 / 주문 검증 등" className="h-7 text-[11px]" />
              </Field>
              <Field label="Domain">
                <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="scm / purchasing / …" className="h-7 text-[11px]" />
              </Field>
              <Field label="Description">
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className="w-full px-2 py-1 text-[11px] rounded border bg-background" placeholder="설명 (optional)" />
              </Field>
              <Field label="Aliases (콤마 구분)">
                <Input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="VIP, 우수고객" className="h-7 text-[11px]" />
              </Field>
            </>
          )}

          {kind === "term" && (
            <>
              <Field label="Kind">
                <div className="flex gap-2">
                  <RadioPill checked={termKind === "atomic"} onChange={() => setTermKind("atomic")} label="atomic (단일 값)" />
                  <RadioPill checked={termKind === "composite"} onChange={() => setTermKind("composite")} label="composite (복합)" />
                </div>
              </Field>
              <Field label="Root entity?">
                <label className="flex items-center gap-2">
                  <input type="checkbox" checked={isRootEntity} onChange={(e) => setIsRootEntity(e.target.checked)} />
                  <span className="text-[11px] text-muted-foreground">독립 lifecycle (검색 가능 entity)</span>
                </label>
              </Field>
            </>
          )}

          {kind === "action" && (
            <>
              <Field label="Kind">
                <div className="flex gap-1.5 flex-wrap">
                  <RadioPill checked={actionKind === "pure_function"} onChange={() => setActionKind("pure_function")} label="pure" />
                  <RadioPill checked={actionKind === "effectful"} onChange={() => setActionKind("effectful")} label="effectful" />
                  <RadioPill checked={actionKind === "workflow"} onChange={() => setActionKind("workflow")} label="workflow" />
                </div>
              </Field>
              <Field label="Declared on Term (optional)">
                <Input value={declaredOnTerm} onChange={(e) => setDeclaredOnTerm(e.target.value)} placeholder="term.scm.order" className="h-7 text-[11px] font-mono" />
              </Field>
            </>
          )}

          {kind === "rule" && (
            <>
              <Field label="Statement" required>
                <textarea value={statement} onChange={(e) => setStatement(e.target.value)} rows={3} className="w-full px-2 py-1 text-[11px] rounded border bg-background" placeholder="예: 0.10 ≤ C ≤ 0.25" />
              </Field>
              <Field label="Severity">
                <div className="flex gap-2">
                  <RadioPill checked={severity === "hard"} onChange={() => setSeverity("hard")} label="hard" />
                  <RadioPill checked={severity === "soft"} onChange={() => setSeverity("soft")} label="soft" />
                </div>
              </Field>
            </>
          )}

          {kind === "anchor" && (
            <>
              <Field label="Anchor locator" required>
                <Input value={anchorLocator} onChange={(e) => setAnchorLocator(e.target.value)} placeholder="args[0] / return / literal:0.10" className="h-7 text-[11px] font-mono" />
              </Field>
              <Field label="Code method" required>
                <SearchPicker
                  value={codeMethodFqn}
                  onChange={setCodeMethodFqn}
                  kindFilter="code_method"
                  placeholder="메서드명 / 클래스명 검색"
                />
              </Field>
              <Field label="Target action" required>
                <SearchPicker
                  value={targetActionFqn}
                  onChange={setTargetActionFqn}
                  kindFilter="action"
                  placeholder="action 이름 / 한글 label 검색"
                />
              </Field>
              <Field label="Target slot" required>
                <Input value={targetSlot} onChange={(e) => setTargetSlot(e.target.value)} placeholder="params[0] / output / preconditions[0]" className="h-7 text-[11px] font-mono" />
              </Field>
              <Field label="Rationale">
                <textarea value={rationale} onChange={(e) => setRationale(e.target.value)} rows={2} className="w-full px-2 py-1 text-[11px] rounded border bg-background" />
              </Field>
            </>
          )}

          {err && (
            <div className="px-2 py-1.5 rounded bg-rose-500/10 border border-rose-500/30 text-[11px] text-rose-300">
              {err}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={busy}>취소</Button>
          <Button size="sm" onClick={submit} disabled={busy}>
            {busy && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
            생성 (confirmed=False)
          </Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider">
        {label}{required && <span className="text-rose-400 ml-0.5">*</span>}
      </div>
      {children}
    </div>
  );
}

function RadioPill({ checked, onChange, label }: { checked: boolean; onChange: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onChange}
      className={cn(
        "px-2 py-0.5 rounded border text-[11px] transition-colors",
        checked ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

/**
 * Autocomplete input — backend search 호출 후 dropdown. kindFilter 로 결과 좁힘.
 * `value` 는 FQN; user 가 dropdown 에서 선택하면 onChange(fqn). 자유 타이핑도 허용 (선택 안 해도 submit 가능).
 */
function SearchPicker({
  value, onChange, kindFilter, placeholder,
}: {
  value: string;
  onChange: (fqn: string) => void;
  kindFilter: SearchHitDTO["kind"];
  placeholder: string;
}) {
  const repoId = useWorkbench((s) => s.activeRepoId);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHitDTO[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 dropdown 닫기
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  // debounced 검색
  useEffect(() => {
    if (!query.trim()) { setHits([]); return; }
    let cancelled = false;
    setLoading(true);
    const t = setTimeout(() => {
      ontologyApi
        .search(query, { repo_id: repoId, limit: 30 })
        .then((d) => {
          if (cancelled) return;
          setHits(d.filter((h) => h.kind === kindFilter));
        })
        .catch(() => { if (!cancelled) setHits([]); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 200);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query, repoId, kindFilter]);

  const display = value || query;

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-muted-foreground" />
        <Input
          value={display}
          onChange={(e) => {
            setQuery(e.target.value);
            // 사용자가 타이핑 시작하면 value 도 동기화 (수동 입력 허용)
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="pl-7 pr-7 h-7 text-[11px] font-mono"
        />
        {loading && <Loader2 className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 animate-spin text-muted-foreground" />}
      </div>
      {open && hits.length > 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-card border border-border rounded shadow-lg max-h-48 overflow-auto z-30">
          {hits.slice(0, 20).map((h) => (
            <button
              key={`${h.kind}|${h.fqn}`}
              type="button"
              onClick={() => {
                onChange(h.fqn);
                setQuery("");
                setOpen(false);
              }}
              className="w-full text-left px-2 py-1.5 text-[10.5px] hover:bg-muted flex items-center gap-2 border-b border-border last:border-b-0 min-w-0"
            >
              <span className="font-mono truncate flex-1 min-w-0">{h.label || h.fqn}</span>
              <span className="text-[9px] text-muted-foreground/70 truncate max-w-[40%] shrink-0" title={h.fqn}>
                {h.fqn.split(".").slice(-2).join(".")}
              </span>
            </button>
          ))}
        </div>
      )}
      {open && !loading && query.trim() && hits.length === 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-card border border-border rounded shadow-lg p-2 z-30 text-[10px] text-muted-foreground">
          매칭 없음 — 직접 입력한 값으로 진행 가능
        </div>
      )}
    </div>
  );
}
