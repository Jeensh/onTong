"use client";

import { useState, useRef, useEffect } from "react";
import { GLOSSARY, type GlossaryEntry } from "./glossary";
import { cn } from "@/lib/utils";

/**
 * 작은 ? 아이콘. 호버 / 클릭 시 용어 설명 popup.
 *
 * 사용:
 *   <HelpHint term="anchor" />
 *   <HelpHint term="confidence" inline />   (label 옆 inline 표시)
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
  const entry = custom ?? (term ? GLOSSARY[term.toLowerCase()] ?? null : null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, [open]);

  if (!entry) {
    return (
      <span className={cn("inline-block text-[10px] text-muted-foreground", className)} title={term ? `(${term} — 사전 미등록)` : ""}>
        ?
      </span>
    );
  }

  return (
    <span ref={ref} className={cn("relative inline-block", className)}>
      {/*
        주의: button 이 아니라 span (role=button) — 부모가 이미 button 일 때
        nested button 으로 인한 hydration error 방지.
      */}
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            setOpen((v) => !v);
          }
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className={cn(
          "inline-flex items-center justify-center rounded-full border text-[9.5px] font-semibold transition-colors cursor-help select-none",
          inline
            ? "w-3.5 h-3.5 ml-1 align-middle border-muted-foreground/40 text-muted-foreground hover:bg-muted hover:text-foreground"
            : "w-4 h-4 border-primary/40 text-primary hover:bg-primary hover:text-primary-foreground",
        )}
        title={`${entry.label} 설명 보기`}
        aria-label={`${entry.label} 설명`}
      >
        ?
      </span>
      {open && (
        <span
          role="tooltip"
          className="absolute z-50 left-0 top-full mt-1 w-72 bg-popover border border-border rounded-md shadow-lg p-2.5 text-[11.5px] text-popover-foreground"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <div className="font-semibold text-foreground mb-1">{entry.label}</div>
          <div className="text-muted-foreground leading-relaxed">{entry.short}</div>
          {entry.example && (
            <div className="mt-1.5 text-[10.5px] text-foreground italic">{entry.example}</div>
          )}
        </span>
      )}
    </span>
  );
}
