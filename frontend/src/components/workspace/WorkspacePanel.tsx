"use client";

import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { TabBar } from "./TabBar";
import { FileRouter } from "./FileRouter";

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
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <p className="text-lg font-medium">파일을 선택하세요</p>
              <p className="text-sm mt-1">
                좌측 트리에서 파일을 클릭하면 여기에 표시됩니다
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
