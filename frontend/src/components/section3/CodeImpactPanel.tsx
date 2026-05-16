"use client";

import { useState } from "react";
import { Flame, Loader2, Play, RotateCcw, Code2, MessageSquare } from "lucide-react";
import { runCodeImpact, type StreamEvent, type AgentFinalPayload } from "@/lib/section3/api";
import { StreamTimeline } from "./rich/StreamTimeline";
import { RichResultCard } from "./rich/RichResultCard";

export function CodeImpactPanel() {
  const [targetKind, setTargetKind] = useState<"method" | "class" | "column">("method");
  const [targetId, setTargetId] = useState("");
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
      await runCodeImpact(
        { target_kind: targetKind, target_id: targetId.trim() },
        (ev) => { collected.push(ev); setEvents([...collected]); if (ev.type === "final") setFinalPayload(ev.payload as AgentFinalPayload); },
      );
    } catch (e) {
      collected.push({ type: "error", payload: { message: String(e) }, timestamp: new Date().toISOString() });
      setEvents([...collected]);
    } finally {
      setRunning(false);
    }
  };

  const reset = () => { setEvents([]); setFinalPayload(null); };

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-background to-muted/20">
      <div className="px-5 py-3 border-b border-border bg-card/80 backdrop-blur-sm">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 text-white flex items-center justify-center">
            <Flame size={14} />
          </div>
          영향도 분석 <span className="text-[10px] text-muted-foreground font-normal">코드 변경 (method / class / column)</span>
        </h2>
        <p className="text-[11px] text-muted-foreground mt-0.5 ml-9">
          modeling.impact_analysis API → direct/indirect impact + risk_level + ontology graph
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 p-4 flex-1 overflow-hidden">
        <section className="overflow-y-auto pr-2 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div>
              <label className="block text-[11px] font-semibold mb-1.5">변경 대상 종류</label>
              <select
                value={targetKind}
                onChange={(e) => setTargetKind(e.target.value as any)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary outline-none"
              >
                <option value="method">Method (Java 메서드)</option>
                <option value="class">Class (Java 클래스)</option>
                <option value="column">Column (테이블 컬럼)</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-semibold mb-1.5">대상 ID</label>
              <input
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder={targetKind === "method" ? "method 이름 (자연어로 검색하려면 → 브릿지 chat)" : `${targetKind} id`}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:border-primary outline-none"
              />
              <p className="text-[10px] text-muted-foreground mt-1.5 flex items-start gap-1">
                <MessageSquare size={11} className="flex-shrink-0 mt-0.5" />
                <span>
                  id 모르면 <b>온톨로지 브릿지</b> 에서 자연어로 검색
                  → 검색 결과의 method 이름을 그대로 여기 붙여넣으면 됩니다.
                </span>
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={submit}
                disabled={running || !targetId.trim()}
                className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 text-white text-sm font-semibold hover:from-orange-600 hover:to-red-600 disabled:opacity-40 transition-all shadow-sm"
              >
                {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                {running ? "분석 중" : "영향 분석"}
              </button>
              {(events.length > 0 || finalPayload) && (
                <button onClick={reset} disabled={running} className="inline-flex items-center gap-1 px-3 py-2.5 rounded-lg border border-border bg-background text-muted-foreground hover:bg-muted text-sm">
                  <RotateCcw size={14} />
                </button>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-orange-200 bg-orange-50 dark:bg-orange-900/20 p-3 text-[11px] text-orange-800 dark:text-orange-200 flex gap-2">
            <Code2 size={14} className="flex-shrink-0 mt-0.5" />
            <div>
              <b>분석:</b> ontology graph traversal — 변경 대상 Method 의 <code className="text-[10px]">CALCULATES</code> 관계로 영향 Step 추적, <code className="text-[10px]">PRECEDES</code> 로 다운스트림 Step 도출.
            </div>
          </div>
        </section>

        <section className="overflow-y-auto pr-1">
          {events.length === 0 ? <EmptyResults /> : (
            <div className="space-y-4">
              {finalPayload ? (
                <RichResultCard result={finalPayload} highlightMethod={targetKind === "method" ? targetId : undefined} />
              ) : (
                <StreamTimeline events={events} active={running} />
              )}
              {finalPayload && (
                <details className="rounded-xl border border-border bg-card p-3">
                  <summary className="cursor-pointer text-[11px] font-semibold text-muted-foreground hover:text-foreground">
                    ▶ 전체 실행 timeline ({events.length} events)
                  </summary>
                  <div className="mt-3"><StreamTimeline events={events} /></div>
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
      <div className="w-16 h-16 rounded-2xl bg-orange-100 text-orange-600 flex items-center justify-center mb-3">
        <Flame size={28} />
      </div>
      <h3 className="text-sm font-semibold">분석 대기 중</h3>
      <p className="text-[11px] text-muted-foreground mt-1">변경 대상 method/class 를 입력하세요.</p>
    </div>
  );
}
