"use client";

// 우측 영향도 분석 패널 — 설계 프로세스 SEQ별 체크 트리 + 범위 초과 경고

import { useState } from "react";
import type { SlabDesignResult, SlabDesignStep } from "@/lib/simulation/types";

interface Props {
  result: SlabDesignResult | null;
  isCalculating: boolean;
}

const STATUS_ICON: Record<string, string> = {
  ok:      "✅",
  warning: "⚠️",
  error:   "🔴",
};

const STATUS_TEXT_CLS: Record<string, string> = {
  ok:      "text-green-400",
  warning: "text-yellow-400",
  error:   "text-red-400",
};

const STATUS_BG_CLS: Record<string, string> = {
  ok:      "bg-green-900/20 border-green-800/40",
  warning: "bg-yellow-900/20 border-yellow-700/40",
  error:   "bg-red-900/20 border-red-700/40",
};

// ── 단계 상세 데이터 렌더링 ───────────────────────────────────────────

function StepDetails({ step }: { step: SlabDesignStep }) {
  const result = step.result as Record<string, unknown>;

  // width_range, length_range, weight_range 등 주요 결과값 표시
  const entries = Object.entries(result).filter(([k]) => !k.startsWith("_"));

  return (
    <div className="mt-1.5 pl-2 border-l border-slate-700 space-y-0.5">
      {entries.map(([key, val]) => {
        if (val && typeof val === "object" && "lower" in (val as object)) {
          const r = val as { lower: number; upper: number };
          return (
            <div key={key} className="text-[10px] text-slate-400">
              <span className="text-slate-500">{key}: </span>
              {r.lower.toLocaleString()} ~ {r.upper.toLocaleString()}
            </div>
          );
        }
        return (
          <div key={key} className="text-[10px] text-slate-400">
            <span className="text-slate-500">{key}: </span>
            {typeof val === "number"
              ? val > 1000 ? val.toLocaleString() : val
              : String(val)}
          </div>
        );
      })}
      {step.details && Object.keys(step.details).length > 0 && (
        <div className="text-[10px] text-orange-400 mt-0.5">
          {Object.entries(step.details).map(([k, v]) => (
            <span key={k} className="mr-2">
              {k}: {typeof v === "number" ? v.toLocaleString() : String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 단계 행 ──────────────────────────────────────────────────────────

function StepRow({ step }: { step: SlabDesignStep }) {
  const [expanded, setExpanded] = useState(step.status !== "ok");

  return (
    <div
      className={`rounded border text-xs ${STATUS_BG_CLS[step.status]} cursor-pointer select-none`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex items-start gap-1.5 p-2">
        <span className="flex-shrink-0 mt-0.5">{STATUS_ICON[step.status]}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className="text-slate-500 text-[10px]">SEQ{step.seq}.</span>
            <span className={`font-medium ${STATUS_TEXT_CLS[step.status]}`}>{step.name}</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5 leading-relaxed">{step.message}</div>
          {expanded && <StepDetails step={step} />}
        </div>
        <span className="text-slate-600 text-[10px] flex-shrink-0">{expanded ? "▲" : "▼"}</span>
      </div>
    </div>
  );
}

// ── 설계 가부 배지 ────────────────────────────────────────────────────

function FeasibilityBadge({ result }: { result: SlabDesignResult }) {
  const cfg = {
    ok:      { bg: "bg-blue-600", text: "✅ 설계 가능", sub: "모든 SEQ 통과" },
    warning: { bg: "bg-yellow-600", text: "⚠️ 경고", sub: "일부 파라미터 경계 근접" },
    error:   { bg: "bg-red-700",  text: "🔴 설계 불가", sub: "SEQ 통과 실패" },
  }[result.overall_status] ?? { bg: "bg-slate-700", text: "-", sub: "" };

  return (
    <div className={`rounded-lg ${cfg.bg} px-3 py-2 flex items-center justify-between`}>
      <div>
        <div className="text-white text-xs font-semibold">{cfg.text}</div>
        <div className="text-white/70 text-[10px]">{cfg.sub}</div>
      </div>
      <div className="text-right">
        <div className="text-white/70 text-[10px]">통과 SEQ</div>
        <div className="text-white text-xs font-semibold">
          {result.steps.filter((s) => s.status === "ok").length} /
          {result.steps.length}
        </div>
      </div>
    </div>
  );
}

// ── 요약 수치 ─────────────────────────────────────────────────────────

function SummaryRow({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="flex justify-between text-[11px]">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-200 font-mono">
        {typeof value === "number" ? value.toLocaleString() : value}
        {unit && <span className="text-slate-500 ml-0.5">{unit}</span>}
      </span>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────

export function SlabImpactPanel({ result, isCalculating }: Props) {
  if (isCalculating) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-950 text-slate-500 text-sm">
        <div className="text-center space-y-2">
          <div className="text-2xl animate-spin">⚙️</div>
          <div>계산 중…</div>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex items-center justify-center h-full bg-slate-950 text-slate-600 text-sm">
        파라미터를 조작하면 결과가 표시됩니다
      </div>
    );
  }

  const { summary } = result;

  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-100 overflow-y-auto">
      {/* 헤더 */}
      <div className="px-3 pt-3 pb-2 border-b border-slate-800">
        <span className="text-xs font-semibold text-slate-300 tracking-wide uppercase">
          영향도 분석
        </span>
      </div>

      <div className="flex-1 p-3 space-y-3 overflow-y-auto">
        {/* 설계 가부 배지 */}
        <FeasibilityBadge result={result} />

        {/* 계산 요약 */}
        <div className="bg-slate-900 rounded-lg p-2.5 space-y-1.5">
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wide mb-2">
            계산 요약
          </div>
          <SummaryRow
            label="1차 폭범위"
            value={`${summary.width_range.lower.toLocaleString()} ~ ${summary.width_range.upper.toLocaleString()}`}
            unit="mm"
          />
          <SummaryRow
            label="1차 길이범위"
            value={`${summary.length_range.lower.toLocaleString()} ~ ${summary.length_range.upper.toLocaleString()}`}
            unit="mm"
          />
          <SummaryRow
            label="1차 단중범위"
            value={`${summary.weight_range.lower.toLocaleString()} ~ ${summary.weight_range.upper.toLocaleString()}`}
            unit="kg"
          />
          <div className="border-t border-slate-700 my-1" />
          <SummaryRow label="분할 단중" value={summary.unit_weight_per_split} unit="kg/분할" />
          <SummaryRow label="산정 매수" value={summary.slab_count} unit="매" />
        </div>

        {/* SEQ 체크 트리 */}
        <div>
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wide mb-2">
            설계 프로세스 체크
          </div>
          <div className="space-y-1.5">
            {result.steps.map((step) => (
              <StepRow key={step.seq} step={step} />
            ))}
          </div>
        </div>

        {/* 에러 강조 */}
        {result.steps.filter((s) => s.status === "error").length > 0 && (
          <div className="bg-red-950/40 border border-red-800/50 rounded-lg p-2.5">
            <div className="text-[10px] text-red-400 font-semibold mb-1">연쇄 실패 감지</div>
            {result.steps
              .filter((s) => s.status === "error")
              .map((s) => (
                <div key={s.seq} className="text-[10px] text-red-300">
                  SEQ{s.seq} {s.name} → {s.message}
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
