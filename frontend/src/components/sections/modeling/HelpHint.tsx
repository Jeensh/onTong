"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { GLOSSARY, type GlossaryEntry, type GlossaryEntryV2, toV2 } from "./glossary";
import { cn } from "@/lib/utils";

const TOOLTIP_W = 320;        // px (max-w-[320px])
const TOOLTIP_MAX_H = 320;    // px — flip math budget
const GAP = 6;
const VIEWPORT_PAD = 8;

type Pos = { top: number; left: number; placement: "bottom" | "top" };

/**
 * 작은 ? 아이콘. 호버/클릭 시 용어 설명 popup.
 *
 * Wave 2 (2026-05-11): structured GlossaryEntry 지원 — summary / detail bullets /
 * example code block / related chips. related chip 클릭 시 popup 내용 swap.
 *
 * Popup 은 React Portal 로 document.body 에 렌더되어 부모의 overflow-hidden /
 * truncate / max-width 에 의해 잘리지 않는다.
 */
export function HelpHint({
  term, custom, inline = false, className,
}: {
  term?: string;
  custom?: GlossaryEntry;
  inline?: boolean;
  className?: string;
}) {
  // related chip 클릭 시 swap 가능하도록 active key 를 state 로.
  const [activeKey, setActiveKey] = useState<string | null>(term?.toLowerCase() ?? null);
  useEffect(() => { setActiveKey(term?.toLowerCase() ?? null); }, [term]);

  const rawEntry: GlossaryEntry | null =
    custom ?? (activeKey ? GLOSSARY[activeKey] ?? null : null);
  const entry: GlossaryEntryV2 | null = rawEntry
    ? toV2(rawEntry, activeKey ?? term ?? "")
    : null;

  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<Pos | null>(null);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMounted(true); }, []);

  const computePos = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let top = r.bottom + GAP;
    let left = r.left;
    let placement: Pos["placement"] = "bottom";
    if (top + TOOLTIP_MAX_H > vh - VIEWPORT_PAD) {
      const flipped = r.top - GAP - TOOLTIP_MAX_H;
      if (flipped > VIEWPORT_PAD) {
        top = r.top - GAP - TOOLTIP_MAX_H;
        placement = "top";
      } else {
        top = Math.max(VIEWPORT_PAD, vh - TOOLTIP_MAX_H - VIEWPORT_PAD);
      }
    }
    if (left + TOOLTIP_W > vw - VIEWPORT_PAD) left = vw - TOOLTIP_W - VIEWPORT_PAD;
    if (left < VIEWPORT_PAD) left = VIEWPORT_PAD;
    setPos({ top, left, placement });
  }, []);

  useEffect(() => {
    if (!open) { setPos(null); return; }
    computePos();
    const onDoc = (e: MouseEvent) => {
      const t = e.target as Node;
      if (triggerRef.current?.contains(t)) return;
      if (popupRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    const onReposition = () => computePos();
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onReposition, true);
    window.addEventListener("resize", onReposition);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onReposition, true);
      window.removeEventListener("resize", onReposition);
    };
  }, [open, computePos]);

  // 모르는 용어 — 작은 ? 만 표시.
  if (!entry) {
    return (
      <span
        className={cn("inline-block text-[10px] text-muted-foreground", className)}
        title={term ? `(${term} — 사전 미등록)` : ""}
      >?</span>
    );
  }

  const popup = open && pos && mounted
    ? createPortal(
        <div
          ref={popupRef}
          role="tooltip"
          style={{
            position: "fixed", top: pos.top, left: pos.left,
            width: TOOLTIP_W, maxHeight: TOOLTIP_MAX_H, zIndex: 1000,
          }}
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
          className="bg-popover border border-border rounded-md shadow-lg p-3 text-[11.5px] text-popover-foreground overflow-y-auto"
        >
          <HelpHintBody
            entry={entry}
            onSwap={(nextKey) => { if (GLOSSARY[nextKey]) setActiveKey(nextKey); }}
          />
        </div>,
        document.body,
      )
    : null;

  return (
    <span ref={triggerRef} className={cn("relative inline-block", className)}>
      {/* span(role=button) — 부모가 button 일 때 nested-button hydration error 방지. */}
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault(); e.stopPropagation(); setOpen((v) => !v);
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
      >?</span>
      {popup}
    </span>
  );
}

/** Popup 본문 — summary / detail bullets / example block / related chips. */
export function HelpHintBody({
  entry,
  onSwap,
}: {
  entry: GlossaryEntryV2;
  onSwap?: (nextKey: string) => void;
}) {
  const labelCls = TONE_LABEL[entry.tone ?? "neutral"];
  return (
    <div>
      <div className={cn("font-semibold mb-1 leading-snug", labelCls)}>{entry.label}</div>
      <div className="text-foreground leading-relaxed">{entry.summary}</div>
      {entry.detail && entry.detail.length > 0 && (
        <ul className="mt-1.5 pl-3.5 space-y-0.5 text-[11px] text-muted-foreground list-disc marker:text-muted-foreground/50">
          {entry.detail.map((d, i) => <li key={i} className="leading-relaxed">{d}</li>)}
        </ul>
      )}
      {entry.example && (
        <div className="mt-2 px-2 py-1 rounded bg-muted/70 border border-border/70 font-mono text-[10.5px] text-foreground break-all">
          예: {entry.example}
        </div>
      )}
      {entry.related && entry.related.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {entry.related.map((rk) => {
            const exists = !!GLOSSARY[rk];
            return (
              <button
                key={rk}
                type="button"
                onClick={(e) => { e.stopPropagation(); if (exists && onSwap) onSwap(rk); }}
                className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded border font-mono transition-colors",
                  exists
                    ? "border-border/70 text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer"
                    : "border-border/40 text-muted-foreground/50 cursor-default",
                )}
                title={exists ? `→ ${rk} 보기` : `${rk} (사전 미등록)`}
                disabled={!exists}
              >{rk}</button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** 카테고리별 label 색조 — popup 첫 줄(label)에만 적용. 나머지는 중립. */
const TONE_LABEL: Record<NonNullable<GlossaryEntryV2["tone"]>, string> = {
  term:    "text-violet-700",
  action:  "text-orange-700",
  code:    "text-primary",
  anchor:  "text-sky-700",
  rule:    "text-rose-700",
  verify:  "text-amber-700",
  queue:   "text-emerald-700",
  neutral: "text-foreground",
};
