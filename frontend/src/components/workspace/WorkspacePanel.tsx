"use client";

import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { useSearchStore } from "@/lib/search/useSearchStore";
import { TabBar } from "./TabBar";
import { FileRouter } from "./FileRouter";
import { FileText, Search, MessageSquare, BookOpen } from "lucide-react";

function EmptyState() {
  const toggle = useSearchStore((s) => s.toggle);

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center max-w-md px-6">
        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-primary/10 flex items-center justify-center">
          <BookOpen className="w-8 h-8 text-primary" />
        </div>
        <h2 className="text-xl font-semibold text-foreground mb-2">
          시작하기
        </h2>
        <p className="text-sm text-muted-foreground mb-8">
          좌측 트리에서 파일을 선택하거나, 아래 방법으로 시작하세요
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={toggle}
            className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border bg-card hover:bg-accent hover:border-primary/20 transition-all group"
          >
            <Search className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
            <span className="text-sm font-medium text-foreground">문서 검색</span>
            <span className="text-xs text-muted-foreground">Ctrl+K</span>
          </button>
          <button
            onClick={() => {
              const ev = new KeyboardEvent("keydown", { key: "b", metaKey: true });
              document.dispatchEvent(ev);
            }}
            className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border bg-card hover:bg-accent hover:border-primary/20 transition-all group"
          >
            <FileText className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
            <span className="text-sm font-medium text-foreground">파일 탐색</span>
            <span className="text-xs text-muted-foreground">Ctrl+B</span>
          </button>
          <button
            onClick={() => {
              const ev = new KeyboardEvent("keydown", { key: "j", metaKey: true });
              document.dispatchEvent(ev);
            }}
            className="flex flex-col items-center gap-2 p-4 rounded-lg border border-border bg-card hover:bg-accent hover:border-primary/20 transition-all group"
          >
            <MessageSquare className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
            <span className="text-sm font-medium text-foreground">AI에게 질문</span>
            <span className="text-xs text-muted-foreground">Ctrl+J</span>
          </button>
        </div>
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
