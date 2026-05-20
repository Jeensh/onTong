/**
 * Workbench state (V7 IA, D plan).
 *
 * V6/V7 prototype mock 의 잔재 (top tabs, GraphFilters path-trace state, mock leftTab) 정리됨.
 * 실제 사용 중인 것만 유지.
 */
import { create } from "zustand";

export type LeftTab = "code" | "ontology" | "queue";
export type MainMode = "detail" | "split" | "authoring";
export type GraphViewMode = "neighborhood" | "path" | "cluster";

// 새 그래프 IA — 일상 진입은 Coverage, 변경 후 ripple 분석은 Impact, 옛 신경망 뷰는 explore 로 남김
export type GraphTopMode = "coverage" | "impact" | "explore";
export type CoverageLens = "draft" | "orphan" | "recent";
export type ImpactFocusKind = "action" | "term" | "code_type" | "code_method";
export type ImpactDirection = "forward" | "backward" | "both";

interface WorkbenchStore {
  // panels
  leftTab: LeftTab;
  mainMode: MainMode;
  graphModeActive: boolean;
  rightWidth: number;
  cmdkOpen: boolean;
  cmdkInitialQuery: string;   // 팔레트 열릴 때 미리 채울 쿼리 (좌측 검색 → ⌘K 이어받기)

  setLeftTab: (t: LeftTab) => void;
  setMainMode: (m: MainMode) => void;
  setGraphMode: (on: boolean) => void;
  setRightWidth: (px: number) => void;
  toggleCmdK: (open?: boolean, initialQuery?: string) => void;

  // Graph state (R4-T2.3 — URL sync 가능하도록 store 로 lift)
  graphMode: GraphViewMode;
  graphFocus: string | null;
  graphTarget: string | null;
  graphNMax: number;
  activePerspectiveId: number | null;
  setGraphViewMode: (m: GraphViewMode) => void;
  setGraphFocus: (fqn: string | null) => void;
  setGraphTarget: (fqn: string | null) => void;
  setGraphNMax: (n: number) => void;
  setActivePerspectiveId: (id: number | null) => void;
  /** Perspective spec 한 번에 적용 (Saved fetch 후) */
  applyGraphState: (s: Partial<{
    mode: GraphViewMode; focus: string | null; target: string | null; nMax: number;
  }>) => void;

  // 새 그래프 IA — top-level mode + Coverage lens + Impact knob
  graphTopMode: GraphTopMode;
  coverageLenses: CoverageLens[];               // multi-select toggle (draft/orphan/recent)
  coverageRecentDays: number;                   // recent lens 기준 (default 7)
  coverageExpandedDomain: string | null;        // cell click → 패널 펼침
  impactFocusFqn: string | null;
  impactFocusKind: ImpactFocusKind;
  impactHops: number;
  impactDirection: ImpactDirection;
  impactMinStrength: number;                    // 0.5 default
  impactIncludeMethods: boolean;                // method 노드 lazy expand 결과 누적
  impactExpandedTypes: string[];                // 클래스 → method expand 한 fqn 들
  setGraphTopMode: (m: GraphTopMode) => void;
  setCoverageLenses: (l: CoverageLens[]) => void;
  toggleCoverageLens: (l: CoverageLens) => void;
  setCoverageRecentDays: (n: number) => void;
  setCoverageExpandedDomain: (d: string | null) => void;
  jumpToImpact: (fqn: string, kind: ImpactFocusKind) => void;
  setImpactHops: (n: number) => void;
  setImpactDirection: (d: ImpactDirection) => void;
  setImpactMinStrength: (n: number) => void;
  setImpactIncludeMethods: (on: boolean) => void;
  toggleImpactExpandedType: (fqn: string) => void;
  resetImpact: () => void;

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

  // queue refresh ping — Authoring confirm 같은 외부 mutation 후 QueueTab 이 reload 하도록 신호
  queueRefreshTick: number;
  bumpQueueRefresh: () => void;

  // 큐 row 클릭 시 RightPanel preview 표시용. {kind, id} — id 는 term/action fqn 또는 realization id
  selectedQueueItem: { kind: "term" | "action" | "realization"; id: string } | null;
  setSelectedQueueItem: (q: { kind: "term" | "action" | "realization"; id: string } | null) => void;
}

