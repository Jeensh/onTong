"use client";

/**
 * Phase 17 — Stage 1 (사용자 의도 파악) hero 패널.
 *
 * 3-Stage workflow 의 첫 단계. Gate I 의 분류 결과 (intent / search_terms /
 * conditions / user_query) 를 카드 timeline 위에 prominent 하게 surface.
 *
 * 상태 3 가지:
 *   - awaiting_confirm (Phase 21b): payload.kind=="intent_classified" → confirm
 *     버튼 + retry. 사용자 vision: candidates 보기 전 intent 검토.
 *   - active: turn 2 (Gate I real, target_selected) 가 마지막 → full hero
 *   - collapsed: turn 3+ 진행 시 → 1줄 header
 *
 * 편집 (Phase 17b 로 분리): 현재는 read-only. 사용자가 잘못 분류된 걸 알면
 * "새 대화" 로 다시 시작 (16J 패턴). inline edit 는 후속에서.
 */

import { Target, ChevronDown, ChevronRight, Sparkles, FileSearch, CheckCircle2, RefreshCw } from "lucide-react";
import type { GateIntentClassified, GateTarget } from "@/lib/section3/multiturn";

const INTENT_META: Record<
  string, { label: string; cls: string; description: string }
> = {
  simulate:    { label: "시뮬레이션",        cls: "bg-purple-50 text-purple-700 border-purple-200", description: "코드를 돌려서 결과 확인" },
  impact:      { label: "영향도 분석",       cls: "bg-amber-50 text-amber-700 border-amber-200",   description: "변경 시 어디가 영향 받는지" },
  ambiguous:   { label: "모호 (재분류 필요)", cls: "bg-gray-100 text-gray-700 border-gray-300",      description: "더 명확한 표현 필요" },
  locate:      { label: "위치 찾기",         cls: "bg-sky-50 text-sky-700 border-sky-200",         description: "관련 코드가 어디 있는지" },
  explain:     { label: "동작 설명",         cls: "bg-emerald-50 text-emerald-700 border-emerald-200", description: "코드가 무엇을 하는지" },
  hypothesis:  { label: "가설 검증",         cls: "bg-pink-50 text-pink-700 border-pink-200",      description: "이 조건일 때 결과가 X 인지" },
};

interface Props {
  payload: GateTarget | GateIntentClassified;
  /** 다음 stage (Gate II/III) 가 이미 진행됐는지 → true 면 collapsed. */
  collapsed: boolean;
  /** 편집 (현재는 새 대화로 다시 시작 — 16J 패턴). */
  onEdit?: () => void;
  /** Phase 21b — intent_classified payload 일 때 confirm 버튼 콜백. */
  onConfirm?: () => void;
  /** Phase 21b — intent_classified payload 일 때 disabled (이미 confirmed). */
  confirmDisabled?: boolean;
  /** Phase 21b — pending state (confirm in-flight). */
  pending?: boolean;
}

