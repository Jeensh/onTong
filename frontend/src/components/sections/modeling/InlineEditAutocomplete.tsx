"use client";

/**
 * InlineEditAutocomplete — text input + dropdown of typed candidates.
 *
 * #2 (2026-05-10) — replaces AnchorBinding.anchor_locator's free text edit
 * with a typed dropdown sourced from `getAnchorCandidates`. Free-text
 * fallback is preserved (don't gate to suggestions only).
 *
 * Behavior
 *   - On focus: fetches the suggestion list (cached in component state).
 *   - Arrow up/down: navigate the dropdown.
 *   - Enter: pick the highlighted suggestion (or save current text if none).
 *   - Tab: accept the highlighted suggestion (don't blur input).
 *   - Esc: cancel edit.
 *   - User can type any text (free-text fallback).
 */

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AutocompleteSuggestion {
  /** value written into the input on selection (== anchor_locator). */
  value: string;
  /** Optional kind label for icon mapping. */
  kind?: string;
  /** Optional secondary description shown next to the value. */
  description?: string;
  /** Optional 1-based source line for tooltip. */
  line?: number | null;
}

type SaveFn = (value: string) => Promise<void>;
type FetchFn = () => Promise<AutocompleteSuggestion[]>;

/**
 * Icon for each AnchorCandidate.kind. Falls back to a neutral dot.
 *
 * Mapping defined in spec; chosen so colors don't collide with existing
 * status badges (emerald=confirmed, amber=draft).
 */
function kindIcon(kind: string | undefined): string {
  switch (kind) {
    case "method-body":   return "🟢";
    case "param-name":    return "🔵";
    case "if-stmt":       return "🟡";
    case "loop-body":     return "🟠";
    case "return-stmt":   return "🟣";
    case "try-block":     return "🔴";
    case "assignment":    return "⚪";
    case "call":          return "🟤";
    default:              return "·";
  }
}

