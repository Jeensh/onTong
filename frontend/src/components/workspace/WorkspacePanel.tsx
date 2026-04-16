"use client";

import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { TabBar } from "./TabBar";
import { FileRouter } from "./FileRouter";
import { Search, BookOpen } from "lucide-react";

function EmptyState() {
  const toggle = useSearchStore((s) => s.toggle);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-sm px-6">
        <div className="w-14 h-14 mx-auto mb-5 rounded-2xl bg-primary/10 flex items-center justify-center">
          <BookOpen className="w-7 h-7 text-primary" />
        </div>
        <h2 className="text-lg font-semibold text-foreground mb-1">
          시작하기
        </h2>
        <p className="text-sm text-muted-foreground mb-6">
          문서를 검색하거나 트리에서 선택하세요
        </p>
        <button
          onClick={toggle}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-border bg-card hover:bg-accent hover:border-primary/20 transition-colors group"
        >
          <Search className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
          <span className="text-sm font-medium text-foreground">문서 검색</span>
          <kbd className="ml-1 text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">⌘K</kbd>
        </button>
      </div>
    </div>
  );
}

export function WorkspacePanel() {
  const { tabs, activeTabId } = useWorkspaceStore();
  const activeTab = tabs.find((t) => t.id === activeTabId);

  return (
    <div className="flex flex-col h-full">
      <TabBar />
      <div className="flex-1 overflow-auto">
        {activeTab ? (
          <FileRouter
            key={activeTab.id}
            filePath={activeTab.filePath}
            fileType={activeTab.fileType as import("@/types").TabType}
            tabId={activeTab.id}
          />
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}
