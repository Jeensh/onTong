"use client";

import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { GLOSSARY, type GlossaryEntry } from "./glossary";
import { cn } from "@/lib/utils";

/**
 * 작은 ? 아이콘. hover / 클릭 시 용어 설명 popup.
 *
 * Tooltip 은 React portal 로 document.body 에 렌더 → 부모의 `overflow: hidden`
 * 에 잘리지 않음 (Section 같은 좁은 컨테이너 안에서도 안전하게 보임).
 *
 * 사용:
 *   <HelpHint term="anchor" />
 *   <HelpHint term="confidence" inline />
 *   <HelpHint custom={{ label: "X", short: "...", example: "..." }} />
 */
export function HelpHint({
  term,
  custom,
  inline = false,
  className,
}: {
  term?: string;
  custom?: GlossaryEntry;
  inline?: boolean;
  className?: string;
}) {
  const entry: GlossaryEntry | null =
    custom ?? (term ? GLOSSARY[term.toLowerCase()] ?? null : null);
  const fallbackEntry: GlossaryEntry = {
    label: term ? `${term}` : "용어",
    short: term
      ? `이 용어는 아직 사전(glossary)에 등록되지 않았습니다. (key: ${term})`
      : "이 용어는 아직 사전에 등록되지 않았습니다.",
  };
  const display = entry ?? fallbackEntry;
  const isRegistered = entry !== null;

  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const anchorRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);

  // Compute viewport-coord position whenever open. Position below icon by
  // default; flip above if it would clip the viewport bottom.
  useEffect(() => {
    if (!open || !anchorRef.current || typeof window === "undefined") {
      setPos(null);
      return;
    }
    const rect = anchorRef.current.getBoundingClientRect();
    const tooltipW = 288; // matches w-72
    const tooltipH = 100; // approximate
    const margin = 6;
    let top = rect.bottom + margin;
    if (top + tooltipH > window.innerHeight) {
      top = Math.max(margin, rect.top - tooltipH - margin);
    }
    let left = rect.left;
    if (left + tooltipW > window.innerWidth - margin) {
      left = Math.max(margin, window.innerWidth - tooltipW - margin);
    }
    setPos({ top, left });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      const a = anchorRef.current;
      const t = tooltipRef.current;
      const target = e.target as Node;
      if (a?.contains(target)) return;
      if (t?.contains(target)) return;
      setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("click", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("click", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  return (
    <span ref={anchorRef} className={cn("relative inline-block", className)}>
      {/*
        주의: button 이 아니라 span (role=button) — 부모가 이미 button 일 때
        nested button 으로 인한 hydration error 방지.
      */}
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            setOpen((v) => !v);
          }
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => {
          // Delay close so user can move into tooltip without flicker
          window.setTimeout(() => {
            if (!tooltipRef.current?.matches(":hover")) setOpen(false);
          }, 80);
        }}
        className={cn(
          "inline-flex items-center justify-center rounded-full border text-[9.5px] font-semibold transition-colors cursor-help select-none align-middle",
          inline ? "w-3.5 h-3.5 ml-1" : "w-4 h-4",
          isRegistered
            ? inline
              ? "border-muted-foreground/40 text-muted-foreground hover:bg-muted hover:text-foreground"
              : "border-primary/40 text-primary hover:bg-primary hover:text-primary-foreground"
            : "border-amber-400/50 text-amber-600 hover:bg-amber-100 hover:text-amber-800",
        )}
        title={
          isRegistered
            ? `${display.label} 설명 보기`
            : `(${term ?? "?"} — 사전 미등록) 클릭해서 자세히`
        }
        aria-label={`${display.label} 설명`}
      >
        ?
      </span>
      {open &&
        pos &&
        typeof document !== "undefined" &&
        createPortal(
          <span
            ref={tooltipRef}
            role="tooltip"
            style={{ position: "fixed", top: pos.top, left: pos.left }}
            className="z-[9999] w-72 bg-popover border border-border rounded-md shadow-lg p-2.5 text-[11.5px] text-popover-foreground block"
            onMouseEnter={() => setOpen(true)}
            onMouseLeave={() => setOpen(false)}
          >
            <div className="font-semibold text-foreground mb-1 flex items-center gap-1.5 break-words">
              {display.label}
              {!isRegistered && (
                <span className="text-[9.5px] uppercase tracking-wider text-amber-600 border border-amber-400/50 rounded px-1 py-px">
                  사전 미등록
                </span>
              )}
            </div>
            <div className="text-muted-foreground leading-relaxed break-words whitespace-pre-wrap">
              {display.short}
            </div>
            {display.example && (
              <div className="mt-1.5 text-[10.5px] text-foreground italic break-words">
                {display.example}
              </div>
            )}
          </span>,
          document.body,
        )}
    </span>
  );
}
