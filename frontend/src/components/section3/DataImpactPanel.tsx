"use client";

/**
 * 데이터 변경 분석 메뉴 — 기준값 (Standard) / Table / 주문 변경 영향.
 */

import { useState } from "react";
import { Database, Loader2, Play } from "lucide-react";
import { runDataImpact, type StreamEvent } from "@/lib/section3/api";
import { EventStreamView } from "./EventStreamView";

export function DataImpactPanel() {
  const [targetKind, setTargetKind] = useState<"table" | "standard_value" | "order">("standard_value");
  const [targetId, setTargetId] = useState("SC160");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [running, setRunning] = useState(false);

  const submit = async () => {
    if (running || !targetId.trim()) return;
    setRunning(true);
    setEvents([]);
    const collected: StreamEvent[] = [];
    try {
      await runDataImpact(
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
          <Database size={18} className="text-primary" />
          데이터 변경 분석 — 기준값 / Table / 주문
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          SC 기준값 변경, Table 변경, 주문 (14 Step 시뮬) 의 영향 — modeling.impact_analysis (Cypher 기반).
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
              <option value="standard_value">SC 기준값 (Standard)</option>
              <option value="table">Table (slab data 테이블)</option>
              <option value="order">주문 (14 Step 전체 시뮬)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">대상 ID</label>
            <input
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder={targetKind === "standard_value" ? "예: SC160" : targetKind === "table" ? "예: TB_C40_050SC160" : "예: order_001"}
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

          <div className="text-[10px] text-muted-foreground mt-2 space-y-1">
            <p>💡 정확한 ID 모를 때 <b>온톨로지 브릿지 agent</b> 에 자연어로 물어보세요.</p>
            <p>⚠ table / standard_value 의 id 카탈로그 endpoint 는 modeling 측 추가 요청 사항 (#2)</p>
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
