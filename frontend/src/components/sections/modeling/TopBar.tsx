"use client";

import { useState } from "react";
import { Search, Network, FolderInput, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkbench } from "./store";
import { RepoImportModal } from "./RepoImportModal";

/**
 * TopBar (V7 IA, D plan) — 항상 어디 있는지 보이는 breadcrumb 노출.
 * `repo / view / selection` 패턴.
 */
export function TopBar() {
  const {
    activeRepoId, setGraphMode, toggleCmdK,
    graphModeActive, selectedActionFqn, selectedCodeTypeFqn, selectedTermFqn,
  } = useWorkbench();
  const [importOpen, setImportOpen] = useState(false);

  const view = graphModeActive ? "Graph" : "Detail";
  const selection =
    selectedActionFqn?.split(".").pop() ||
    selectedTermFqn?.split(".").pop() ||
    selectedCodeTypeFqn?.split(".").pop() ||
    null;

  return (
    <header
      className="flex items-center gap-2 px-3 bg-card border-b border-border"
      style={{ gridArea: "top" }}
    >
      <span className="font-bold tracking-tight select-none text-sm shrink-0">
        <span className="text-primary">on</span>Tong
      </span>

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-[11px] text-muted-foreground min-w-0 flex-1 overflow-hidden">
        <Crumb label={activeRepoId} primary />
        <ChevronRight className="w-3 h-3 shrink-0" />
        <Crumb label={view} />
        {selection && (
          <>
            <ChevronRight className="w-3 h-3 shrink-0" />
            <Crumb label={selection} mono />
          </>
        )}
      </nav>

      <button
        onClick={() => toggleCmdK(true)}
        className="flex items-center gap-2 px-2.5 py-1 text-xs text-muted-foreground bg-muted rounded border border-border min-w-[180px] hover:text-foreground hover:bg-muted/70 shrink-0"
      >
        <Search className="w-3 h-3" />
        검색 / 명령
        <kbd className="ml-auto text-[10px] px-1 py-0 bg-background rounded border border-border">⌘K</kbd>
      </button>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setImportOpen(true)}
        className="gap-1.5 shrink-0"
        title="Java repo 분석 + 자동 매핑 추천"
      >
        <FolderInput className="w-3.5 h-3.5" /> Import
      </Button>
      <Button
        variant={graphModeActive ? "default" : "outline"}
        size="sm"
        onClick={() => setGraphMode(!graphModeActive)}
        className="gap-1.5 shrink-0"
      >
        <Network className="w-3.5 h-3.5" /> 그래프
      </Button>

      <RepoImportModal open={importOpen} onOpenChange={setImportOpen} />
    </header>
  );
}

function Crumb({
  label, primary, mono,
}: { label: string; primary?: boolean; mono?: boolean }) {
  return (
    <span
      className={
        (primary ? "text-foreground font-semibold " : "") +
        (mono ? "font-mono text-[10.5px] " : "") +
        "truncate min-w-0"
      }
      title={label}
    >
      {label}
    </span>
  );
}
