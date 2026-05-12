"use client";

import { useState, useEffect } from "react";
import { Beaker, Loader2, Play, RotateCcw, Sparkles } from "lucide-react";
import { runSandbox, getStats, type StreamEvent, type AgentFinalPayload } from "@/lib/section3/api";
import { StreamTimeline } from "./rich/StreamTimeline";
import { RichResultCard } from "./rich/RichResultCard";

const CASE_TYPES: Array<{ id: "normal" | "boundary" | "error"; label: string; emoji: string; tone: string }> = [
  { id: "normal", label: "정상", emoji: "✅", tone: "bg-emerald-100 text-emerald-700 border-emerald-400" },
  { id: "boundary", label: "경계", emoji: "⚠️", tone: "bg-amber-100 text-amber-700 border-amber-400" },
  { id: "error", label: "오류", emoji: "❌", tone: "bg-red-100 text-red-700 border-red-400" },
];

export function SandboxPanel() {
  const [targetKind, setTargetKind] = useState<"step" | "method" | "class">("step");
  const [targetId, setTargetId] = useState("");
  const [stepCount, setStepCount] = useState<number>(0);

  // modeling.graph_stats 응답으로 Step 개수 동적 가져옴 (하드코딩 0건)
  useEffect(() => {
    getStats()
      .then((s) => setStepCount(s.nodes?.Step ?? 0))
      .catch(() => setStepCount(0));
  }, []);

  const stepPresets = Array.from({ length: stepCount }, (_, i) => ({
    id: String(i + 1),
    label: `Step ${i + 1}`,
  }));
  const [selected, setSelected] = useState<Array<"normal" | "boundary" | "error">>(["normal", "boundary", "error"]);
  const [runAfter, setRunAfter] = useState(true);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [finalPayload, setFinalPayload] = useState<AgentFinalPayload | null>(null);
  const [running, setRunning] = useState(false);

  const submit = async () => {
    if (running || !targetId.trim()) return;
    setRunning(true);
    setEvents([]);
    setFinalPayload(null);
    const collected: StreamEvent[] = [];
    try {
      await runSandbox(
        { target_kind: targetKind, target_id: targetId.trim(), case_types: selected, run_after_generate: runAfter },
        (ev) => {
          collected.push(ev);
          setEvents([...collected]);
          if (ev.type === "final") setFinalPayload(ev.payload as AgentFinalPayload);
        },
      );
    } catch (e) {
      collected.push({ type: "error", payload: { message: String(e) }, timestamp: new Date().toISOString() });
      setEvents([...collected]);
    } finally {
      setRunning(false);
    }
  };

  const reset = () => {
    setEvents([]);
    setFinalPayload(null);
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-background to-muted/20">
      <div className="px-5 py-3 border-b border-border bg-card/80 backdrop-blur-sm">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 text-white flex items-center justify-center">
            <Beaker size={14} />
          </div>
          샌드박스 <span className="text-[10px] text-muted-foreground font-normal">테스트 데이터 + 격리 실행</span>
        </h2>
        <p className="text-[11px] text-muted-foreground mt-0.5 ml-9">
          modeling.simulate API → 자동 케이스 생성 → LLM 으로 Python 합성 → subprocess 격리 실행
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 p-4 flex-1 overflow-hidden">
        {/* ── 입력 ─────────────────────────────────── */}
        <section className="overflow-y-auto pr-2 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div>
              <label className="block text-[11px] font-semibold text-foreground mb-1.5">대상 종류</label>
              <select
                value={targetKind}
                onChange={(e) => setTargetKind(e.target.value as any)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary outline-none"
              >
                <option value="step">Step (ontology Step #)</option>
                <option value="method">Method (실험적)</option>
                <option value="class">Class (실험적)</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-foreground mb-1.5">대상 ID</label>
              <input
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder={targetKind === "step" ? (stepCount ? `1 ~ ${stepCount}` : "Step 번호") : "id"}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:border-primary outline-none"
              />
              {targetKind === "step" && stepPresets.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {stepPresets.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => setTargetId(s.id)}
                      className={`text-[10px] px-2 py-0.5 rounded-full border ${targetId === s.id ? "border-primary bg-primary/10 text-primary" : "border-border bg-muted text-muted-foreground hover:bg-muted/70"}`}
                    >
                      {s.label}
                    </button>
                  ))}
                  <span className="text-[9px] text-muted-foreground self-center ml-1">
                    (modeling 의 graph_stats 응답에서 동적 생성)
                  </span>
                </div>
              )}
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-foreground mb-1.5">케이스 유형</label>
              <div className="grid grid-cols-3 gap-1.5">
                {CASE_TYPES.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelected((sel) => sel.includes(c.id) ? sel.filter((x) => x !== c.id) : [...sel, c.id])}
                    className={`px-2 py-1.5 rounded-lg border-2 text-[11px] font-semibold transition-all ${selected.includes(c.id) ? c.tone : "border-border bg-background text-muted-foreground"}`}
                  >
                    <div className="text-lg">{c.emoji}</div>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="flex items-center gap-2 text-[11px] cursor-pointer">
              <input type="checkbox" checked={runAfter} onChange={(e) => setRunAfter(e.target.checked)} className="rounded" />
              <span>코드 합성 후 sandbox 실행까지 진행</span>
            </label>

            <div className="flex gap-2">
              <button
                onClick={submit}
                disabled={running || !targetId.trim() || selected.length === 0}
                className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 text-white text-sm font-semibold hover:from-emerald-600 hover:to-emerald-700 disabled:opacity-40 transition-all shadow-sm"
              >
                {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                {running ? "실행 중" : "시뮬 실행"}
              </button>
              {(events.length > 0 || finalPayload) && (
                <button
                  onClick={reset}
                  disabled={running}
                  className="inline-flex items-center gap-1 px-3 py-2.5 rounded-lg border border-border bg-background text-muted-foreground hover:bg-muted text-sm"
                  title="결과 지우기"
                >
                  <RotateCcw size={14} />
                </button>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700/40 p-3 text-[11px] text-amber-800 dark:text-amber-200 flex gap-2">
            <Sparkles size={14} className="flex-shrink-0 mt-0.5" />
            <div>
              <b>흐름:</b> modeling.simulate → test_case 자동 생성 (normal/boundary/error)
              → LLM 이 ontology trace 만 보고 Python 합성 → subprocess 격리 실행 → 결과 비교
            </div>
          </div>
        </section>

        {/* ── 결과 ─────────────────────────────────── */}
        <section className="overflow-y-auto pr-1">
          {events.length === 0 ? (
            <EmptyResults />
          ) : (
            <div className="space-y-4">
              {finalPayload ? (
                <RichResultCard result={finalPayload} />
              ) : (
                <StreamTimeline events={events} active={running} />
              )}
              {finalPayload && (
                <details className="rounded-xl border border-border bg-card p-3">
                  <summary className="cursor-pointer text-[11px] font-semibold text-muted-foreground hover:text-foreground">
                    ▶ 전체 실행 timeline ({events.length} events)
                  </summary>
                  <div className="mt-3">
                    <StreamTimeline events={events} />
                  </div>
                </details>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function EmptyResults() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center py-12">
      <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3">
        <Beaker size={28} />
      </div>
      <h3 className="text-sm font-semibold">실행 대기 중</h3>
      <p className="text-[11px] text-muted-foreground mt-1">대상을 고르고 "시뮬 실행" 을 누르세요.</p>
    </div>
  );
}
