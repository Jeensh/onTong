"use client";

/**
 * 영향도 분석 메뉴 — 코드 변경 (method/class/column) 시 영향 분석.
 */

import { useState } from "react";
import { Flame, Loader2, Play } from "lucide-react";
import { runCodeImpact, type StreamEvent } from "@/lib/section3/api";
import { EventStreamView } from "./EventStreamView";

export function CodeImpactPanel() {
  const [targetKind, setTargetKind] = useState<"method" | "class" | "column">("method");
  const [targetId, setTargetId] = useState("calculateThickness");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [running, setRunning] = useState(false);

  const submit = async () => {
    if (running || !targetId.trim()) return;
    setRunning(true);
    setEvents([]);
    const collected: StreamEvent[] = [];
    try {
      await runCodeImpact(
        { target_kind: targetKind, target_id: targetId.trim() },
        (ev) => { collected.push(ev); setEvents([...collected]); },
      );
    } catch (e) {
      collected.push({ type: "error", payload: { message: String(e) }, timestamp: new Date().toISOString() });
      setEvents([...collected]);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Flame size={18} className="text-primary" />
          영향도 분석 — 코드 변경 (method / class / column)
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          modeling.impact_analysis API 의 direct/indirect impact + risk_level + ontology graph 결과 — Cypher 그대로 노출.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[400px_1fr] gap-4 p-4 flex-1 overflow-hidden">
        <section className="space-y-3 overflow-y-auto pr-2">
          <div>
            <label className="block text-xs font-medium mb-1">변경 대상 종류</label>
            <select
              value={targetKind}
              onChange={(e) => setTargetKind(e.target.value as any)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="method">Method (Java 메서드)</option>
              <option value="class">Class (Java 클래스)</option>
              <option value="column">Column (테이블 컬럼)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">대상 ID</label>
            <input
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="예: calculateThickness"
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-mono"
            />
          </div>

          <button
            onClick={submit}
            disabled={running || !targetId.trim()}
            className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            영향 분석
          </button>

          <div className="text-[10px] text-muted-foreground mt-2">
            💡 자연어로 검색하려면 <b>온톨로지 브릿지 agent</b> 를 사용하세요. 거기서 같은 분석이 chat 으로 가능합니다.
          </div>
        </section>

        <section className="overflow-y-auto rounded-lg border border-border bg-card p-3">
          {events.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-12">대상을 입력하고 실행을 누르세요.</div>
          ) : (
            <EventStreamView events={events} />
          )}
        </section>
      </div>
    </div>
  );
}
