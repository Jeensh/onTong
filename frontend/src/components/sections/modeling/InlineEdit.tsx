"use client";

/**
 * Inline edit primitives — Term / Action / BR / Anchor detail 카드의 field 를
 * 클릭해서 바로 수정. 5-ii Stage 2.
 *
 * 전부 controlled-ish: 외부 value 와 onSave 만 받음. 내부에서 edit/save 상태 관리.
 *
 * 4 종:
 *   - InlineEditText      single line string
 *   - InlineEditTextArea  multi-line string (description, statement, rationale)
 *   - InlineEditList      string[] (aliases, enum_values) — comma-separated input
 *   - InlineEditSelect    enum string (severity hard/soft, ...)
 *
 * 모두 같은 패턴:
 *   - idle:    텍스트 + ✏️ hover 보임
 *   - editing: input/textarea + Save / Cancel 버튼
 *   - saving:  spinner + disable
 */

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------
type SaveFn<T> = (value: T) => Promise<void>;

function useSaver<T>(initial: T, onSave: SaveFn<T>) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<T>(initial);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!editing) setValue(initial);
  }, [initial, editing]);

  const start = () => {
    setValue(initial);
    setErr(null);
    setEditing(true);
  };
  const cancel = () => {
    setValue(initial);
    setErr(null);
    setEditing(false);
  };
  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      await onSave(value);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return { editing, value, setValue, saving, err, start, cancel, save };
}

function EditButtons({
  onSave,
  onCancel,
  saving,
}: {
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1 ml-1">
      <button
        onClick={onSave}
        disabled={saving}
        title="저장 (Cmd/Ctrl+Enter)"
        className="text-emerald-700 hover:text-emerald-900 disabled:opacity-50"
      >
        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
      </button>
      <button
        onClick={onCancel}
        disabled={saving}
        title="취소 (Esc)"
        className="text-zinc-500 hover:text-rose-700 disabled:opacity-50"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </span>
  );
}

function EditPencil({ onClick, title }: { onClick: () => void; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title ?? "편집"}
      className="opacity-0 group-hover:opacity-100 transition-opacity ml-1 text-zinc-400 hover:text-zinc-700"
    >
      <Pencil className="w-3 h-3" />
    </button>
  );
}

function ErrSpan({ err }: { err: string | null }) {
  if (!err) return null;
  return (
    <span className="ml-1 text-[10px] text-rose-700" title={err}>⚠ {err}</span>
  );
}

