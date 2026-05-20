"use client";

/**
 * Gate I — target_selected.
 * 의도 (simulate / impact / ambiguous) + 후보 리스트 + [확인] / [다른 후보 검색].
 *
 * Phase 11 — 후보 카드가 file_path / line / 5-line preview 노출.
 * "코드 보기" 버튼으로 CodeViewerDrawer 열림 (Java + Python 사이드바이사이드).
 */

import { useState } from "react";
import { Target, RefreshCw, Check, Eye, FileCode2, Sparkles, Link2, Tag } from "lucide-react";
import type { GateTarget, ActionCandidate } from "@/lib/section3/multiturn";
import { ProvenanceRow } from "./ProvenanceBadge";
import { CodeViewerDrawer } from "./CodeViewerDrawer";

// Phase 16K — boost rationale 색상 매핑 (role / parent_role 별 시각 구분)
const ROLE_STYLE: Record<string, string> = {
  business: "bg-emerald-50 text-emerald-700 border-emerald-200",
  adapter:  "bg-sky-50 text-sky-700 border-sky-200",
  helper:   "bg-gray-100 text-gray-600 border-gray-300",
  unknown:  "bg-gray-50 text-gray-500 border-gray-200",
};
const PARENT_ROLE_STYLE: Record<string, string> = {
  domain:    "bg-indigo-50 text-indigo-700 border-indigo-200",
  infra:     "bg-amber-50 text-amber-700 border-amber-200",
  framework: "bg-rose-50 text-rose-700 border-rose-200",
  unknown:   "bg-gray-50 text-gray-500 border-gray-200",
};