export function IntentStage({
  payload, collapsed, onEdit, onConfirm, confirmDisabled, pending,
}: Props) {
  const meta = INTENT_META[payload.intent] ?? INTENT_META.ambiguous;
  const isAwaitingConfirm = payload.kind === "intent_classified" && !confirmDisabled;
  const conditionSummary = (payload.conditions ?? [])
    .map((c) => `${c.var} ${c.op} ${c.value}${c.unit ? c.unit : ""}`)
    .join(" · ");
  const truncatedQuery = (payload.user_query || "").length > 60
    ? payload.user_query.slice(0, 60) + "..."
    : payload.user_query;

  if (collapsed) {
    return (
      <div className="flex items-center gap-2 text-[12px] border border-border/50 bg-muted/30 rounded px-3 py-2">
        <ChevronRight size={12} className="text-muted-foreground shrink-0" />
        <span className="text-emerald-600 font-medium">✓ Stage 1</span>
        <span className={`px-1.5 py-0.5 rounded text-[10px] border ${meta.cls}`}>
          {meta.label}
        </span>
        <span className="text-muted-foreground truncate flex-1 italic">
          {conditionSummary || `"${truncatedQuery}"`}
        </span>
        {onEdit && (
          <button
            onClick={onEdit}
            className="text-[10px] text-muted-foreground hover:text-foreground hover:underline shrink-0"
            title="새 대화로 다시 시작 (현재 세션은 보존)"
          >
            편집
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="border border-primary/30 bg-primary/5 rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <ChevronDown size={14} className="text-primary" />
        <Target size={14} className="text-primary" />
        <span className="text-sm font-semibold">Stage 1 — 의도 파악</span>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {payload.sources.length > 0 ? `${payload.sources.length} sources` : ""}
        </span>
      </div>

      <div className="space-y-3">
        {/* Intent type hero */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            의도 분류
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className={`text-base px-2.5 py-1 rounded border font-semibold ${meta.cls}`}
            >
              {meta.label}
            </span>
            <span className="text-[11px] text-muted-foreground italic">
              {meta.description}
            </span>
          </div>
        </div>

        {/* User query */}
        {payload.user_query && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              원본 질문
            </div>
            <div className="text-[13px] font-mono text-foreground bg-card/50 border border-border/50 rounded px-2 py-1.5">
              {payload.user_query}
            </div>
          </div>
        )}

        {/* Hypothesis conditions */}
        {payload.intent === "hypothesis" && (payload.conditions?.length ?? 0) > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-pink-700/70 mb-1">
              검증 조건
            </div>
            <div className="flex flex-wrap gap-1.5">
              {payload.conditions!.map((c, i) => (
                <span
                  key={i}
                  className="font-mono text-[12px] bg-white border border-pink-300 px-2 py-1 rounded text-pink-900"
                >
                  <span className="text-pink-600/60 mr-1 text-[10px]">var</span>
                  {c.var}
                  <span className="text-pink-500 mx-1">{c.op}</span>
                  <span className="font-semibold">{c.value}</span>
                  {c.unit && <span className="text-pink-600/70 ml-1">{c.unit}</span>}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Empty hypothesis — info chip */}
        {payload.intent === "hypothesis" && !(payload.conditions?.length) && (
          <div className="text-[11px] text-amber-700 bg-amber-50/50 border border-amber-200 rounded px-2 py-1.5">
            ⚠️ 조건이 추출되지 않았습니다. 자연어를 더 구체적으로 (예: "두께 0.1mm 이하일 때")
          </div>
        )}

        {/* Provenance */}
        {payload.sources.length > 0 && (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground/80">
            <Sparkles size={10} />
            <span className="font-mono">
              {payload.sources[0].source}
              {payload.sources[0].detail && ` — ${payload.sources[0].detail.slice(0, 70)}`}
              {payload.sources[0].detail.length > 70 && "…"}
            </span>
          </div>
        )}

        {/* Phase 21b — intent_classified confirm buttons (awaiting user) */}
        {isAwaitingConfirm && onConfirm && (
          <div className="border-t border-primary/20 pt-3 mt-2 flex items-center gap-2">
            <button
              onClick={onConfirm}
              disabled={pending || payload.intent === "ambiguous"}
              className="inline-flex items-center gap-1.5 bg-primary text-primary-foreground px-3 py-1.5 text-[12px] rounded hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              <CheckCircle2 size={13} />
              {pending ? "처리 중…" : "맞아 → 후보 찾기"}
            </button>
            {onEdit && (
              <button
                onClick={onEdit}
                disabled={pending}
                className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground px-2 py-1.5 rounded hover:bg-muted disabled:opacity-50"
                title="새 대화로 의도 다시 설정"
              >
                <RefreshCw size={11} />
                다른 의도로
              </button>
            )}
            {payload.intent === "ambiguous" && (
              <span className="text-[11px] text-amber-700 ml-auto">
                ⚠ 모호 — [다른 의도로] 로 재입력하세요
              </span>
            )}
          </div>
        )}

        {/* Action hint (intent_classified 가 아니거나 confirmed 상태) */}
        {!isAwaitingConfirm && (
          <div className="border-t border-primary/20 pt-2 mt-2 flex items-center gap-2">
            <FileSearch size={11} className="text-muted-foreground" />
            <span className="text-[11px] text-muted-foreground">
              의도가 정확하면 아래 Stage 2 (영향 영역) 에서 후보를 확정하세요.
              잘못됐다면 [새 대화] 로 다시 시작.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
