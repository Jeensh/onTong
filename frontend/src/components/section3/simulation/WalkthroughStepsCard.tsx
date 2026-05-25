"use client";

/**
 * 질문에 관련된 21-step 카탈로그 카드 — walkthrough.md 포맷.
 *
 * 구조: ① 큰 그림 (질문 + 흐름 한 줄) → ② Phase 별 단계 (색칠 group)
 *      → ③ 단계 카드 (입력·공식·출력·근거 테이블) → ④ 결과 요약 표
 *      → ⑤ 핵심 흐름 직관
 *
 * backend 가 ontology 응답 + step_catalog 매칭 결과만 사용 — java/walkthrough.md 직접 참조 0.
 */
import { Workflow, ChevronRight } from "lucide-react";

interface Step {
  step_no: number | null;
  phase: string;
  phase_label: string;
  title: string;
  purpose: string;
  formula: string;
  input_terms: string[];
  output_field: string;
  action_fqn: string | null;
  base_tables: string[];
  notes: string;
}

interface Props {
  steps: Step[];
  phaseLabels?: Record<string, string>;
  insight?: string;  // backend 가 질문별 동적 합성한 인사이트 (하드코딩 제거)
}

const PHASE_META: Record<string, {
  bg: string; border: string; text: string; chip: string; chipText: string;
  emoji: string; shortName: string;
}> = {
  phase1:  {
    bg: "bg-sky-50/60",     border: "border-sky-300",     text: "text-sky-900",
    chip: "bg-sky-600",     chipText: "text-white",
    emoji: "📋",            shortName: "사전 검사·환산",
  },
  phase2a: {
    bg: "bg-emerald-50/60", border: "border-emerald-300", text: "text-emerald-900",
    chip: "bg-emerald-600", chipText: "text-white",
    emoji: "📐",            shortName: "Slab 가능 범위 좁히기",
  },
  phase2b: {
    bg: "bg-amber-50/60",   border: "border-amber-300",   text: "text-amber-900",
    chip: "bg-amber-600",   chipText: "text-white",
    emoji: "🔄",            shortName: "분할수×매수 탐색 (A-a 루프)",
  },
  phase2c: {
    bg: "bg-violet-50/60",  border: "border-violet-300",  text: "text-violet-900",
    chip: "bg-violet-600",  chipText: "text-white",
    emoji: "🎯",            shortName: "최종 폭/길이 역산",
  },
  save: {
    bg: "bg-rose-50/60",    border: "border-rose-300",    text: "text-rose-900",
    chip: "bg-rose-600",    chipText: "text-white",
    emoji: "💾",            shortName: "DB 저장",
  },
};

const PHASE_ORDER = ["phase1", "phase2a", "phase2b", "phase2c", "save"];

