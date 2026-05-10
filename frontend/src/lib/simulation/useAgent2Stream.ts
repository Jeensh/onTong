// Agent 2 SSE 스트리밍 hook.
//
// `POST /api/simulation/agents/test-data/stream` 엔드포인트를 fetch + ReadableStream으로
// 수신. 표준 EventSource는 GET만 지원하므로 fetch 기반으로 SSE 파싱.

import { useCallback, useRef, useState } from "react";

const API_BASE = "";

export type CaseType = "normal" | "boundary" | "error" | "performance";

export interface Agent2StreamRequest {
  target_id: string;
  case_types: CaseType[];
  test_count: number;
  rules?: Record<string, string>;
}

export interface CaseStartedEvent {
  event: "case_started";
  data: { idx: number; case_id: string; case_type: CaseType; description: string };
}

export interface CaseDoneEvent {
  event: "case_done" | "case_failed";
  data: {
    case_id: string;
    case_type: CaseType;
    description: string;
    matches_expectation: boolean;
    elapsed_ms: number;
    input_data: Record<string, unknown>;
    expected: Record<string, unknown>;
    actual_output: Record<string, unknown>;
    error: Record<string, unknown> | null;
  };
}

export interface HeatmapMark {
  line: number;
  count: number;
  label: string;
}

export interface HeatmapData {
  step_id: string;
  file_path: string;
  file_content: string;
  marks: HeatmapMark[];
  total_cases: number;
}

export interface SummaryEvent {
  event: "summary";
  data: {
    total: number;
    failed_count: number;
    by_type: Record<string, { total: number; matched: number; failed: number }>;
    fail_cases: Array<Record<string, unknown>>;
    slab_count_distribution: number[];
    productivity_distribution: number[];
    avg_elapsed_ms: number;
    code_skeleton: string;
    step_id: string;
    request_id: string;
    heatmap?: HeatmapData | null;
  };
}

export interface RunStartedEvent {
  event: "run_started";
  data: { request_id: string; step_id: string; total: number; case_types: CaseType[] };
}

export type AgentEvent =
  | RunStartedEvent
  | CaseStartedEvent
  | CaseDoneEvent
  | SummaryEvent
  | { event: "run_complete"; data: { request_id: string } }
  | { event: "error"; data: { message: string; type: string } };

export interface CaseLogEntry {
  case_id: string;
  case_type: CaseType;
  description: string;
  matches_expectation: boolean;
  elapsed_ms: number;
  status: "running" | "done" | "failed";
  /** case_done 이벤트로부터 채워지는 실제 입력 + 결과 (펼침 표시용). */
  input_data?: Record<string, unknown>;
  expected?: Record<string, unknown>;
  actual_output?: Record<string, unknown>;
  error?: Record<string, unknown> | null;
}

export interface UseAgent2StreamReturn {
  start: (req: Agent2StreamRequest) => Promise<void>;
  cancel: () => void;
  running: boolean;
  progress: { received: number; total: number };
  cases: CaseLogEntry[];
  /** case_done 이벤트마다 적재되는 풀 payload — Time-travel scrubber 용. */
  casesDetailed: CaseDoneEvent["data"][];
  summary: SummaryEvent["data"] | null;
  error: string | null;
  failures: CaseDoneEvent["data"][];
}

export function useAgent2Stream(): UseAgent2StreamReturn {
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ received: 0, total: 0 });
  const [cases, setCases] = useState<CaseLogEntry[]>([]);
  const [summary, setSummary] = useState<SummaryEvent["data"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failures, setFailures] = useState<CaseDoneEvent["data"][]>([]);
  const [casesDetailed, setCasesDetailed] = useState<CaseDoneEvent["data"][]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setRunning(false);
  }, []);

  const start = useCallback(async (req: Agent2StreamRequest) => {
    cancel();
    const ac = new AbortController();
    abortRef.current = ac;

    setRunning(true);
    setProgress({ received: 0, total: 0 });
    setCases([]);
    setCasesDetailed([]);
    setSummary(null);
    setError(null);
    setFailures([]);

    try {
      const res = await fetch(`${API_BASE}/api/simulation/agents/test-data/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: ac.signal,
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      if (!res.body) {
        throw new Error("No response body");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let nlIdx: number;
        while ((nlIdx = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, nlIdx);
          buffer = buffer.slice(nlIdx + 2);
          const dataLine = chunk.split("\n").find((l) => l.startsWith("data: "));
          if (!dataLine) continue;
          const json = dataLine.slice("data: ".length);
          let evt: AgentEvent;
          try {
            evt = JSON.parse(json) as AgentEvent;
          } catch {
            continue;
          }
          handleEvent(evt);
        }
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message ?? String(e));
    } finally {
      setRunning(false);
      abortRef.current = null;
    }

    function handleEvent(evt: AgentEvent) {
      switch (evt.event) {
        case "run_started":
          setProgress({ received: 0, total: evt.data.total });
          break;
        case "case_started":
          setCases((prev) => [
            ...prev,
            {
              case_id: evt.data.case_id,
              case_type: evt.data.case_type,
              description: evt.data.description,
              matches_expectation: false,
              elapsed_ms: 0,
              status: "running",
            },
          ]);
          break;
        case "case_done":
        case "case_failed": {
          const d = evt.data;
          setCases((prev) =>
            prev.map((c) =>
              c.case_id === d.case_id
                ? {
                    ...c,
                    matches_expectation: d.matches_expectation,
                    elapsed_ms: d.elapsed_ms,
                    status: d.matches_expectation ? "done" : "failed",
                    input_data: d.input_data,
                    expected: d.expected,
                    actual_output: d.actual_output,
                    error: d.error,
                  }
                : c
            )
          );
          setProgress((p) => ({ ...p, received: p.received + 1 }));
          setCasesDetailed((prev) => [...prev, d]);
          if (!d.matches_expectation) {
            setFailures((prev) => [...prev, d]);
          }
          break;
        }
        case "summary":
          setSummary(evt.data);
          break;
        case "error":
          setError(evt.data.message);
          break;
        case "run_complete":
          // 스트림 종료 신호 — 별도 동작 없음
          break;
      }
    }
  }, [cancel]);

  return { start, cancel, running, progress, cases, casesDetailed, summary, error, failures };
}
