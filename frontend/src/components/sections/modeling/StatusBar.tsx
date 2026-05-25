"use client";

import { useEffect, useState } from "react";
import { ontologyApi } from "@/lib/api/ontology";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";

const LEVELS = [
  { key: "unmapped",         label: "U",  full: "UNMAPPED",         dot: "bg-destructive"    },
  { key: "draft",            label: "D",  full: "DRAFT",            dot: "bg-amber-400"      },
  { key: "signature_locked", label: "SL", full: "SIGNATURE_LOCKED", dot: "bg-muted-foreground/60" },
  { key: "body_anchored",    label: "BA", full: "BODY_ANCHORED",    dot: "bg-sky-400"        },
  { key: "sim_verified",     label: "SV", full: "SIM_VERIFIED",     dot: "bg-emerald-400"    },
  { key: "pr_proven",        label: "PR", full: "PR_PROVEN",        dot: "bg-emerald-500"    },
];

export function StatusBar() {
  const { activeRepoId } = useWorkbench();
  const [progress, setProgress] = useState<{ total: number; byLevel: Record<string, number> }>({
    total: 0,
    byLevel: {},
  });

  useEffect(() => {
    let cancelled = false;
    ontologyApi
      .getVerificationProgress(activeRepoId)
      .then((p) => {
        if (cancelled) return;
        setProgress({ total: p.total_actions, byLevel: p.by_level });
      })
      .catch(() => {
        // backend 가 비어있을 수 있음 (Phase 1 시작 직후)
        if (!cancelled) setProgress({ total: 0, byLevel: {} });
      });
    return () => {
      cancelled = true;
    };
  }, [activeRepoId]);

  const bodyAnchoredOrAbove = ["body_anchored", "sim_verified", "pr_proven"]
    .map((k) => progress.byLevel[k] ?? 0)
    .reduce((a, b) => a + b, 0);

  const pct = progress.total > 0 ? Math.round((bodyAnchoredOrAbove / progress.total) * 100) : 0;

  return (
    <footer
      className="flex items-center gap-4 px-3 bg-card border-t border-border text-[11px] text-muted-foreground"
      style={{ gridArea: "status" }}
    >
      <div className="flex items-center gap-2.5">
        {LEVELS.map((lv) => {
          const count = progress.byLevel[lv.key] ?? 0;
          return (
            <span
              key={lv.key}
              className="inline-flex items-center gap-1 text-[10.5px]"
              title={`${lv.full}: ${count}`}
            >
              <span className={cn("w-1.5 h-1.5 rounded-full", lv.dot, count === 0 && "opacity-30")} />
              <span className={cn("font-mono tabular-nums", count > 0 ? "text-foreground" : "text-muted-foreground/60")}>
                {lv.label} {count}
              </span>
            </span>
          );
        })}
      </div>
      <span className="w-px h-3 bg-border" />
      <span className="text-[10.5px]">
        <span className="font-mono tabular-nums text-foreground">{progress.total}</span>
        <span className="text-muted-foreground/70"> actions ·</span>{" "}
        <span className="font-mono tabular-nums text-emerald-500">{bodyAnchoredOrAbove}</span>
        <span className="text-muted-foreground/70"> body-anchored+ </span>
        <span className="font-mono tabular-nums text-foreground">({pct}%)</span>
      </span>
      <div className="flex-1" />
    </footer>
  );
}
