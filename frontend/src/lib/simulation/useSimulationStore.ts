// Section 3 Slab Simulation — Zustand state store
import { create } from "zustand";
import type {
  ScenarioType,
  SlabState,
  GraphState,
  ChatMessage,
  ThinkingStep,
  ToolCall,
  OntologyGraphData,
  Order,
  SlabSizeParams,
  CustomAgent,
  ActiveView,
} from "./types";

interface SimulationStore {
  // ── Active view (사이드바 선택 상태) ──────────────────────────────────
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;

  // ── Scenario selection (기존 — ChatPanel 등 하위 호환) ───────────────
  activeScenario: ScenarioType;
  setActiveScenario: (s: ScenarioType) => void;

  // ── Chat messages (빌트인 시나리오 A/B/C) ───────────────────────────
  messages: ChatMessage[];
  addUserMessage: (content: string) => void;
  startAssistantMessage: () => string;
  appendContent: (id: string, delta: string) => void;
  addThinkingStep: (id: string, step: ThinkingStep) => void;
  addToolCall: (id: string, call: ToolCall) => void;
  finalizeMessage: (id: string) => void;
  clearMessages: () => void;

  // ── 3D Slab state ────────────────────────────────────────────────────
  slabs: SlabState[];
  setSlabs: (slabs: SlabState[]) => void;

  // ── Ontology graph ───────────────────────────────────────────────────
  graphData: OntologyGraphData | null;
  setGraphData: (data: OntologyGraphData) => void;
  graphHighlight: GraphState;
  setGraphHighlight: (state: GraphState) => void;

  // ── Orders ───────────────────────────────────────────────────────────
  orders: Order[];
  setOrders: (orders: Order[]) => void;

  // ── Agent running state (빌트인) ─────────────────────────────────────
  isRunning: boolean;
  setIsRunning: (v: boolean) => void;
  abortController: AbortController | null;
  setAbortController: (ac: AbortController | null) => void;
  stopAgent: () => void;

  // ── Last agent result (딥링크 버튼용) ────────────────────────────────
  lastAgentResult: Record<string, unknown> | null;
  setLastAgentResult: (r: Record<string, unknown> | null) => void;

  // ── Pending slab params (SlabSizeSimulator 딥링크) ───────────────────
  pendingSlabParams: SlabSizeParams | null;
  setPendingSlabParams: (p: SlabSizeParams | null) => void;

  // ── Custom Agent ─────────────────────────────────────────────────────
  customAgents: CustomAgent[];
  setCustomAgents: (agents: CustomAgent[]) => void;
  addCustomAgent: (agent: CustomAgent) => void;
  deleteCustomAgent: (id: string) => void;

  // 채팅 빌더 전용 메시지
  builderMessages: ChatMessage[];
  addBuilderUserMessage: (content: string) => void;
  startBuilderAssistantMessage: () => string;
  appendBuilderContent: (id: string, delta: string) => void;
  addBuilderThinkingStep: (id: string, step: ThinkingStep) => void;
  finalizeBuilderMessage: (id: string) => void;
  clearBuilderMessages: () => void;
  builderRunning: boolean;
  setBuilderRunning: (v: boolean) => void;
  builderAbortController: AbortController | null;
  setBuilderAbortController: (ac: AbortController | null) => void;
  stopBuilder: () => void;

  // agent_ready 이벤트로 수신된 에이전트 정의 (등록 대기)
  pendingAgentDef: Omit<CustomAgent, "id" | "created_at"> | null;
  setPendingAgentDef: (def: Omit<CustomAgent, "id" | "created_at"> | null) => void;

  // 커스텀 에이전트별 대화 기록
  customAgentMessages: Record<string, ChatMessage[]>;
  addCustomAgentUserMessage: (agentId: string, content: string) => void;
  startCustomAgentAssistantMessage: (agentId: string) => string;
  appendCustomAgentContent: (agentId: string, id: string, delta: string) => void;
  addCustomAgentThinkingStep: (agentId: string, id: string, step: ThinkingStep) => void;
  addCustomAgentToolCall: (agentId: string, id: string, call: ToolCall) => void;
  finalizeCustomAgentMessage: (agentId: string, id: string) => void;

  // 커스텀 에이전트 실행 상태
  customAgentRunning: Record<string, boolean>;
  setCustomAgentRunning: (agentId: string, v: boolean) => void;
  customAgentAbortControllers: Record<string, AbortController>;
  setCustomAgentAbortController: (agentId: string, ac: AbortController | null) => void;
  stopCustomAgent: (agentId: string) => void;
}

