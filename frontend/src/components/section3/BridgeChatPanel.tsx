"use client";

/**
 * 온톨로지 브릿지 agent — chat UI.
 * 사용자 자연어 → bridge agent → intent 분류 → 적절한 task agent → SSE 스트리밍.
 */

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, MessageSquare } from "lucide-react";
import { chat, type StreamEvent } from "@/lib/section3/api";
import { EventStreamView } from "./EventStreamView";

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  events?: StreamEvent[];
  followups?: string[];
}

export function BridgeChatPanel() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [activeEvents, setActiveEvents] = useState<StreamEvent[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, activeEvents]);

  const submit = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || running) return;
    if (!override) setInput("");
    setRunning(true);
    setActiveEvents([]);

    const newTurns = [...turns, { role: "user" as const, content: text }];
    setTurns(newTurns);

    abortRef.current = new AbortController();
    const collected: StreamEvent[] = [];
    let finalSummary = "";
    let followups: string[] = [];

    try {
      await chat(
        {
          message: text,
          history: newTurns.slice(0, -1).map((t) => ({ role: t.role, content: t.content })),
        },
        (ev) => {
          collected.push(ev);
          setActiveEvents([...collected]);
          if (ev.type === "intent_classification") followups = ev.payload.suggested_followups ?? [];
          if (ev.type === "final") finalSummary = ev.payload.summary;
          if (ev.type === "error") finalSummary = "⚠ " + ev.payload.message;
          if (ev.type === "need_more_info") finalSummary = "ℹ " + ev.payload.missing_info.reason;
        },
        abortRef.current.signal,
      );
    } catch (e) {
      finalSummary = `요청 실패: ${e instanceof Error ? e.message : String(e)}`;
    }

    setTurns((prev) => [...prev, { role: "assistant", content: finalSummary || "(응답 없음)", events: collected, followups }]);
    setActiveEvents([]);
    setRunning(false);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-border">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquare size={18} className="text-primary" />
          온톨로지 브릿지 agent
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          자연어로 묻으면 의도 분석 → modeling API 호출 → layer 스캔 → 결과. <br />
          예: <code className="bg-muted px-1 rounded text-[10px]">실수율 어디서 계산?</code> / <code className="bg-muted px-1 rounded text-[10px]">SC160 변경 영향 분석</code> / <code className="bg-muted px-1 rounded text-[10px]">Step 1 시뮬해줘</code>
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {turns.length === 0 && (
          <div className="text-center text-muted-foreground text-sm py-12">
            <MessageSquare size={32} className="mx-auto mb-2 opacity-30" />
            <p>자연어로 ontology 에 대해 물어보세요.</p>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i}>
            <div className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${t.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"} rounded-lg px-4 py-2`}>
                <div className="text-sm">{t.content}</div>
                {t.events && t.events.length > 0 && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] opacity-70 hover:opacity-100">▶ trace ({t.events.length} events)</summary>
                    <div className="mt-2"><EventStreamView events={t.events} /></div>
                  </details>
                )}
              </div>
            </div>
            {t.role === "assistant" && t.followups && t.followups.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2 ml-2">
                <span className="text-[10px] text-muted-foreground self-center">💡 다음 질문:</span>
                {t.followups.map((q, j) => (
                  <button
                    key={j}
                    onClick={() => submit(q)}
                    disabled={running}
                    className="text-[11px] px-2.5 py-1 rounded-full border border-primary/30 bg-primary/5 hover:bg-primary/15 text-primary disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {activeEvents.length > 0 && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
            <div className="text-[11px] font-semibold text-primary mb-2 flex items-center gap-1">
              <Loader2 size={12} className="animate-spin" /> 처리 중...
            </div>
            <EventStreamView events={activeEvents} />
          </div>
        )}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            disabled={running}
            placeholder="자연어로 물어보세요..."
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <button
            onClick={() => submit()}
            disabled={running || !input.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            전송
          </button>
        </div>
      </div>
    </div>
  );
}
