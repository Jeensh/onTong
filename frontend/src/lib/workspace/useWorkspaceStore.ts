import { create } from "zustand";
import type { Tab, FileType, VirtualTabType, SectionId } from "@/types";

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
  newContent?: string;       // proposed new content (for pre-approval diff)
  actionId?: string;         // pending action ID for approval API
  sessionId?: string;        // session ID for approval API
}

export interface AgentWrite {
  filePath: string;
  content: string;           // proposed content for new file
  actionId: string;          // pending action ID for approval API
  sessionId: string;         // session ID for approval API
}

const VIRTUAL_TAB_TITLES: Record<VirtualTabType, string> = {
  "metadata-templates": "메타데이터 템플릿 관리",
  "untagged-dashboard": "미태깅 문서 대시보드",
  "conflict-dashboard": "관련 문서 관리",
  "document-compare": "문서 비교",
  "document-graph": "문서 관계 그래프",
  "permission-editor": "접근 권한 관리",
  "scoring-dashboard": "신뢰도 설정",
  "maintenance-digest": "관리가 필요한 문서",
  "image-management": "이미지 관리",
};

interface WorkspaceState {
  activeSection: SectionId;
  tabs: Tab[];
  activeTabId: string | null;
  treeVersion: number;
  agentDiff: AgentDiff | null;
  agentWrite: AgentWrite | null;
  graphCenterPath: string | null;
  resolvedConflicts: Set<string>;
  /** Unsaved editor content keyed by filePath — survives tab switches */
  drafts: Record<string, string>;
  /** Cursor + scroll position keyed by filePath — restored on tab switch */
  viewStates: Record<string, { cursorPos: number; scrollTop: number }>;
  setActiveSection: (section: SectionId) => void;
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
  setAgentWrite: (write: AgentWrite) => void;
  clearAgentWrite: () => void;
  addResolvedConflict: (pairKey: string) => void;
  setDraft: (filePath: string, markdown: string) => void;
  clearDraft: (filePath: string) => void;
  setViewState: (filePath: string, state: { cursorPos: number; scrollTop: number }) => void;
  clearViewState: (filePath: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  activeSection: "wiki" as SectionId,
  tabs: [],
  activeTabId: null,
  treeVersion: 0,
  agentDiff: null,
  agentWrite: null,
  graphCenterPath: null,
  resolvedConflicts: new Set<string>(),
  drafts: {},
  viewStates: {},

  setActiveSection: (section: SectionId) => {
    set({ activeSection: section });
  },

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
    const { tabs, activeTabId, drafts } = get();
    const idx = tabs.findIndex((t) => t.id === tabId);
    if (idx === -1) return;

    // Clear draft and view state for the closed tab's file
    const closedTab = tabs[idx];
    const newDrafts = { ...drafts };
    delete newDrafts[closedTab.filePath];
    const newViewStates = { ...get().viewStates };
    delete newViewStates[closedTab.filePath];

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

    set({ tabs: newTabs, activeTabId: newActiveId, drafts: newDrafts, viewStates: newViewStates });
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

  setAgentWrite: (write: AgentWrite) => {
    set({ agentWrite: write });
  },

  clearAgentWrite: () => {
    set({ agentWrite: null });
  },

  addResolvedConflict: (pairKey: string) => {
    set((state) => {
      const next = new Set(state.resolvedConflicts);
      next.add(pairKey);
      return { resolvedConflicts: next };
    });
  },

  setDraft: (filePath: string, markdown: string) => {
    set((state) => ({ drafts: { ...state.drafts, [filePath]: markdown } }));
  },

  clearDraft: (filePath: string) => {
    set((state) => {
      const next = { ...state.drafts };
      delete next[filePath];
      return { drafts: next };
    });
  },

  setViewState: (filePath: string, state: { cursorPos: number; scrollTop: number }) => {
    set((s) => ({ viewStates: { ...s.viewStates, [filePath]: state } }));
  },

  clearViewState: (filePath: string) => {
    set((s) => {
      const next = { ...s.viewStates };
      delete next[filePath];
      return { viewStates: next };
    });
  },
}));
