"use client";

/**
 * 모던 timeline 형 stream event 표시.
 *
 * - 좌측에 phase dot (연결선) — 진행/완료/실패 시각화
 * - 각 phase 별 풍부한 내용 (modeling_call 시 endpoint + params, layer_scan 시 데이터 chip,
 *   code_gen 시 코드 syntax highlight 등)
 * - "현재 진행 중" 인 phase 는 pulse 애니메이션
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, Brain, Server, Layers, Code2, Play, CheckCircle2, AlertCircle, HelpCircle, Sparkles, Zap } from "lucide-react";
import type { StreamEvent } from "@/lib/section3/api";
import { CodeBlock } from "./CodeBlock";
import { DataTable } from "./DataTable";

interface Props {
  events: StreamEvent[];
  /** true 면 마지막 event 를 "진행 중" 으로 표시 (pulse). */
  active?: boolean;
}

const EVENT_META: Record<string, { label: string; tone: string; ringTone: string; icon: React.ReactNode }> = {
  thinking: { label: "사고", tone: "bg-slate-500", ringTone: "ring-slate-300", icon: <Brain size={12} /> },
  intent_classification: { label: "의도 분류", tone: "bg-violet-500", ringTone: "ring-violet-300", icon: <Sparkles size={12} /> },
  modeling_call: { label: "ontology 호출", tone: "bg-blue-500", ringTone: "ring-blue-300", icon: <Server size={12} /> },
  modeling_result: { label: "ontology 응답", tone: "bg-blue-500", ringTone: "ring-blue-300", icon: <Server size={12} /> },
  layer_scan: { label: "Layer 스캔", tone: "bg-amber-500", ringTone: "ring-amber-300", icon: <Layers size={12} /> },
  code_gen: { label: "Python 합성", tone: "bg-emerald-500", ringTone: "ring-emerald-300", icon: <Code2 size={12} /> },
  sandbox_run: { label: "Sandbox 실행", tone: "bg-emerald-600", ringTone: "ring-emerald-300", icon: <Play size={12} /> },
  sandbox_result: { label: "실행 결과", tone: "bg-emerald-600", ringTone: "ring-emerald-300", icon: <Zap size={12} /> },
  final: { label: "완료", tone: "bg-primary", ringTone: "ring-primary/30", icon: <CheckCircle2 size={12} /> },
  error: { label: "오류", tone: "bg-red-500", ringTone: "ring-red-300", icon: <AlertCircle size={12} /> },
  need_more_info: { label: "추가 정보 필요", tone: "bg-amber-500", ringTone: "ring-amber-300", icon: <HelpCircle size={12} /> },
};

export function StreamTimeline({ events, active = false }: Props) {
  if (events.length === 0) return null;

  return (
    <div className="relative">
      {/* vertical connection line */}
      <div className="absolute left-3 top-3 bottom-3 w-px bg-border" aria-hidden />

      <div className="space-y-1.5">
        {events.map((ev, i) => {
          const isLast = i === events.length - 1;
          const isActive = active && isLast && ev.type !== "final" && ev.type !== "error" && ev.type !== "need_more_info";
          return <TimelineRow key={i} event={ev} index={i} active={isActive} />;
        })}
      </div>
    </div>
  );
}

