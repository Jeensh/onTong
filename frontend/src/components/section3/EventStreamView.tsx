"use client";

/**
 * agent 가 보내는 StreamEvent 들을 시간순으로 표시.
 * 4 nav 의 panel 들이 공통으로 사용.
 */

import type { StreamEvent } from "@/lib/section3/api";
import { ChevronDown, ChevronRight, Layers, Brain, Server, Code2, Play, CheckCircle2, AlertCircle, HelpCircle } from "lucide-react";
import { useState } from "react";
import { OntologyGraphSVG } from "./OntologyGraphSVG";

const EVENT_META: Record<string, { label: string; tone: string; icon: React.ReactNode }> = {
  thinking: { label: "사고 중", tone: "border-slate-300 bg-slate-50 text-slate-700", icon: <Brain size={14} /> },
  intent_classification: { label: "의도 분류", tone: "border-violet-300 bg-violet-50 text-violet-700", icon: <Brain size={14} /> },
  modeling_call: { label: "modeling 호출", tone: "border-blue-300 bg-blue-50 text-blue-700", icon: <Server size={14} /> },
  modeling_result: { label: "modeling 응답", tone: "border-blue-300 bg-blue-50 text-blue-700", icon: <Server size={14} /> },
  layer_scan: { label: "Layer 스캔", tone: "border-amber-300 bg-amber-50 text-amber-700", icon: <Layers size={14} /> },
  code_gen: { label: "코드 합성", tone: "border-emerald-300 bg-emerald-50 text-emerald-700", icon: <Code2 size={14} /> },
  sandbox_run: { label: "샌드박스 실행", tone: "border-emerald-300 bg-emerald-50 text-emerald-700", icon: <Play size={14} /> },
  sandbox_result: { label: "실행 결과", tone: "border-emerald-300 bg-emerald-50 text-emerald-700", icon: <CheckCircle2 size={14} /> },
  simv2_fixtures: { label: "W71 fixtures", tone: "border-indigo-300 bg-indigo-50 text-indigo-700", icon: <Layers size={14} /> },
  simv2_stubs: { label: "W74 stubs", tone: "border-indigo-300 bg-indigo-50 text-indigo-700", icon: <Layers size={14} /> },
  simv2_baseline: { label: "Java baseline", tone: "border-indigo-300 bg-indigo-50 text-indigo-700", icon: <Layers size={14} /> },
  simv2_suggestions: { label: "sim_v2 후보", tone: "border-violet-300 bg-violet-50 text-violet-700", icon: <HelpCircle size={14} /> },
  final: { label: "최종 결과", tone: "border-primary bg-primary/5 text-primary", icon: <CheckCircle2 size={14} /> },
  error: { label: "오류", tone: "border-red-300 bg-red-50 text-red-700", icon: <AlertCircle size={14} /> },
  need_more_info: { label: "추가 정보 필요", tone: "border-amber-400 bg-amber-100 text-amber-800", icon: <HelpCircle size={14} /> },
};

export function EventStreamView({ events }: { events: StreamEvent[] }) {
  return (
    <div className="space-y-2">
      {events.map((ev, i) => (
        <EventCard key={i} event={ev} />
      ))}
    </div>
  );
}

