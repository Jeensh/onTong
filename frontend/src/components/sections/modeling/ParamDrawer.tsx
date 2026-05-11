"use client";

/**
 * ParamDrawer — slide-in drawer showing all 9 ActionParamDTO fields.
 *
 * #9 (2026-05-10) — triggered from ActionDetail's ParamRow click. Read-only
 * for now — full param editing is an Authoring-mode workflow (param schema
 * mutations require touching the Action's signature lock, anchor rebinding,
 * etc). The drawer footer surfaces a CTA to open Authoring mode.
 */

import { useEffect } from "react";
import { X } from "lucide-react";
import type { ActionParamDTO } from "@/lib/api/ontology";

export function ParamDrawer({
  param,
  index,
  onClose,
  onOpenAuthoring,
}: {
  param: ActionParamDTO | null;
  index: number | null;
  onClose: () => void;
  onOpenAuthoring?: () => void;
}) {
  const open = param !== null;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !param) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Backdrop — click to close. */}
      <div
        className="absolute inset-0 bg-black/30 transition-opacity"
        onClick={onClose}
        aria-hidden
      />
      {/* Drawer panel. */}
      <div
        role="dialog"
        aria-label="Action parameter detail"
        className="relative bg-white border-l border-border shadow-xl w-[480px] max-w-[95vw] h-full flex flex-col animate-in slide-in-from-right duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header. */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold">
            Action Parameter
          </span>
          <span className="font-mono text-xs text-primary">
            {index != null ? `[${index}]` : ""} {param.name}
          </span>
          <button
            onClick={onClose}
            className="ml-auto text-muted-foreground hover:text-foreground"
            title="닫기 (Esc)"
            aria-label="닫기"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body — read-only field grid. */}
        <div className="overflow-y-auto flex-1 p-4 text-xs">
          <FieldRow label="name"            value={param.name} mono />
          <FieldRow label="type"            value={param.type || "—"} mono />
          <FieldRow
            label="object_ref_term"
            value={param.object_ref_term || "—"}
            mono
            hint="이 param 이 가리키는 BusinessTerm FQN"
          />
          <FieldRow label="unit"            value={param.unit || "—"} hint="단위 (e.g. mm, kg)" />
          <FieldRow
            label="range"
            value={
              param.range && param.range.length === 2
                ? `[${param.range[0]}, ${param.range[1]}]`
                : "—"
            }
            mono
            hint="허용 범위 [min, max]"
          />
          <FieldRow
            label="nullable"
            value={param.nullable ? "✓ true" : "false"}
            hint="null 값 허용 여부"
          />
          <FieldRow
            label="anchor_locator"
            value={param.anchor_locator || "—"}
            mono
            hint="이 param 이 코드에서 바인딩되는 fragment locator"
          />
          <FieldRow
            label="confirmed"
            value={param.confirmed ? "✓ confirmed" : "draft"}
            hint="사용자가 이 param 매핑을 confirm 했는지"
          />
          <div className="mt-3">
            <div className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">
              description
            </div>
            <div className="bg-muted px-3 py-2 rounded text-[12px] text-foreground whitespace-pre-wrap leading-relaxed">
              {param.description || <span className="text-zinc-400 italic">— (미지정)</span>}
            </div>
          </div>
        </div>

        {/* Footer — Authoring CTA. */}
        <div className="border-t border-border bg-muted/40 p-3 flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground flex-1">
            param 편집은 Authoring 모드에서 (signature lock + anchor rebind 필요)
          </span>
          {onOpenAuthoring && (
            <button
              onClick={onOpenAuthoring}
              className="text-[11px] px-3 py-1 rounded border border-violet-400 text-violet-700 bg-white hover:bg-violet-100 transition-colors"
            >
              ✏️ Authoring 모드에서 편집
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function FieldRow({
  label,
  value,
  mono,
  hint,
}: {
  label: string;
  value: string;
  mono?: boolean;
  hint?: string;
}) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 my-1.5 items-start">
      <span className="text-[10.5px] uppercase tracking-wider text-muted-foreground font-semibold pt-0.5">
        {label}
        {hint && <div className="text-[9.5px] normal-case font-normal tracking-normal text-muted-foreground/70 mt-0.5">{hint}</div>}
      </span>
      <span
        className={`text-foreground break-all ${mono ? "font-mono text-[11.5px]" : "text-xs"}`}
      >
        {value}
      </span>
    </div>
  );
}