const INTENT_META = {
  simulate:  { label: "시뮬레이션",       cls: "bg-purple-50 text-purple-700 border-purple-200" },
  impact:    { label: "영향도 검토",      cls: "bg-amber-50 text-amber-700 border-amber-200" },
  ambiguous: { label: "모호 (재분류 필요)", cls: "bg-gray-100 text-gray-700 border-gray-300" },
  locate:    { label: "위치 조회",        cls: "bg-sky-50 text-sky-700 border-sky-200" },
  explain:   { label: "설명",             cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  hypothesis:{ label: "가설 검증",        cls: "bg-pink-50 text-pink-700 border-pink-200" },
} as const;

interface Props {
  payload: GateTarget;
  turn_no: number;
  alreadyConfirmed: boolean;
  pending: boolean;
  repoId: string;
  onConfirm: (selected_index: number) => void;
  onRetry: () => void;
  /** Phase 14C — 0-cand suggestions chip 클릭 시 새 세션 시작 (1-click auto-research). */
  onSuggestionClick?: (suggestion: string) => void;
}

export function GateTargetCard(p: Props) {
  const [picked, setPicked] = useState<number>(
    p.payload.recommended_index ?? 0,
  );
  const [viewing, setViewing] = useState<ActionCandidate | null>(null);
  const intent = INTENT_META[p.payload.intent];
  const empty = p.payload.candidates.length === 0;

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      {/* header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Target size={14} className="text-primary" />
            <span className="text-sm font-semibold">Gate I — 대상 선택</span>
            <span className="text-[10px] text-muted-foreground">turn {p.turn_no}</span>
          </div>
          <div className="mt-1.5 text-[11px] text-muted-foreground">
            <span className="font-mono">"{p.payload.user_query}"</span>
          </div>
        </div>
        <span
          className={`px-2 py-1 rounded border text-[10px] font-medium ${intent.cls}`}
        >
          {intent.label}
        </span>
      </div>

      {/* Phase 17 — hypothesis conditions 는 IntentStage 가 surface 함 (중복 제거) */}

      {/* candidates */}
      {empty ? (
        <div className="border border-dashed border-border rounded p-3 text-[12px] text-muted-foreground bg-muted/30 space-y-2">
          <div>매칭되는 액션을 찾지 못했습니다. 다른 단어로 시도해보세요.</div>
          {p.payload.suggestions && p.payload.suggestions.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground/70 mb-1">
                <Sparkles size={10} /> 비슷한 키워드로 다시 검색
              </div>
              <div className="flex flex-wrap gap-1.5">
                {p.payload.suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => p.onSuggestionClick?.(s)}
                    disabled={p.pending || !p.onSuggestionClick}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full border border-primary/30 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary/50 disabled:opacity-50 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-1">
          {p.payload.candidates.map((c, i) => (
            <label
              key={c.action_id}
              className={`flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors ${
                picked === i
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-muted/50"
              }`}
            >
              <input
                type="radio"
                name={`gate-target-${p.turn_no}`}
                checked={picked === i}
                onChange={() => setPicked(i)}
                disabled={p.alreadyConfirmed}
                className="mt-1"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="font-medium text-sm truncate">{c.label}</span>
                  {i === p.payload.recommended_index && (
                    <span className="text-[9px] uppercase text-emerald-600 font-semibold tracking-wider">
                      추천
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground ml-auto shrink-0">
                    score {c.score.toFixed(1)}
                  </span>
                </div>
                <div className="text-[11px] font-mono text-muted-foreground truncate mt-0.5">
                  {c.code_method_fqn}
                </div>
                {c.location && (
                  <div className="text-[10px] text-muted-foreground/80 mt-0.5 flex items-center gap-1">
                    <FileCode2 size={10} />
                    <span className="font-mono truncate">
                      {c.location.file_path}:{c.location.line_start}–{c.location.line_end}
                    </span>
                  </div>
                )}
                {c.body_preview && (
                  <pre className="text-[10px] font-mono bg-muted/40 rounded mt-1.5 p-1.5 overflow-auto max-h-24 whitespace-pre">
{c.body_preview}
                  </pre>
                )}
                {c.aliases.length > 0 && (
                  <div className="text-[10px] text-muted-foreground/70 mt-0.5">
                    aliases: {c.aliases.join(", ")}
                  </div>
                )}

                {/* Phase 16K — boost rationale: role / parent_role / declared_on_term / annotations.
                    Phase 14E declared_on_term × query alias 가 가장 강한 ranking 신호 → 별도 강조. */}
                {(c.role || c.parent_role || c.declared_on_term || (c.annotations && c.annotations.length > 0)) && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.declared_on_term && (
                      <span
                        title={`이 후보가 도메인 term ${c.declared_on_term} 에 매핑 — ranking 강한 신호`}
                        className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full border bg-pink-50 text-pink-700 border-pink-200 font-mono"
                      >
                        <Link2 size={9} />
                        {c.declared_on_term.replace(/^term\./, "")}
                      </span>
                    )}
                    {c.role && (
                      <span
                        title={`method role = ${c.role}`}
                        className={`inline-flex items-center text-[9px] px-1.5 py-0.5 rounded-full border ${ROLE_STYLE[c.role.toLowerCase()] ?? ROLE_STYLE.unknown}`}
                      >
                        {c.role}
                      </span>
                    )}
                    {c.parent_role && c.parent_role !== c.role && (
                      <span
                        title={`class role = ${c.parent_role}`}
                        className={`inline-flex items-center text-[9px] px-1.5 py-0.5 rounded-full border ${PARENT_ROLE_STYLE[c.parent_role.toLowerCase()] ?? PARENT_ROLE_STYLE.unknown}`}
                      >
                        @{c.parent_role}
                      </span>
                    )}
                    {c.annotations && c.annotations.slice(0, 3).map((a) => (
                      <span
                        key={a}
                        title={a}
                        className="inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded-full border bg-slate-50 text-slate-700 border-slate-200 font-mono"
                      >
                        <Tag size={9} />
                        {a.replace(/^@/, "").split("(")[0]}
                      </span>
                    ))}
                    {c.annotations && c.annotations.length > 3 && (
                      <span className="text-[9px] text-muted-foreground/70 self-center">
                        +{c.annotations.length - 3}
                      </span>
                    )}
                  </div>
                )}
                <div className="mt-1.5 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); setViewing(c); }}
                    className="text-[10px] inline-flex items-center gap-1 px-2 py-0.5 rounded border border-border bg-card hover:bg-muted text-muted-foreground hover:text-foreground"
                  >
                    <Eye size={10} /> 코드 보기
                  </button>
                </div>
              </div>
            </label>
          ))}
        </div>
      )}

      {/* actions */}
      {!p.alreadyConfirmed && (
        <div className="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-border/50">
          <button
            onClick={p.onRetry}
            disabled={p.pending}
            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground px-2 py-1 rounded hover:bg-muted disabled:opacity-50"
          >
            <RefreshCw size={11} /> 다른 후보 검색
          </button>
          <button
            onClick={() => p.onConfirm(picked)}
            disabled={p.pending || empty || p.payload.intent === "ambiguous"}
            className="inline-flex items-center gap-1 text-[12px] bg-primary text-primary-foreground px-3 py-1.5 rounded hover:bg-primary/90 disabled:opacity-50"
            title={empty ? "candidates 가 0 — 위 suggestion 으로 재검색" : ""}
          >
            <Check size={12} /> 이걸로 진행
          </button>
        </div>
      )}
      {p.alreadyConfirmed && (
        <div className="mt-3 pt-2 text-[11px] text-emerald-600 font-medium">
          ✓ 선택 확정됨
        </div>
      )}

      <ProvenanceRow sources={p.payload.sources} />

      {viewing && (
        <CodeViewerDrawer
          open
          fqn={viewing.code_method_fqn}
          repoId={p.repoId}
          location={viewing.location ?? null}
          preloadedBody={viewing.body_preview ?? null}
          onClose={() => setViewing(null)}
        />
      )}
    </div>
  );
}
