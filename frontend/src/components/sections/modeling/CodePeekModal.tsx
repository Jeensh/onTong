"use client";

/**
 * CodePeekModal — peek-and-close modal for viewing class signature or method
 * body without changing workbench selection (Wave C-A, 2026-05-10).
 *
 * Pattern parallels ParamDrawer (Esc / backdrop close, semi-transparent
 * backdrop, X button). UX choice: center modal (max-w-[800px]) over right
 * drawer because Java code lines run 80-120 chars and benefit from the
 * extra horizontal room.
 *
 * Inner navigation: peeking a class shows the signature view (fields +
 * method signatures). Clicking a method swaps the modal body to the method
 * peek view (body_text + line numbers) without closing. A "← back to class"
 * affordance returns to the signature view. The outer `fqn` prop is left
 * unchanged so closing + reopening with the same fqn restores the original
 * peek target.
 *
 * Backend: uses `getCodeMethodBody` (single-method endpoint) for method
 * peeks and `getCodeType` for class peeks. The method endpoint avoids
 * pulling the whole parent type, which matters at 5K-class repo scale.
 *
 * NOT a React portal — the `fixed inset-0 z-50` overlay is sufficient
 * for a workbench modal (no parent overflow:hidden traps), and matches
 * the project's RepoImportModal / ParamDrawer convention.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ExternalLink, FileCode, X } from "lucide-react";
import { JavaCode } from "./JavaCode";
import {
  ontologyApi,
  type CodeMethodBodyDTO,
  type CodeMethodDTO,
  type CodeTypeDTO,
} from "@/lib/api/ontology";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Public API contract — Wave C-B integration depends on these names.
// Do NOT rename without coordinating with the parallel agent.
// ---------------------------------------------------------------------------
export interface CodePeekModalProps {
  open: boolean;
  onClose: () => void;
  kind: "code_type" | "code_method";
  /** for code_method: full method FQN; for code_type: class FQN. */
  fqn: string;
  repoId: string;
  /** optional — line marker (e.g. anchor_locator line) to highlight in peek. */
  highlightLine?: number;
}

// ---------------------------------------------------------------------------
// Inner-navigation state — independent of outer `kind`/`fqn` props so the
// user can drill class → method → back without losing the original target.
// ---------------------------------------------------------------------------
type PeekView =
  | { mode: "class"; classFqn: string }
  | { mode: "method"; methodFqn: string; parentClassFqn: string };

/** "com.foo.Bar.method(Args)" → "com.foo.Bar". method paren-aware split. */
function parentTypeFqnOfMethod(methodFqn: string): string | null {
  const parenIdx = methodFqn.indexOf("(");
  const beforeParen = parenIdx >= 0 ? methodFqn.slice(0, parenIdx) : methodFqn;
  const lastDot = beforeParen.lastIndexOf(".");
  if (lastDot < 0) return null;
  return beforeParen.slice(0, lastDot);
}

/** "com.foo.Bar" → "Bar". Last segment after final dot. */
function simpleNameOfFqn(fqn: string): string {
  const parenIdx = fqn.indexOf("(");
  const beforeParen = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
  const lastDot = beforeParen.lastIndexOf(".");
  const tail = lastDot < 0 ? beforeParen : beforeParen.slice(lastDot + 1);
  return parenIdx >= 0 ? `${tail}${fqn.slice(parenIdx)}` : tail;
}

