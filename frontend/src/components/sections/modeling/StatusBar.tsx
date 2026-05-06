"use client";

import { useEffect, useState } from "react";
import { ontologyApi } from "@/lib/api/ontology";
import { useWorkbench } from "./store";
import { cn } from "@/lib/utils";

const LEVELS = [
  { key: "unmapped", label: "U", color: "text-destructive border-destructive bg-destructive/10" },
  { key: "draft", label: "D", color: "text-amber-400 border-amber-400 bg-amber-400/10" },
  { key: "signature_locked", label: "SL", color: "text-muted-foreground border-border" },
  { key: "body_anchored", label: "BA", color: "text-muted-foreground border-border" },
  { key: "sim_verified", label: "SV", color: "text-emerald-400 border-emerald-400 bg-emerald-400/10" },
  { key: "pr_proven", label: "PR", color: "text-emerald-400 border-emerald-400 bg-emerald-400/10" },
];

export function StatusBar() {
  const { activeRepoId, direction } = useWorkbench();
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
      className="flex items-center gap-3 px-3 bg-card border-t border-border text-[11px] text-muted-foreground"
      style={{ gridArea: "status" }}
    >
      <span className="flex items-center gap-1">
        {LEVELS.map((lv) => (
          <span
            key={lv.key}
            className={cn(
              "inline-flex items-center gap-1 text-[10px] px-1 py-0 rounded-full border",
              lv.color,
            )}
          >
            <span className="font-semibold">{lv.label}</span>
            {progress.byLevel[lv.key] ?? 0}
          </span>
        ))}
      </span>
      <span>
        총 <strong className="text-foreground">{progress.total}</strong> actions ·
        BODY_ANCHORED+ <strong className="text-emerald-400">{bodyAnchoredOrAbove}</strong> ({pct}%)
      </span>
      <div className="flex-1" />
      <span className={direction === "fwd" ? "text-primary" : "text-amber-400"}>
        {direction === "fwd" ? "🔍 Forward" : "🔧 Backward"} 모드
      </span>
    </footer>
  );
}
