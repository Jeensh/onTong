// Section 3 Slab Simulation API client

import type { ScenarioType, Order, OntologyGraphData, SlabState, GraphState, CustomAgent } from "./types";

// Detect if running locally to bypass Next.js SSE buffering
const API_BASE =
  typeof window !== "undefined" && window.location.hostname === "localhost"
    ? "http://localhost:8002"
    : "";

// ── Built-in Agent SSE ────────────────────────────────────────────────

export interface SlabAgentCallbacks {
  onThinking?: (message: string) => void;
  onToolCall?: (tool: string, args: Record<string, unknown>) => void;
  onToolResult?: (tool: string, result: unknown) => void;
  onContentDelta?: (delta: string) => void;
  onSlabState?: (slabs: SlabState[]) => void;
  onGraphState?: (state: GraphState) => void;
  onDone?: (result: unknown) => void;
  onError?: (message: string) => void;
}

export async function runSlabAgent(
  scenario: ScenarioType,
  message: string,
  callbacks: SlabAgentCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE}/api/simulation/slab/run`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario, message }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  await consumeSSE(response, {
    thinking: (data) => callbacks.onThinking?.(data.message as string),
    tool_call: (data) => callbacks.onToolCall?.(data.tool as string, data.args as Record<string, unknown>),
    tool_result: (data) => callbacks.onToolResult?.(data.tool as string, data.result),
    content_delta: (data) => callbacks.onContentDelta?.(data.delta as string),
    slab_state: (data) => callbacks.onSlabState?.(data.slabs as SlabState[]),
    graph_state: (data) =>
      callbacks.onGraphState?.({
        traversal: (data.traversal as string[]) ?? [],
        highlighted_edges: (data.highlighted_edges as { from: string; to: string }[]) ?? [],
      }),
    done: (data) => callbacks.onDone?.(data.result),
    error: (data) => callbacks.onError?.(data.message as string),
  });
}

export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch(`${API_BASE}/api/simulation/slab/orders`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchOntologyGraph(): Promise<OntologyGraphData> {
  const res = await fetch(`${API_BASE}/api/simulation/slab/ontology`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Custom Agent CRUD ─────────────────────────────────────────────────

export async function fetchCustomAgents(): Promise<CustomAgent[]> {
  const res = await fetch(`${API_BASE}/api/simulation/custom-agents`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createCustomAgent(
  agent: Omit<CustomAgent, "id" | "created_at">
): Promise<CustomAgent> {
  const res = await fetch(`${API_BASE}/api/simulation/custom-agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(agent),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteCustomAgent(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/simulation/custom-agents/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

// ── Agent Builder Chat SSE ────────────────────────────────────────────

export interface AgentBuilderCallbacks extends Omit<SlabAgentCallbacks, "onSlabState" | "onGraphState"> {
  onAgentReady?: (agentDef: Omit<CustomAgent, "id" | "created_at">) => void;
}

export async function runAgentBuilderChat(
  message: string,
  history: Array<{ role: "user" | "assistant"; content: string }>,
  callbacks: AgentBuilderCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE}/api/simulation/custom-agents/build/chat`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  await consumeSSE(response, {
    thinking: (data) => callbacks.onThinking?.(data.message as string),
    content_delta: (data) => callbacks.onContentDelta?.(data.delta as string),
    agent_ready: (data) => callbacks.onAgentReady?.(data.agent as Omit<CustomAgent, "id" | "created_at">),
    done: (data) => callbacks.onDone?.(data),
    error: (data) => callbacks.onError?.(data.message as string),
  });
}

// ── Custom Agent Runner SSE ───────────────────────────────────────────

export async function runCustomAgent(
  agentId: string,
  message: string,
  callbacks: SlabAgentCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE}/api/simulation/custom-agents/${agentId}/run`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  await consumeSSE(response, {
    thinking: (data) => callbacks.onThinking?.(data.message as string),
    tool_call: (data) => callbacks.onToolCall?.(data.tool as string, data.args as Record<string, unknown>),
    tool_result: (data) => callbacks.onToolResult?.(data.tool as string, data.result),
    content_delta: (data) => callbacks.onContentDelta?.(data.delta as string),
    done: (data) => callbacks.onDone?.(data.result),
    error: (data) => callbacks.onError?.(data.message as string),
  });
}

// ── SSE 공통 파서 ────────────────────────────────────────────────────

type SSEHandlers = Record<string, (data: Record<string, unknown>) => void>;

async function consumeSSE(response: Response, handlers: SSEHandlers): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";

    for (const block of blocks) {
      if (!block.trim()) continue;

      const lines = block.split("\n");
      let eventType = "message";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6).trim();
        }
      }

      if (!dataStr) continue;

      try {
        const data = JSON.parse(dataStr);
        handlers[eventType]?.(data);
      } catch {
        // ignore parse errors
      }
    }
  }
}