function TimelineRow({ event, index, active }: { event: StreamEvent; index: number; active: boolean }) {
  const meta = EVENT_META[event.type] ?? EVENT_META.thinking;
  const hasBody = canExpand(event);
  const [open, setOpen] = useState(() =>
    event.type === "final" || event.type === "error" || event.type === "need_more_info" || event.type === "code_gen" || event.type === "layer_scan"
  );

  return (
    <div className="relative pl-9">
      {/* dot */}
      <div className={`absolute left-0 top-1 w-6 h-6 rounded-full flex items-center justify-center text-white ${meta.tone} ${active ? `ring-4 ${meta.ringTone} animate-pulse` : "ring-2 ring-background"}`}>
        {meta.icon}
      </div>

      {/* card */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <button
          onClick={() => hasBody && setOpen(!open)}
          className={`w-full flex items-center gap-2 px-3 py-2 text-left ${hasBody ? "hover:bg-muted/50" : ""} transition-colors`}
        >
          {hasBody && <span className="text-muted-foreground">{open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</span>}
          <span className="text-[11px] font-semibold">{meta.label}</span>
          <span className="flex-1 min-w-0 text-[11px] text-muted-foreground truncate">{summarize(event)}</span>
          {active && <span className="text-[9px] text-primary animate-pulse">●</span>}
        </button>
        {open && hasBody && (
          <div className="border-t border-border bg-muted/30 p-3">
            <EventBody event={event} />
          </div>
        )}
      </div>
    </div>
  );
}

function canExpand(ev: StreamEvent): boolean {
  return ev.type !== "thinking" && ev.type !== "sandbox_run";
}

function summarize(ev: StreamEvent): string {
  switch (ev.type) {
    case "thinking": return ev.payload.message;
    case "intent_classification": return `${ev.payload.modeling_intent} · conf ${ev.payload.confidence.toFixed(2)}`;
    case "modeling_call": return `intent=${ev.payload.intent}`;
    case "modeling_result": {
      const r = ev.payload.response?.result as any;
      return r?.summary ?? ev.payload.response?.status ?? "";
    }
    case "layer_scan": return `${ev.payload.layer} — ${ev.payload.items?.length ?? 0}건`;
    case "code_gen": return `${ev.payload.source?.split("\n").length ?? 0} 줄`;
    case "sandbox_run": return ev.payload.message;
    case "sandbox_result": return `${Array.isArray(ev.payload.result) ? ev.payload.result.length : 0} 케이스 실행 완료`;
    case "final": return ev.payload.summary;
    case "error": return ev.payload.message;
    case "need_more_info": return ev.payload.missing_info?.reason ?? "추가 정보 필요";
    default: return "";
  }
}

function EventBody({ event }: { event: StreamEvent }) {
  switch (event.type) {
    case "intent_classification":
      return (
        <div className="space-y-2 text-[11px]">
          <div className="flex flex-wrap gap-1.5">
            <Chip color="violet">intent: {event.payload.modeling_intent}</Chip>
            <Chip color="slate">conf: {event.payload.confidence.toFixed(2)}</Chip>
          </div>
          {Object.keys(event.payload.parameters || {}).length > 0 && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-1">parameters</div>
              <CodeBlock code={JSON.stringify(event.payload.parameters, null, 2)} language="json" maxHeight={120} showLineNumbers={false} />
            </div>
          )}
          {event.payload.reasoning && (
            <div className="text-[11px] italic text-foreground/80">💭 {event.payload.reasoning}</div>
          )}
        </div>
      );
    case "modeling_call":
      return (
        <div className="space-y-2 text-[11px]">
          <div className="flex items-center gap-1.5">
            <Chip color="blue">POST</Chip>
            <code className="text-[10px]">/api/modeling/ontology/query</code>
          </div>
          <CodeBlock
            code={JSON.stringify({ intent: event.payload.intent, parameters: event.payload.parameters }, null, 2)}
            language="json"
            maxHeight={150}
            showLineNumbers={false}
          />
        </div>
      );
    case "modeling_result": {
      const resp = event.payload.response;
      return (
        <div className="space-y-2 text-[11px]">
          <div className="flex items-center gap-1.5">
            <Chip color={resp?.status === "success" ? "emerald" : resp?.status === "error" ? "red" : "slate"}>{resp?.status}</Chip>
            {typeof resp?.confidence === "number" && <Chip color="slate">conf {resp.confidence.toFixed(2)}</Chip>}
          </div>
          <details>
            <summary className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">▶ raw response</summary>
            <div className="mt-1">
              <CodeBlock code={JSON.stringify(resp, null, 2)} language="json" maxHeight={300} />
            </div>
          </details>
        </div>
      );
    }
    case "layer_scan": {
      const items = event.payload.items || [];
      if (items.length === 0) return <div className="text-xs text-muted-foreground italic">항목 없음.</div>;
      // dict-like items 면 DataTable, 아니면 chip list
      const sample = items[0];
      if (sample && typeof sample === "object" && !Array.isArray(sample)) {
        return <DataTable rows={items as any} compact maxRows={10} />;
      }
      return (
        <div className="flex flex-wrap gap-1">
          {items.slice(0, 20).map((it, i) => (
            <span key={i} className="text-[10px] bg-amber-50 border border-amber-200 text-amber-800 px-2 py-0.5 rounded">{String(it)}</span>
          ))}
        </div>
      );
    }
    case "code_gen":
      return <CodeBlock code={event.payload.source} language="python" filename="agent_generated.py" maxHeight={300} />;
    case "sandbox_result": {
      const cases = (event.payload.result as any[]) || [];
      return (
        <DataTable
          rows={cases.map((c) => ({
            case_id: c.case_id,
            case_type: c.case_type,
            ok: c.execution?.ok,
            matched: c.matched_expected,
            input: c.input,
            result: c.execution?.result,
            elapsed_sec: c.execution?.elapsed_sec,
          }))}
          preferredColumns={["case_id", "case_type", "ok", "matched", "input", "result", "elapsed_sec"]}
          renderCell={{
            case_type: (v) => {
              const tone: Record<string, string> = {
                normal: "bg-emerald-100 text-emerald-700",
                boundary: "bg-amber-100 text-amber-700",
                error: "bg-red-100 text-red-700",
              };
              return <span className={`px-1.5 py-0 rounded text-[9px] font-bold ${tone[String(v)] || "bg-muted"}`}>{String(v)}</span>;
            },
            ok: (v) => v ? <span className="text-emerald-600">✓</span> : <span className="text-red-600">✗</span>,
            matched: (v) => v == null ? <span className="text-muted-foreground">—</span> : v ? <span className="text-emerald-600">✓</span> : <span className="text-amber-600">≠</span>,
            input: (v) => <code className="text-[9px]">{JSON.stringify(v)}</code>,
            result: (v) => <code className="text-[9px]">{JSON.stringify(v)}</code>,
          }}
          compact
        />
      );
    }
    case "need_more_info": {
      const mi = event.payload.missing_info;
      return (
        <div className="space-y-2 text-[11px]">
          <div className="font-semibold text-amber-700">{mi?.reason}</div>
          {mi?.questions?.map((q, i) => (
            <div key={i} className="rounded border border-amber-200 bg-amber-50 p-2">
              <div className="text-[11px] font-medium">{q.question}</div>
              {q.options && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {q.options.map((o) => (
                    <span key={o.id} className="text-[10px] px-2 py-0.5 rounded-full bg-white border border-amber-300 text-amber-800">{o.label} <code className="opacity-60">{o.id}</code></span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      );
    }
    case "error":
      return <div className="text-[11px] text-red-700">{event.payload.message}</div>;
    case "final":
      return <div className="text-[11px] text-foreground">{event.payload.summary}</div>;
    default:
      return <CodeBlock code={JSON.stringify(event.payload, null, 2)} language="json" maxHeight={200} showLineNumbers={false} />;
  }
}

function Chip({ color, children }: { color: "blue" | "violet" | "emerald" | "red" | "slate" | "amber"; children: React.ReactNode }) {
  const tone = {
    blue: "bg-blue-100 text-blue-700 border-blue-300",
    violet: "bg-violet-100 text-violet-700 border-violet-300",
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-300",
    red: "bg-red-100 text-red-700 border-red-300",
    slate: "bg-slate-100 text-slate-700 border-slate-300",
    amber: "bg-amber-100 text-amber-700 border-amber-300",
  }[color];
  return <span className={`text-[10px] px-2 py-0.5 rounded-full border font-mono ${tone}`}>{children}</span>;
}
