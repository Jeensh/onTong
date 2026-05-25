"use client";

/**
 * Provenance surface — Q5 비전 "확실한 근거 보면서 진행".
 *
 * 모든 GateCard footer 에 깔리는 컴포넌트. sources: list[Provenance] 을 받아서
 * source 별 색상 칩 + confidence + detail tooltip.
 */

import { Database, Cpu, Brain, User } from "lucide-react";
import type { Provenance } from "@/lib/section3/multiturn";

const SOURCE_META = {
  ontology: {
    label: "ontology",
    icon: <Database size={11} />,
    cls: "bg-blue-50 text-blue-700 border-blue-200",
  },
  sim_v2: {
    label: "sim_v2",
    icon: <Cpu size={11} />,
    cls: "bg-purple-50 text-purple-700 border-purple-200",
  },
  llm_inference: {
    label: "LLM",
    icon: <Brain size={11} />,
    cls: "bg-amber-50 text-amber-700 border-amber-200",
  },
  user_input: {
    label: "user",
    icon: <User size={11} />,
    cls: "bg-gray-50 text-gray-600 border-gray-200",
  },
} as const;

function confidenceColor(c: number | null): string {
  if (c === null) return "text-gray-500";
  if (c >= 0.7) return "text-emerald-600";
  if (c >= 0.4) return "text-amber-600";
  return "text-rose-600";
}

export function ProvenanceBadge({ source }: { source: Provenance }) {
  const meta = SOURCE_META[source.source];
  return (
    <span
      title={source.detail}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono ${meta.cls}`}
    >
      {meta.icon}
      <span>{meta.label}</span>
      {source.confidence !== null && (
        <span className={`font-semibold ${confidenceColor(source.confidence)}`}>
          {Math.round(source.confidence * 100)}%
        </span>
      )}
    </span>
  );
}

export function ProvenanceRow({ sources }: { sources: Provenance[] }) {
  if (!sources?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 mt-2 pt-2 border-t border-border/50">
      <span className="text-[9px] uppercase text-muted-foreground/70 font-medium tracking-wider mr-1">
        근거
      </span>
      {sources.map((s, i) => (
        <ProvenanceBadge key={i} source={s} />
      ))}
    </div>
  );
}
