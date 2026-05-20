"use client";

/**
 * Phase 13a / 13c — executed_lookup / executed_hypothesis 통합 카드.
 *
 * locate / explain: body + file + linked term + callers + business_rules
 * hypothesis: body + conditions + verdict + reasoning + evidence + confidence
 */

import { FileCode2, FileText, Users, AlertTriangle, RotateCcw } from "lucide-react";
import type {
  GateExecutedLookup, GateExecutedHypothesis, HypothesisVerdict,
} from "@/lib/section3/multiturn";
import {
  parseIntegrityWarnings,
  RED_KINDS, YELLOW_KINDS, YELLOW_GROUP_THRESHOLD,
} from "@/lib/section3/warning_meta";
import { getVerdictMeta } from "@/lib/section3/verdict_meta";
import { ProvenanceRow } from "./ProvenanceBadge";

interface Props {
  payload: GateExecutedLookup | GateExecutedHypothesis;
  turn_no: number;
  // Phase 16J — target_is_test 시 부모가 제공하는 retry 동선 (새 세션 + 같은 query).
  // 부모(MultiturnChat) 는 빨강 발화일 때만 callback 채움 — disabled 처리 없음.
  onRetryWithDifferentTarget?: {
    label: string;
    onClick: () => void;
  } | null;
}

