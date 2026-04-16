// Section 3 Slab Simulation — TypeScript type definitions

export type ScenarioType = "A" | "B" | "C" | "SLAB_DESIGN";

// ── Custom Agent Types ─────────────────────────────────────────────────

export interface CustomAgent {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  system_prompt: string;
  available_tools: string[];   // Slab 설계 도구 ID 목록
  example_prompt: string;
  created_at: string;          // ISO datetime
  created_by: "chat" | "form";
}

// Slab 설계 도메인에서 사용 가능한 도구 목록
export const SLAB_TOOLS = [
  { id: "get_order_info",           label: "주문 정보 조회",       icon: "📋" },
  { id: "simulate_width_range",     label: "폭 범위 시뮬레이션",    icon: "📐" },
  { id: "suggest_adjusted_width",   label: "폭 조정 제안",         icon: "🔧" },
  { id: "get_equipment_spec",       label: "설비 기준 조회",        icon: "🏭" },
  { id: "simulate_edging_impact",   label: "Edging 파급효과",      icon: "📊" },
  { id: "optimize_split_count",     label: "분할수 최적화",         icon: "⚙️" },
  { id: "calculate_slab_design",    label: "설계 전체 계산",        icon: "🧮" },
] as const;

// ── Active View (사이드바 선택 상태) ────────────────────────────────────

export type ActiveView =
  | { kind: "scenario"; id: ScenarioType }
  | { kind: "custom_hub" }
  | { kind: "custom_chat_builder" }
  | { kind: "custom_form_builder" }
  | { kind: "custom_agent"; agentId: string };

// ── Slab Size Simulator Types ─────────────────────────────────────────

export interface SlabSizeParams {
  target_width: number;   // 목표폭 (mm)
  thickness: number;      // 두께 (mm)
  target_length: number;  // 목표길이 (mm)
  unit_weight: number;    // 단중 (kg)
  split_count: number;    // 분할수
  yield_rate: number;     // 실수율 (0~1)
  assigned_rolling?: string;
  assigned_caster?: string;
}

export const DEFAULT_SLAB_PARAMS: SlabSizeParams = {
  target_width: 1040,
  thickness: 250,
  target_length: 11700,
  unit_weight: 23800,
  split_count: 2,
  yield_rate: 0.943,
  assigned_rolling: "HR-A",
  assigned_caster: "CC-01",
};

export type StepStatus = "ok" | "warning" | "error";

export interface SlabDesignStep {
  seq: number;
  name: string;
  result: Record<string, unknown>;
  status: StepStatus;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface SlabDesignSummary {
  width_range: { lower: number; upper: number };
  length_range: { lower: number; upper: number };
  weight_range: { lower: number; upper: number };
  target_width: number;
  target_length: number;
  split_count: number;
  slab_count: number;
  unit_weight_per_split: number;
}

export interface SlabDesignResult {
  feasible: boolean;
  steps: SlabDesignStep[];
  summary: SlabDesignSummary;
  overall_status: StepStatus;
}

export interface ParamConstraint {
  min: number;
  max: number;
  default: number;
  unit: string;
}

export interface SlabConstraints {
  target_width: ParamConstraint;
  thickness: ParamConstraint;
  target_length: ParamConstraint;
  unit_weight: ParamConstraint;
  split_count: ParamConstraint;
  yield_rate: ParamConstraint;
}

export interface SlabState {
  id: string;
  status: "normal" | "error" | "warning" | "adjusted" | "optimal";
  width: number;       // mm
  length: number;      // mm
  thickness: number;   // mm (stored as mm, converted from cm)
  split_count?: number;
  animating?: boolean;
  label?: string;
}

export interface OntologyNode {
  id: string;
  type: "Order" | "ContinuousCaster" | "HotRollingMill" | "EdgeSpec" | "Slab";
  label: string;
  status?: string;
}

export interface OntologyEdge {
  from: string;
  to: string;
  relation: string;
}

export interface OntologyGraphData {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
}

export interface GraphState {
  traversal: string[];
  highlighted_edges: { from: string; to: string }[];
}

// Chat message types
export type MessageRole = "user" | "assistant";

export interface ThinkingStep {
  message: string;
  timestamp: number;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result?: unknown;
  timestamp: number;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  thinking_steps?: ThinkingStep[];
  tool_calls?: ToolCall[];
  timestamp: number;
  isStreaming?: boolean;
}

// Agent run result
export interface AgentResult {
  scenario: ScenarioType;
  order_id?: string;
  [key: string]: unknown;
}

// Order types
export interface Order {
  order_id: string;
  product_type: string;
  target_thickness: number;
  target_width: number;
  target_length: number;
  order_weight_min: number;
  order_weight_max: number;
  yield_rate: number;
  assigned_caster: string;
  assigned_rolling: string;
  status: "ERROR" | "DESIGNED" | "PENDING";
  error_code?: string;
  error_msg?: string;
  split_count?: number;
  slab_weight?: number;
  slab_count?: number;
  satisfaction_rate?: number;
}

// Scenario metadata
export interface ScenarioMeta {
  id: ScenarioType;
  title: string;
  description: string;
  example_prompt: string;
  icon: string;
  color: string;
}

export const SCENARIO_META: Record<ScenarioType, ScenarioMeta> = {
  A: {
    id: "A",
    title: "폭 범위 산정 불가 (DG320)",
    description: "Edging 기준 매칭 불가 에러 원인 탐색 & 파라미터 자동 조정",
    example_prompt: "주문 ORD-2024-0042가 폭 범위 계산에서 DG320 에러났어. 왜 그러는지 찾고, 폭을 어떻게 조정하면 되는지 알려줘.",
    icon: "🔍",
    color: "#ef4444",
  },
  B: {
    id: "B",
    title: "Edging 기준 변경 파급효과",
    description: "What-If 시뮬레이션 — Edging 능력 변경 시 연결 주문 영향 분석",
    example_prompt: "열연 A라인 Edging 최대 능력을 180mm에서 160mm로 줄이면, 현재 설계 중인 주문들 중 몇 개나 폭 범위가 깨져?",
    icon: "📊",
    color: "#f59e0b",
  },
  C: {
    id: "C",
    title: "단중·매수 최적화",
    description: "분할수 조합 최적화 — 단중 만족률 최대화",
    example_prompt: "주문 ORD-2024-0055 Slab 설계 결과 분할수 3으로 나왔는데, 단중 만족률이 60%밖에 안 돼. 더 나은 조합 없어?",
    icon: "⚙️",
    color: "#3b82f6",
  },
  SLAB_DESIGN: {
    id: "SLAB_DESIGN",
    title: "Slab 설계 시뮬레이터",
    description: "파라미터 실시간 조작 → 3D 형태 변화 + 설계 프로세스 영향도 분석",
    example_prompt: "",
    icon: "🧊",
    color: "#6366f1",
  },
};