function EventCard({ event }: { event: StreamEvent }) {
  const meta = EVENT_META[event.type] ?? {
    label: event.type,
    tone: "border-border bg-muted",
    icon: <Layers size={14} />,
  };
  const [open, setOpen] = useState(event.type === "final" || event.type === "error" || event.type === "need_more_info");

  return (
    <div className={`rounded-md border ${meta.tone}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-2 px-3 py-2 text-left"
      >
        <span className="flex-shrink-0 mt-0.5">{open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</span>
        <span className="flex-shrink-0 mt-0.5">{meta.icon}</span>
        <span className="text-[12px] font-semibold flex-shrink-0">{meta.label}</span>
        <span className="flex-1 min-w-0 text-[11px] opacity-80 truncate ml-2">{summarize(event)}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 text-[11px] space-y-2">
          <EventBody event={event} />
        </div>
      )}
    </div>
  );
}

function summarize(ev: StreamEvent): string {
  switch (ev.type) {
    case "thinking": return ev.payload.message;
    case "intent_classification": return `${ev.payload.modeling_intent} (conf ${ev.payload.confidence.toFixed(2)})`;
    case "modeling_call": return `intent=${ev.payload.intent}`;
    case "modeling_result": return ev.payload.response?.result && typeof ev.payload.response.result === "object" && "summary" in ev.payload.response.result ? String(ev.payload.response.result.summary) : ev.payload.response?.status ?? "";
    case "layer_scan": return `${ev.payload.layer} (${ev.payload.items?.length ?? 0}건)`;
    case "code_gen": return `${ev.payload.source?.split("\n").length ?? 0} 줄 Python 합성`;
    case "sandbox_run": return ev.payload.message;
    case "sandbox_result": return `${Array.isArray(ev.payload.result) ? ev.payload.result.length : 0} 케이스`;
    case "simv2_fixtures": return `${ev.payload.count}개 (W71 합성, primitive ${ev.payload.synthesizable}/skip ${ev.payload.skipped})`;
    case "simv2_stubs": return `${ev.payload.count}개 stub (anchor + AST + entity)`;
    case "simv2_baseline": return `Java baseline ${ev.payload.entries}건 부착`;
    case "simv2_suggestions": return `${ev.payload.count}개 후보`;
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
        <div className="space-y-1">
          <div><b>intent:</b> {event.payload.modeling_intent}</div>
          <div><b>parameters:</b> <code className="text-[10px]">{JSON.stringify(event.payload.parameters)}</code></div>
          <div><b>reasoning:</b> {event.payload.reasoning}</div>
          {event.payload.suggested_followups?.length > 0 && (
            <div><b>다음 질문:</b> <ul className="list-disc pl-5">{event.payload.suggested_followups.map((s, i) => <li key={i}>{s}</li>)}</ul></div>
          )}
        </div>
      );
    case "modeling_call":
      return <pre className="bg-background border rounded p-2 overflow-x-auto text-[10px]">POST /api/modeling/ontology/query{"\n"}{JSON.stringify({intent: event.payload.intent, parameters: event.payload.parameters}, null, 2)}</pre>;
    case "modeling_result":
      return <pre className="bg-background border rounded p-2 overflow-x-auto text-[10px] max-h-72">{JSON.stringify(event.payload.response, null, 2)}</pre>;
    case "layer_scan":
      return (
        <div>
          <div className="font-semibold mb-1">{event.payload.layer}</div>
          <ul className="list-disc pl-5 space-y-0.5">
            {event.payload.items?.slice(0, 12).map((it, i) => (
              <li key={i}><code className="text-[10px]">{JSON.stringify(it)}</code></li>
            ))}
            {event.payload.items?.length > 12 && <li className="text-muted-foreground">... +{event.payload.items.length - 12} more</li>}
          </ul>
        </div>
      );
    case "code_gen":
      return (
        <pre className="bg-slate-900 text-slate-100 rounded p-2 overflow-x-auto text-[10px] max-h-72">
          <code>{event.payload.source}</code>
        </pre>
      );
    case "simv2_suggestions":
      return (
        <div className="space-y-2">
          <div className="text-[11px] text-muted-foreground">
            자연어 query: <code>{event.payload.query}</code>
          </div>
          {(event.payload.suggestions ?? []).map((s: any, i: number) => (
            <div key={i} className="rounded border bg-background p-2 text-[11px]">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold">{s.label}</span>
                <span className="font-mono text-[10px] text-muted-foreground">{s.action_fqn}</span>
                <span className="text-[10px] text-violet-700 bg-violet-100 px-1.5 py-0.5 rounded">{s.matched_via}</span>
                <span className="text-[10px] text-muted-foreground">score={s.score?.toFixed(1)}</span>
              </div>
              {s.code_method_fqn && (
                <div className="mt-1 text-[10px] font-mono text-muted-foreground break-all">{s.code_method_fqn}</div>
              )}
              {s.diagnostic && (
                <div className="mt-1 flex items-center gap-3 text-[10px]">
                  <span className={s.diagnostic.passing > 0 ? "text-emerald-700" : "text-rose-700"}>
                    invariant {s.diagnostic.passing}/{s.diagnostic.fixtures} PASS
                  </span>
                  <span className="text-muted-foreground">stubs {s.diagnostic.stubs}</span>
                  {s.diagnostic.primary_failure && (
                    <span className="text-amber-700">{s.diagnostic.primary_failure}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      );
    case "simv2_fixtures":
    case "simv2_stubs":
    case "simv2_baseline":
      return (
        <pre className="text-[10px] font-mono whitespace-pre-wrap break-all">
          {JSON.stringify(event.payload, null, 2)}
        </pre>
      );
    case "sandbox_result":
      return (
        <div className="space-y-2">
          {Array.isArray(event.payload.result) && event.payload.result.map((c: any, i: number) => (
            <div key={i} className="rounded border bg-background p-2">
              <div className="flex items-center gap-2 text-[11px] flex-wrap">
                {c.case_type && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${c.case_type === 'normal' ? 'bg-emerald-100 text-emerald-700' : c.case_type === 'boundary' ? 'bg-amber-100 text-amber-700' : c.case_type === 'synthesized' ? 'bg-indigo-100 text-indigo-700' : 'bg-red-100 text-red-700'}`}>{c.case_type}</span>
                )}
                <span className="font-mono">{c.case_id}</span>
                <span className={c.execution?.ok ? "text-emerald-600" : "text-red-600"}>{c.execution?.ok ? "✓ ok" : "✗ fail"}</span>
                <span className="text-muted-foreground text-[10px]">{c.execution?.elapsed_sec}s</span>
                {c.invariant_status && (
                  <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${c.invariant_status === 'PASS' ? 'bg-emerald-50 text-emerald-700' : c.invariant_status === 'UNVERIFIED' ? 'bg-slate-100 text-slate-600' : 'bg-rose-50 text-rose-700'}`}>{c.invariant_status}</span>
                )}
                {c.output_match === true && <span className="text-emerald-600 text-[10px]">expected 일치</span>}
                {c.output_match === false && <span className="text-red-600 text-[10px]">expected 불일치</span>}
                {c.matched_expected === true && c.output_match === undefined && <span className="text-emerald-600 text-[10px]">expected 일치</span>}
                {c.matched_expected === false && c.output_match === undefined && <span className="text-red-600 text-[10px]">expected 불일치</span>}
              </div>
              <div className="grid grid-cols-3 gap-1 mt-1 text-[10px]">
                <div><b>input:</b> <code>{JSON.stringify(c.input)}</code></div>
                <div><b>expected:</b> <code>{c.expected_value === undefined || c.expected_value === null ? "—" : JSON.stringify(c.expected_value)}</code></div>
                <div><b>actual:</b> <code>{c.actual_value !== undefined ? JSON.stringify(c.actual_value) : JSON.stringify(c.execution?.result)}</code></div>
              </div>
              {c.diff_summary && <div className="mt-1 text-[9px] text-amber-700 break-all">⚠ {c.diff_summary}</div>}
              {c.execution?.stderr && <div className="mt-1 text-[9px] text-red-600 font-mono break-all">{c.execution.stderr}</div>}
            </div>
          ))}
        </div>
      );
    case "final":
      return (
        <div className="space-y-3">
          <div className="text-sm font-semibold text-foreground bg-primary/10 rounded p-2 border border-primary/20">
            ✅ {event.payload.summary}
          </div>
          {event.payload.visualization?.nodes && event.payload.visualization.nodes.length > 0 && (
            <div>
              <div className="text-[11px] font-semibold text-muted-foreground mb-1 uppercase tracking-wide">
                🗺 Ontology Graph — {event.payload.visualization.nodes.length} nodes · {event.payload.visualization.edges?.length ?? 0} edges
              </div>
              <OntologyGraphSVG
                nodes={event.payload.visualization.nodes}
                edges={event.payload.visualization.edges ?? []}
                cypher={event.payload.visualization.cypher}
              />
            </div>
          )}
          {event.payload.generated_python && (
            <details>
              <summary className="cursor-pointer text-muted-foreground text-[11px] font-medium">▶ 합성된 Python 코드</summary>
              <pre className="mt-1 bg-slate-900 text-slate-100 rounded p-2 overflow-x-auto text-[10px]">
                <code>{event.payload.generated_python}</code>
              </pre>
            </details>
          )}
        </div>
      );
    case "error":
      return <div className="text-red-600">{event.payload.message}</div>;
    case "need_more_info":
      return (
        <div>
          <div className="font-semibold mb-1">{event.payload.missing_info?.reason}</div>
          {event.payload.missing_info?.questions?.map((q, i) => (
            <div key={i} className="mt-2 p-2 bg-background border rounded">
              <div className="text-[11px]">{q.question}</div>
              {q.options && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {q.options.map((o) => (
                    <span key={o.id} className="text-[10px] px-1.5 py-0.5 rounded border bg-amber-50">{o.label} (<code>{o.id}</code>)</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      );
    default:
      return <pre className="text-[10px] bg-background border rounded p-2 overflow-x-auto">{JSON.stringify(event.payload, null, 2)}</pre>;
  }
}
