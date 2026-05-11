"use client";

// ─────────────────────────────────────────────────────────────────────────
// Detail panel noise-reduction helpers (Wave B-1)
//
// FlagsRow    — render only TRUE flags as small chips; nothing if all false
// PanelStripe — 4-px colored left border replacing the per-panel banner
//
// (Empty-section folding is done inline at each call site with `length > 0 && ...`
// because each section has a different rule for what to keep vs hide.)
// ─────────────────────────────────────────────────────────────────────────

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { HelpHint } from "./HelpHint";

export type PanelStripeColor = "violet" | "primary" | "rose" | "sky" | "orange";

const STRIPE_BORDER_CLASS: Record<PanelStripeColor, string> = {
  violet:  "border-violet-500",
  primary: "border-primary",
  rose:    "border-rose-500",
  sky:     "border-sky-500",
  orange:  "border-orange-500",
};

/**
 * 4-px colored left stripe replacing the old banner div.
 * Wrap around the Detail's outer container; preserves max-width inside.
 */
export function PanelStripe({
  color,
  children,
}: {
  color: PanelStripeColor;
  children: ReactNode;
}) {
  return (
    <div className={cn("border-l-4 pl-4", STRIPE_BORDER_CLASS[color])}>
      {children}
    </div>
  );
}

/** A boolean flag with its display label, optional tooltip. */
export type FlagItem = {
  key: string;
  value: boolean;
  /** Optional human label (defaults to `key`). */
  label?: string;
  /** Optional tooltip surfaced via `title`. */
  tooltip?: string;
  /** Optional glossary key — when set, a HelpHint chip is rendered alongside. */
  glossaryKey?: string;
};

/**
 * Render only flags whose `value === true` as small chips.
 * If all false → returns null (no header, no empty space).
 */
export function FlagsRow({ flags }: { flags: FlagItem[] }) {
  const onFlags = flags.filter((f) => f.value);
  if (onFlags.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {onFlags.map((f) => (
        <span
          key={f.key}
          title={f.tooltip}
          className="text-[10.5px] px-1.5 py-0.5 rounded-full border border-border bg-muted text-foreground inline-flex items-center gap-0.5"
        >
          {f.label ?? f.key}
          {f.glossaryKey && <HelpHint term={f.glossaryKey} inline />}
        </span>
      ))}
    </div>
  );
}

