"use client";

import { useState } from "react";
import { Database, Loader2, Play, RotateCcw, Layers, MessageSquare } from "lucide-react";
import { runDataImpact, type StreamEvent, type AgentFinalPayload } from "@/lib/section3/api";
import { StreamTimeline } from "./rich/StreamTimeline";
import { RichResultCard } from "./rich/RichResultCard";

export function DataImpactPanel() {
  const [targetKind, setTargetKind] = useState<"table" | "standard_value" | "order">("standard_value");
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
      await runDataImpact(
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
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 text-white flex items-center justify-center">
            <Database size={14} />
          </div>
          데이터 변경 분석 <span className="text-[10px] text-muted-foreground font-normal">기준값 / Table / 주문</span>
        </h2>
        <p className="text-[11px] text-muted-foreground mt-0.5 ml-9">
          modeling.impact_analysis (data layer) → 영향 Step + Method + Cypher
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 p-4 flex-1 overflow-hidden">
        <section className="overflow-y-auto pr-2 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div>
              <label className="block text-[11px] font-semibold mb-1.5">변경 대상 종류</label>
              <div className="grid grid-cols-3 gap-1.5">
                {[
                  { id: "standard_value" as const, label: "SC 기준", emoji: "📐" },
                  { id: "table" as const, label: "Table", emoji: "📋" },
                  { id: "order" as const, label: "주문", emoji: "📦" },
                ].map((c) => (
                  <button
                    key={c.id}
                    onClick={() => { setTargetKind(c.id); setTargetId(""); }}
                    className={`px-2 py-2 rounded-lg border-2 text-[11px] font-semibold transition-all ${targetKind === c.id ? "border-amber-500 bg-amber-50 text-amber-700" : "border-border bg-background text-muted-foreground"}`}
                  >
                    <div className="text-lg">{c.emoji}</div>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold mb-1.5">대상 ID</label>
              <input
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder={targetKind === "standard_value" ? "기준값 코드" : targetKind === "table" ? "테이블 이름" : "주문 id"}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono focus:border-primary outline-none"
              />
              <p className="text-[10px] text-muted-foreground mt-1.5 flex items-start gap-1">
                <MessageSquare size={11} className="flex-shrink-0 mt-0.5" />
                <span>
                  id 카탈로그가 modeling 측에 아직 미구현 (요청 #② 진행 중).
                  지금은 <b>온톨로지 브릿지 agent</b> 에서 자연어로 검색 (예: "<i>기준값 목록 보여줘</i>") → 발견된 id 를 여기 붙여넣기.
                </span>
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={submit}
                disabled={running || !targetId.trim()}
                className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 text-white text-sm font-semibold hover:from-amber-600 hover:to-orange-600 disabled:opacity-40 transition-all shadow-sm"
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

          <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-900/20 p-3 text-[11px] text-amber-800 dark:text-amber-200 flex gap-2">
            <Layers size={14} className="flex-shrink-0 mt-0.5" />
            <div>
              <b>분석:</b> SC 기준값 / Table / 주문 변경 시 <code className="text-[10px]">USES_STANDARD</code> · <code className="text-[10px]">MAPS_TO_STANDARD</code> · <code className="text-[10px]">CALCULATES</code> 관계 traversal 로 영향 Step + Method 추적.
            </div>
          </div>
        </section>

        <section className="overflow-y-auto pr-1">
          {events.length === 0 ? <EmptyResults /> : (
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
      <div className="w-16 h-16 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center mb-3">
        <Database size={28} />
      </div>
      <h3 className="text-sm font-semibold">분석 대기 중</h3>
      <p className="text-[11px] text-muted-foreground mt-1">SC 기준값 / Table / 주문 ID 를 입력하세요.</p>
    </div>
  );
}