// ---------------------------------------------------------------------------
// InlineEditText
// ---------------------------------------------------------------------------
export function InlineEditText({
  value,
  onSave,
  placeholder,
  className,
  inputClassName,
}: {
  value: string;
  onSave: SaveFn<string>;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
}) {
  const s = useSaver(value, onSave);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (s.editing) ref.current?.focus(); }, [s.editing]);

  if (s.editing) {
    return (
      <span className={cn("inline-flex items-center", className)}>
        <input
          ref={ref}
          value={s.value}
          onChange={(e) => s.setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") s.cancel();
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); s.save(); }
          }}
          disabled={s.saving}
          placeholder={placeholder}
          className={cn(
            "border border-sky-400 rounded px-1.5 py-0.5 text-sm bg-white",
            "focus:outline-none focus:ring-1 focus:ring-sky-400",
            inputClassName,
          )}
        />
        <EditButtons onSave={s.save} onCancel={s.cancel} saving={s.saving} />
        <ErrSpan err={s.err} />
      </span>
    );
  }
  return (
    <span className={cn("group inline-flex items-center", className)}>
      <span className={cn(!value && "text-zinc-400 italic")}>{value || placeholder || "—"}</span>
      <EditPencil onClick={s.start} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// InlineEditTextArea
// ---------------------------------------------------------------------------
export function InlineEditTextArea({
  value,
  onSave,
  placeholder,
  rows = 3,
  className,
}: {
  value: string;
  onSave: SaveFn<string>;
  placeholder?: string;
  rows?: number;
  className?: string;
}) {
  const s = useSaver(value, onSave);
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (s.editing) ref.current?.focus(); }, [s.editing]);

  if (s.editing) {
    return (
      <div className={cn("flex flex-col gap-1", className)}>
        <textarea
          ref={ref}
          value={s.value}
          onChange={(e) => s.setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") s.cancel();
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); s.save(); }
          }}
          disabled={s.saving}
          rows={rows}
          placeholder={placeholder}
          className={cn(
            "w-full border border-sky-400 rounded px-2 py-1 text-sm bg-white resize-y",
            "focus:outline-none focus:ring-1 focus:ring-sky-400",
          )}
        />
        <div className="flex items-center gap-2">
          <button
            onClick={s.save}
            disabled={s.saving}
            className="text-xs px-2 py-0.5 rounded border border-emerald-400 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 disabled:opacity-50 inline-flex items-center gap-1"
          >
            {s.saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            저장
          </button>
          <button
            onClick={s.cancel}
            disabled={s.saving}
            className="text-xs px-2 py-0.5 rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 inline-flex items-center gap-1"
          >
            <X className="w-3 h-3" />
            취소
          </button>
          <span className="text-[10px] text-zinc-400">Cmd/Ctrl+Enter 로 저장 · Esc 로 취소</span>
          <ErrSpan err={s.err} />
        </div>
      </div>
    );
  }
  return (
    <div className={cn("group flex items-start gap-1", className)}>
      <div className={cn("flex-1 whitespace-pre-wrap", !value && "text-zinc-400 italic")}>
        {value || placeholder || "—"}
      </div>
      <EditPencil onClick={s.start} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// InlineEditList — comma-separated input → string[]
// ---------------------------------------------------------------------------
export function InlineEditList({
  value,
  onSave,
  placeholder,
  className,
}: {
  value: string[];
  onSave: SaveFn<string[]>;
  placeholder?: string;
  className?: string;
}) {
  const initial = value.join(", ");
  const ref = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { if (!editing) setText(initial); }, [initial, editing]);
  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);

  const start = () => { setText(initial); setErr(null); setEditing(true); };
  const cancel = () => { setText(initial); setErr(null); setEditing(false); };
  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const parsed = text.split(",").map((s) => s.trim()).filter((s) => s.length > 0);
      await onSave(parsed);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <span className={cn("inline-flex items-center flex-wrap gap-1", className)}>
        <input
          ref={ref}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") cancel();
            if (e.key === "Enter") { e.preventDefault(); save(); }
          }}
          disabled={saving}
          placeholder={placeholder ?? "콤마(,)로 구분"}
          className="border border-sky-400 rounded px-1.5 py-0.5 text-sm bg-white min-w-[200px] focus:outline-none focus:ring-1 focus:ring-sky-400"
        />
        <EditButtons onSave={save} onCancel={cancel} saving={saving} />
        <ErrSpan err={err} />
      </span>
    );
  }
  return (
    <span className={cn("group inline-flex items-center flex-wrap gap-1", className)}>
      {value.length === 0 ? (
        <span className="text-zinc-400 italic">{placeholder ?? "—"}</span>
      ) : (
        value.map((v, i) => (
          <span key={`${v}-${i}`} className="px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 text-xs">
            {v}
          </span>
        ))
      )}
      <EditPencil onClick={start} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// InlineEditSelect — fixed enum
//
// 2026-05-10 (#1, #3) — gained two opt-in props:
//   - confirmModal: show a modal "Y → X 로 바꿀까요?" before calling onSave.
//     Useful for high-impact fields (BR.severity, CodeType.role).
//   - fallbackText: { value, label } — selecting that option swaps the select
//     into a free-text input so the user can type any value not in the enum.
//     Used by Term.value_type "기타..." fallback.
// ---------------------------------------------------------------------------
type ConfirmModalOpts<T> = boolean | { title?: string; body?: (v: T) => string };

export function InlineEditSelect<T extends string>({
  value,
  options,
  onSave,
  className,
  renderOption,
  confirmModal,
  fallbackText,
}: {
  value: T;
  options: readonly T[];
  onSave: SaveFn<T>;
  className?: string;
  renderOption?: (v: T) => string;
  confirmModal?: ConfirmModalOpts<T>;
  fallbackText?: { value: T; label: string };
}) {
  const s = useSaver(value, onSave);
  const ref = useRef<HTMLSelectElement>(null);
  const textRef = useRef<HTMLInputElement>(null);
  // Confirmation modal — staged value waiting for user OK.
  const [pending, setPending] = useState<T | null>(null);
  // Free-text mode — set when user picks the fallback option.
  const [textMode, setTextMode] = useState(false);
  const [text, setText] = useState("");

  useEffect(() => {
    if (s.editing && !textMode) ref.current?.focus();
  }, [s.editing, textMode]);
  useEffect(() => {
    if (textMode) textRef.current?.focus();
  }, [textMode]);

  const display = renderOption ? renderOption(value) : value;

  // Save flow: if confirmModal is set, stage the current value and let the
  // modal call s.save(). Otherwise call s.save() directly — `s.value` is
  // already up-to-date because the <select onChange> wrote to it.
  const requestSave = () => {
    if (confirmModal) {
      setPending(s.value);
    } else {
      void s.save();
    }
  };

  const cancelEdit = () => {
    setTextMode(false);
    setText("");
    setPending(null);
    s.cancel();
  };

  const confirmModalBody = (v: T): string => {
    if (typeof confirmModal === "object" && confirmModal?.body) return confirmModal.body(v);
    return `값을 ${v} 로 바꿉니다.`;
  };
  const confirmModalTitle = (v: T): string => {
    if (typeof confirmModal === "object" && confirmModal?.title) return confirmModal.title;
    return `정말 ${value} → ${v} 로 바꿀까요?`;
  };

  // Editing state ----------------------------------------------------------
  if (s.editing) {
    // 1) Free-text fallback — user picked the "기타..." option.
    if (textMode) {
      const saveText = async () => {
        const trimmed = text.trim();
        if (!trimmed) return;
        s.setValue(trimmed as T);
        // Use save directly with the typed text (skipping confirmModal — text edit IS the confirm).
        try {
          await onSave(trimmed as T);
          cancelEdit();
        } catch (e) {
          // Surface error via the saver state machine instead of throwing.
          // (useSaver doesn't expose setErr — fall back to inline display.)
          // eslint-disable-next-line no-console
          console.error("[InlineEditSelect.fallbackText] save failed", e);
        }
      };
      return (
        <span className={cn("inline-flex items-center", className)}>
          <input
            ref={textRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") cancelEdit();
              if (e.key === "Enter") { e.preventDefault(); void saveText(); }
            }}
            placeholder={fallbackText?.label ?? "직접 입력"}
            className="border border-sky-400 rounded px-1.5 py-0.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-sky-400"
          />
          <EditButtons onSave={() => void saveText()} onCancel={cancelEdit} saving={s.saving} />
          <ErrSpan err={s.err} />
        </span>
      );
    }

    return (
      <span className={cn("inline-flex items-center", className)}>
        <select
          ref={ref}
          value={s.value}
          onChange={(e) => {
            const next = e.target.value as T;
            // If user picked the fallback sentinel → swap to text mode (don't save yet).
            if (fallbackText && next === fallbackText.value) {
              setTextMode(true);
              return;
            }
            s.setValue(next);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") cancelEdit();
            if (e.key === "Enter") { e.preventDefault(); requestSave(); }
          }}
          disabled={s.saving}
          className="border border-sky-400 rounded px-1.5 py-0.5 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-sky-400"
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {fallbackText && o === fallbackText.value
                ? fallbackText.label
                : renderOption ? renderOption(o) : o}
            </option>
          ))}
        </select>
        <EditButtons onSave={requestSave} onCancel={cancelEdit} saving={s.saving} />
        <ErrSpan err={s.err} />
        {pending !== null && (
          <ConfirmModal
            title={confirmModalTitle(pending)}
            body={confirmModalBody(pending)}
            onConfirm={async () => {
              // s.value is already === pending (staged from s.value at request).
              setPending(null);
              await s.save();
            }}
            onCancel={() => setPending(null)}
            saving={s.saving}
          />
        )}
      </span>
    );
  }

  return (
    <span className={cn("group inline-flex items-center", className)}>
      <span>{display}</span>
      <EditPencil onClick={s.start} />
    </span>
  );
}

