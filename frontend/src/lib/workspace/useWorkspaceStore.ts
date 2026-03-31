import { create } from "zustand";
import type { Tab, FileType, VirtualTabType } from "@/types";

function getFileType(filePath: string): FileType {
  const ext = filePath.split(".").pop()?.toLowerCase() ?? "";
  switch (ext) {
    case "md":
      return "markdown";
    case "xlsx":
    case "xls":
    case "csv":
      return "spreadsheet";
    case "pptx":
    case "ppt":
      return "presentation";
    case "pdf":
      return "pdf";
    case "png":
    case "jpg":
    case "jpeg":
    case "gif":
    case "svg":
    case "webp":
      return "image";
    default:
      return "unknown";
  }
}

function getTitle(filePath: string): string {
  return filePath.split("/").pop() ?? filePath;
}

export interface AgentDiff {
  filePath: string;
  oldContent: string;
}

const VIRTUAL_TAB_TITLES: Record<VirtualTabType, string> = {
  "metadata-templates": "메타데이터 템플릿 관리",
  "untagged-dashboard": "미태깅 문서 대시보드",
  "conflict-dashboard": "문서 충돌 감지",
  "document-compare": "문서 비교",
  "document-graph": "문서 관계 그래프",
  "permission-editor": "접근 권한 관리",
};

interface WorkspaceState {
  tabs: Tab[];
  activeTabId: string | null;
  treeVersion: number;
  agentDiff: AgentDiff | null;
  graphCenterPath: string | null;
  openTab: (filePath: string) => void;
  openVirtualTab: (tabType: VirtualTabType) => void;
  openGraphTab: (centerPath: string) => void;
  openCompareTab: (pathA: string, pathB: string) => void;
  closeTab: (tabId: string) => void;
  setActiveTab: (tabId: string) => void;
  reorderTabs: (fromIndex: number, toIndex: number) => void;
  setDirty: (tabId: string, isDirty: boolean) => void;
  updateTabPath: (tabId: string, newFilePath: string) => void;
  refreshTree: () => void;
  setAgentDiff: (diff: AgentDiff) => void;
  clearAgentDiff: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  tabs: [],
  activeTabId: null,
  treeVersion: 0,
  agentDiff: null,
  graphCenterPath: null,

  openTab: (filePath: string) => {
    const { tabs } = get();
    const existing = tabs.find((t) => t.filePath === filePath);
    if (existing) {
      set({ activeTabId: existing.id });
      return;
    }
    const newTab: Tab = {
      id: `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      filePath,
      fileType: getFileType(filePath),
      title: getTitle(filePath),
      isDirty: false,
    };
    set({ tabs: [...tabs, newTab], activeTabId: newTab.id });
  },

  openVirtualTab: (tabType: VirtualTabType) => {
    const { tabs } = get();
    // Virtual tabs use tabType as filePath identifier (singleton)
    const existing = tabs.find((t) => t.filePath === `__${tabType}__`);
    if (existing) {
      set({ activeTabId: existing.id });
      return;
    }
    const newTab: Tab = {
      id: `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      filePath: `__${tabType}__`,
      fileType: tabType,
      title: VIRTUAL_TAB_TITLES[tabType] ?? tabType,
      isDirty: false,
    };
    set({ tabs: [...tabs, newTab], activeTabId: newTab.id });
  },

  openGraphTab: (centerPath: string) => {
    const { tabs } = get();
    set({ graphCenterPath: centerPath });
    const existing = tabs.find((t) => t.filePath === "__document-graph__");
    if (existing) {
      set({ activeTabId: existing.id });
      return;
    }
    const newTab: Tab = {
      id: `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      filePath: "__document-graph__",
      fileType: "document-graph" as VirtualTabType,
      title: VIRTUAL_TAB_TITLES["document-graph"],
      isDirty: false,
    };
    set({ tabs: [...tabs, newTab], activeTabId: newTab.id });
  },

  openCompareTab: (pathA: string, pathB: string) => {
    const { tabs } = get();
    const compareId = `__compare__${pathA}__${pathB}__`;
    const existing = tabs.find((t) => t.filePath === compareId);
    if (existing) {
      set({ activeTabId: existing.id });
      return;
    }
    const nameA = pathA.split("/").pop() ?? pathA;
    const nameB = pathB.split("/").pop() ?? pathB;
    const newTab: Tab = {
      id: `tab-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      filePath: compareId,
      fileType: "document-compare" as VirtualTabType,
      title: `비교: ${nameA} ↔ ${nameB}`,
      isDirty: false,
    };
    set({ tabs: [...tabs, newTab], activeTabId: newTab.id });
  },

  closeTab: (tabId: string) => {
    const { tabs, activeTabId } = get();
    const idx = tabs.findIndex((t) => t.id === tabId);
    if (idx === -1) return;

    const newTabs = tabs.filter((t) => t.id !== tabId);

    let newActiveId: string | null = activeTabId;
    if (activeTabId === tabId) {
      if (newTabs.length === 0) {
        newActiveId = null;
      } else if (idx < newTabs.length) {
        newActiveId = newTabs[idx].id;
      } else {
        newActiveId = newTabs[newTabs.length - 1].id;
      }
    }

    set({ tabs: newTabs, activeTabId: newActiveId });
  },

  setActiveTab: (tabId: string) => {
    set({ activeTabId: tabId });
  },

  reorderTabs: (fromIndex: number, toIndex: number) => {
    const { tabs } = get();
    const newTabs = [...tabs];
    const [moved] = newTabs.splice(fromIndex, 1);
    newTabs.splice(toIndex, 0, moved);
    set({ tabs: newTabs });
  },

  setDirty: (tabId: string, isDirty: boolean) => {
    set((state) => ({
      tabs: state.tabs.map((t) =>
        t.id === tabId ? { ...t, isDirty } : t
      ),
    }));
  },

  updateTabPath: (tabId: string, newFilePath: string) => {
    set((state) => ({
      tabs: state.tabs.map((t) =>
        t.id === tabId
          ? { ...t, filePath: newFilePath, title: getTitle(newFilePath), fileType: getFileType(newFilePath) }
          : t
      ),
    }));
  },

  refreshTree: () => {
    set((state) => ({ treeVersion: state.treeVersion + 1 }));
  },

  setAgentDiff: (diff: AgentDiff) => {
    set({ agentDiff: diff });
  },

  clearAgentDiff: () => {
    set({ agentDiff: null });
  },
}));
