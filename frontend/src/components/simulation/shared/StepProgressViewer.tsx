"use client";

import { useEffect, useRef, useState } from "react";

export interface StepEvent {
  stepNumber: number;
  stepName: string;
  fromValue?: number | null;
  toValue?: number | null;
  detail?: string | null;
  executedAt?: string;
}

export interface StreamingDesignSummary {
  thickness?: number;
  target_width?: number;
  target_length?: number;
  slab_weight?: number;
  split_count?: number;
  unit_count?: number;
  design_status?: string;
}

interface StepProgressViewerProps {
  /** 14 Step 정의 (예측 단계 — 이름은 온톨로지에서 미리 알 수 있다). */
  expectedSteps: { stepNumber: number; stepName: string }[];
  /** SSE 스트리밍 URL — null이면 비활성화. */
  streamUrl: string | null;
  onCompleted?: (summary: StreamingDesignSummary) => void;
  onError?: (msg: string) => void;
}

type StepState = "pending" | "running" | "done" | "error";

interface StepDisplay extends StepEvent {
  state: StepState;
}

export function StepProgressViewer({
  expectedSteps,
  streamUrl,
  onCompleted,
  onError,
}: StepProgressViewerProps) {
  const [steps, setSteps] = useState<StepDisplay[]>(
    expectedSteps.map((s) => ({ ...s, state: "pending" }))
  );
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!streamUrl) return;
    setSteps(expectedSteps.map((s) => ({ ...s, state: "pending" })));
    setError(null);
    setDone(false);

    const es = new EventSource(streamUrl);
    esRef.current = es;

    // Step 시작/진행 effect: 일정 텀으로 다음 step을 'running'으로 표시
    let nextRunningIdx = 0;
    const tick = setInterval(() => {
      setSteps((prev) => {
        const idx = prev.findIndex((s) => s.state === "pending");
        if (idx === -1 || idx > nextRunningIdx) return prev;
        const next = [...prev];
        next[idx] = { ...next[idx], state: "running" };
        nextRunningIdx = idx + 1;
        return next;
      });
    }, 200);

    es.addEventListener("started", (e) => {
      // optional payload
      console.log("[SSE] started", e.data);
    });

    es.addEventListener("step", (e) => {
      try {
        const data: StepEvent = JSON.parse((e as MessageEvent).data);
        setSteps((prev) => {
          const idx = prev.findIndex((s) => s.stepNumber === data.stepNumber);
          if (idx === -1) return prev;
          const next = [...prev];
          next[idx] = { ...data, state: "done" };
          return next;
        });
      } catch (err) {
        console.error(err);
      }
    });

    es.addEventListener("completed", (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data);
        setDone(true);
        setSteps((prev) =>
          prev.map((s) => (s.state === "pending" || s.state === "running" ? { ...s, state: "done" } : s))
        );
        onCompleted?.({
          thickness: data.slabThickness,
          target_width: data.targetSlabWidth,
          target_length: data.targetSlabLength,
          slab_weight: data.slabWeight,
          split_count: data.splitCount,
          unit_count: data.unitCount,
          design_status: data.designStatus,
        });
        es.close();
        clearInterval(tick);
      } catch (err) {
        console.error(err);
      }
    });

    es.addEventListener("error", (e) => {
      try {
        const raw = (e as MessageEvent).data;
        const data = raw ? JSON.parse(raw) : {};
        const msg = data.message || data.errorCode || "스트리밍 에러";
        setError(msg);
        setSteps((prev) =>
          prev.map((s) => (s.state === "running" ? { ...s, state: "error" } : s))
        );
        onError?.(msg);
      } catch {
        setError("스트리밍 에러 (응답 파싱 실패)");
      }
      es.close();
      clearInterval(tick);
    });

    return () => {
      es.close();
      clearInterval(tick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamUrl]);

  const completedCount = steps.filter((s) => s.state === "done").length;
  const total = steps.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between rounded border border-gray-200 bg-white p-3 shadow-sm">
        <div className="text-sm font-semibold text-gray-700">
          {done ? "✅ 14 Step 모두 실행 완료" : error ? "❌ 실행 중 오류" : "⏳ 14 Step 실행 중..."}
        </div>
        <div className="text-xs text-gray-500">
          {completedCount} / {total} 완료
        </div>
      </div>

      <div className="rounded border border-gray-200 bg-white p-2 shadow-sm">
        <ul className="divide-y divide-gray-100">
          {steps.map((s) => (
            <li key={s.stepNumber} className="flex items-start gap-3 py-2 px-2">
              <StepIcon state={s.state} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] font-mono font-semibold text-gray-700">
                    Step {s.stepNumber}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {s.stepName}
                  </span>
                </div>
                {s.state === "done" && s.detail && (
                  <div className="mt-1 text-xs text-gray-600">
                    {s.detail}
                    {(s.fromValue !== null && s.fromValue !== undefined && s.fromValue !== 0) ||
                    (s.toValue !== null && s.toValue !== undefined && s.toValue !== 0) ? (
                      <span className="ml-2 font-mono text-gray-500">
                        [from={s.fromValue} → to={s.toValue}]
                      </span>
                    ) : null}
                  </div>
                )}
                {s.state === "running" && (
                  <div className="mt-1 text-xs italic text-blue-600">
                    온톨로지 기반 SC/메서드 추적 중...
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
          ⚠️ {error}
        </div>
      )}
    </div>
  );
}

function StepIcon({ state }: { state: StepState }) {
  if (state === "done")
    return <span className="mt-0.5 inline-block text-green-600">✅</span>;
  if (state === "running")
    return (
      <span className="mt-0.5 inline-block animate-spin text-blue-500">⏳</span>
    );
  if (state === "error")
    return <span className="mt-0.5 inline-block text-red-500">❌</span>;
  return <span className="mt-0.5 inline-block text-gray-300">⚪</span>;
}