let msgCounter = 0;
const genId = () => `msg-${++msgCounter}-${Date.now()}`;

export const useSimulationStore = create<SimulationStore>((set, get) => ({
  // ── Active view ───────────────────────────────────────────────────────
  activeView: { kind: "scenario", id: "A" },
  setActiveView: (view) => {
    const updates: Partial<SimulationStore> = { activeView: view };
    if (view.kind === "scenario") {
      updates.activeScenario = view.id;
      updates.messages = [];
      updates.slabs = [];
      updates.graphHighlight = { traversal: [], highlighted_edges: [] };
      updates.lastAgentResult = null;
    }
    set(updates);
  },

  // ── activeScenario (기존 하위 호환) ───────────────────────────────────
  activeScenario: "A",
  setActiveScenario: (s) =>
    set({
      activeScenario: s,
      activeView: { kind: "scenario", id: s },
      messages: [],
      slabs: [],
      graphHighlight: { traversal: [], highlighted_edges: [] },
      lastAgentResult: null,
    }),

  // ── Messages ──────────────────────────────────────────────────────────
  messages: [],
  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { id: genId(), role: "user", content, timestamp: Date.now() },
      ],
    })),

  startAssistantMessage: () => {
    const id = genId();
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id,
          role: "assistant",
          content: "",
          thinking_steps: [],
          tool_calls: [],
          timestamp: Date.now(),
          isStreaming: true,
        },
      ],
    }));
    return id;
  },

  appendContent: (id, delta) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + delta } : m
      ),
    })),

  addThinkingStep: (id, step) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id
          ? { ...m, thinking_steps: [...(m.thinking_steps ?? []), step] }
          : m
      ),
    })),

  addToolCall: (id, call) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id
          ? { ...m, tool_calls: [...(m.tool_calls ?? []), call] }
          : m
      ),
    })),

  finalizeMessage: (id) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, isStreaming: false } : m
      ),
    })),

  clearMessages: () => set({ messages: [] }),

  // ── Slabs ──────────────────────────────────────────────────────────────
  slabs: [],
  setSlabs: (slabs) => set({ slabs }),

  // ── Graph ─────────────────────────────────────────────────────────────
  graphData: null,
  setGraphData: (data) => set({ graphData: data }),
  graphHighlight: { traversal: [], highlighted_edges: [] },
  setGraphHighlight: (state) => set({ graphHighlight: state }),

  // ── Orders ───────────────────────────────────────────────────────────
  orders: [],
  setOrders: (orders) => set({ orders }),

  // ── Built-in agent running ────────────────────────────────────────────
  isRunning: false,
  setIsRunning: (v) => set({ isRunning: v }),
  abortController: null,
  setAbortController: (ac) => set({ abortController: ac }),
  stopAgent: () => {
    const { abortController } = get();
    abortController?.abort();
    set({ isRunning: false, abortController: null });
    set((state) => ({
      messages: state.messages.map((m) =>
        m.isStreaming ? { ...m, isStreaming: false } : m
      ),
    }));
  },

  // ── Last result / pending params ──────────────────────────────────────
  lastAgentResult: null,
  setLastAgentResult: (r) => set({ lastAgentResult: r }),
  pendingSlabParams: null,
  setPendingSlabParams: (p) => set({ pendingSlabParams: p }),

  // ── Custom Agents ─────────────────────────────────────────────────────
  customAgents: [],
  setCustomAgents: (agents) => set({ customAgents: agents }),
  addCustomAgent: (agent) =>
    set((state) => ({ customAgents: [...state.customAgents, agent] })),
  deleteCustomAgent: (id) =>
    set((state) => ({
      customAgents: state.customAgents.filter((a) => a.id !== id),
    })),

  // ── Builder messages ──────────────────────────────────────────────────
  builderMessages: [],
  addBuilderUserMessage: (content) =>
    set((state) => ({
      builderMessages: [
        ...state.builderMessages,
        { id: genId(), role: "user", content, timestamp: Date.now() },
      ],
    })),
  startBuilderAssistantMessage: () => {
    const id = genId();
    set((state) => ({
      builderMessages: [
        ...state.builderMessages,
        {
          id,
          role: "assistant",
          content: "",
          thinking_steps: [],
          tool_calls: [],
          timestamp: Date.now(),
          isStreaming: true,
        },
      ],
    }));
    return id;
  },
  appendBuilderContent: (id, delta) =>
    set((state) => ({
      builderMessages: state.builderMessages.map((m) =>
        m.id === id ? { ...m, content: m.content + delta } : m
      ),
    })),
  addBuilderThinkingStep: (id, step) =>
    set((state) => ({
      builderMessages: state.builderMessages.map((m) =>
        m.id === id
          ? { ...m, thinking_steps: [...(m.thinking_steps ?? []), step] }
          : m
      ),
    })),
  finalizeBuilderMessage: (id) =>
    set((state) => ({
      builderMessages: state.builderMessages.map((m) =>
        m.id === id ? { ...m, isStreaming: false } : m
      ),
    })),
  clearBuilderMessages: () => set({ builderMessages: [], pendingAgentDef: null }),
  builderRunning: false,
  setBuilderRunning: (v) => set({ builderRunning: v }),
  builderAbortController: null,
  setBuilderAbortController: (ac) => set({ builderAbortController: ac }),
  stopBuilder: () => {
    const { builderAbortController } = get();
    builderAbortController?.abort();
    set({ builderRunning: false, builderAbortController: null });
    set((state) => ({
      builderMessages: state.builderMessages.map((m) =>
        m.isStreaming ? { ...m, isStreaming: false } : m
      ),
    }));
  },

  // ── Pending agent def (agent_ready 이벤트 수신) ───────────────────────
  pendingAgentDef: null,
  setPendingAgentDef: (def) => set({ pendingAgentDef: def }),

  // ── Custom agent messages ──────────────────────────────────────────────
  customAgentMessages: {},
  addCustomAgentUserMessage: (agentId, content) =>
    set((state) => {
      const msgs = state.customAgentMessages[agentId] ?? [];
      return {
        customAgentMessages: {
          ...state.customAgentMessages,
          [agentId]: [...msgs, { id: genId(), role: "user", content, timestamp: Date.now() }],
        },
      };
    }),
  startCustomAgentAssistantMessage: (agentId) => {
    const id = genId();
    set((state) => {
      const msgs = state.customAgentMessages[agentId] ?? [];
      return {
        customAgentMessages: {
          ...state.customAgentMessages,
          [agentId]: [
            ...msgs,
            { id, role: "assistant", content: "", thinking_steps: [], tool_calls: [], timestamp: Date.now(), isStreaming: true },
          ],
        },
      };
    });
    return id;
  },
  appendCustomAgentContent: (agentId, id, delta) =>
    set((state) => ({
      customAgentMessages: {
        ...state.customAgentMessages,
        [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) =>
          m.id === id ? { ...m, content: m.content + delta } : m
        ),
      },
    })),
  addCustomAgentThinkingStep: (agentId, id, step) =>
    set((state) => ({
      customAgentMessages: {
        ...state.customAgentMessages,
        [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) =>
          m.id === id ? { ...m, thinking_steps: [...(m.thinking_steps ?? []), step] } : m
        ),
      },
    })),
  addCustomAgentToolCall: (agentId, id, call) =>
    set((state) => ({
      customAgentMessages: {
        ...state.customAgentMessages,
        [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) =>
          m.id === id ? { ...m, tool_calls: [...(m.tool_calls ?? []), call] } : m
        ),
      },
    })),
  finalizeCustomAgentMessage: (agentId, id) =>
    set((state) => ({
      customAgentMessages: {
        ...state.customAgentMessages,
        [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) =>
          m.id === id ? { ...m, isStreaming: false } : m
        ),
      },
    })),

  // ── Custom agent running ───────────────────────────────────────────────
  customAgentRunning: {},
  setCustomAgentRunning: (agentId, v) =>
    set((state) => ({ customAgentRunning: { ...state.customAgentRunning, [agentId]: v } })),
  customAgentAbortControllers: {},
  setCustomAgentAbortController: (agentId, ac) =>
    set((state) => {
      if (ac === null) {
        const { [agentId]: _, ...rest } = state.customAgentAbortControllers;
        return { customAgentAbortControllers: rest };
      }
      return { customAgentAbortControllers: { ...state.customAgentAbortControllers, [agentId]: ac } };
    }),
  stopCustomAgent: (agentId) => {
    const { customAgentAbortControllers } = get();
    customAgentAbortControllers[agentId]?.abort();
    set((state) => {
      const { [agentId]: _, ...rest } = state.customAgentAbortControllers;
      return {
        customAgentRunning: { ...state.customAgentRunning, [agentId]: false },
        customAgentAbortControllers: rest,
      };
    });
    set((state) => ({
      customAgentMessages: {
        ...state.customAgentMessages,
        [agentId]: (state.customAgentMessages[agentId] ?? []).map((m) =>
          m.isStreaming ? { ...m, isStreaming: false } : m
        ),
      },
    }));
  },
}));
