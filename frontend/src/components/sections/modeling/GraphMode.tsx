"use client";

import { useEffect } from "react";
import { useWorkbench } from "./store";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { X, Layers, Waves, Network } from "lucide-react";
import { OntologyGraph } from "./OntologyGraph";
import { CoverageView } from "./CoverageView";
import { ImpactView } from "./ImpactView";

/**
 * Graph mode — V8 IA (graph redesign Option 3).
 *
 * Top-level mode switcher:
 *   📊 Coverage — daily entry point, domain heatmap + lens
 *   🌊 Impact   — event-driven ripple, focus + bidirectional BFS
 *   🌐 Explore  — 옛 xyflow neighborhood/path/cluster (legacy)
 *
 * Esc 로 닫기.
 */
export function GraphMode() {
  const { setGraphMode, activeRepoId, graphTopMode, setGraphTopMode } = useWorkbench();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement | null;
      if (tgt && (tgt.tagName === "INPUT" || tgt.tagName === "TEXTAREA" || tgt.isContentEditable)) {
        return;
      }
      if (e.key === "Escape") setGraphMode(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setGraphMode]);

  return (
    <div className="flex flex-col h-full">
      <header className="h-9 px-3 bg-card border-b border-border flex items-center gap-3">
        <h3 className="text-[12px] font-semibold flex items-center gap-1.5">
          <span>🌐</span> 온톨로지 그래프
        </h3>
        <div className="flex items-center gap-1">
          <ModeButton
            active={graphTopMode === "coverage"}
            onClick={() => setGraphTopMode("coverage")}
            icon={<Layers className="w-3 h-3" />}
            label="Coverage"
            hint="도메인 진척률 (daily)"
          />
          <ModeButton
            active={graphTopMode === "impact"}
            onClick={() => setGraphTopMode("impact")}
            icon={<Waves className="w-3 h-3" />}
            label="Impact"
            hint="변경 ripple (event)"
          />
          <ModeButton
            active={graphTopMode === "explore"}
            onClick={() => setGraphTopMode("explore")}
            icon={<Network className="w-3 h-3" />}
            label="Explore"
            hint="자유 탐색 (legacy)"
          />
        </div>
        <span className="text-[10px] text-muted-foreground ml-2 hidden lg:inline">
          {graphTopMode === "coverage" && "도메인 cell 클릭 → 우선 처리 대상 → Impact 점프"}
          {graphTopMode === "impact" && "focus 중심 양방향 BFS · risk score · 재검증 대상"}
          {graphTopMode === "explore" && "xyflow + ELK Layered · neighborhood / path / cluster"}
        </span>
        <div className="ml-auto">
          <Button variant="outline" size="sm" onClick={() => setGraphMode(false)} className="gap-1 h-7">
            <X className="w-3 h-3" /> 닫기 (esc)
          </Button>
        </div>
      </header>
      <div className="flex-1 relative min-h-0">
        {graphTopMode === "coverage" && <CoverageView repoId={activeRepoId} />}
        {graphTopMode === "impact" && <ImpactView repoId={activeRepoId} />}
        {graphTopMode === "explore" && <OntologyGraph repoId={activeRepoId} />}
      </div>
    </div>
  );
}

function ModeButton({
  active, onClick, icon, label, hint,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  hint: string;
}) {
  return (
    <button
      onClick={onClick}
      title={hint}
      className={cn(
        "flex items-center gap-1 px-2 py-0.5 rounded text-[11px] transition-all border",
        active
          ? "bg-primary text-primary-foreground border-primary"
          : "bg-transparent text-muted-foreground border-transparent hover:bg-muted",
      )}
    >
      {icon} {label}
    </button>
  );
}