// ---------------------------------------------------------------------------
// Modal shell — backdrop + centered card + Esc/click-outside close.
// ---------------------------------------------------------------------------
export function CodePeekModal(props: CodePeekModalProps) {
  const { open, onClose, kind, fqn, repoId, highlightLine } = props;

  // Reset inner view when the modal (re)opens with a new target.
  const initialView = useMemo<PeekView>(() => {
    if (kind === "code_type") return { mode: "class", classFqn: fqn };
    const parent = parentTypeFqnOfMethod(fqn);
    return {
      mode: "method",
      methodFqn: fqn,
      parentClassFqn: parent ?? "",
    };
  }, [kind, fqn]);

  const [view, setView] = useState<PeekView>(initialView);

  useEffect(() => {
    if (open) setView(initialView);
  }, [open, initialView]);

  // Esc closes — only registered while open. Cleanup on unmount/close.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-6 py-10"
      onClick={onClose}
      aria-hidden={false}
    >
      <div
        role="dialog"
        aria-label={view.mode === "class" ? "Code class peek" : "Code method peek"}
        aria-modal="true"
        className="relative w-full max-w-[800px] max-h-[80vh] bg-card border border-border rounded-lg shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        <ModalHeader
          view={view}
          onClose={onClose}
          onBackToClass={
            view.mode === "method" && view.parentClassFqn
              ? () => setView({ mode: "class", classFqn: view.parentClassFqn })
              : undefined
          }
        />

        <div className="flex-1 overflow-y-auto">
          {view.mode === "class" ? (
            <ClassSignatureView
              classFqn={view.classFqn}
              repoId={repoId}
              onPeekMethod={(methodFqn) =>
                setView({
                  mode: "method",
                  methodFqn,
                  parentClassFqn: view.classFqn,
                })
              }
            />
          ) : (
            <MethodBodyView
              methodFqn={view.methodFqn}
              parentClassFqn={view.parentClassFqn}
              repoId={repoId}
              highlightLine={highlightLine}
            />
          )}
        </div>

        <ModalFooter />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header — entity icon + simple name large + full FQN small + close X.
// ---------------------------------------------------------------------------
function ModalHeader({
  view,
  onClose,
  onBackToClass,
}: {
  view: PeekView;
  onClose: () => void;
  onBackToClass?: () => void;
}) {
  const fqn = view.mode === "class" ? view.classFqn : view.methodFqn;
  const simple = simpleNameOfFqn(fqn);
  const tail = (() => {
    const parenIdx = fqn.indexOf("(");
    const beforeParen = parenIdx >= 0 ? fqn.slice(0, parenIdx) : fqn;
    const lastDot = beforeParen.lastIndexOf(".");
    return lastDot < 0 ? "" : beforeParen.slice(0, lastDot);
  })();

  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/30">
      {onBackToClass && (
        <button
          onClick={onBackToClass}
          className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-[11px]"
          title="클래스 시그니처로 돌아가기"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          클래스
        </button>
      )}
      <FileCode className="w-4 h-4 text-primary shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold">
            {view.mode === "class" ? "Class" : "Method"}
          </span>
          <span className="font-mono text-sm font-semibold text-foreground truncate">
            {simple}
          </span>
        </div>
        {tail && (
          <div className="font-mono text-[10.5px] text-muted-foreground truncate">
            {tail}
          </div>
        )}
      </div>
      <button
        onClick={onClose}
        className="text-muted-foreground hover:text-foreground"
        title="닫기 (Esc)"
        aria-label="닫기"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Footer — explanatory hint + close keystroke.
// ---------------------------------------------------------------------------
function ModalFooter() {
  return (
    <div className="border-t border-border bg-muted/40 px-4 py-2 flex items-center gap-2 text-[10.5px] text-muted-foreground">
      <span>피크 모드 — 현재 선택은 변경되지 않습니다</span>
      <span className="ml-auto">
        <kbd className="px-1 border border-border rounded bg-card font-mono">Esc</kbd> 닫기
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Class signature view — fields + method signatures (no body).
// Click a method row → swap to method body view inside same modal.
// ---------------------------------------------------------------------------
function ClassSignatureView({
  classFqn,
  repoId: _repoId,
  onPeekMethod,
}: {
  classFqn: string;
  repoId: string;
  onPeekMethod: (methodFqn: string) => void;
}) {
  // _repoId reserved for future per-repo-scoped class fetch — current
  // ontologyApi.getCodeType is FQN-keyed (FQN already namespaces by repo).
  void _repoId;

  const [ct, setCt] = useState<CodeTypeDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    ontologyApi
      .getCodeType(classFqn)
      .then((t) => {
        if (cancelled) return;
        if (!t) {
          setError(`Class 를 찾을 수 없음: ${classFqn}`);
          setCt(null);
        } else {
          setCt(t);
        }
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [classFqn]);

  if (loading) return <PeekStatus label="Loading…" />;
  if (error) return <PeekStatus label={error} tone="error" />;
  if (!ct) return <PeekStatus label="Class 데이터 없음" tone="error" />;

  return (
    <div className="p-4 space-y-3">
      {/* Modifiers / kind row */}
      <div className="flex flex-wrap items-center gap-1.5 text-[10.5px]">
        <span className="px-1.5 py-px rounded-full border border-primary/40 text-primary bg-primary/10">
          {ct.kind}
        </span>
        <span className="px-1.5 py-px rounded-full border border-border text-muted-foreground">
          role: {ct.role}
        </span>
        {ct.is_abstract && (
          <span className="px-1.5 py-px rounded-full border border-amber-400 text-amber-700 bg-amber-50">
            abstract
          </span>
        )}
        {ct.line_start && (
          <span className="ml-auto font-mono text-muted-foreground">
            {ct.source_file}:{ct.line_start}
            {ct.line_end ? `–${ct.line_end}` : ""}
          </span>
        )}
      </div>

      {/* extends / implements */}
      {(ct.extends || ct.implements.length > 0) && (
        <div className="text-[11px] space-y-0.5">
          {ct.extends && (
            <div>
              <span className="text-muted-foreground">extends</span>{" "}
              <span className="font-mono text-primary">{ct.extends}</span>
            </div>
          )}
          {ct.implements.map((i, idx) => (
            <div key={idx}>
              <span className="text-muted-foreground">
                {idx === 0 ? "implements" : ""}
              </span>{" "}
              <span className="font-mono text-primary">{i}</span>
            </div>
          ))}
        </div>
      )}

      {/* Fields */}
      {ct.fields.length > 0 && (
        <PeekSection title={`Fields · ${ct.fields.length}`}>
          {ct.fields.slice(0, 30).map((f, i) => (
            <div
              key={i}
              className="px-2 py-1 rounded my-0.5 text-[11.5px] grid grid-cols-[160px_1fr_60px] gap-2 items-center hover:bg-muted/50"
            >
              <span className="font-mono text-primary truncate">{f.name}</span>
              <span className="font-mono text-foreground truncate">{f.type}</span>
              <span className="text-[9.5px] text-muted-foreground font-mono text-right">
                {f.line ? `L${f.line}` : ""}
              </span>
            </div>
          ))}
          {ct.fields.length > 30 && (
            <p className="text-[10.5px] text-muted-foreground mt-1 px-2">
              … {ct.fields.length - 30}개 더 (Detail 에서 전체 보기)
            </p>
          )}
        </PeekSection>
      )}

      {/* Method signatures — clickable */}
      <PeekSection title={`Methods · ${ct.methods.length}`}>
        {ct.methods.length === 0 && (
          <p className="text-[11px] text-muted-foreground px-2">메서드 없음</p>
        )}
        {ct.methods.slice(0, 50).map((m, i) => (
          <MethodSignatureRow
            key={i}
            method={m}
            onClick={() => onPeekMethod(m.fqn)}
          />
        ))}
        {ct.methods.length > 50 && (
          <p className="text-[10.5px] text-muted-foreground mt-1 px-2">
            … {ct.methods.length - 50}개 더 (Detail 에서 전체 보기)
          </p>
        )}
      </PeekSection>

      <p className="text-[10.5px] text-muted-foreground italic">
        메서드를 클릭하면 본문(body)을 펼쳐 볼 수 있습니다.
      </p>
    </div>
  );
}

function MethodSignatureRow({
  method,
  onClick,
}: {
  method: CodeMethodDTO;
  onClick: () => void;
}) {
  const sig = `${method.name}(${method.params.map((p) => p.type).join(", ")}) → ${method.return_type}`;
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-2 py-1 rounded my-0.5 hover:bg-primary/5 group flex items-center gap-2"
      title="이 메서드 body 보기"
    >
      <span
        className={cn(
          "text-[9.5px] px-1 rounded border shrink-0",
          method.role === "business"
            ? "text-emerald-700 border-emerald-300 bg-emerald-50"
            : method.role === "helper"
              ? "text-amber-700 border-amber-300 bg-amber-50"
              : "text-muted-foreground border-border bg-card",
        )}
      >
        {method.role}
      </span>
      <span className="font-mono text-[11.5px] truncate flex-1 text-foreground group-hover:text-primary">
        {sig}
      </span>
      {method.line_start && (
        <span className="text-[9.5px] text-muted-foreground font-mono shrink-0">
          L{method.line_start}
        </span>
      )}
      {method.is_override && (
        <span className="text-[9px] text-muted-foreground border border-border px-1 rounded shrink-0">
          @Override
        </span>
      )}
      <ExternalLink className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 shrink-0" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Method body view — JavaCode with line numbers + optional highlight marker.
// ---------------------------------------------------------------------------
function MethodBodyView({
  methodFqn,
  parentClassFqn,
  repoId,
  highlightLine,
}: {
  methodFqn: string;
  parentClassFqn: string;
  repoId: string;
  highlightLine?: number;
}) {
  const [body, setBody] = useState<CodeMethodBodyDTO | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setBody(null);
    ontologyApi
      .getCodeMethodBody(methodFqn, repoId)
      .then((b) => {
        if (cancelled) return;
        setBody(b);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [methodFqn, repoId]);

  // Pre-compute marker map outside conditional rendering so React's hook
  // count stays stable across loading / error / success states.
  const markers = useMemo(() => {
    if (!highlightLine) return undefined;
    return new Map<number, { label: string; tone: "semantic" | "static" | "info" }>([
      [highlightLine, { label: `L${highlightLine}`, tone: "info" as const }],
    ]);
  }, [highlightLine]);

  if (loading) return <PeekStatus label="Method body 로딩 중…" />;
  if (error) return <PeekStatus label={error} tone="error" />;
  if (!body) return <PeekStatus label="Method 데이터 없음" tone="error" />;

  if (!body.body_text) {
    return (
      <div className="p-4 space-y-2">
        <MethodMetaLine body={body} parentClassFqn={parentClassFqn} />
        <PeekStatus label="Method body 가 없음 (abstract / interface 가능)" />
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <MethodMetaLine body={body} parentClassFqn={parentClassFqn} />
      <div className="border border-border rounded overflow-hidden bg-muted/20">
        <div className="overflow-x-auto">
          <JavaCode
            source={body.body_text}
            startLine={body.line_start ?? 1}
            markers={markers}
            showLineNumbers
          />
        </div>
      </div>
    </div>
  );
}

function MethodMetaLine({
  body,
  parentClassFqn,
}: {
  body: CodeMethodBodyDTO;
  parentClassFqn: string;
}) {
  const range =
    body.line_start && body.line_end
      ? `L${body.line_start}-${body.line_end}`
      : body.line_start
        ? `L${body.line_start}`
        : "";
  return (
    <div className="text-[11px] text-muted-foreground flex flex-wrap items-center gap-2">
      <span>parent class:</span>
      <span className="font-mono text-primary truncate">
        {parentClassFqn || body.parent_type_fqn}
      </span>
      {range && (
        <span className="ml-auto font-mono text-muted-foreground">{range}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------
function PeekSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1 px-1">
        {title}
      </div>
      <div>{children}</div>
    </div>
  );
}

function PeekStatus({
  label,
  tone = "info",
}: {
  label: string;
  tone?: "info" | "error";
}) {
  return (
    <div
      className={cn(
        "p-6 text-center text-sm",
        tone === "error" ? "text-rose-600" : "text-muted-foreground",
      )}
    >
      {label}
    </div>
  );
}