export function InlineEditAutocomplete({
  value,
  onSave,
  fetchSuggestions,
  placeholder,
  className,
  inputClassName,
}: {
  value: string;
  onSave: SaveFn;
  /** Lazy fetcher — first focus triggers it once; result cached in state. */
  fetchSuggestions: FetchFn;
  placeholder?: string;
  className?: string;
  inputClassName?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AutocompleteSuggestion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const fetched = useRef(false);

  useEffect(() => {
    if (!editing) {
      setText(value);
      setErr(null);
    }
  }, [value, editing]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const start = () => {
    setText(value);
    setErr(null);
    setEditing(true);
    setOpen(true);
  };

  const cancel = () => {
    setText(value);
    setErr(null);
    setOpen(false);
    setEditing(false);
  };

  const save = async (override?: string) => {
    const v = override ?? text;
    setSaving(true);
    setErr(null);
    try {
      await onSave(v);
      setOpen(false);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const ensureFetched = async () => {
    if (fetched.current) return;
    fetched.current = true;
    setLoading(true);
    try {
      const list = await fetchSuggestions();
      setItems(list);
    } catch (e) {
      // Silent — autocomplete is best-effort. Free text still works.
      // eslint-disable-next-line no-console
      console.warn("[InlineEditAutocomplete] fetch failed", e);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  // Filter suggestions by current text (substring, case-insensitive).
  const filtered = (items ?? []).filter((it) =>
    !text || it.value.toLowerCase().includes(text.toLowerCase()),
  );
  const visibleCount = Math.min(filtered.length, 12);

  if (editing) {
    return (
      <span className={cn("inline-flex items-start", className)}>
        <span className="relative inline-flex flex-col">
          <input
            ref={inputRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setHighlight(0);
              if (!open) setOpen(true);
            }}
            onFocus={() => {
              setOpen(true);
              void ensureFetched();
            }}
            onBlur={() => {
              // Defer so a click on a suggestion can still register before close.
              setTimeout(() => setOpen(false), 120);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") { e.preventDefault(); cancel(); return; }
              if (e.key === "ArrowDown") {
                e.preventDefault();
                if (visibleCount > 0) setHighlight((h) => (h + 1) % visibleCount);
                return;
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                if (visibleCount > 0) setHighlight((h) => (h - 1 + visibleCount) % visibleCount);
                return;
              }
              if (e.key === "Tab" && open && visibleCount > 0) {
                e.preventDefault();
                const pick = filtered[highlight];
                if (pick) setText(pick.value);
                return;
              }
              if (e.key === "Enter") {
                e.preventDefault();
                if (open && visibleCount > 0 && filtered[highlight]) {
                  const pick = filtered[highlight];
                  setText(pick.value);
                  void save(pick.value);
                } else {
                  void save();
                }
              }
            }}
            disabled={saving}
            placeholder={placeholder}
            className={cn(
              "border border-sky-400 rounded px-1.5 py-0.5 text-sm bg-white",
              "focus:outline-none focus:ring-1 focus:ring-sky-400",
              inputClassName,
            )}
          />
          {open && (
            <div className="absolute top-full left-0 mt-0.5 w-full min-w-[320px] max-w-[600px] z-30 bg-white border border-border rounded shadow-md max-h-[280px] overflow-y-auto">
              {loading && (
                <div className="px-2 py-1.5 text-[11px] text-muted-foreground inline-flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  candidates 로드 중…
                </div>
              )}
              {!loading && filtered.length === 0 && (
                <div className="px-2 py-1.5 text-[11px] text-muted-foreground italic">
                  candidates 없음 (자유 입력 가능)
                </div>
              )}
              {!loading && filtered.slice(0, 12).map((it, i) => (
                <button
                  key={`${it.value}-${i}`}
                  type="button"
                  // mousedown fires before input blur — keeps click reliable.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setText(it.value);
                    void save(it.value);
                  }}
                  onMouseEnter={() => setHighlight(i)}
                  className={cn(
                    "w-full text-left px-2 py-1 text-[11.5px] grid grid-cols-[16px_1fr] gap-1.5 items-start",
                    i === highlight ? "bg-sky-50" : "hover:bg-zinc-50",
                  )}
                  title={it.line != null ? `line ${it.line}` : undefined}
                >
                  <span className="text-[12px] leading-none pt-0.5 select-none">{kindIcon(it.kind)}</span>
                  <span className="min-w-0">
                    <span className="font-mono text-foreground break-all">{it.value}</span>
                    {it.description && (
                      <span className="text-muted-foreground"> — {it.description}</span>
                    )}
                  </span>
                </button>
              ))}
              {!loading && filtered.length > 12 && (
                <div className="px-2 py-1 text-[10px] text-muted-foreground border-t border-border">
                  … {filtered.length - 12} 더 (검색어 좁혀보세요)
                </div>
              )}
            </div>
          )}
        </span>
        <span className="inline-flex items-center gap-1 ml-1">
          <button
            onClick={() => void save()}
            disabled={saving}
            title="저장 (Enter)"
            className="text-emerald-700 hover:text-emerald-900 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={cancel}
            disabled={saving}
            title="취소 (Esc)"
            className="text-zinc-500 hover:text-rose-700 disabled:opacity-50"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </span>
        {err && (
          <span className="ml-1 text-[10px] text-rose-700" title={err}>⚠ {err}</span>
        )}
      </span>
    );
  }

  return (
    <span className={cn("group inline-flex items-center", className)}>
      <span className={cn(!value && "text-zinc-400 italic")}>{value || placeholder || "—"}</span>
      <button
        onClick={start}
        title="편집 (자동완성)"
        className="opacity-0 group-hover:opacity-100 transition-opacity ml-1 text-zinc-400 hover:text-zinc-700"
      >
        <Pencil className="w-3 h-3" />
      </button>
    </span>
  );
}