export const useWorkbench = create<WorkbenchStore>((set) => ({
  leftTab: "code",
  mainMode: "detail",
  graphModeActive: false,
  rightWidth: 380,
  cmdkOpen: false,
  cmdkInitialQuery: "",

  setLeftTab: (t) => set({ leftTab: t }),
  setMainMode: (m) => set({ mainMode: m }),
  setGraphMode: (on) => set({ graphModeActive: on }),
  setRightWidth: (px) => set({ rightWidth: Math.max(250, Math.min(700, px)) }),
  toggleCmdK: (open, initialQuery) =>
    set((s) => ({
      cmdkOpen: open === undefined ? !s.cmdkOpen : open,
      cmdkInitialQuery: initialQuery ?? "",
    })),

  graphMode: "neighborhood",
  graphFocus: null,
  graphTarget: null,
  graphNMax: 60,
  activePerspectiveId: null,
  setGraphViewMode: (m) => set({ graphMode: m }),
  setGraphFocus: (fqn) => set({ graphFocus: fqn }),
  setGraphTarget: (fqn) => set({ graphTarget: fqn }),
  setGraphNMax: (n) => set({ graphNMax: n }),
  setActivePerspectiveId: (id) => set({ activePerspectiveId: id }),
  applyGraphState: (patch) => set((s) => ({
    graphMode: patch.mode ?? s.graphMode,
    graphFocus: patch.focus !== undefined ? patch.focus : s.graphFocus,
    graphTarget: patch.target !== undefined ? patch.target : s.graphTarget,
    graphNMax: patch.nMax ?? s.graphNMax,
  })),

  // 새 IA: Coverage 가 daily entry point — 기본 lens = draft+orphan
  graphTopMode: "coverage",
  coverageLenses: ["draft", "orphan"],
  coverageRecentDays: 7,
  coverageExpandedDomain: null,
  impactFocusFqn: null,
  impactFocusKind: "action",
  impactHops: 2,
  impactDirection: "both",
  impactMinStrength: 0.5,
  impactIncludeMethods: false,
  impactExpandedTypes: [],
  setGraphTopMode: (m) => set({ graphTopMode: m }),
  setCoverageLenses: (l) => set({ coverageLenses: l }),
  toggleCoverageLens: (l) => set((s) => ({
    coverageLenses: s.coverageLenses.includes(l)
      ? s.coverageLenses.filter((x) => x !== l)
      : [...s.coverageLenses, l],
  })),
  setCoverageRecentDays: (n) => set({ coverageRecentDays: Math.max(1, Math.min(90, n)) }),
  setCoverageExpandedDomain: (d) => set({ coverageExpandedDomain: d }),
  jumpToImpact: (fqn, kind) => set({
    graphTopMode: "impact",
    impactFocusFqn: fqn,
    impactFocusKind: kind,
    impactExpandedTypes: [],
  }),
  setImpactHops: (n) => set({ impactHops: Math.max(1, Math.min(5, n)) }),
  setImpactDirection: (d) => set({ impactDirection: d }),
  setImpactMinStrength: (n) => set({ impactMinStrength: Math.max(0, Math.min(1, n)) }),
  setImpactIncludeMethods: (on) => set({ impactIncludeMethods: on }),
  toggleImpactExpandedType: (fqn) => set((s) => ({
    impactExpandedTypes: s.impactExpandedTypes.includes(fqn)
      ? s.impactExpandedTypes.filter((x) => x !== fqn)
      : [...s.impactExpandedTypes, fqn],
  })),
  resetImpact: () => set({
    impactFocusFqn: null,
    impactExpandedTypes: [],
  }),

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

  // 기본 repo — Phase 6 시드 반영 (slab-design-real-v2). Import 모달이 done 시 setRepoId 로 갱신.
  activeRepoId: "slab-design-real-v2",
  setRepoId: (id) => set({ activeRepoId: id }),

  queueRefreshTick: 0,
  bumpQueueRefresh: () => set((s) => ({ queueRefreshTick: s.queueRefreshTick + 1 })),

  selectedQueueItem: null,
  setSelectedQueueItem: (q) => set({ selectedQueueItem: q }),
}));
