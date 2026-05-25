"use client";

/**
 * 신뢰도 source breakdown bar — 카드 전체의 ontology / business_rule / seed /
 * inference / propagation / assumption 비율을 stacked bar 로 보여주고,
 * 종합 confidence chip + 각 field 별 근거 details 펼침.
 *
 * 사용자 요구 (2026-05-23): "온톨로지 근거 몇 프로? AI 분석 결과 몇 프로?
 * 추측 vs 사실 표시. hover 하면 근거가 보이게."
 */
import { useState } from "react";
import { ChevronDown, ChevronRight, ShieldCheck, ShieldAlert } from "lucide-react";

interface EvidenceItem {
  kind: string;
  summary: string;
  confidence: number;
  source_ref?: string | null;
  detail?: string | null;
}

interface EvidenceData {
  overall_confidence: number;
  source_breakdown_pct: Record<string, number>;
  fields: Record<string, EvidenceItem[]>;
}

const KIND_META: Record<string, { label: string; color: string; bg: string; text: string }> = {
  ontology:      { label: "ontology",     color: "#7c3aed", bg: "bg-violet-500",   text: "text-violet-700" },
  business_rule: { label: "rule",         color: "#dc2626", bg: "bg-red-500",      text: "text-red-700" },
  seed_data:     { label: "seed",         color: "#059669", bg: "bg-emerald-500",  text: "text-emerald-700" },
  java_anchor:   { label: "java",         color: "#2563eb", bg: "bg-blue-500",     text: "text-blue-700" },
  propagation:   { label: "propagation",  color: "#0891b2", bg: "bg-cyan-500",     text: "text-cyan-700" },
  inference:     { label: "AI 추론",       color: "#d97706", bg: "bg-amber-500",    text: "text-amber-700" },
  assumption:    { label: "가정",          color: "#6b7280", bg: "bg-gray-400",     text: "text-gray-600" },
};

function _confidenceLevel(conf: number): { label: string; color: string; cls: string } {
  if (conf >= 0.85) return { label: "높음 (사실 근거)", color: "#059669", cls: "bg-emerald-50 text-emerald-800 border-emerald-300" };
  if (conf >= 0.7)  return { label: "중간 (혼합)",      color: "#0891b2", cls: "bg-cyan-50 text-cyan-800 border-cyan-300" };
  if (conf >= 0.5)  return { label: "보통 (일부 추론)",  color: "#d97706", cls: "bg-amber-50 text-amber-800 border-amber-300" };
  return                  { label: "낮음 (추측 위주)",   color: "#6b7280", cls: "bg-gray-100 text-gray-700 border-gray-300" };
}

export function EvidenceBar({ evidence }: { evidence: EvidenceData }) {
  const [open, setOpen] = useState(false);
  const conf = evidence.overall_confidence;
  const confLevel = _confidenceLevel(conf);
  const breakdown = evidence.source_breakdown_pct ?? {};
  const entries = Object.entries(breakdown).filter(([_, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="border border-gray-200 rounded-lg bg-gradient-to-br from-slate-50 to-white p-2.5">
      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1 text-[11px] text-gray-700 hover:text-gray-900"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          <span className="font-semibold">근거 신뢰도</span>
        </button>
        <span className={"text-[10.5px] px-2 py-0.5 rounded border flex items-center gap-1 " + confLevel.cls}>
          {conf >= 0.7 ? <ShieldCheck size={11} /> : <ShieldAlert size={11} />}
          종합 {(conf * 100).toFixed(0)}% · {confLevel.label}
        </span>
        <span className="text-[10px] text-gray-500 ml-auto">
          {Object.values(evidence.fields).reduce((acc, v) => acc + v.length, 0)}개 근거 항목
        </span>
      </div>

      {/* stacked bar — 소스 종류별 비율 */}
      {entries.length > 0 && (
        <div className="mt-2 flex h-2 rounded-full overflow-hidden border border-gray-200 bg-gray-50" title="source 비율">
          {entries.map(([k, v]) => {
            const meta = KIND_META[k] ?? { bg: "bg-gray-400", label: k, color: "#999", text: "text-gray-600" };
            return (
              <div
                key={k}
                className={meta.bg + " transition"}
                style={{ width: `${v}%` }}
                title={`${meta.label}: ${v}%`}
              />
            );
          })}
        </div>
      )}

      {/* 범례 */}
      <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
        {entries.map(([k, v]) => {
          const meta = KIND_META[k] ?? { label: k, color: "#999", text: "text-gray-600", bg: "bg-gray-400" };
          return (
            <span key={k} className={"inline-flex items-center gap-1 " + meta.text}>
              <span className={"w-2 h-2 rounded-sm " + meta.bg} />
              <span className="font-semibold">{meta.label}</span>
              <span className="text-gray-500">{v}%</span>
            </span>
          );
        })}
      </div>

      {/* 펼침 — field 별 근거 list */}
      {open && (
        <div className="mt-2 border-t border-gray-200 pt-2 space-y-2 max-h-72 overflow-y-auto">
          {Object.entries(evidence.fields).map(([fieldPath, evs]) => (
            <div key={fieldPath} className="text-[10.5px]">
              <div className="font-mono text-gray-700 mb-0.5">
                <code className="bg-gray-100 px-1 rounded">{fieldPath}</code>
                <span className="text-gray-400 ml-1">({evs.length})</span>
              </div>
              <ul className="ml-2 space-y-0.5">
                {evs.slice(0, 8).map((e, i) => {
                  const meta = KIND_META[e.kind] ?? { label: e.kind, bg: "bg-gray-400", color: "#999", text: "text-gray-600" };
                  return (
                    <li key={i} className="flex items-start gap-1.5 group">
                      <span className={"text-[9px] px-1 rounded font-semibold " + meta.bg + " text-white flex-shrink-0"}>
                        {meta.label}
                      </span>
                      <span className="text-gray-700 flex-1">{e.summary}</span>
                      <span className={"text-[9px] flex-shrink-0 " + (
                        e.confidence >= 0.85 ? "text-emerald-700" :
                        e.confidence >= 0.7  ? "text-cyan-700" :
                        e.confidence >= 0.5  ? "text-amber-700" : "text-gray-500"
                      )}>{(e.confidence * 100).toFixed(0)}%</span>
                      {e.source_ref && (
                        <code className="text-[9px] text-gray-500 max-w-[180px] truncate" title={e.source_ref}>
                          {e.source_ref}
                        </code>
                      )}
                      {e.detail && (
                        <details className="ml-1">
                          <summary className="cursor-pointer text-gray-400 hover:text-gray-700 text-[9px]">+근거</summary>
                          <pre className="mt-0.5 text-[9px] bg-yellow-50 border border-yellow-200 rounded p-1 text-gray-700 whitespace-pre-wrap max-w-md">
                            {e.detail}
                          </pre>
                        </details>
                      )}
                    </li>
                  );
                })}
                {evs.length > 8 && (
                  <li className="text-[9px] text-gray-500 italic">... +{evs.length - 8} 건</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
