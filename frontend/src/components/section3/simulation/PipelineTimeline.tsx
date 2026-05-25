"use client";

/**
 * 순차 ontology 호출 timeline — 한 번에 결과만 보지 않고 각 단계
 * (자연어 분석 → ontology 호출 → 보강 → 신뢰도 평가) 를 사용자가 볼 수 있게.
 *
 * 사용자 요구 (2026-05-23): "순차적으로 온톨로지 호출해서 최종 결과를 내게끔하고,
 * 사용자에게 확인받고 승인하는 과정"
 *
 * 현 구현: backend 가 한 번에 trace 를 합성해서 보내고, frontend 가 collapsible
 * timeline 으로 표시. 각 step 의 detail 펼침/접힘 + 마지막 confirm 버튼.
 */
import { useState, type ReactNode } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, Database, Cog, Sparkles, ShieldCheck, RotateCcw } from "lucide-react";

interface PipelineStep {
  step_no: number;
  title: string;
  action: string;
  result_summary: string;
  details?: Record<string, unknown>;
  evidence_kind?: string;
  duration_hint?: string;
}

interface Props {
  steps: PipelineStep[];
  onApprove?: () => void;
  onRegenerate?: () => void;
  approved?: boolean;
  regenerating?: boolean;
}

const KIND_ICON: Record<string, ReactNode> = {
  inference: <Sparkles size={11} className="text-amber-600" />,
  ontology: <Database size={11} className="text-violet-600" />,
  propagation: <Cog size={11} className="text-cyan-600" />,
  java_anchor: <Cog size={11} className="text-blue-600" />,
};

export function PipelineTimeline({ steps, onApprove, onRegenerate, approved, regenerating }: Props) {
  const [openIdx, setOpenIdx] = useState<Set<number>>(new Set([steps.length - 1]));

  if (!steps?.length) return null;

  function toggle(i: number) {
    setOpenIdx((s) => {
      const n = new Set(s);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  }

  return (
    <div className="border-2 border-slate-300 bg-gradient-to-br from-slate-50 to-white rounded-lg p-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700 text-white font-semibold">PIPELINE</span>
        <span className="text-[11px] text-slate-700 font-semibold">순차 실행 단계 ({steps.length})</span>
        <span className="text-[10px] text-slate-500 ml-auto">각 단계 클릭 → 상세</span>
      </div>

      <ol className="space-y-1.5">
        {steps.map((s, i) => {
          const isOpen = openIdx.has(i);
          const icon = KIND_ICON[s.evidence_kind ?? ""] ?? <Cog size={11} className="text-gray-500" />;
          return (
            <li key={i} className="relative">
              {/* 연결선 */}
              {i < steps.length - 1 && (
                <div className="absolute left-[10px] top-6 bottom-0 w-px bg-slate-300" />
              )}
              <button
                type="button"
                onClick={() => toggle(i)}
                className="w-full text-left flex items-start gap-2 group"
              >
                {/* step 원형 마커 */}
                <div className="relative z-10 mt-0.5 w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center flex-shrink-0 font-bold text-[11px]">
                  {s.step_no}
                </div>
                <div className="flex-1 bg-white rounded-lg border-2 border-slate-200 hover:border-slate-400 p-2.5 transition">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {isOpen ? <ChevronDown size={12} className="text-slate-500" /> : <ChevronRight size={12} className="text-slate-500" />}
                    {icon}
                    <span className="text-[13px] font-bold text-slate-900">{s.title}</span>
                    {s.duration_hint && (
                      <span className="text-[10px] text-slate-400 ml-auto">{s.duration_hint}</span>
                    )}
                  </div>
                  <div className="text-[11.5px] text-slate-700 mt-1 pl-5">{s.action}</div>
                  <div className="text-[11.5px] text-emerald-700 mt-0.5 pl-5 font-semibold">→ {s.result_summary}</div>

                  {isOpen && s.details && Object.keys(s.details).length > 0 && (
                    <div className="mt-2 pl-5">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold mb-1">상세 응답·근거</div>
                      <pre className="text-[10.5px] bg-slate-50 border border-slate-200 rounded p-2 text-slate-700 whitespace-pre-wrap max-h-56 overflow-auto leading-relaxed">
                        {JSON.stringify(s.details, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ol>

      {/* 사용자 승인 게이트 + 재생성 */}
      <div className="mt-3 pt-2 border-t border-slate-200 flex items-center gap-2 flex-wrap">
        {approved ? (
          <>
            <span className="text-[11px] text-emerald-700 flex items-center gap-1 font-semibold">
              <ShieldCheck size={13} /> 사용자 승인 완료 — 결과 확인 가능
            </span>
            {onRegenerate && (
              <button
                onClick={onRegenerate}
                disabled={regenerating}
                className="ml-auto px-3 py-1 text-[11px] rounded border border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100 disabled:opacity-50 flex items-center gap-1"
              >
                <RotateCcw size={12} className={regenerating ? "animate-spin" : ""} />
                {regenerating ? "재생성 중…" : "결과 재생성"}
              </button>
            )}
          </>
        ) : (
          <>
            <span className="text-[11px] text-slate-700">위 단계 검토 후 결과를 채택하시겠습니까?</span>
            <div className="ml-auto flex items-center gap-1.5">
              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  disabled={regenerating}
                  className="px-3 py-1 text-[11px] rounded border border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100 disabled:opacity-50 flex items-center gap-1"
                >
                  <RotateCcw size={12} className={regenerating ? "animate-spin" : ""} />
                  {regenerating ? "재생성 중…" : "재생성"}
                </button>
              )}
              {onApprove && (
                <button
                  onClick={onApprove}
                  className="px-3 py-1 text-[11px] rounded bg-emerald-600 text-white hover:bg-emerald-500 flex items-center gap-1 font-semibold"
                >
                  <CheckCircle2 size={12} /> 결과 승인
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
