"use client";

/**
 * InlineEditRange — atomic Term.range editor.
 *
 * #6 (2026-05-10) — replaces the read-only `[min, max]` KV row with two number
 * inputs separated by `→`. On save calls `onSave([min, max])`.
 *
 * NOTE: Backend status — `range` is in the codegen'd `TermPatch`
 * (`backend/modeling/api/_generated_patch_models.py`) but the hand-written
 * `queue_actions_api.TermPatch` has not been regenerated yet, so PATCH
 * may currently 422. W2-A is wiring this in parallel; until then we
 * surface the backend error inline. See TODO below.
 */

import { useEffect, useRef, useState } from "react";
import { Check, Loader2, Pencil, X } from "lucide-react";
import { cn } from "@/lib/utils";

type SaveFn = (value: number[]) => Promise<void>;

export function InlineEditRange({
  value,
  onSave,
  className,
}: {
  value: number[] | null | undefined;
  onSave: SaveFn;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [minStr, setMinStr] = useState("");
  const [maxStr, setMaxStr] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const minRef = useRef<HTMLInputElement>(null);

  // Keep local state synced when the parent value changes (and we're not in the
  // middle of editing).
  useEffect(() => {
    if (!editing) {
      const v = value ?? [];
      setMinStr(v[0] != null ? String(v[0]) : "");
      setMaxStr(v[1] != null ? String(v[1]) : "");
    }
  }, [value, editing]);

  useEffect(() => {
    if (editing) minRef.current?.focus();
  }, [editing]);

  const start = () => {
    const v = value ?? [];
    setMinStr(v[0] != null ? String(v[0]) : "");
    setMaxStr(v[1] != null ? String(v[1]) : "");
    setErr(null);
    setEditing(true);
  };
  const cancel = () => {
    setErr(null);
    setEditing(false);
  };

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const min = Number(minStr);
      const max = Number(maxStr);
      if (Number.isNaN(min) || Number.isNaN(max)) {
        throw new Error("min / max 모두 숫자여야 합니다.");
      }
      if (min > max) {
        throw new Error("min 은 max 보다 작거나 같아야 합니다.");
      }
      // TODO 2026-05-10 — backend `queue_actions_api.TermPatch` 가 아직
      // `range` field 를 노출하지 않았다면 422 error 가 떨어질 수 있다.
      // W2-A 의 patch model regeneration 후 자동으로 동작.
      await onSave([min, max]);
      setEditing(false);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <span className={cn("inline-flex items-center gap-1", className)}>
        <input
          ref={minRef}
          type="number"
          value={minStr}
          onChange={(e) => setMinStr(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") cancel();
            if (e.key === "Enter")  { e.preventDefault(); void save(); }
          }}
          disabled={saving}
          placeholder="min"
          className="w-24 border border-sky-400 rounded px-1.5 py-0.5 text-xs font-mono bg-white focus:outline-none focus:ring-1 focus:ring-sky-400"
        />
        <span className="text-xs text-muted-foreground">→</span>
        <input
          type="number"
          value={maxStr}
          onChange={(e) => setMaxStr(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") cancel();
            if (e.key === "Enter")  { e.preventDefault(); void save(); }
          }}
          disabled={saving}
          placeholder="max"
          className="w-24 border border-sky-400 rounded px-1.5 py-0.5 text-xs font-mono bg-white focus:outline-none focus:ring-1 focus:ring-sky-400"
        />
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
    <span className={cn("group inline-flex items-center gap-1", className)}>
      {value && value.length === 2 ? (
        <span className="font-mono text-xs">[{value[0]}, {value[1]}]</span>
      ) : (
        <span className="text-zinc-400 italic text-xs">—</span>
      )}
      <button
        onClick={start}
        title="편집 (min → max)"
        className="opacity-0 group-hover:opacity-100 transition-opacity ml-1 text-zinc-400 hover:text-zinc-700"
      >
        <Pencil className="w-3 h-3" />
      </button>
    </span>
  );
}