// ---------------------------------------------------------------------------
// ConfirmModal — small inline modal, used by InlineEditSelect when
// `confirmModal` prop is set. Light-mode style, Esc/Enter shortcuts.
// ---------------------------------------------------------------------------
function ConfirmModal({
  title,
  body,
  onConfirm,
  onCancel,
  saving,
}: {
  title: string;
  body: string;
  onConfirm: () => void;
  onCancel: () => void;
  saving: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onCancel(); }
      if (e.key === "Enter")  { e.preventDefault(); onConfirm(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onConfirm, onCancel]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div
        className="bg-white border border-border rounded-lg shadow-lg p-4 w-[420px] max-w-[90vw]"
        // Stop the click from reaching the backdrop.
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-sm font-semibold text-foreground mb-2">{title}</div>
        <div className="text-[12.5px] text-muted-foreground mb-4 leading-relaxed">{body}</div>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="text-xs px-3 py-1 rounded border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-100 disabled:opacity-50"
          >
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={saving}
            className="text-xs px-3 py-1 rounded border border-emerald-400 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 disabled:opacity-50 inline-flex items-center gap-1"
          >
            {saving && <Loader2 className="w-3 h-3 animate-spin" />}
            확인
          </button>
        </div>
      </div>
    </div>
  );
}
