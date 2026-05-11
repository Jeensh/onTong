/**
 * Workbench state (V7 IA, D plan).
 *
 * V6/V7 prototype mock 의 잔재 (top tabs, GraphFilters path-trace state, mock leftTab) 정리됨.
 * 실제 사용 중인 것만 유지.
 */
import { create } from "zustand";

export type LeftTab = "code" | "ontology" | "queue";
export type MainMode = "detail" | "split" | "authoring";
export type Direction = "fwd" | "bwd";
export type Lens = "verify" | "domain" | "confidence" | "simulation" | "none";
export type GraphViewMode = "neighborhood" | "path" | "cluster";

/**
 * Code Peek modal target — drives a single global CodePeekModal mounted in MainPanel.
 *
 * Use `openPeek()` from any FqnLink (or other code-pointing affordance) so the user
 * can browse a class / method body without losing the current Detail selection.
 */
export interface PeekTarget {
  kind: "code_type" | "code_method";
  fqn: string;
  repoId: string;
  highlightLine?: number;
}

interface WorkbenchStore {
  // panels
  leftTab: LeftTab;
  mainMode: MainMode;
  direction: Direction;
  graphModeActive: boolean;
  rightWidth: number;
  cmdkOpen: boolean;

  setLeftTab: (t: LeftTab) => void;
  setMainMode: (m: MainMode) => void;
  setDirection: (d: Direction) => void;
  setGraphMode: (on: boolean) => void;
  setRightWidth: (px: number) => void;
  toggleCmdK: (open?: boolean) => void;

  // 보고용 lens (verify lens 가 default; 다른 것은 다음 phase)
  lens: Lens;
  setLens: (l: Lens) => void;

  // Graph state (R4-T2.3 — URL sync 가능하도록 store 로 lift)
  graphMode: GraphViewMode;
  graphFocus: string | null;
  graphTarget: string | null;
  graphNMax: number;
  graphCompound: boolean;          // R4-T3.3 — Domain 노드 안에 CodeType nest
  activePerspectiveId: number | null;
  setGraphViewMode: (m: GraphViewMode) => void;
  setGraphFocus: (fqn: string | null) => void;
  setGraphTarget: (fqn: string | null) => void;
  setGraphNMax: (n: number) => void;
  setGraphCompound: (on: boolean) => void;
  setActivePerspectiveId: (id: number | null) => void;
  /** Perspective spec 한 번에 적용 (Saved fetch 후) */
  applyGraphState: (s: Partial<{
    mode: GraphViewMode; focus: string | null; target: string | null; nMax: number;
  }>) => void;

  // selection
  selectedActionFqn: string | null;
  selectedCodeTypeFqn: string | null;
  selectedTermFqn: string | null;
  selectedRuleFqn: string | null;
  selectedAnchorId: string | null;
  setSelectedAction: (fqn: string | null) => void;
  setSelectedCodeType: (fqn: string | null) => void;
  setSelectedTerm: (fqn: string | null) => void;
  setSelectedRule: (fqn: string | null) => void;
  setSelectedAnchor: (id: string | null) => void;
  /** 단일 entity 만 활성 — 새 selection 시 다른 4개를 null 로. */
  selectOnly: (kind: "action" | "codeType" | "term" | "rule" | "anchor", id: string | null) => void;

  // repo
  activeRepoId: string;
  setRepoId: (id: string) => void;

  // Code peek — global modal driver. null = closed.
  peekTarget: PeekTarget | null;
  openPeek: (target: PeekTarget) => void;
  closePeek: () => void;
}

export const useWorkbench = create<WorkbenchStore>((set) => ({
  leftTab: "code",
  mainMode: "detail",
  direction: "fwd",
  graphModeActive: false,
  rightWidth: 380,
  cmdkOpen: false,

  setLeftTab: (t) => set({ leftTab: t }),
  setMainMode: (m) => set({ mainMode: m }),
  setDirection: (d) => set({ direction: d }),
  setGraphMode: (on) => set({ graphModeActive: on }),
  setRightWidth: (px) => set({ rightWidth: Math.max(250, Math.min(700, px)) }),
  toggleCmdK: (open) =>
    set((s) => ({ cmdkOpen: open === undefined ? !s.cmdkOpen : open })),

  lens: "verify",
  setLens: (l) => set({ lens: l }),

  graphMode: "neighborhood",
  graphFocus: null,
  graphTarget: null,
  graphNMax: 60,
  graphCompound: false,         // 1차 default off — 사용자 토글
  activePerspectiveId: null,
  setGraphViewMode: (m) => set({ graphMode: m }),
  setGraphFocus: (fqn) => set({ graphFocus: fqn }),
  setGraphTarget: (fqn) => set({ graphTarget: fqn }),
  setGraphNMax: (n) => set({ graphNMax: n }),
  setGraphCompound: (on) => set({ graphCompound: on }),
  setActivePerspectiveId: (id) => set({ activePerspectiveId: id }),
  applyGraphState: (patch) => set((s) => ({
    graphMode: patch.mode ?? s.graphMode,
    graphFocus: patch.focus !== undefined ? patch.focus : s.graphFocus,
    graphTarget: patch.target !== undefined ? patch.target : s.graphTarget,
    graphNMax: patch.nMax ?? s.graphNMax,
  })),

  // 첫 진입 시 어떤 노드도 선택 안 됨 — 사용자가 트리/검색 으로 고름
  selectedActionFqn: null,
  selectedCodeTypeFqn: null,
  selectedTermFqn: null,
  selectedRuleFqn: null,
  selectedAnchorId: null,
  setSelectedAction: (fqn) => set({
    selectedActionFqn: fqn,
    selectedCodeTypeFqn: null, selectedTermFqn: null, selectedRuleFqn: null, selectedAnchorId: null,
  }),
  setSelectedCodeType: (fqn) => set({
    selectedCodeTypeFqn: fqn,
    selectedActionFqn: null, selectedTermFqn: null, selectedRuleFqn: null, selectedAnchorId: null,
  }),
  setSelectedTerm: (fqn) => set({
    selectedTermFqn: fqn,
    selectedActionFqn: null, selectedCodeTypeFqn: null, selectedRuleFqn: null, selectedAnchorId: null,
  }),
  setSelectedRule: (fqn) => set({
    selectedRuleFqn: fqn,
    selectedActionFqn: null, selectedCodeTypeFqn: null, selectedTermFqn: null, selectedAnchorId: null,
  }),
  setSelectedAnchor: (id) => set({
    selectedAnchorId: id,
    selectedActionFqn: null, selectedCodeTypeFqn: null, selectedTermFqn: null, selectedRuleFqn: null,
  }),
  selectOnly: (kind, id) => set({
    selectedActionFqn:   kind === "action"   ? id : null,
    selectedCodeTypeFqn: kind === "codeType" ? id : null,
    selectedTermFqn:     kind === "term"     ? id : null,
    selectedRuleFqn:     kind === "rule"     ? id : null,
    selectedAnchorId:    kind === "anchor"   ? id : null,
  }),

  // 기본 repo — Phase 3 데모 정합. Import 모달이 done 시 setRepoId 로 갱신.
  activeRepoId: "slab-design-real",
  setRepoId: (id) => set({ activeRepoId: id }),

  // Code peek — null = closed. selection state intentionally untouched on open.
  peekTarget: null,
  openPeek: (target) => set({ peekTarget: target }),
  closePeek: () => set({ peekTarget: null }),
}));