export function GateExecutedReadOnlyCard({
  payload, turn_no, onRetryWithDifferentTarget,
}: Props) {
  const isHypothesis = payload.kind === "executed_hypothesis";
  const isLookup = payload.kind === "executed_lookup";

  // Phase 16E — integrity_warning 칩 surface
  const warnings = parseIntegrityWarnings(payload.sources);

  // Phase 16I — 빨강 칩 발화 시 confidence 회색·취소선 (신뢰도 visual de-emphasis)
  const hasRedWarning = warnings.some((w) => RED_KINDS.has(w.kind));
  // Phase 16I — 노랑 N 종 동시 발화 시 단일 그룹 칩 (≥ threshold)
  const yellowWarnings = warnings.filter((w) => YELLOW_KINDS.has(w.kind));
  const nonYellowWarnings = warnings.filter((w) => !YELLOW_KINDS.has(w.kind));
  const yellowGrouped = yellowWarnings.length >= YELLOW_GROUP_THRESHOLD;

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      {/* header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <FileText size={14} className="text-primary" />
            <span className="text-sm font-semibold">
              {isHypothesis ? "Gate III — 가설 검증" : isLookup && payload.mode === "locate" ? "Gate III — 위치 조회" : "Gate III — 설명"}
            </span>
            <span className="text-[10px] text-muted-foreground">turn {turn_no}</span>
          </div>
          <div className="mt-1 text-[11px] font-mono text-muted-foreground truncate">
            {payload.target.code_method_fqn}
          </div>
        </div>
        {isHypothesis && (
          <VerdictBadge
            verdict={payload.verdict}
            confidence={payload.confidence}
            dimmed={hasRedWarning}
          />
        )}
      </div>

      {/* Phase 16E + 16I — integrity warning 칩 (16I: 노랑 N+ 동시 발화 시 그룹화)
          Phase 16J — 빨강 발화 시 옆에 retry CTA (해결 동선) */}
      {warnings.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {nonYellowWarnings.map((w) => {
            const Icon = w.Icon;
            const detail = payload.sources.find(
              (s) => s.detail.includes(`integrity_warning=${w.kind}`),
            )?.detail ?? "";
            return (
              <span
                key={w.kind}
                title={detail}
                className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border ${w.cls}`}
              >
                <Icon size={10} />
                {w.label}
              </span>
            );
          })}
          {yellowGrouped ? (
            <span
              title={yellowWarnings.map((w) => w.label).join(" · ")}
              className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border bg-amber-50 text-amber-700 border-amber-300"
            >
              <AlertTriangle size={10} />
              근거 약한 경고 {yellowWarnings.length}건
            </span>
          ) : (
            yellowWarnings.map((w) => {
              const Icon = w.Icon;
              const detail = payload.sources.find(
                (s) => s.detail.includes(`integrity_warning=${w.kind}`),
              )?.detail ?? "";
              return (
                <span
                  key={w.kind}
                  title={detail}
                  className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full border ${w.cls}`}
                >
                  <Icon size={10} />
                  {w.label}
                </span>
              );
            })
          )}
          {hasRedWarning && onRetryWithDifferentTarget && (
            <button
              onClick={onRetryWithDifferentTarget.onClick}
              className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border border-primary/40 bg-primary/5 text-primary hover:bg-primary/10 hover:border-primary transition-colors"
              title="새 세션을 시작하고 다른 후보를 직접 골라주세요"
            >
              <RotateCcw size={10} />
              {onRetryWithDifferentTarget.label}
            </button>
          )}
        </div>
      )}

      {/* Phase 13c — conditions */}
      {isHypothesis && payload.conditions.length > 0 && (
        <div className="mb-3 border border-pink-200 rounded p-2 bg-pink-50/50">
          <div className="text-[10px] uppercase tracking-wider text-pink-700/70 mb-1">
            검증 조건
          </div>
          <div className="flex flex-wrap gap-1.5">
            {payload.conditions.map((c, i) => (
              <span
                key={i}
                className="font-mono text-[11px] bg-white border border-pink-300 px-2 py-0.5 rounded text-pink-900"
              >
                {c.var} {c.op} {c.value}{c.unit && (
                  <span className="text-pink-600/70 ml-0.5">{c.unit}</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Phase 13c — reasoning */}
      {isHypothesis && payload.reasoning && (
        <div className="mb-3 text-[12px] text-foreground bg-muted/50 border border-border/50 rounded p-2">
          <span className="text-[10px] uppercase text-muted-foreground/70 mr-1">근거</span>
          {payload.reasoning}
        </div>
      )}

      {/* file + line */}
      {payload.file_path && (
        <div className="text-[10px] text-muted-foreground/90 mb-2 flex items-center gap-1">
          <FileCode2 size={10} />
          <span className="font-mono truncate">
            {payload.file_path}:{payload.line_start}–{payload.line_end}
          </span>
        </div>
      )}

      {/* body_text */}
      {payload.body_text && (
        <pre className="text-[11px] font-mono bg-muted/40 rounded p-2 overflow-auto max-h-72 whitespace-pre mb-3 border border-border/50">
{payload.body_text}
        </pre>
      )}

      {/* lookup-only: linked_term + callers */}
      {isLookup && payload.linked_term && (
        <div className="text-[11px] text-muted-foreground mb-2">
          연결 도메인 term:{" "}
          <span className="font-mono text-foreground">{payload.linked_term}</span>
          {payload.linked_action_label && (
            <span className="ml-2 text-muted-foreground/70">
              ({payload.linked_action_label})
            </span>
          )}
        </div>
      )}

      {isLookup && payload.callers.length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] uppercase text-muted-foreground/70 mb-1 flex items-center gap-1">
            <Users size={10} /> 호출자 ({payload.callers.length})
          </div>
          <ul className="space-y-0.5">
            {payload.callers.slice(0, 8).map((c, i) => (
              <li key={i} className="text-[11px] font-mono text-muted-foreground truncate">
                {c.fqn}
                {c.match_kind && (
                  <span className="ml-2 text-[10px] text-muted-foreground/60">
                    [{c.match_kind}{c.strength != null && ` ${c.strength.toFixed(2)}`}]
                  </span>
                )}
              </li>
            ))}
            {payload.callers.length > 8 && (
              <li className="text-[10px] text-muted-foreground/70">
                ... +{payload.callers.length - 8} more
              </li>
            )}
          </ul>
        </div>
      )}

      {/* evidence (둘 다 — lookup.business_rules / hypothesis.evidence) */}
      {((isLookup && payload.business_rules.length > 0) ||
        (isHypothesis && payload.evidence.length > 0)) && (
        <div className="mb-3">
          <div className="text-[10px] uppercase text-muted-foreground/70 mb-1">
            관련 비즈니스 규칙
          </div>
          <ul className="space-y-1">
            {(isLookup ? payload.business_rules : payload.evidence).slice(0, 6).map((r, i) => (
              <li
                key={i}
                className="text-[11px] border border-border/50 rounded px-2 py-1 bg-muted/20"
              >
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-mono text-muted-foreground">{r.fqn}</span>
                  <span
                    className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                      r.severity.toLowerCase() === "hard"
                        ? "bg-rose-100 text-rose-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {r.severity}
                  </span>
                </div>
                <div className="text-foreground/90">{r.statement}</div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ProvenanceRow sources={payload.sources} />
    </div>
  );
}

function VerdictBadge({
  verdict, confidence, dimmed = false,
}: { verdict: HypothesisVerdict; confidence: number; dimmed?: boolean }) {
  // Phase 16I — dimmed=true (빨강 칩 발화) → confidence % 취소선·회색
  const m = getVerdictMeta(verdict);
  const Icon = m.Icon;
  return (
    <div
      className={`flex items-center gap-1 px-2 py-1 rounded border text-[11px] font-medium ${m.cls}`}
    >
      <Icon size={12} />
      <span>{m.label}</span>
      <span
        className={
          dimmed
            ? "ml-1 text-[10px] opacity-40 line-through text-gray-500"
            : "ml-1 text-[10px] opacity-70"
        }
        title={dimmed ? "신뢰도 낮음 (warning 발화)" : undefined}
      >
        {(confidence * 100).toFixed(0)}%
      </span>
    </div>
  );
}