export function WalkthroughStepsCard({ steps, insight }: Props) {
  if (!steps?.length) return null;

  // phase 별 group
  const byPhase: Record<string, Step[]> = {};
  for (const s of steps) (byPhase[s.phase] ||= []).push(s);

  // 결과 요약표 — step 별 (단계 / 결정된 값 / 결과)
  const summaryRows = steps.map((s) => ({
    label: s.step_no !== null ? `Step ${s.step_no}` : s.phase_label.replace(/Phase \d+ — /, ""),
    decided: s.title,
    output: s.output_field,
  }));

  // 핵심 흐름 1줄 — phase 별 가장 짧은 통찰
  const insights = PHASE_ORDER
    .filter((p) => byPhase[p]?.length)
    .map((p) => {
      const meta = PHASE_META[p];
      return `${meta.emoji} ${meta.shortName}`;
    });

  return (
    <div className="border-2 border-indigo-300 bg-gradient-to-br from-indigo-50/50 to-violet-50/40 rounded-lg p-3.5 space-y-3 sim-anim-fadein">
      {/* ── 큰 그림 헤더 ────────────────────────────────────────── */}
      <div>
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <Workflow size={18} className="text-indigo-700" />
          <strong className="text-[14px] text-indigo-900">slab 설계 21단계 알고리즘 — 이 질문 관련 단계 {steps.length}개</strong>
        </div>
        <p className="text-[12px] text-indigo-700 leading-relaxed">
          주문 1건이 Slab 데이터로 변해가는 전체 흐름 중, 질문에 직접 관련된 단계만 모았습니다<br/>
          각 단계는 온톨로지(ontology)의 입력 용어·공식·출력을 그대로 가져온 것
        </p>
        {/* 흐름 chip — Phase 순서 시각화 */}
        <div className="flex items-center gap-1 flex-wrap mt-2">
          {insights.map((txt, i) => (
            <span key={i} className="inline-flex items-center gap-1">
              <span className="text-[10.5px] px-2 py-0.5 rounded-full bg-white border border-indigo-200 text-indigo-800 font-semibold">
                {txt}
              </span>
              {i < insights.length - 1 && <ChevronRight size={11} className="text-indigo-400" />}
            </span>
          ))}
        </div>
      </div>

      {/* ── Phase 별 단계 카드 ──────────────────────────────────── */}
      {PHASE_ORDER.filter((p) => byPhase[p]?.length).map((phase, pIdx) => {
        const meta = PHASE_META[phase];
        const phaseSteps = byPhase[phase];
        const phaseLabel = phaseSteps[0]?.phase_label ?? phase;
        return (
          <div
            key={phase}
            className={"rounded-lg border-2 p-3 sim-anim-fadein " + meta.border + " " + meta.bg}
            style={{ animationDelay: `${(pIdx + 1) * 120}ms` }}
          >
            <div className={"flex items-center gap-2 mb-2 " + meta.text}>
              <span className="text-lg">{meta.emoji}</span>
              <strong className="text-[12.5px] font-bold uppercase tracking-wide">{phaseLabel}</strong>
              <span className="text-[10.5px] opacity-75 ml-auto">단계 {phaseSteps.length}개</span>
            </div>
            <div className="space-y-2">
              {phaseSteps.map((s, i) => (
                <div
                  key={i}
                  className="bg-white rounded-lg p-3 border border-white shadow-sm sim-anim-fadein"
                  style={{ animationDelay: `${(pIdx + 1) * 120 + (i + 1) * 80}ms` }}
                >
                  <div className="flex items-baseline gap-1.5 flex-wrap mb-1.5">
                    {s.step_no !== null && (
                      <span className={"text-[11px] px-2 py-0.5 rounded font-bold " + meta.chip + " " + meta.chipText}>
                        Step {s.step_no}
                      </span>
                    )}
                    <strong className={"text-[14px] " + meta.text}>{s.title}</strong>
                  </div>
                  <div className="text-[12px] text-gray-800 leading-relaxed mb-1.5">
                    💡 {s.purpose}
                  </div>

                  {/* 핵심: 출력 필드만 항상 표시. 참조 기준·계산식·노트는 펼침으로 숨김 */}
                  <div className="flex items-baseline gap-1.5 mb-1.5 text-[11px]">
                    <span className="text-gray-500">→ 출력</span>
                    <code className="text-emerald-700 font-semibold">{s.output_field}</code>
                  </div>

                  {(s.base_tables.length > 0 || s.formula || s.notes) && (
                    <details className="text-[11px]">
                      <summary className="cursor-pointer text-gray-500 hover:text-gray-800 select-none">
                        ⋯ 상세 보기 (계산식·근거)
                      </summary>
                      <div className="mt-1.5 bg-gray-50/70 rounded border border-gray-200 overflow-hidden">
                        {s.base_tables.length > 0 && (
                          <div className="flex border-b border-gray-200 text-[10.5px]">
                            <div className="bg-gray-100 px-2 py-1.5 font-semibold text-gray-700 w-24 flex-shrink-0">참조 기준</div>
                            <div className="px-2 py-1.5 flex-1 flex flex-wrap gap-1">
                              {s.base_tables.map((t) => (
                                <code key={t} className="bg-white border border-gray-200 px-1.5 py-0.5 rounded text-gray-700 text-[10px]">{t}</code>
                              ))}
                            </div>
                          </div>
                        )}
                        {s.formula && (
                          <div className="flex text-[10.5px]">
                            <div className="bg-gray-100 px-2 py-1.5 font-semibold text-gray-700 w-24 flex-shrink-0">계산식</div>
                            <pre className="px-2 py-1.5 flex-1 font-mono text-gray-800 whitespace-pre-wrap leading-relaxed text-[10.5px] overflow-x-auto">{s.formula}</pre>
                          </div>
                        )}
                      </div>
                      {s.notes && (
                        <div className="text-[10.5px] text-gray-600 italic leading-relaxed pl-1 border-l-2 border-gray-300 mt-1.5">
                          ⚡ {s.notes}
                        </div>
                      )}
                    </details>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {/* ── 결과 변천 요약표 — 펼침으로 숨김 ───────────────────── */}
      <details
        className="bg-white border border-indigo-200 rounded-lg p-2.5 sim-anim-fadein"
        style={{ animationDelay: `${(PHASE_ORDER.length + 1) * 150}ms` }}
      >
        <summary className="text-[12px] font-bold text-indigo-900 cursor-pointer hover:text-indigo-700">
          📋 단계별 결정값 요약 ({summaryRows.length} 행) — 펼치기
        </summary>
        <table className="w-full text-[11px] mt-2">
          <thead className="bg-indigo-50">
            <tr className="border-b border-indigo-200 text-indigo-700">
              <th className="text-left p-1.5 font-semibold w-24">단계</th>
              <th className="text-left p-1.5 font-semibold">결정된 내용</th>
              <th className="text-left p-1.5 font-semibold w-36">출력 필드</th>
            </tr>
          </thead>
          <tbody>
            {summaryRows.map((r, i) => (
              <tr key={i} className="border-b border-gray-100">
                <td className="p-1.5"><code className="text-indigo-700 font-semibold">{r.label}</code></td>
                <td className="p-1.5 text-gray-800">{r.decided}</td>
                <td className="p-1.5"><code className="text-emerald-700 text-[10.5px]">{r.output}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>

      {/* ── 질문별 동적 인사이트 (backend 가 합성, 하드코딩 제거) ─────── */}
      {insight && (
        <div
          className="bg-gradient-to-r from-indigo-100/60 to-violet-100/40 rounded-lg p-2.5 border border-indigo-200 sim-anim-fadein"
          style={{ animationDelay: `${(PHASE_ORDER.length + 2) * 150}ms` }}
        >
          <div className="text-[11.5px] font-bold text-indigo-900 mb-1">🎯 이 질문에서 핵심으로 본 단계</div>
          <div className="text-[12px] text-indigo-800 leading-relaxed whitespace-pre-wrap">
            {insight}
          </div>
        </div>
      )}
    </div>
  );
}
